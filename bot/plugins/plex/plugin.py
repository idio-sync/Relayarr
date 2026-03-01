import logging
import time
from typing import Any, Callable, Awaitable

from bot.plugins.base import Command, CommandContext, Plugin
from bot.plugins.plex.plex_client import PlexClient, PlexError
from bot.plugins.plex.tautulli_client import TautulliClient, TautulliError
from bot.plugins.plex.formatters import PlexFormatter
from bot.plugins.plex.announcer import RecentlyAddedAnnouncer

logger = logging.getLogger(__name__)

SEVEN_DAYS = 7 * 24 * 60 * 60


class PlexPlugin(Plugin):
    def __init__(
        self,
        plex_api: PlexClient,
        tautulli_api: TautulliClient | None,
        formatter: PlexFormatter,
        announce_channel: str | None,
        announce_interval: int,
        send_callback: Callable[[str, str], Awaitable[None]],
    ):
        self._plex_api = plex_api
        self._tautulli_api = tautulli_api
        self._formatter = formatter
        self._announce_channel = announce_channel
        self._announce_interval = announce_interval
        self._send_callback = send_callback
        self._announcer: RecentlyAddedAnnouncer | None = None

    def name(self) -> str:
        return "plex"

    def register_commands(self) -> list[Command]:
        return [
            Command(
                name="plex",
                handler=self.handle_plex,
                help_text="Plex info: !plex <playing|stats|recent>",
                required_role="none",
            ),
            Command(
                name="np",
                handler=self.handle_np,
                help_text="Now playing on Plex",
                required_role="none",
            ),
            Command(
                name="plexstats",
                handler=self.handle_plexstats,
                help_text="Plex library statistics",
                required_role="none",
            ),
            Command(
                name="plexrecent",
                handler=self.handle_plexrecent,
                help_text="Recently added to Plex",
                required_role="none",
            ),
        ]

    async def on_load(self) -> None:
        if self._announce_channel:
            self._announcer = RecentlyAddedAnnouncer(
                plex_api=self._plex_api,
                formatter=self._formatter,
                send_callback=self._send_callback,
                channel=self._announce_channel,
                interval=self._announce_interval,
            )
            self._announcer.start()

    async def on_unload(self) -> None:
        if self._announcer:
            await self._announcer.stop()
        await self._plex_api.close()
        if self._tautulli_api:
            await self._tautulli_api.close()

    # --- Main command router ---

    async def handle_plex(self, ctx: CommandContext) -> None:
        if not ctx.args:
            await ctx.reply("Usage: !plex <playing|stats|recent>")
            return
        sub = ctx.args[0].lower()
        if sub == "playing":
            await self._handle_playing(ctx)
        elif sub == "stats":
            await self._handle_stats(ctx)
        elif sub == "recent":
            await self._handle_recent(ctx)
        else:
            await ctx.reply("Usage: !plex <playing|stats|recent>")

    # --- Aliases ---

    async def handle_np(self, ctx: CommandContext) -> None:
        await self._handle_playing(ctx)

    async def handle_plexstats(self, ctx: CommandContext) -> None:
        await self._handle_stats(ctx)

    async def handle_plexrecent(self, ctx: CommandContext) -> None:
        await self._handle_recent(ctx)

    # --- Handlers ---

    async def _handle_playing(self, ctx: CommandContext) -> None:
        # Try Tautulli first if available
        if self._tautulli_api:
            try:
                activity = await self._tautulli_api.get_activity()
                sessions = activity.get("sessions", [])
                lines = self._formatter.format_now_playing_tautulli(sessions)
                for line in lines:
                    await ctx.reply(line)
                return
            except TautulliError as e:
                logger.warning(f"Tautulli unavailable, falling back to Plex: {e}")

        # Fallback to Plex API
        try:
            sessions = await self._plex_api.get_sessions()
            lines = self._formatter.format_now_playing_plex(sessions)
            for line in lines:
                await ctx.reply(line)
        except PlexError as e:
            await ctx.reply("Plex is currently unavailable. Try again later.")
            logger.error(f"Plex sessions error: {e}")

    async def _handle_stats(self, ctx: CommandContext) -> None:
        try:
            sections = await self._plex_api.get_libraries()
        except PlexError as e:
            await ctx.reply("Plex is currently unavailable. Try again later.")
            logger.error(f"Plex libraries error: {e}")
            return

        libraries = []
        cutoff = int(time.time()) - SEVEN_DAYS

        for section in sections:
            section_id = section.get("key", "")
            lib_entry: dict[str, Any] = {
                "title": section.get("title", "Unknown"),
                "type": section.get("type", ""),
            }

            try:
                details = await self._plex_api.get_library_details(section_id)
                lib_entry["count"] = details.get("totalSize", 0)
            except PlexError:
                lib_entry["count"] = 0

            # Count items added in last 7 days
            try:
                recent = await self._plex_api.get_recently_added(count=50, since_timestamp=cutoff)
                # Filter to this library section
                section_recent = [
                    i for i in recent
                    if str(i.get("librarySectionID", "")) == str(section_id)
                ]
                lib_entry["added_7d"] = len(section_recent)
            except PlexError:
                lib_entry["added_7d"] = 0

            libraries.append(lib_entry)

        lines = self._formatter.format_library_stats(libraries)
        for line in lines:
            await ctx.reply(line)

    async def _handle_recent(self, ctx: CommandContext) -> None:
        try:
            items = await self._plex_api.get_recently_added(count=5)
        except PlexError as e:
            await ctx.reply("Plex is currently unavailable. Try again later.")
            logger.error(f"Plex recently added error: {e}")
            return

        lines = self._formatter.format_recently_added(items)
        for line in lines:
            await ctx.reply(line)
