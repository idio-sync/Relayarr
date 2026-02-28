import logging
import time
from typing import Any

from bot.plugins.base import Command, CommandContext, Plugin

logger = logging.getLogger(__name__)


class MediaCoordinator(Plugin):
    """Routes !request, !select, !status to the appropriate media backend plugin."""

    def __init__(self, backends: dict[str, Plugin], session_timeout: int = 300):
        """
        Args:
            backends: Maps media type to plugin instance.
                e.g. {"movie": overseerr, "tv": overseerr, "music": lidarr}
            session_timeout: Seconds before coordinator session expires.
        """
        self._backends = backends
        self._sessions: dict[str, dict[str, Any]] = {}
        self._session_timeout = session_timeout

    def name(self) -> str:
        return "media"

    def register_commands(self) -> list[Command]:
        types_list = "/".join(sorted(self._backends.keys()))
        return [
            Command(name="request", handler=self.handle_request,
                    help_text=f"Search for media: !request {types_list} <title>"),
            Command(name="select", handler=self.handle_select,
                    help_text="Select and request from results: !select <number>"),
            Command(name="status", handler=self.handle_status,
                    help_text="Check your request statuses"),
        ]

    def _clean_expired(self) -> None:
        now = time.time()
        expired = [n for n, s in self._sessions.items()
                   if now - s.get("timestamp", now) > self._session_timeout]
        for n in expired:
            del self._sessions[n]

    async def handle_request(self, ctx: CommandContext) -> None:
        types_list = "/".join(sorted(self._backends.keys()))

        if len(ctx.args) < 2:
            await ctx.reply(f"Usage: !request {types_list} <title>")
            return

        media_type = ctx.args[0].lower()
        if media_type not in self._backends:
            await ctx.reply(f"Unknown type '{media_type}'. Available: {types_list}")
            return

        backend = self._backends[media_type]

        # Clear any previous session from a different backend
        self._clean_expired()
        if ctx.sender in self._sessions:
            old_key = self._sessions[ctx.sender]["backend"]
            old_backend = self._backends.get(old_key)
            if old_backend and old_backend is not backend:
                old_backend._sessions.pop(ctx.sender, None)

        # Track which backend this session belongs to
        self._sessions[ctx.sender] = {
            "backend": media_type,
            "timestamp": time.time(),
        }

        # For Overseerr: pass full args (it expects args[0] = "movie"/"tv", args[1:] = query)
        # For Lidarr: strip "music" prefix (it expects args = [query words...])
        if media_type in ("movie", "tv"):
            await backend.handle_request(ctx)
        else:
            # Strip the media type arg for non-overseerr backends
            delegated_ctx = CommandContext(
                sender=ctx.sender,
                hostmask=ctx.hostmask,
                channel=ctx.channel,
                args=ctx.args[1:],
                reply=ctx.reply,
            )
            await backend.handle_request(delegated_ctx)

    async def handle_select(self, ctx: CommandContext) -> None:
        self._clean_expired()

        if ctx.sender not in self._sessions:
            types_list = "/".join(sorted(self._backends.keys()))
            await ctx.reply(f"No active search. Use !request {types_list} <title> first.")
            return

        backend_key = self._sessions[ctx.sender]["backend"]
        backend = self._backends[backend_key]
        await backend.handle_select(ctx)

        # If backend cleared its session, clear coordinator session too
        if ctx.sender not in backend._sessions:
            self._sessions.pop(ctx.sender, None)

    async def handle_status(self, ctx: CommandContext) -> None:
        # Delegate to each unique backend
        seen = set()
        for backend in self._backends.values():
            if id(backend) not in seen:
                seen.add(id(backend))
                await backend.handle_status(ctx)

    async def on_unload(self) -> None:
        seen = set()
        for backend in self._backends.values():
            if id(backend) not in seen:
                seen.add(id(backend))
                await backend.on_unload()
