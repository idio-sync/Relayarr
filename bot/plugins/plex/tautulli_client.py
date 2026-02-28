import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class TautulliError(Exception):
    pass


class TautulliClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get(self, params: dict | None = None) -> Any:
        session = await self._get_session()
        url = f"{self._base_url}/api/v2"
        all_params = {"apikey": self._api_key}
        if params:
            all_params.update(params)
        async with session.get(url, params=all_params) as resp:
            if resp.status != 200:
                raise TautulliError(f"API error: {resp.status}")
            return await resp.json()

    async def get_activity(self) -> dict[str, Any]:
        data = await self._get(params={"cmd": "get_activity"})
        response = data.get("response", {})
        if response.get("result") != "success":
            raise TautulliError(response.get("message", "Unknown error"))
        return response.get("data", {})

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
