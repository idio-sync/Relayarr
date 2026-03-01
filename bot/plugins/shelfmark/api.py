import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class ShelfmarkError(Exception):
    pass


class ShelfmarkClient:
    def __init__(self, base_url: str, username: str, password: str):
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self._logged_in = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._logged_in = False
        return self._session

    async def _login(self) -> None:
        session = await self._get_session()
        url = f"{self._base_url}/api/auth/login"
        payload = {"username": self._username, "password": self._password}
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                raise ShelfmarkError(f"Auth failed: {resp.status}")
            await resp.json()
        self._logged_in = True

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self._logged_in:
            await self._login()
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        async with session.request(method, url, **kwargs) as resp:
            if resp.status == 401:
                self._logged_in = False
                await self._login()
                async with session.request(method, url, **kwargs) as retry_resp:
                    if retry_resp.status != 200:
                        raise ShelfmarkError(f"API error: {retry_resp.status} from {path}")
                    return await retry_resp.json()
            if resp.status != 200:
                raise ShelfmarkError(f"API error: {resp.status} from {path}")
            return await resp.json()

    async def search(self, query: str, content_type: str = "ebook") -> list[dict[str, Any]]:
        params: dict[str, str] = {"query": query, "content": content_type}
        result = await self._request("GET", "/api/search", params=params)
        if isinstance(result, list):
            return result
        return []

    async def get_info(self, book_id: str) -> dict[str, Any]:
        return await self._request("GET", "/api/info", params={"id": book_id})

    async def download(self, book_id: str) -> dict[str, Any]:
        return await self._request("GET", "/api/download", params={"id": book_id})

    async def get_status(self) -> dict[str, Any]:
        return await self._request("GET", "/api/status")

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
