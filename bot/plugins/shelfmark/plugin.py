import logging
import time
from typing import Any

from bot.core.database import Database
from bot.plugins.base import Command, CommandContext, Plugin
from bot.plugins.shelfmark.api import ShelfmarkClient, ShelfmarkError
from bot.plugins.shelfmark.formatters import ShelfmarkFormatter

logger = logging.getLogger(__name__)


class ShelfmarkPlugin(Plugin):
    def __init__(self, api: ShelfmarkClient, db: Database,
                 irc_colors: bool = True, session_timeout: int = 300):
        self._api = api
        self._db = db
        self._formatter = ShelfmarkFormatter(irc_colors=irc_colors)
        self._session_timeout = session_timeout
        self._sessions: dict[str, dict[str, Any]] = {}

    def name(self) -> str:
        return "shelfmark"

    def register_commands(self) -> list[Command]:
        return [
            Command(name="request", handler=self.handle_request,
                    help_text="Search for books: !request book/audiobook <title>"),
            Command(name="select", handler=self.handle_select,
                    help_text="Select and download from results: !select <number>"),
            Command(name="status", handler=self.handle_status,
                    help_text="Check download queue status"),
        ]

    def _clean_expired_sessions(self) -> None:
        now = time.time()
        expired = [nick for nick, session in self._sessions.items()
                   if now - session.get("timestamp", now) > self._session_timeout]
        for nick in expired:
            del self._sessions[nick]

    async def handle_request(self, ctx: CommandContext, content_type: str = "ebook") -> None:
        if not ctx.args:
            await ctx.reply("Usage: !request book/audiobook <title>")
            return

        query = " ".join(ctx.args)
        try:
            results = await self._api.search(query, content_type=content_type)
        except ShelfmarkError as e:
            await ctx.reply("Shelfmark is currently unavailable. Try again later.")
            logger.error(f"Shelfmark search error: {e}")
            return

        if not results:
            await ctx.reply(f"No {content_type} results found for '{query}'.")
            return

        results = results[:5]
        self._clean_expired_sessions()
        self._sessions[ctx.sender] = {
            "results": results,
            "content_type": content_type,
            "timestamp": time.time(),
        }
        lines = self._formatter.format_search_results(results, content_type)
        for line in lines:
            await ctx.reply(line)

    async def handle_select(self, ctx: CommandContext) -> None:
        self._clean_expired_sessions()
        if ctx.sender not in self._sessions:
            await ctx.reply("No active search. Use !request book/audiobook <title> to search first.")
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
        content_type = session["content_type"]
        if index < 1 or index > len(results):
            await ctx.reply(f"Invalid selection. Choose between 1 and {len(results)}.")
            return
        selected = results[index - 1]
        title = selected.get("title", "Unknown")
        author = selected.get("author", "Unknown")
        book_id = selected.get("id", "")
        try:
            await self._api.download(book_id)
        except ShelfmarkError as e:
            await ctx.reply("Failed to queue download. Shelfmark may be unavailable.")
            logger.error(f"Shelfmark download error: {e}")
            return
        try:
            await self._db.execute(
                "INSERT INTO shelfmark_requests (nick, content_type, title, author, book_id) VALUES (?, ?, ?, ?, ?)",
                (ctx.sender, content_type, title, author, book_id),
            )
        except Exception as e:
            logger.error(f"Failed to log shelfmark request: {e}")
        await ctx.reply(self._formatter.format_download_queued(title, author))
        del self._sessions[ctx.sender]

    async def handle_status(self, ctx: CommandContext) -> None:
        try:
            status = await self._api.get_status()
        except ShelfmarkError as e:
            await ctx.reply("Shelfmark is currently unavailable. Try again later.")
            logger.error(f"Shelfmark status error: {e}")
            return
        lines = self._formatter.format_status(status)
        for line in lines:
            await ctx.reply(line)

    async def on_load(self) -> None:
        await self._db.execute("""CREATE TABLE IF NOT EXISTS shelfmark_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nick TEXT NOT NULL,
            content_type TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            book_id TEXT,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

    async def on_unload(self) -> None:
        await self._api.close()
