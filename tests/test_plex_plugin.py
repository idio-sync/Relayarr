import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import time

from bot.plugins.plex.plugin import PlexPlugin
from bot.plugins.plex.plex_client import PlexClient, PlexError
from bot.plugins.plex.tautulli_client import TautulliClient, TautulliError
from bot.plugins.plex.formatters import PlexFormatter
from bot.plugins.base import CommandContext


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


@pytest.fixture
def mock_plex_api():
    api = AsyncMock(spec=PlexClient)
    api.get_sessions = AsyncMock(return_value=[])
    api.get_libraries = AsyncMock(return_value=[])
    api.get_library_details = AsyncMock(return_value={})
    api.get_recently_added = AsyncMock(return_value=[])
    api.close = AsyncMock()
    return api


@pytest.fixture
def mock_tautulli_api():
    api = AsyncMock(spec=TautulliClient)
    api.get_activity = AsyncMock(return_value={"stream_count": "0", "sessions": []})
    api.close = AsyncMock()
    return api


@pytest.fixture
def mock_send():
    return AsyncMock()


@pytest.fixture
def plugin(mock_plex_api, mock_send):
    return PlexPlugin(
        plex_api=mock_plex_api,
        tautulli_api=None,
        formatter=PlexFormatter(irc_colors=False),
        announce_channel=None,
        announce_interval=300,
        send_callback=mock_send,
    )


@pytest.fixture
def plugin_with_tautulli(mock_plex_api, mock_tautulli_api, mock_send):
    return PlexPlugin(
        plex_api=mock_plex_api,
        tautulli_api=mock_tautulli_api,
        formatter=PlexFormatter(irc_colors=False),
        announce_channel=None,
        announce_interval=300,
        send_callback=mock_send,
    )


class TestPlexPlugin:
    def test_name(self, plugin):
        assert plugin.name() == "plex"

    def test_registers_commands(self, plugin):
        commands = plugin.register_commands()
        names = {c.name for c in commands}
        assert "plex" in names
        assert "np" in names
        assert "plexstats" in names
        assert "plexrecent" in names

    def test_all_commands_role_none(self, plugin):
        for cmd in plugin.register_commands():
            assert cmd.required_role == "none"


class TestPlexSubcommand:
    async def test_no_subcommand_shows_usage(self, plugin):
        ctx, replies = make_ctx(args=[])
        await plugin.handle_plex(ctx)
        assert any("usage" in r.lower() for r in replies)

    async def test_unknown_subcommand(self, plugin):
        ctx, replies = make_ctx(args=["unknown"])
        await plugin.handle_plex(ctx)
        assert any("usage" in r.lower() or "unknown" in r.lower() for r in replies)


class TestNowPlaying:
    async def test_playing_uses_plex_when_no_tautulli(self, plugin, mock_plex_api):
        mock_plex_api.get_sessions.return_value = [
            {"User": {"title": "jake"}, "title": "The Matrix", "year": 1999, "type": "movie"}
        ]
        ctx, replies = make_ctx(args=["playing"])
        await plugin.handle_plex(ctx)
        text = "\n".join(replies)
        assert "jake" in text
        assert "The Matrix" in text

    async def test_playing_uses_tautulli_when_available(self, plugin_with_tautulli, mock_tautulli_api):
        mock_tautulli_api.get_activity.return_value = {
            "stream_count": "1",
            "sessions": [
                {
                    "friendly_name": "jake",
                    "full_title": "The Matrix (1999)",
                    "media_type": "movie",
                    "progress_percent": "45",
                    "quality_profile": "1080p",
                    "transcode_decision": "direct play",
                    "state": "playing",
                }
            ],
        }
        ctx, replies = make_ctx(args=["playing"])
        await plugin_with_tautulli.handle_plex(ctx)
        text = "\n".join(replies)
        assert "jake" in text
        assert "1080p" in text

    async def test_playing_falls_back_on_tautulli_error(self, plugin_with_tautulli, mock_tautulli_api, mock_plex_api):
        mock_tautulli_api.get_activity.side_effect = TautulliError("down")
        mock_plex_api.get_sessions.return_value = [
            {"User": {"title": "jake"}, "title": "The Matrix", "year": 1999, "type": "movie"}
        ]
        ctx, replies = make_ctx(args=["playing"])
        await plugin_with_tautulli.handle_plex(ctx)
        text = "\n".join(replies)
        assert "jake" in text
        assert "The Matrix" in text

    async def test_np_alias(self, plugin, mock_plex_api):
        mock_plex_api.get_sessions.return_value = []
        ctx, replies = make_ctx(args=[])
        await plugin.handle_np(ctx)
        assert any("no active" in r.lower() for r in replies)

    async def test_plex_api_error(self, plugin, mock_plex_api):
        mock_plex_api.get_sessions.side_effect = PlexError("error")
        ctx, replies = make_ctx(args=["playing"])
        await plugin.handle_plex(ctx)
        assert any("unavailable" in r.lower() for r in replies)


class TestLibraryStats:
    async def test_stats_output(self, plugin, mock_plex_api):
        mock_plex_api.get_libraries.return_value = [
            {"key": "1", "title": "Movies", "type": "movie"},
        ]
        mock_plex_api.get_library_details.return_value = {"totalSize": 1234}
        mock_plex_api.get_recently_added.return_value = [
            {"addedAt": int(time.time()) - 86400, "type": "movie", "librarySectionID": "1"}
        ] * 12
        ctx, replies = make_ctx(args=["stats"])
        await plugin.handle_plex(ctx)
        text = "\n".join(replies)
        assert "Movies" in text
        assert "1,234" in text

    async def test_plexstats_alias(self, plugin, mock_plex_api):
        mock_plex_api.get_libraries.return_value = []
        ctx, replies = make_ctx(args=[])
        await plugin.handle_plexstats(ctx)
        assert len(replies) >= 1

    async def test_stats_api_error(self, plugin, mock_plex_api):
        mock_plex_api.get_libraries.side_effect = PlexError("error")
        ctx, replies = make_ctx(args=["stats"])
        await plugin.handle_plex(ctx)
        assert any("unavailable" in r.lower() for r in replies)


class TestRecentlyAdded:
    async def test_recent_output(self, plugin, mock_plex_api):
        mock_plex_api.get_recently_added.return_value = [
            {"title": "New Movie", "year": 2026, "type": "movie", "librarySectionTitle": "Movies", "addedAt": 1000}
        ]
        ctx, replies = make_ctx(args=["recent"])
        await plugin.handle_plex(ctx)
        text = "\n".join(replies)
        assert "New Movie" in text

    async def test_plexrecent_alias(self, plugin, mock_plex_api):
        mock_plex_api.get_recently_added.return_value = []
        ctx, replies = make_ctx(args=[])
        await plugin.handle_plexrecent(ctx)
        assert any("no recently" in r.lower() for r in replies)


class TestLifecycle:
    async def test_on_unload_closes_apis(self, plugin_with_tautulli, mock_plex_api, mock_tautulli_api):
        await plugin_with_tautulli.on_unload()
        mock_plex_api.close.assert_called_once()
        mock_tautulli_api.close.assert_called_once()

    async def test_on_unload_no_tautulli(self, plugin, mock_plex_api):
        await plugin.on_unload()
        mock_plex_api.close.assert_called_once()
