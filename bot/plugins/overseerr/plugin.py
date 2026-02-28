import logging
import time
from typing import Any
from bot.core.database import Database
from bot.plugins.base import Command, CommandContext, Plugin
from bot.plugins.overseerr.api import OverseerrClient, OverseerrError
from bot.plugins.overseerr.formatters import ResultFormatter, STATUS_AVAILABLE

logger = logging.getLogger(__name__)


class OverseerrPlugin(Plugin):
    def __init__(self, api: OverseerrClient, db: Database, irc_colors: bool = True, session_timeout: int = 300):
        self._api = api
        self._db = db
        self._formatter = ResultFormatter(irc_colors=irc_colors)
        self._session_timeout = session_timeout
        self._sessions: dict[str, dict[str, Any]] = {}

    def name(self) -> str:
        return "overseerr"

    def register_commands(self) -> list[Command]:
        return [
            Command(name="request", handler=self.handle_request, help_text="Search for media: !request movie/tv <title>"),
            Command(name="select", handler=self.handle_select, help_text="Select and request from results: !select <number>"),
            Command(name="status", handler=self.handle_status, help_text="Check your request statuses"),
        ]

    def _clean_expired_sessions(self) -> None:
        now = time.time()
        expired = [nick for nick, session in self._sessions.items() if now - session.get("timestamp", now) > self._session_timeout]
        for nick in expired:
            del self._sessions[nick]

    async def handle_request(self, ctx: CommandContext) -> None:
        if len(ctx.args) < 2:
            await ctx.reply("Usage: !request movie/tv <title>")
            return
        media_type = ctx.args[0].lower()
        if media_type not in ("movie", "tv"):
            await ctx.reply("Type must be 'movie' or 'tv'. Usage: !request movie/tv <title>")
            return
        query = " ".join(ctx.args[1:])
        try:
            results = await self._api.search(query)
        except OverseerrError as e:
            await ctx.reply("Overseerr is currently unavailable. Try again later.")
            logger.error(f"Overseerr search error: {e}")
            return
        results = [r for r in results if r.get("mediaType") == media_type]
        if not results:
            await ctx.reply(f"No {media_type} results found for '{query}'.")
            return
        results = results[:5]
        self._clean_expired_sessions()
        self._sessions[ctx.sender] = {"results": results, "media_type": media_type, "timestamp": time.time()}
        lines = self._formatter.format_search_results(results)
        for line in lines:
            await ctx.reply(line)

    async def handle_select(self, ctx: CommandContext) -> None:
        self._clean_expired_sessions()
        if ctx.sender not in self._sessions:
            await ctx.reply("No active search. Use !request movie/tv <title> to search first.")
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
        media_type = session["media_type"]
        if index < 1 or index > len(results):
            await ctx.reply(f"Invalid selection. Choose between 1 and {len(results)}.")
            return
        selected = results[index - 1]
        title = selected.get("title") or selected.get("name", "Unknown")
        year = (selected.get("releaseDate") or selected.get("firstAirDate", ""))[:4]
        media_info = selected.get("mediaInfo")
        if media_info and media_info.get("status") == STATUS_AVAILABLE:
            await ctx.reply(self._formatter.format_already_available(title, year))
            del self._sessions[ctx.sender]
            return
        try:
            await self._api.request_media(media_id=selected["id"], media_type=media_type)
        except OverseerrError as e:
            await ctx.reply("Failed to submit request. Overseerr may be unavailable.")
            logger.error(f"Overseerr request error: {e}")
            return
        try:
            await self._db.execute(
                "INSERT INTO request_log (nick, media_type, media_title, overseerr_id) VALUES (?, ?, ?, ?)",
                (ctx.sender, media_type, title, selected["id"]),
            )
        except Exception as e:
            logger.error(f"Failed to log request: {e}")
        await ctx.reply(self._formatter.format_request_success(title, year))
        del self._sessions[ctx.sender]

    async def handle_status(self, ctx: CommandContext) -> None:
        try:
            rows = await self._db.fetch_all(
                "SELECT media_title, media_type, requested_at FROM request_log WHERE nick = ? ORDER BY requested_at DESC LIMIT 10",
                (ctx.sender,),
            )
        except Exception as e:
            await ctx.reply("Failed to fetch request status.")
            logger.error(f"DB error in status: {e}")
            return
        if not rows:
            await ctx.reply("You have no recent requests.")
            return
        await ctx.reply("Your recent requests:")
        for row in rows:
            await ctx.reply(f"  {row['media_title']} ({row['media_type']}) - requested {row['requested_at']}")

    async def on_unload(self) -> None:
        await self._api.close()
