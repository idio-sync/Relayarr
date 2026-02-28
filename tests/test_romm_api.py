import pytest
from aioresponses import aioresponses
from bot.plugins.romm.api import RommClient, RommError


TOKEN_RESPONSE = {
    "access_token": "test-access-token",
    "refresh_token": "test-refresh-token",
    "token_type": "bearer",
    "expires": 3600,
}

PLATFORMS_RESPONSE = [
    {"id": 1, "name": "Nintendo Entertainment System", "slug": "nes"},
    {"id": 2, "name": "Super Nintendo", "slug": "snes"},
]

ROMS_PAGINATED_RESPONSE = {
    "items": [
        {"id": 10, "name": "Super Mario Bros", "fs_name": "Super Mario Bros.nes", "platform_id": 1},
        {"id": 11, "name": "Mega Man", "fs_name": "Mega Man.nes", "platform_id": 1},
    ],
    "total": 2,
    "page": 1,
    "size": 25,
}

ROMS_LIST_RESPONSE = [
    {"id": 10, "name": "Super Mario Bros", "fs_name": "Super Mario Bros.nes", "platform_id": 1},
]

ROM_RESPONSE = {
    "id": 10,
    "name": "Super Mario Bros",
    "fs_name": "Super Mario Bros.nes",
    "platform_id": 1,
    "summary": "A classic platformer.",
}

FIRMWARE_RESPONSE = [
    {"id": 5, "file_name": "bios.bin", "platform_id": 1},
]


@pytest.fixture
def api():
    return RommClient(
        base_url="http://romm:3000",
        username="admin",
        password="secret",
        domain="https://romm.example.com",
    )


def _mock_auth(m):
    """Helper to register a token endpoint mock."""
    m.post("http://romm:3000/api/token", payload=TOKEN_RESPONSE)


class TestRommAuth:
    async def test_auth_fetches_token_on_first_request(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/platforms", payload=PLATFORMS_RESPONSE)
            await api.get_platforms()
            # Token endpoint should have been called once
            token_calls = [k for k in m.requests if k[1].path == "/api/token"]
            assert len(token_calls) == 1

    async def test_auth_sends_form_data(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/platforms", payload=PLATFORMS_RESPONSE)
            await api.get_platforms()
            import yarl
            token_key = ("POST", yarl.URL("http://romm:3000/api/token"))
            call = m.requests[token_key][0]
            sent_data = call.kwargs.get("data", {})
            assert sent_data["grant_type"] == "password"
            assert sent_data["username"] == "admin"
            assert sent_data["password"] == "secret"

    async def test_auth_failure_raises_romm_error(self, api):
        with aioresponses() as m:
            m.post("http://romm:3000/api/token", status=401)
            with pytest.raises(RommError, match="Auth"):
                await api.get_platforms()

    async def test_token_not_refetched_when_still_valid(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/platforms", payload=PLATFORMS_RESPONSE)
            m.get("http://romm:3000/api/platforms", payload=PLATFORMS_RESPONSE)
            await api.get_platforms()
            await api.get_platforms()
            import yarl
            token_key = ("POST", yarl.URL("http://romm:3000/api/token"))
            assert len(m.requests.get(token_key, [])) == 1

    async def test_token_uses_bearer_auth_header(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/platforms", payload=PLATFORMS_RESPONSE)
            await api.get_platforms()
            import yarl
            platforms_key = ("GET", yarl.URL("http://romm:3000/api/platforms"))
            call = m.requests[platforms_key][0]
            assert call.kwargs["headers"]["Authorization"] == "Bearer test-access-token"


class TestGetPlatforms:
    async def test_returns_list(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/platforms", payload=PLATFORMS_RESPONSE)
            result = await api.get_platforms()
            assert len(result) == 2
            assert result[0]["name"] == "Nintendo Entertainment System"

    async def test_error_raises_romm_error(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/platforms", status=500)
            with pytest.raises(RommError, match="API error"):
                await api.get_platforms()


class TestSearchRoms:
    async def test_paginated_response_returns_items(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get(
                "http://romm:3000/api/roms?platform_id=1&search_term=mario&limit=25",
                payload=ROMS_PAGINATED_RESPONSE,
            )
            result = await api.search_roms(platform_id=1, search_term="mario")
            assert len(result) == 2
            assert result[0]["name"] == "Super Mario Bros"

    async def test_list_response_returned_directly(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get(
                "http://romm:3000/api/roms?platform_id=1&search_term=mario&limit=25",
                payload=ROMS_LIST_RESPONSE,
            )
            result = await api.search_roms(platform_id=1, search_term="mario")
            assert len(result) == 1
            assert result[0]["name"] == "Super Mario Bros"

    async def test_empty_paginated_response(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get(
                "http://romm:3000/api/roms?platform_id=1&search_term=zzz&limit=25",
                payload={"items": [], "total": 0, "page": 1, "size": 25},
            )
            result = await api.search_roms(platform_id=1, search_term="zzz")
            assert result == []

    async def test_empty_list_response(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get(
                "http://romm:3000/api/roms?platform_id=1&search_term=zzz&limit=25",
                payload=[],
            )
            result = await api.search_roms(platform_id=1, search_term="zzz")
            assert result == []

    async def test_custom_limit(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get(
                "http://romm:3000/api/roms?platform_id=2&search_term=zelda&limit=10",
                payload={"items": [], "total": 0, "page": 1, "size": 10},
            )
            result = await api.search_roms(platform_id=2, search_term="zelda", limit=10)
            assert result == []

    async def test_error_raises_romm_error(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get(
                "http://romm:3000/api/roms?platform_id=1&search_term=mario&limit=25",
                status=500,
            )
            with pytest.raises(RommError, match="API error"):
                await api.search_roms(platform_id=1, search_term="mario")


class TestGetRom:
    async def test_returns_rom_dict(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/roms/10", payload=ROM_RESPONSE)
            result = await api.get_rom(10)
            assert result["id"] == 10
            assert result["name"] == "Super Mario Bros"

    async def test_error_raises_romm_error(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/roms/99", status=404)
            with pytest.raises(RommError, match="API error"):
                await api.get_rom(99)


class TestGetFirmware:
    async def test_returns_firmware_list(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/firmware?platform_id=1", payload=FIRMWARE_RESPONSE)
            result = await api.get_firmware(platform_id=1)
            assert len(result) == 1
            assert result[0]["file_name"] == "bios.bin"

    async def test_error_raises_romm_error(self, api):
        with aioresponses() as m:
            _mock_auth(m)
            m.get("http://romm:3000/api/firmware?platform_id=1", status=500)
            with pytest.raises(RommError, match="API error"):
                await api.get_firmware(platform_id=1)


class TestDownloadUrl:
    def test_simple_filename(self, api):
        url = api.download_url(rom_id=10, fs_name="Super Mario Bros.nes")
        assert url == "https://romm.example.com/api/roms/10/content/Super%20Mario%20Bros.nes"

    def test_filename_with_special_chars(self, api):
        url = api.download_url(rom_id=42, fs_name="Mega Man & Bass.gba")
        assert url == "https://romm.example.com/api/roms/42/content/Mega%20Man%20%26%20Bass.gba"

    def test_plain_filename_no_encoding_needed(self, api):
        url = api.download_url(rom_id=5, fs_name="game.rom")
        assert url == "https://romm.example.com/api/roms/5/content/game.rom"
