import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class PlexError(Exception):
    pass


class PlexClient:
    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get(self, path: str, params: dict | None = None) -> Any:
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        all_params = {"X-Plex-Token": self._token}
        if params:
            all_params.update(params)
        headers = {"Accept": "application/json"}
        async with session.get(url, params=all_params, headers=headers) as resp:
            if resp.status != 200:
                raise PlexError(f"API error: {resp.status} from {path}")
            return await resp.json()

    async def get_libraries(self) -> list[dict[str, Any]]:
        data = await self._get("/library/sections")
        return data.get("MediaContainer", {}).get("Directory", [])

    async def get_library_details(self, section_id: str) -> dict[str, Any]:
        data = await self._get(
            f"/library/sections/{section_id}/all",
            params={"X-Plex-Container-Start": "0", "X-Plex-Container-Size": "0"},
        )
        return data.get("MediaContainer", {})

    async def get_recently_added(
        self, count: int = 10, since_timestamp: int | None = None
    ) -> list[dict[str, Any]]:
        data = await self._get(
            "/library/recentlyAdded",
            params={"X-Plex-Container-Size": str(count)},
        )
        items = data.get("MediaContainer", {}).get("Metadata", [])
        if since_timestamp is not None:
            items = [i for i in items if i.get("addedAt", 0) > since_timestamp]
        return items

    async def get_sessions(self) -> list[dict[str, Any]]:
        data = await self._get("/status/sessions")
        return data.get("MediaContainer", {}).get("Metadata", [])

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
