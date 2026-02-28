import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.plugins.romm.plugin import RommPlugin
from bot.plugins.base import CommandContext


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

PLATFORMS = [
    {"id": 1, "name": "SNES", "slug": "snes", "rom_count": 42},
    {"id": 2, "name": "Nintendo 64", "slug": "n64", "rom_count": 10},
    {"id": 3, "name": "Game Boy", "slug": "gb", "rom_count": 0},
]

ROM_RESULTS = [
    {"id": 101, "name": "Super Mario World", "file_size_bytes": 524288, "fs_name": "smw.sfc"},
    {"id": 102, "name": "Donkey Kong Country", "file_size_bytes": 1048576, "fs_name": "dkc.sfc"},
]

ROM_DETAIL = {
    "id": 101,
    "name": "Super Mario World",
    "file_size_bytes": 524288,
    "fs_name": "smw.sfc",
    "files": [{"name": "smw.sfc"}],
}

IGDB_RESULTS = [
    {"id": 1, "name": "Chrono Trigger", "first_release_date": 800000000, "genres": [{"name": "RPG"}]},
    {"id": 2, "name": "Chrono Cross", "first_release_date": 960000000, "genres": []},
]

FIRMWARE_LIST = [
    {"file_name": "bios.bin", "file_size_bytes": 131072, "md5_hash": "abc123"},
]

REQUEST_ROWS = [
    {"game_title": "Chrono Trigger", "platform": "SNES", "status": "pending", "requested_at": "2026-02-28 10:00:00"},
]


def make_api():
    api = AsyncMock()
    api._domain = "http://romm.example.com"
    api.get_platforms.return_value = PLATFORMS
    api.search_roms.return_value = ROM_RESULTS
    api.get_rom.return_value = ROM_DETAIL
    api.get_firmware.return_value = FIRMWARE_LIST
    api.download_url.return_value = "http://romm.example.com/api/roms/101/content/smw.sfc"
    return api


def make_db():
    db = AsyncMock()
    db.fetch_all.return_value = []
    db.execute.return_value = None
    return db


def make_igdb():
    igdb = AsyncMock()
    igdb.search_game.return_value = IGDB_RESULTS
    return igdb


@pytest.fixture
def plugin():
    api = make_api()
    db = make_db()
    p = RommPlugin(api=api, db=db, irc_colors=False, session_timeout=300)
    return p


@pytest.fixture
def plugin_with_igdb():
    api = make_api()
    db = make_db()
    igdb = make_igdb()
    p = RommPlugin(api=api, db=db, igdb=igdb, irc_colors=False, session_timeout=300)
    return p


def make_ctx(sender="testuser", args=None):
    replies = []

    async def reply(msg):
        replies.append(msg)

    ctx = CommandContext(
        sender=sender,
        hostmask=f"{sender}!~user@host",
        channel="#test",
        args=args or [],
        reply=reply,
    )
    return ctx, replies


# ---------------------------------------------------------------------------
# TestRommPluginRegistration
# ---------------------------------------------------------------------------

class TestRommPluginRegistration:
    def test_name(self, plugin):
        assert plugin.name() == "romm"

    def test_registers_expected_commands(self, plugin):
        commands = plugin.register_commands()
        names = {c.name for c in commands}
        assert "game" in names
        assert "platforms" in names
        assert "gamestats" in names
        assert "random" in names
        assert "myrequests" in names
        assert "firmware" in names

    def test_select_not_registered(self, plugin):
        commands = plugin.register_commands()
        names = {c.name for c in commands}
        assert "select" not in names

    def test_command_has_help_text(self, plugin):
        commands = plugin.register_commands()
        for cmd in commands:
            assert cmd.help_text, f"Command '{cmd.name}' missing help_text"


# ---------------------------------------------------------------------------
# TestGameCommand
# ---------------------------------------------------------------------------

