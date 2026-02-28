import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from bot.plugins.base import CommandContext
from bot.plugins.media_coordinator import MediaCoordinator


@pytest.fixture
def mock_overseerr():
    plugin = MagicMock()
    plugin.name.return_value = "overseerr"
    plugin._sessions = {}
    plugin.handle_request = AsyncMock()
    plugin.handle_select = AsyncMock()
    plugin.handle_status = AsyncMock()
    plugin.on_unload = AsyncMock()
    return plugin


@pytest.fixture
def mock_lidarr():
    plugin = MagicMock()
    plugin.name.return_value = "lidarr"
    plugin._sessions = {}
    plugin.handle_request = AsyncMock()
    plugin.handle_select = AsyncMock()
    plugin.handle_status = AsyncMock()
    plugin.on_unload = AsyncMock()
    return plugin


@pytest.fixture
def coordinator(mock_overseerr, mock_lidarr):
    backends = {
        "movie": mock_overseerr,
        "tv": mock_overseerr,
        "music": mock_lidarr,
    }
    return MediaCoordinator(backends=backends, session_timeout=300)


@pytest.fixture
def make_ctx():
    def _make(args=None, sender="testuser"):
        reply = AsyncMock()
        return CommandContext(
            sender=sender,
            hostmask=f"{sender}!user@host",
            channel="#test",
            args=args or [],
            reply=reply,
        ), reply
    return _make


# --- 1. Plugin identity ---

def test_name_returns_media(coordinator):
    assert coordinator.name() == "media"


# --- 2. Command registration ---

def test_registers_three_commands(coordinator):
    cmds = coordinator.register_commands()
    names = {c.name for c in cmds}
    assert names == {"request", "select", "status"}
    assert len(cmds) == 3


# --- 3. Help text includes all types ---

def test_help_text_includes_all_types(coordinator):
    cmds = coordinator.register_commands()
    request_cmd = next(c for c in cmds if c.name == "request")
    assert "movie/music/tv" in request_cmd.help_text


# --- 4. Missing args shows usage ---

@pytest.mark.asyncio
async def test_request_missing_args_shows_usage(coordinator, make_ctx):
    ctx, reply = make_ctx(args=["movie"])
    await coordinator.handle_request(ctx)
    reply.assert_called_once()
    msg = reply.call_args[0][0]
    assert "Usage" in msg
    assert "movie/music/tv" in msg


# --- 5. Unknown type shows error ---

@pytest.mark.asyncio
async def test_request_unknown_type_shows_error(coordinator, make_ctx):
    ctx, reply = make_ctx(args=["anime", "naruto"])
    await coordinator.handle_request(ctx)
    reply.assert_called_once()
    msg = reply.call_args[0][0]
    assert "Unknown type" in msg
    assert "anime" in msg
    assert "movie/music/tv" in msg


# --- 6. Movie routes to overseerr with full ctx ---

@pytest.mark.asyncio
async def test_request_routes_movie_to_overseerr(coordinator, mock_overseerr, make_ctx):
    ctx, reply = make_ctx(args=["movie", "inception"])
    await coordinator.handle_request(ctx)
    mock_overseerr.handle_request.assert_called_once_with(ctx)


# --- 7. TV routes to overseerr with full ctx ---

@pytest.mark.asyncio
async def test_request_routes_tv_to_overseerr(coordinator, mock_overseerr, make_ctx):
    ctx, reply = make_ctx(args=["tv", "breaking", "bad"])
    await coordinator.handle_request(ctx)
    mock_overseerr.handle_request.assert_called_once_with(ctx)


# --- 8. Music routes to lidarr with stripped args ---

@pytest.mark.asyncio
async def test_request_routes_music_to_lidarr(coordinator, mock_lidarr, make_ctx):
    ctx, reply = make_ctx(args=["music", "radiohead"])
    await coordinator.handle_request(ctx)
    mock_lidarr.handle_request.assert_called_once()
    delegated_ctx = mock_lidarr.handle_request.call_args[0][0]
    assert delegated_ctx.args == ["radiohead"]
    assert delegated_ctx.sender == "testuser"


# --- 9. Request creates coordinator session ---

