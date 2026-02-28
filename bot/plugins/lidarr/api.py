import logging
from typing import Any
import aiohttp

logger = logging.getLogger(__name__)


class LidarrError(Exception):
    pass


class LidarrClient:
    def __init__(self, base_url: str, api_key: str, quality_profile_id: int,
                 metadata_profile_id: int, root_folder_path: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._quality_profile_id = quality_profile_id
        self._metadata_profile_id = metadata_profile_id
        self._root_folder_path = root_folder_path
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
                raise LidarrError(f"API error: {resp.status} from {path}")
            return await resp.json()

    async def _post(self, path: str, data: dict) -> Any:
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        async with session.post(url, headers=self._headers, json=data) as resp:
            if resp.status not in (200, 201):
                raise LidarrError(f"API error: {resp.status} from {path}")
            return await resp.json()

    async def search_artist(self, query: str) -> list[dict[str, Any]]:
        """Search for artists by name. GET /api/v1/artist/lookup?term=<query>"""
        return await self._get("/api/v1/artist/lookup", params={"term": query})

    async def get_artists(self) -> list[dict[str, Any]]:
        """Get all artists in the library. GET /api/v1/artist"""
        return await self._get("/api/v1/artist")

    async def add_artist(self, artist_name: str, foreign_artist_id: str) -> dict[str, Any]:
        """Add an artist to the library. POST /api/v1/artist"""
        payload = {
            "artistName": artist_name,
            "foreignArtistId": foreign_artist_id,
            "qualityProfileId": self._quality_profile_id,
            "metadataProfileId": self._metadata_profile_id,
            "rootFolderPath": self._root_folder_path,
            "monitored": True,
            "monitorNewItems": "all",
            "addOptions": {"searchForMissingAlbums": True},
        }
        return await self._post("/api/v1/artist", payload)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