class TestGameCommand:
    async def test_missing_args_shows_usage(self, plugin):
        ctx, replies = make_ctx(args=[])
        await plugin.handle_game(ctx)
        assert any("Usage" in r or "usage" in r for r in replies)

    async def test_only_platform_no_title_shows_usage(self, plugin):
        ctx, replies = make_ctx(args=["snes"])
        await plugin.handle_game(ctx)
        assert any("Usage" in r or "usage" in r for r in replies)

    async def test_unknown_platform_replies_error(self, plugin):
        ctx, replies = make_ctx(args=["unknownplatform", "mario"])
        await plugin.handle_game(ctx)
        text = " ".join(replies)
        assert "not found" in text.lower() or "unknown" in text.lower() or "no platform" in text.lower()

    async def test_found_results_stores_browse_session(self, plugin):
        plugin._api.search_roms.return_value = ROM_RESULTS
        ctx, replies = make_ctx(args=["snes", "mario"])
        await plugin.handle_game(ctx)
        assert "testuser" in plugin._sessions
        assert plugin._sessions["testuser"]["mode"] == "browse"

    async def test_found_results_replies_with_rom_list(self, plugin):
        plugin._api.search_roms.return_value = ROM_RESULTS
        ctx, replies = make_ctx(args=["snes", "mario"])
        await plugin.handle_game(ctx)
        text = "\n".join(replies)
        assert "Super Mario World" in text or "Donkey Kong" in text

    async def test_found_results_session_has_platform(self, plugin):
        plugin._api.search_roms.return_value = ROM_RESULTS
        ctx, replies = make_ctx(args=["snes", "mario"])
        await plugin.handle_game(ctx)
        session = plugin._sessions["testuser"]
        assert "platform" in session
        assert "SNES" in session["platform"] or "snes" in session["platform_slug"]

    async def test_no_results_no_igdb_replies_not_found(self, plugin):
        plugin._api.search_roms.return_value = []
        ctx, replies = make_ctx(args=["snes", "chrono"])
        await plugin.handle_game(ctx)
        text = " ".join(replies)
        assert "no" in text.lower() and ("rom" in text.lower() or "found" in text.lower())
        assert "testuser" not in plugin._sessions

    async def test_no_results_with_igdb_fallback_stores_request_session(self, plugin_with_igdb):
        plugin_with_igdb._api.search_roms.return_value = []
        ctx, replies = make_ctx(args=["snes", "chrono"])
        await plugin_with_igdb.handle_game(ctx)
        assert "testuser" in plugin_with_igdb._sessions
        assert plugin_with_igdb._sessions["testuser"]["mode"] == "request"

    async def test_no_results_with_igdb_fallback_replies_igdb_list(self, plugin_with_igdb):
        plugin_with_igdb._api.search_roms.return_value = []
        ctx, replies = make_ctx(args=["snes", "chrono"])
        await plugin_with_igdb.handle_game(ctx)
        text = "\n".join(replies)
        assert "Chrono Trigger" in text or "IGDB" in text

    async def test_no_results_igdb_also_empty_replies_not_found(self, plugin_with_igdb):
        plugin_with_igdb._api.search_roms.return_value = []
        plugin_with_igdb._igdb.search_game.return_value = []
        ctx, replies = make_ctx(args=["snes", "zzz"])
        await plugin_with_igdb.handle_game(ctx)
        text = " ".join(replies)
        assert "no" in text.lower()
        assert "testuser" not in plugin_with_igdb._sessions

    async def test_platform_matched_by_slug(self, plugin):
        plugin._api.search_roms.return_value = ROM_RESULTS
        ctx, replies = make_ctx(args=["snes", "mario"])
        await plugin.handle_game(ctx)
        plugin._api.get_platforms.assert_called_once()
        # Platform ID 1 used for snes
        plugin._api.search_roms.assert_called_once_with(1, "mario", limit=25)

    async def test_platform_matched_by_name_case_insensitive(self, plugin):
        plugin._api.search_roms.return_value = ROM_RESULTS
        ctx, replies = make_ctx(args=["nintendo 64", "zelda"])
        await plugin.handle_game(ctx)
        plugin._api.search_roms.assert_called_once_with(2, "zelda", limit=25)

    async def test_results_capped_at_10(self, plugin):
        # Return 15 ROMs; session should have at most 10
        many = [{"id": i, "name": f"ROM {i}", "file_size_bytes": 0, "fs_name": f"rom{i}.sfc"}
                for i in range(15)]
        plugin._api.search_roms.return_value = many
        ctx, replies = make_ctx(args=["snes", "mario"])
        await plugin.handle_game(ctx)
        assert len(plugin._sessions["testuser"]["results"]) <= 10