@pytest.mark.asyncio
async def test_request_creates_coordinator_session(coordinator, mock_overseerr, make_ctx):
    ctx, reply = make_ctx(args=["movie", "inception"])
    await coordinator.handle_request(ctx)
    assert "testuser" in coordinator._sessions
    assert coordinator._sessions["testuser"]["backend"] == "movie"
    assert "timestamp" in coordinator._sessions["testuser"]


# --- 10. Select routes to correct backend ---

@pytest.mark.asyncio
async def test_select_routes_to_correct_backend(coordinator, mock_lidarr, make_ctx):
    # First create a music session
    ctx, reply = make_ctx(args=["music", "radiohead"])
    await coordinator.handle_request(ctx)

    # Simulate backend keeping its session
    mock_lidarr._sessions["testuser"] = {"results": [], "timestamp": time.time()}

    # Now select
    ctx2, reply2 = make_ctx(args=["1"])
    await coordinator.handle_select(ctx2)
    mock_lidarr.handle_select.assert_called_once_with(ctx2)


# --- 11. Select without session shows error ---

@pytest.mark.asyncio
async def test_select_without_session_shows_error(coordinator, make_ctx):
    ctx, reply = make_ctx(args=["1"])
    await coordinator.handle_select(ctx)
    reply.assert_called_once()
    msg = reply.call_args[0][0]
    assert "No active search" in msg
    assert "movie/music/tv" in msg


# --- 12. Select clears session when backend clears ---

@pytest.mark.asyncio
async def test_select_clears_session_when_backend_clears(coordinator, mock_lidarr, make_ctx):
    # Create a music session
    ctx, reply = make_ctx(args=["music", "radiohead"])
    await coordinator.handle_request(ctx)

    # Backend has session initially
    mock_lidarr._sessions["testuser"] = {"results": [], "timestamp": time.time()}

    # Simulate backend clearing session during handle_select
    async def clear_session(ctx):
        mock_lidarr._sessions.pop("testuser", None)

    mock_lidarr.handle_select = AsyncMock(side_effect=clear_session)

    ctx2, reply2 = make_ctx(args=["1"])
    await coordinator.handle_select(ctx2)

    assert "testuser" not in coordinator._sessions


# --- 13. Select keeps session when backend keeps ---

@pytest.mark.asyncio
async def test_select_keeps_session_when_backend_keeps(coordinator, mock_lidarr, make_ctx):
    # Create a music session
    ctx, reply = make_ctx(args=["music", "radiohead"])
    await coordinator.handle_request(ctx)

    # Backend keeps session after select
    mock_lidarr._sessions["testuser"] = {"results": [], "timestamp": time.time()}

    ctx2, reply2 = make_ctx(args=["1"])
    await coordinator.handle_select(ctx2)

    # Coordinator session should still exist
    assert "testuser" in coordinator._sessions


# --- 14. Status delegates to all backends (each unique backend once) ---

@pytest.mark.asyncio
async def test_status_delegates_to_all_backends(coordinator, mock_overseerr, mock_lidarr, make_ctx):
    ctx, reply = make_ctx()
    await coordinator.handle_status(ctx)

    # Overseerr should only be called once despite being mapped to both movie and tv
    mock_overseerr.handle_status.assert_called_once_with(ctx)
    mock_lidarr.handle_status.assert_called_once_with(ctx)


# --- 15. on_unload calls all backends once ---

@pytest.mark.asyncio
async def test_on_unload_calls_all_backends(coordinator, mock_overseerr, mock_lidarr):
    await coordinator.on_unload()

    mock_overseerr.on_unload.assert_called_once()
    mock_lidarr.on_unload.assert_called_once()


# --- 16. New search clears old backend session ---

@pytest.mark.asyncio
async def test_new_search_clears_old_backend_session(coordinator, mock_overseerr, mock_lidarr, make_ctx):
    # Start a movie search (overseerr)
    ctx1, reply1 = make_ctx(args=["movie", "inception"])
    await coordinator.handle_request(ctx1)

    # Simulate overseerr having a session
    mock_overseerr._sessions["testuser"] = {"results": [], "timestamp": time.time()}

    # Now start a music search (lidarr) — different backend
    ctx2, reply2 = make_ctx(args=["music", "radiohead"])
    await coordinator.handle_request(ctx2)

    # Old overseerr session should be cleared
    assert "testuser" not in mock_overseerr._sessions
    # Coordinator session should now point to music
    assert coordinator._sessions["testuser"]["backend"] == "music"


