import logging
import time
from typing import Any

from bot.core.database import Database
from bot.plugins.base import Command, CommandContext, Plugin
from bot.plugins.lidarr.api import LidarrClient, LidarrError
from bot.plugins.lidarr.formatters import ArtistFormatter

logger = logging.getLogger(__name__)


class LidarrPlugin(Plugin):
    def __init__(self, api: LidarrClient, db: Database, irc_colors: bool = True,
                 session_timeout: int = 300):
        self._api = api
        self._db = db
        self._formatter = ArtistFormatter(irc_colors=irc_colors)
        self._session_timeout = session_timeout
        self._sessions: dict[str, dict[str, Any]] = {}

    def name(self) -> str:
        return "lidarr"

    def register_commands(self) -> list[Command]:
        return [
            Command(name="request", handler=self.handle_request,
                    help_text="Search for music: !request music <artist>"),
            Command(name="select", handler=self.handle_select,
                    help_text="Select from results: !select <number>"),
            Command(name="status", handler=self.handle_status,
                    help_text="Check your music request statuses"),
        ]

    def _clean_expired_sessions(self) -> None:
        now = time.time()
        expired = [nick for nick, session in self._sessions.items()
                   if now - session.get("timestamp", now) > self._session_timeout]
        for nick in expired:
            del self._sessions[nick]

    async def handle_request(self, ctx: CommandContext) -> None:
        """Search for artists. Expects ctx.args = [<artist name words...>]
        (the coordinator strips the 'music' prefix before delegating)."""
        if not ctx.args:
            await ctx.reply("Usage: !request music <artist name>")
            return

        query = " ".join(ctx.args)
        try:
            results = await self._api.search_artist(query)
        except LidarrError as e:
            await ctx.reply("Lidarr is currently unavailable. Try again later.")
            logger.error(f"Lidarr search error: {e}")
            return

        if not results:
            await ctx.reply(f"No artists found for '{query}'.")
            return

        results = results[:5]
        self._clean_expired_sessions()
        self._sessions[ctx.sender] = {
            "results": results,
            "media_type": "music",
            "timestamp": time.time(),
        }

        lines = self._formatter.format_search_results(results)
        for line in lines:
            await ctx.reply(line)

    async def handle_select(self, ctx: CommandContext) -> None:
        """Select an artist from search results and add to Lidarr."""
        self._clean_expired_sessions()

        if ctx.sender not in self._sessions:
            await ctx.reply("No active search. Use !request music <artist> to search first.")
            return

        if not ctx.args:
            await ctx.reply("Usage: !select <number>")
            return

        try:
            index = int(ctx.args[0])
        except ValueError:
            await ctx.reply("Please provide a valid number. Usage: !select <number>")
            return

        session = self._sessions[ctx.sender]
        results = session["results"]

        if index < 1 or index > len(results):
            await ctx.reply(f"Invalid selection. Choose between 1 and {len(results)}.")
            return

        selected = results[index - 1]
        artist_name = selected.get("artistName", "Unknown")
        foreign_id = selected.get("foreignArtistId", "")

        # Check if artist is already in library
        try:
            existing = await self._api.get_artists()
            existing_ids = {a.get("foreignArtistId") for a in existing}
            if foreign_id in existing_ids:
                await ctx.reply(self._formatter.format_already_monitored(artist_name))
                del self._sessions[ctx.sender]
                return
        except LidarrError as e:
            logger.error(f"Lidarr library check error: {e}")
            # Continue anyway — worst case we get an API error on add

        # Add artist to Lidarr
        try:
            await self._api.add_artist(artist_name, foreign_id)
        except LidarrError as e:
            await ctx.reply("Failed to add artist. Lidarr may be unavailable.")
            logger.error(f"Lidarr add error: {e}")
            return

        # Log to database
        try:
            await self._db.execute(
                "INSERT INTO request_log (nick, media_type, media_title, overseerr_id) VALUES (?, ?, ?, ?)",
                (ctx.sender, "music", artist_name, 0),
            )
        except Exception as e:
            logger.error(f"Failed to log request: {e}")

        await ctx.reply(self._formatter.format_request_success(artist_name))
        del self._sessions[ctx.sender]

    async def handle_status(self, ctx: CommandContext) -> None:
        """Show user's recent music requests."""
        try:
            rows = await self._db.fetch_all(
                "SELECT media_title, media_type, requested_at FROM request_log "
                "WHERE nick = ? AND media_type = 'music' ORDER BY requested_at DESC LIMIT 10",
                (ctx.sender,),
            )
        except Exception as e:
            await ctx.reply("Failed to fetch request status.")
            logger.error(f"DB error in status: {e}")
            return

        if not rows:
            await ctx.reply("You have no recent music requests.")
            return

        await ctx.reply("Your recent music requests:")
        for row in rows:
            await ctx.reply(f"  {row['media_title']} ({row['media_type']}) - requested {row['requested_at']}")

    async def on_unload(self) -> None:
        await self._api.close()