# ---------------------------------------------------------------------------
# TestSelectBrowse
# ---------------------------------------------------------------------------

class TestSelectBrowse:
    def _set_browse_session(self, plugin, results=None):
        plugin._sessions["testuser"] = {
            "results": results or ROM_RESULTS,
            "mode": "browse",
            "platform": "SNES",
            "platform_slug": "snes",
            "timestamp": time.time(),
        }

    async def test_shows_rom_details_and_download_url(self, plugin):
        self._set_browse_session(plugin)
        plugin._api.get_rom.return_value = ROM_DETAIL
        plugin._api.download_url.return_value = "http://romm.example.com/api/roms/101/content/smw.sfc"
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        text = "\n".join(replies)
        assert "Super Mario World" in text
        assert "http" in text  # download URL present

    async def test_clears_session_after_select(self, plugin):
        self._set_browse_session(plugin)
        plugin._api.get_rom.return_value = ROM_DETAIL
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        assert "testuser" not in plugin._sessions

    async def test_out_of_range_replies_error(self, plugin):
        self._set_browse_session(plugin)
        ctx, replies = make_ctx(args=["99"])
        await plugin.handle_select(ctx)
        text = " ".join(replies)
        assert "invalid" in text.lower() or "between" in text.lower() or "range" in text.lower()

    async def test_out_of_range_zero_replies_error(self, plugin):
        self._set_browse_session(plugin)
        ctx, replies = make_ctx(args=["0"])
        await plugin.handle_select(ctx)
        text = " ".join(replies)
        assert "invalid" in text.lower() or "between" in text.lower() or "range" in text.lower()

    async def test_non_number_replies_error(self, plugin):
        self._set_browse_session(plugin)
        ctx, replies = make_ctx(args=["abc"])
        await plugin.handle_select(ctx)
        text = " ".join(replies)
        assert "number" in text.lower() or "valid" in text.lower()

    async def test_no_session_replies_error(self, plugin):
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        text = " ".join(replies)
        assert "no active" in text.lower() or "search first" in text.lower() or "no session" in text.lower()

    async def test_missing_number_arg_replies_error(self, plugin):
        self._set_browse_session(plugin)
        ctx, replies = make_ctx(args=[])
        await plugin.handle_select(ctx)
        text = " ".join(replies)
        assert "usage" in text.lower() or "number" in text.lower()


# ---------------------------------------------------------------------------
# TestSelectRequest
# ---------------------------------------------------------------------------

class TestSelectRequest:
    def _set_request_session(self, plugin, results=None):
        plugin._sessions["testuser"] = {
            "results": results or IGDB_RESULTS,
            "mode": "request",
            "platform": "SNES",
            "platform_slug": "snes",
            "timestamp": time.time(),
        }

    async def test_submits_to_db(self, plugin):
        self._set_request_session(plugin)
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        plugin._db.execute.assert_called_once()
        call_args = plugin._db.execute.call_args
        # First positional arg is the SQL, second is the values tuple
        sql = call_args[0][0]
        assert "romm_requests" in sql
        vals = call_args[0][1]
        assert "testuser" in vals
        assert "Chrono Trigger" in vals

    async def test_reply_contains_success_message(self, plugin):
        self._set_request_session(plugin)
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        text = " ".join(replies)
        assert "request" in text.lower() or "submitted" in text.lower()

    async def test_clears_session_after_request(self, plugin):
        self._set_request_session(plugin)
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        assert "testuser" not in plugin._sessions

    async def test_out_of_range_replies_error(self, plugin):
        self._set_request_session(plugin)
        ctx, replies = make_ctx(args=["99"])
        await plugin.handle_select(ctx)
        text = " ".join(replies)
        assert "invalid" in text.lower() or "between" in text.lower() or "range" in text.lower()


