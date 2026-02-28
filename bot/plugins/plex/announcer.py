import asyncio
import logging
from typing import Any, Callable, Awaitable

from bot.plugins.plex.plex_client import PlexClient, PlexError
from bot.plugins.plex.formatters import PlexFormatter

logger = logging.getLogger(__name__)

MAX_BACKOFF = 300  # 5 minutes


class RecentlyAddedAnnouncer:
    def __init__(
        self,
        plex_api: PlexClient,
        formatter: PlexFormatter,
        send_callback: Callable[[str, str], Awaitable[None]],
        channel: str,
        interval: int = 300,
    ):
        self._plex_api = plex_api
        self._formatter = formatter
        self._send = send_callback
        self._channel = channel
        self._interval = interval
        self._last_seen_timestamp: int | None = None
        self._consecutive_errors = 0
        self._task: asyncio.Task | None = None

    async def _poll(self) -> None:
        try:
            items = await self._plex_api.get_recently_added(count=20)
        except PlexError as e:
            self._consecutive_errors += 1
            logger.error(f"Plex recently-added poll failed: {e}")
            return

        self._consecutive_errors = 0

        if not items:
            if self._last_seen_timestamp is None:
                self._last_seen_timestamp = 0
            return

        max_timestamp = max(i.get("addedAt", 0) for i in items)

        if self._last_seen_timestamp is None:
            # First poll — just record baseline, don't announce
            self._last_seen_timestamp = max_timestamp
            return

        new_items = [
            i for i in items if i.get("addedAt", 0) > self._last_seen_timestamp
        ]

        for item in sorted(new_items, key=lambda i: i.get("addedAt", 0)):
            message = self._formatter.format_announcement(item)
            await self._send(self._channel, message)

        if max_timestamp > self._last_seen_timestamp:
            self._last_seen_timestamp = max_timestamp

    def _backoff_delay(self) -> int:
        if self._consecutive_errors <= 0:
            return self._interval
        delay = min(self._interval * (2 ** self._consecutive_errors), MAX_BACKOFF)
        return delay

    async def _run(self) -> None:
        while True:
            await self._poll()
            delay = self._backoff_delay()
            await asyncio.sleep(delay)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
            logger.info(f"Recently-added announcer started for {self._channel}")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Recently-added announcer stopped")
