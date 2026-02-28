import logging
import time
from typing import Any
import aiohttp

logger = logging.getLogger(__name__)

PLATFORM_SLUGS: dict[str, int] = {
    "nes": 18, "snes": 19, "n64": 4, "gc": 21, "wii": 5, "wiiu": 41, "switch": 130,
    "gb": 33, "gbc": 22, "gba": 24, "nds": 20, "3ds": 37,
    "master-system": 64, "genesis": 29, "saturn": 32, "dreamcast": 23,
    "game-gear": 35, "ps": 7, "ps2": 8, "ps3": 9, "psp": 38, "psvita": 46,
    "xbox": 11, "xbox360": 12, "atari-2600": 59, "atari-7800": 60,
    "neo-geo": 80, "turbografx-16": 86, "arcade": 52,
}

_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
_GAMES_URL = "https://api.igdb.com/v4/games"
_EXPIRY_MARGIN = 60  # seconds before expiry to refresh


class IGDBClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
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
            and time.time() < self._token_expires_at - _EXPIRY_MARGIN
        )

    async def _authenticate(self) -> bool:
        session = await self._get_session()
        try:
            async with session.post(
                _TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "client_credentials",
                },
            ) as resp:
                if resp.status != 200:
                    logger.error("IGDB auth failed: HTTP %s", resp.status)
                    return False
                data = await resp.json()
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data["expires_in"]
                return True
        except Exception:
            logger.exception("IGDB auth error")
            return False

    async def _ensure_token(self) -> bool:
        if self._token_valid():
            return True
        return await self._authenticate()

    async def search_game(
        self,
        name: str,
        platform_slug: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not await self._ensure_token():
            return []

        query = (
            f'search "{name}"; '
            f"fields name,first_release_date,genres.name,cover.url,summary; "
            f"limit {limit};"
        )
        if platform_slug is not None:
            platform_id = PLATFORM_SLUGS.get(platform_slug)
            if platform_id is not None:
                query += f" where platforms = ({platform_id});"

        headers = {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {self._access_token}",
        }

        session = await self._get_session()
        try:
            async with session.post(_GAMES_URL, headers=headers, data=query) as resp:
                if resp.status != 200:
                    logger.error("IGDB search failed: HTTP %s", resp.status)
                    return []
                return await resp.json()
        except Exception:
            logger.exception("IGDB search error")
            return []

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
