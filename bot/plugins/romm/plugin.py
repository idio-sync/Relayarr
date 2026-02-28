import logging
import random
import time
from typing import Any

from bot.core.database import Database
from bot.plugins.base import Command, CommandContext, Plugin
from bot.plugins.romm.api import RommClient, RommError
from bot.plugins.romm.formatters import RommFormatter
from bot.plugins.romm.igdb import IGDBClient

logger = logging.getLogger(__name__)


class RommPlugin(Plugin):
    def __init__(
        self,
        api: RommClient,
        db: Database,
        igdb: IGDBClient | None = None,
        irc_colors: bool = True,
        session_timeout: int = 300,
    ):
        self._api = api
        self._db = db
        self._igdb = igdb
        self._formatter = RommFormatter(irc_colors=irc_colors, domain=api._domain)
        self._session_timeout = session_timeout
        self._sessions: dict[str, dict[str, Any]] = {}

    def name(self) -> str:
        return "romm"

    def register_commands(self) -> list[Command]:
        return [
            Command(
                name="game",
                handler=self.handle_game,
                help_text="Search ROMs: !game <platform> <title>",
            ),
            Command(
                name="platforms",
                handler=self.handle_platforms,
                help_text="List available platforms",
            ),
            Command(
                name="gamestats",
                handler=self.handle_gamestats,
                help_text="Show collection statistics",
            ),
            Command(
                name="random",
                handler=self.handle_random,
                help_text="Random ROM: !random [platform]",
            ),
            Command(
                name="myrequests",
                handler=self.handle_myrequests,
                help_text="View your ROM requests",
            ),
            Command(
                name="firmware",
                handler=self.handle_firmware,
                help_text="List firmware: !firmware <platform>",
            ),
        ]

    def _clean_expired_sessions(self) -> None:
        now = time.time()
        expired = [
            nick
            for nick, session in self._sessions.items()
            if now - session.get("timestamp", now) > self._session_timeout
        ]
        for nick in expired:
            del self._sessions[nick]

    async def _find_platform(self, name: str) -> tuple[dict | None, list[dict]]:
        """Find a platform by slug (exact), name (exact, case-insensitive), or partial match.

        Returns (platform_dict | None, all_platforms).
        """
        platforms = await self._api.get_platforms()
        name_lower = name.lower()

        # 1. Exact slug match
        for p in platforms:
            if p.get("slug", "").lower() == name_lower:
                return p, platforms

        # 2. Exact name match (case-insensitive)
        for p in platforms:
            if p.get("name", "").lower() == name_lower:
                return p, platforms

        # 3. Partial match on slug or name
        for p in platforms:
            if name_lower in p.get("slug", "").lower() or name_lower in p.get("name", "").lower():
                return p, platforms

        return None, platforms

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def handle_game(self, ctx: CommandContext) -> None:
        """Search ROMs: !game <platform> <title words...>"""
        if len(ctx.args) < 2:
            await ctx.reply("Usage: !game <platform> <title>")
            return

        platform_arg = ctx.args[0]
        search_term = " ".join(ctx.args[1:])

        platform, _ = await self._find_platform(platform_arg)
        if platform is None:
            await ctx.reply(f"Platform '{platform_arg}' not found. Use !platforms to see available platforms.")
            return

        platform_name = platform.get("name", platform_arg)
        platform_slug = platform.get("slug", "")
        platform_id = platform["id"]

        try:
            results = await self._api.search_roms(platform_id, search_term, limit=25)
        except RommError as e:
            await ctx.reply("RomM is currently unavailable. Try again later.")
            logger.error(f"RomM search error: {e}")
            return

        results = results[:10]

        if results:
            self._clean_expired_sessions()
            self._sessions[ctx.sender] = {
                "results": results,
                "mode": "browse",
                "platform": platform_name,
                "platform_slug": platform_slug,
                "timestamp": time.time(),
            }
            lines = self._formatter.format_search_results(results, platform_name)
            for line in lines:
                await ctx.reply(line)
            return

        # No RomM results — try IGDB fallback
        if self._igdb is not None:
            igdb_results = await self._igdb.search_game(search_term, platform_slug)
            igdb_results = igdb_results[:10]
            if igdb_results:
                self._clean_expired_sessions()
                self._sessions[ctx.sender] = {
                    "results": igdb_results,
                    "mode": "request",
                    "platform": platform_name,
                    "platform_slug": platform_slug,
                    "timestamp": time.time(),
                }
                lines = self._formatter.format_igdb_results(igdb_results, platform_name)
                for line in lines:
                    await ctx.reply(line)
                return

        await ctx.reply(f"No ROMs found for '{search_term}' on {platform_name}.")

    async def handle_select(self, ctx: CommandContext) -> None:
        """Called by MediaCoordinator when the user has an active romm session.
        NOT registered as a command — select is owned by MediaCoordinator."""
        self._clean_expired_sessions()

        if ctx.sender not in self._sessions:
            await ctx.reply("No active search. Use !game <platform> <title> to search first.")
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
        mode = session.get("mode", "browse")

        if mode == "browse":
            try:
                rom = await self._api.get_rom(selected["id"])
            except RommError as e:
                await ctx.reply("Failed to fetch ROM details. Try again later.")
                logger.error(f"RomM get_rom error: {e}")
                return
            lines = self._formatter.format_rom_details(rom)
            for line in lines:
                await ctx.reply(line)
            del self._sessions[ctx.sender]

        elif mode == "request":
            title = selected.get("name", "Unknown")
            ts = selected.get("first_release_date")
            year: int | str
            if ts:
                from datetime import datetime, timezone
                year = datetime.fromtimestamp(ts, tz=timezone.utc).year
            else:
                year = "????"
            platform_name = session.get("platform", "")

            try:
                await self._db.execute(
                    "INSERT INTO romm_requests (nick, game_title, platform, igdb_id, status) VALUES (?, ?, ?, ?, ?)",
                    (ctx.sender, title, platform_name, selected.get("id", 0), "pending"),
                )
            except Exception as e:
                logger.error(f"Failed to log romm request: {e}")

            await ctx.reply(self._formatter.format_request_success(title, year, platform_name))
            del self._sessions[ctx.sender]

    async def handle_platforms(self, ctx: CommandContext) -> None:
        """List available platforms."""
        try:
            platforms = await self._api.get_platforms()
        except RommError as e:
            await ctx.reply("RomM is currently unavailable. Try again later.")
            logger.error(f"RomM platforms error: {e}")
            return

        lines = self._formatter.format_platforms(platforms)
        for line in lines:
            await ctx.reply(line)

    async def handle_gamestats(self, ctx: CommandContext) -> None:
        """Show collection statistics."""
        try:
            platforms = await self._api.get_platforms()
        except RommError as e:
            await ctx.reply("RomM is currently unavailable. Try again later.")
            logger.error(f"RomM stats error: {e}")
            return

        lines = self._formatter.format_stats(platforms)
        for line in lines:
            await ctx.reply(line)

    async def handle_random(self, ctx: CommandContext) -> None:
        """Random ROM: !random [platform]"""
        try:
            all_platforms = await self._api.get_platforms()
        except RommError as e:
            await ctx.reply("RomM is currently unavailable. Try again later.")
            logger.error(f"RomM random error: {e}")
            return

        if ctx.args:
            platform, _ = await self._find_platform(ctx.args[0])
            if platform is None:
                await ctx.reply(f"Platform '{ctx.args[0]}' not found. Use !platforms to see available platforms.")
                return
            candidate_platforms = [platform]
        else:
            candidate_platforms = [p for p in all_platforms if p.get("rom_count", 0) > 0]
            if not candidate_platforms:
                await ctx.reply("No platforms with ROMs found.")
                return

        chosen_platform = random.choice(candidate_platforms)
        platform_name = chosen_platform.get("name", "Unknown")
        platform_id = chosen_platform["id"]

        try:
            roms = await self._api.search_roms(platform_id, "", limit=100)
        except RommError as e:
            await ctx.reply("RomM is currently unavailable. Try again later.")
            logger.error(f"RomM random ROM search error: {e}")
            return

        if not roms:
            await ctx.reply(f"No ROMs found on {platform_name}.")
            return

        chosen_rom = random.choice(roms)

        try:
            rom_detail = await self._api.get_rom(chosen_rom["id"])
        except RommError as e:
            await ctx.reply("RomM is currently unavailable. Try again later.")
            logger.error(f"RomM get_rom error: {e}")
            return

        lines = self._formatter.format_random_rom(rom_detail, platform_name)
        for line in lines:
            await ctx.reply(line)

    async def handle_myrequests(self, ctx: CommandContext) -> None:
        """View your ROM requests."""
        try:
            rows = await self._db.fetch_all(
                "SELECT game_title, platform, status, requested_at FROM romm_requests "
                "WHERE nick = ? ORDER BY requested_at DESC LIMIT 10",
                (ctx.sender,),
            )
        except Exception as e:
            await ctx.reply("Failed to fetch your ROM requests.")
            logger.error(f"DB error in myrequests: {e}")
            return

        if not rows:
            await ctx.reply("You have no ROM requests.")
            return

        await ctx.reply("Your ROM requests:")
        for row in rows:
            title = row["game_title"] if isinstance(row, dict) else row[0]
            platform = row["platform"] if isinstance(row, dict) else row[1]
            status = row["status"] if isinstance(row, dict) else row[2]
            requested_at = row["requested_at"] if isinstance(row, dict) else row[3]
            await ctx.reply(f"  {title} ({platform}) - {status} - {requested_at}")

    async def handle_firmware(self, ctx: CommandContext) -> None:
        """List firmware: !firmware <platform>"""
        if not ctx.args:
            await ctx.reply("Usage: !firmware <platform>")
            return

        platform, _ = await self._find_platform(ctx.args[0])
        if platform is None:
            await ctx.reply(f"Platform '{ctx.args[0]}' not found. Use !platforms to see available platforms.")
            return

        platform_name = platform.get("name", ctx.args[0])
        platform_id = platform["id"]

        try:
            firmware = await self._api.get_firmware(platform_id)
        except RommError as e:
            await ctx.reply("RomM is currently unavailable. Try again later.")
            logger.error(f"RomM firmware error: {e}")
            return

        lines = self._formatter.format_firmware(firmware, platform_name)
        for line in lines:
            await ctx.reply(line)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_load(self) -> None:
        await self._db.execute(
            """CREATE TABLE IF NOT EXISTS romm_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nick TEXT NOT NULL,
                game_title TEXT NOT NULL,
                platform TEXT NOT NULL,
                igdb_id INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        await self._db.execute(
            """CREATE TABLE IF NOT EXISTS romm_announced (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rom_id INTEGER NOT NULL UNIQUE,
                announced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )

    async def on_unload(self) -> None:
        await self._api.close()
        if self._igdb is not None:
            await self._igdb.close()
