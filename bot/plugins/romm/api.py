import logging
import time
from typing import Any
from urllib.parse import quote
import aiohttp

logger = logging.getLogger(__name__)

_AUTH_SAFETY_MARGIN = 60  # seconds before expiry to refresh


class RommError(Exception):
    pass


class RommClient:
    def __init__(self, base_url: str, username: str, password: str, domain: str):
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._domain = domain.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _token_valid(self) -> bool:
        return (
            self._access_token is not None
            and time.monotonic() < self._token_expires_at - _AUTH_SAFETY_MARGIN
        )

    async def _ensure_token(self) -> None:
        if self._token_valid():
            return
        session = await self._get_session()
        url = f"{self._base_url}/api/token"
        data = {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
        }
        async with session.post(url, data=data) as resp:
            if resp.status != 200:
                raise RommError(f"Auth failed: {resp.status} from /api/token")
            payload = await resp.json()
        self._access_token = payload["access_token"]
        expires_in = payload.get("expires", 3600)
        self._token_expires_at = time.monotonic() + expires_in

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def _get(self, path: str, params: dict | None = None) -> Any:
        await self._ensure_token()
        session = await self._get_session()
        url = f"{self._base_url}/api/{path.lstrip('/')}"
        async with session.get(url, headers=self._auth_headers, params=params) as resp:
            if resp.status != 200:
                raise RommError(f"API error: {resp.status} from {path}")
            return await resp.json()

    async def get_platforms(self) -> list[dict[str, Any]]:
        return await self._get("platforms")

    async def search_roms(
        self, platform_id: int, search_term: str, limit: int = 25
    ) -> list[dict[str, Any]]:
        data = await self._get(
            "roms",
            params={"platform_id": platform_id, "search_term": search_term, "limit": limit},
        )
        if isinstance(data, dict):
            return data.get("items", [])
        return data

    async def get_rom(self, rom_id: int) -> dict[str, Any]:
        return await self._get(f"roms/{rom_id}")

    async def get_firmware(self, platform_id: int) -> list[dict[str, Any]]:
        return await self._get("firmware", params={"platform_id": platform_id})

    def download_url(self, rom_id: int, fs_name: str) -> str:
        encoded = quote(fs_name, safe="")
        return f"{self._domain}/api/roms/{rom_id}/content/{encoded}"

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