# --- 17. Expired session cleaned ---

@pytest.mark.asyncio
async def test_expired_session_cleaned(coordinator, make_ctx):
    # Manually insert an expired session
    coordinator._sessions["olduser"] = {
        "backend": "movie",
        "timestamp": time.time() - 600,  # 10 min ago, well past 5 min timeout
    }

    # Trigger cleanup via a request call
    ctx, reply = make_ctx(args=["movie", "inception"], sender="newuser")
    await coordinator.handle_request(ctx)

    assert "olduser" not in coordinator._sessions


# --- 18. Select routes to RomM when romm session exists ---

@pytest.mark.asyncio
async def test_select_routes_to_romm_when_romm_session_exists(mock_overseerr, mock_lidarr, make_ctx):
    mock_romm = MagicMock()
    mock_romm.name.return_value = "romm"
    mock_romm._sessions = {}
    mock_romm.handle_select = AsyncMock()
    mock_romm.on_unload = AsyncMock()

    backends = {"movie": mock_overseerr, "tv": mock_overseerr, "music": mock_lidarr}
    coordinator = MediaCoordinator(backends=backends, session_timeout=300, romm_backend=mock_romm)

    # Put a session in romm (simulating user ran !game)
    mock_romm._sessions["testuser"] = {"results": [], "timestamp": time.time()}

    ctx, reply = make_ctx(args=["1"])
    await coordinator.handle_select(ctx)

    mock_romm.handle_select.assert_called_once_with(ctx)
    reply.assert_not_called()


# --- 19. Select no session shows !game hint when romm configured ---

@pytest.mark.asyncio
async def test_select_no_session_shows_game_hint(mock_overseerr, mock_lidarr, make_ctx):
    mock_romm = MagicMock()
    mock_romm.name.return_value = "romm"
    mock_romm._sessions = {}
    mock_romm.handle_select = AsyncMock()
    mock_romm.on_unload = AsyncMock()

    backends = {"movie": mock_overseerr, "tv": mock_overseerr, "music": mock_lidarr}
    coordinator = MediaCoordinator(backends=backends, session_timeout=300, romm_backend=mock_romm)

    ctx, reply = make_ctx(args=["1"])
    await coordinator.handle_select(ctx)

    reply.assert_called_once()
    msg = reply.call_args[0][0]
    assert "No active search" in msg
    assert "!game" in msg


# --- 20. Select prefers coordinator session over romm ---

@pytest.mark.asyncio
async def test_select_prefers_coordinator_session_over_romm(mock_overseerr, mock_lidarr, make_ctx):
    mock_romm = MagicMock()
    mock_romm.name.return_value = "romm"
    mock_romm._sessions = {}
    mock_romm.handle_select = AsyncMock()
    mock_romm.on_unload = AsyncMock()

    backends = {"movie": mock_overseerr, "tv": mock_overseerr, "music": mock_lidarr}
    coordinator = MediaCoordinator(backends=backends, session_timeout=300, romm_backend=mock_romm)

    # Both coordinator and romm have sessions for testuser
    coordinator._sessions["testuser"] = {"backend": "music", "timestamp": time.time()}
    mock_romm._sessions["testuser"] = {"results": [], "timestamp": time.time()}
    mock_lidarr._sessions["testuser"] = {"results": [], "timestamp": time.time()}

    ctx, reply = make_ctx(args=["1"])
    await coordinator.handle_select(ctx)

    # Coordinator session wins — lidarr gets the call, not romm
    mock_lidarr.handle_select.assert_called_once_with(ctx)
    mock_romm.handle_select.assert_not_called()


# --- 21. on_unload calls romm backend when present ---

@pytest.mark.asyncio
async def test_on_unload_calls_romm_backend(mock_overseerr, mock_lidarr):
    mock_romm = MagicMock()
    mock_romm.name.return_value = "romm"
    mock_romm._sessions = {}
    mock_romm.on_unload = AsyncMock()

    backends = {"movie": mock_overseerr, "tv": mock_overseerr, "music": mock_lidarr}
    coordinator = MediaCoordinator(backends=backends, session_timeout=300, romm_backend=mock_romm)

    await coordinator.on_unload()

    mock_romm.on_unload.assert_called_once()
