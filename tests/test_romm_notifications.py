import pytest
from unittest.mock import AsyncMock
from bot.plugins.romm.plugin import RommPlugin


MOCK_PLATFORMS = [
    {"id": 1, "name": "SNES", "slug": "snes", "rom_count": 3},
]

MOCK_ROMS = [
    {"id": 100, "name": "New Game", "fs_name": "new.sfc", "fs_size_bytes": 1048576},
    {"id": 101, "name": "Another New", "fs_name": "another.sfc", "fs_size_bytes": 524288},
]


@pytest.fixture
def plugin():
    api = AsyncMock()
    api._domain = "http://romm.example.com"
    db = AsyncMock()
    p = RommPlugin(api=api, db=db, irc_colors=False, session_timeout=300)
    return p


class TestCheckNewRoms:
    async def test_detects_new_roms(self, plugin):
        plugin._api.get_platforms.return_value = MOCK_PLATFORMS
        plugin._api.search_roms.return_value = MOCK_ROMS
        plugin._db.fetch_all.return_value = []  # none announced yet

        new_roms = await plugin._check_new_roms()
        assert len(new_roms) == 2
        assert new_roms[0]["rom"]["id"] == 100
        assert new_roms[0]["platform_name"] == "SNES"

    async def test_skips_already_announced(self, plugin):
        plugin._api.get_platforms.return_value = MOCK_PLATFORMS
        plugin._api.search_roms.return_value = MOCK_ROMS
        plugin._db.fetch_all.return_value = [{"rom_id": 100}]  # ROM 100 already announced

        new_roms = await plugin._check_new_roms()
        assert len(new_roms) == 1
        assert new_roms[0]["rom"]["id"] == 101

    async def test_all_announced_returns_empty(self, plugin):
        plugin._api.get_platforms.return_value = MOCK_PLATFORMS
        plugin._api.search_roms.return_value = MOCK_ROMS
        plugin._db.fetch_all.return_value = [{"rom_id": 100}, {"rom_id": 101}]

        new_roms = await plugin._check_new_roms()
        assert new_roms == []

    async def test_api_error_returns_empty(self, plugin):
        from bot.plugins.romm.api import RommError
        plugin._api.get_platforms.side_effect = RommError("down")
        new_roms = await plugin._check_new_roms()
        assert new_roms == []

    async def test_multiple_platforms(self, plugin):
        plugin._api.get_platforms.return_value = [
            {"id": 1, "name": "SNES", "slug": "snes", "rom_count": 1},
            {"id": 2, "name": "GBA", "slug": "gba", "rom_count": 1},
        ]
        plugin._api.search_roms.side_effect = [
            [{"id": 200, "name": "SNES Game", "fs_name": "snes.sfc", "fs_size_bytes": 1024}],
            [{"id": 300, "name": "GBA Game", "fs_name": "gba.gba", "fs_size_bytes": 2048}],
        ]
        plugin._db.fetch_all.return_value = []

        new_roms = await plugin._check_new_roms()
        assert len(new_roms) == 2
        platforms = {r["platform_name"] for r in new_roms}
        assert platforms == {"SNES", "GBA"}


class TestAnnounceRoms:
    async def test_sends_messages_and_marks_announced(self, plugin):
        sent = []
        async def send_fn(msg):
            sent.append(msg)

        new_roms = [
            {"rom": {"id": 100, "name": "New Game", "fs_name": "new.sfc", "fs_size_bytes": 1048576}, "platform_name": "SNES"},
        ]
        await plugin._announce_roms(send_fn, new_roms)

        assert len(sent) == 1
        assert "New Game" in sent[0]
        plugin._db.execute.assert_called_once()
        call_args = plugin._db.execute.call_args
        assert "romm_announced" in call_args[0][0]
        assert call_args[0][1] == (100,)

    async def test_announces_multiple(self, plugin):
        sent = []
        async def send_fn(msg):
            sent.append(msg)

        new_roms = [
            {"rom": {"id": 100, "name": "Game A", "fs_name": "a.sfc", "fs_size_bytes": 1024}, "platform_name": "SNES"},
            {"rom": {"id": 101, "name": "Game B", "fs_name": "b.sfc", "fs_size_bytes": 2048}, "platform_name": "GBA"},
        ]
        await plugin._announce_roms(send_fn, new_roms)

        assert len(sent) == 2
        assert plugin._db.execute.call_count == 2