# ---------------------------------------------------------------------------
# TestPlatformsCommand
# ---------------------------------------------------------------------------

class TestPlatformsCommand:
    async def test_lists_platforms(self, plugin):
        ctx, replies = make_ctx()
        await plugin.handle_platforms(ctx)
        text = "\n".join(replies)
        assert "SNES" in text or "snes" in text

    async def test_replies_at_least_one_line(self, plugin):
        ctx, replies = make_ctx()
        await plugin.handle_platforms(ctx)
        assert len(replies) >= 1

    async def test_empty_platforms_replies_gracefully(self, plugin):
        plugin._api.get_platforms.return_value = []
        ctx, replies = make_ctx()
        await plugin.handle_platforms(ctx)
        assert len(replies) >= 1


# ---------------------------------------------------------------------------
# TestStatsCommand
# ---------------------------------------------------------------------------

class TestStatsCommand:
    async def test_shows_platform_count(self, plugin):
        ctx, replies = make_ctx()
        await plugin.handle_gamestats(ctx)
        text = " ".join(replies)
        assert "3" in text  # 3 platforms

    async def test_shows_rom_count(self, plugin):
        ctx, replies = make_ctx()
        await plugin.handle_gamestats(ctx)
        text = " ".join(replies)
        total = sum(p["rom_count"] for p in PLATFORMS)  # 52
        assert str(total) in text

    async def test_replies_at_least_one_line(self, plugin):
        ctx, replies = make_ctx()
        await plugin.handle_gamestats(ctx)
        assert len(replies) >= 1


# ---------------------------------------------------------------------------
# TestRandomCommand
# ---------------------------------------------------------------------------

class TestRandomCommand:
    async def test_returns_a_rom(self, plugin):
        plugin._api.search_roms.return_value = ROM_RESULTS
        plugin._api.get_rom.return_value = ROM_DETAIL
        ctx, replies = make_ctx()
        await plugin.handle_random(ctx)
        text = "\n".join(replies)
        # Should reply with at least a ROM name
        assert len(replies) >= 1

    async def test_with_platform_arg(self, plugin):
        plugin._api.search_roms.return_value = ROM_RESULTS
        plugin._api.get_rom.return_value = ROM_DETAIL
        ctx, replies = make_ctx(args=["snes"])
        await plugin.handle_random(ctx)
        assert len(replies) >= 1

    async def test_unknown_platform_arg_replies_error(self, plugin):
        ctx, replies = make_ctx(args=["unknownxyz"])
        await plugin.handle_random(ctx)
        text = " ".join(replies)
        assert "not found" in text.lower() or "unknown" in text.lower() or "no platform" in text.lower()

    async def test_no_roms_on_platform_replies_gracefully(self, plugin):
        # Only platform with rom_count > 0: SNES(42), N64(10). GB has 0.
        # Force snes search to return empty
        plugin._api.search_roms.return_value = []
        ctx, replies = make_ctx(args=["snes"])
        await plugin.handle_random(ctx)
        assert len(replies) >= 1


# ---------------------------------------------------------------------------
# TestMyRequestsCommand
# ---------------------------------------------------------------------------

