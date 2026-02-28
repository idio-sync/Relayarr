import logging
from typing import Any
import aiohttp

logger = logging.getLogger(__name__)


class OverseerrError(Exception):
    pass


class OverseerrClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._session: aiohttp.ClientSession | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key, "Content-Type": "application/json"}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get(self, path: str, params: dict | None = None) -> Any:
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        async with session.get(url, headers=self._headers, params=params) as resp:
            if resp.status != 200:
                raise OverseerrError(f"API error: {resp.status} from {path}")
            return await resp.json()

    async def _post(self, path: str, data: dict) -> Any:
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        async with session.post(url, headers=self._headers, json=data) as resp:
            if resp.status not in (200, 201):
                raise OverseerrError(f"API error: {resp.status} from {path}")
            return await resp.json()

    async def search(self, query: str, page: int = 1) -> list[dict[str, Any]]:
        data = await self._get("/api/v1/search", params={"query": query, "page": page, "language": "en"})
        return data.get("results", [])

    async def request_media(self, media_id: int, media_type: str, seasons: list[int] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"mediaId": media_id, "mediaType": media_type}
        if seasons:
            payload["seasons"] = seasons
        return await self._post("/api/v1/request", payload)

    async def get_requests(self, take: int = 20, skip: int = 0) -> list[dict[str, Any]]:
        data = await self._get("/api/v1/request", params={"take": take, "skip": skip, "sort": "added"})
        return data.get("results", [])

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