class TestMyRequestsCommand:
    async def test_shows_requests(self, plugin):
        plugin._db.fetch_all.return_value = REQUEST_ROWS
        ctx, replies = make_ctx()
        await plugin.handle_myrequests(ctx)
        text = "\n".join(replies)
        assert "Chrono Trigger" in text

    async def test_no_requests_replies_gracefully(self, plugin):
        plugin._db.fetch_all.return_value = []
        ctx, replies = make_ctx()
        await plugin.handle_myrequests(ctx)
        text = " ".join(replies)
        assert "no" in text.lower() or "empty" in text.lower() or "request" in text.lower()

    async def test_queries_correct_table(self, plugin):
        plugin._db.fetch_all.return_value = []
        ctx, replies = make_ctx()
        await plugin.handle_myrequests(ctx)
        plugin._db.fetch_all.assert_called_once()
        sql = plugin._db.fetch_all.call_args[0][0]
        assert "romm_requests" in sql

    async def test_queries_by_sender(self, plugin):
        plugin._db.fetch_all.return_value = []
        ctx, replies = make_ctx(sender="alice")
        await plugin.handle_myrequests(ctx)
        args = plugin._db.fetch_all.call_args[0][1]
        assert "alice" in args


# ---------------------------------------------------------------------------
# TestFirmwareCommand
# ---------------------------------------------------------------------------

class TestFirmwareCommand:
    async def test_lists_firmware(self, plugin):
        ctx, replies = make_ctx(args=["snes"])
        await plugin.handle_firmware(ctx)
        text = "\n".join(replies)
        assert "bios.bin" in text

    async def test_missing_platform_arg_shows_usage(self, plugin):
        ctx, replies = make_ctx(args=[])
        await plugin.handle_firmware(ctx)
        text = " ".join(replies)
        assert "usage" in text.lower() or "platform" in text.lower()

    async def test_unknown_platform_replies_error(self, plugin):
        ctx, replies = make_ctx(args=["unknownxyz"])
        await plugin.handle_firmware(ctx)
        text = " ".join(replies)
        assert "not found" in text.lower() or "unknown" in text.lower() or "no platform" in text.lower()

    async def test_empty_firmware_replies_gracefully(self, plugin):
        plugin._api.get_firmware.return_value = []
        ctx, replies = make_ctx(args=["snes"])
        await plugin.handle_firmware(ctx)
        assert len(replies) >= 1


# ---------------------------------------------------------------------------
# TestOnLoad / TestOnUnload
# ---------------------------------------------------------------------------

class TestLifecycle:
    async def test_on_load_creates_tables(self, plugin):
        await plugin.on_load()
        # Should call execute at least twice (romm_requests, romm_announced)
        assert plugin._db.execute.call_count >= 2
        calls_sql = [c[0][0] for c in plugin._db.execute.call_args_list]
        assert any("romm_requests" in s for s in calls_sql)
        assert any("romm_announced" in s for s in calls_sql)

    async def test_on_unload_closes_api(self, plugin):
        await plugin.on_unload()
        plugin._api.close.assert_called_once()

    async def test_on_unload_closes_igdb(self, plugin_with_igdb):
        await plugin_with_igdb.on_unload()
        plugin_with_igdb._igdb.close.assert_called_once()

    async def test_on_unload_no_igdb_does_not_error(self, plugin):
        # plugin has no IGDB; should not raise
        await plugin.on_unload()


# ---------------------------------------------------------------------------
# TestSessionExpiry
# ---------------------------------------------------------------------------

class TestSessionExpiry:
    async def test_expired_sessions_are_cleaned(self, plugin):
        old_time = time.time() - 400  # older than 300s timeout
        plugin._sessions["alice"] = {"results": [], "mode": "browse", "timestamp": old_time}
        plugin._sessions["bob"] = {"results": [], "mode": "browse", "timestamp": time.time()}
        plugin._clean_expired_sessions()
        assert "alice" not in plugin._sessions
        assert "bob" in plugin._sessions
