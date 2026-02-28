import pytest
from unittest.mock import AsyncMock

from bot.plugins.lidarr.plugin import LidarrPlugin
from bot.plugins.lidarr.api import LidarrClient, LidarrError
from bot.plugins.base import CommandContext
from bot.core.database import Database

SAMPLE_ARTISTS = [
    {
        "artistName": "Radiohead",
        "disambiguation": "UK rock band",
        "foreignArtistId": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
        "overview": "English rock band",
        "rating": {"value": 85, "count": 1234},
    },
    {
        "artistName": "Radiohead Tribute",
        "disambiguation": "",
        "foreignArtistId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "overview": "Tribute band",
        "rating": {"value": 30, "count": 5},
    },
]


@pytest.fixture
def mock_api():
    api = AsyncMock(spec=LidarrClient)
    api.search_artist = AsyncMock(return_value=[])
    api.get_artists = AsyncMock(return_value=[])
    api.add_artist = AsyncMock(return_value={})
    api.close = AsyncMock()
    return api


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=Database)
    db.execute = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    return db


@pytest.fixture
def plugin(mock_api, mock_db):
    return LidarrPlugin(api=mock_api, db=mock_db, irc_colors=False)


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


class TestLidarrPlugin:
    def test_name_returns_lidarr(self, plugin):
        assert plugin.name() == "lidarr"

    def test_registers_commands(self, plugin):
        commands = plugin.register_commands()
        names = {c.name for c in commands}
        assert len(commands) == 3
        assert "request" in names
        assert "select" in names
        assert "status" in names

    async def test_request_missing_args(self, plugin):
        ctx, replies = make_ctx(args=[])
        await plugin.handle_request(ctx)
        assert any("Usage" in r for r in replies)

    async def test_request_search_returns_results(self, plugin):
        plugin._api.search_artist.return_value = SAMPLE_ARTISTS
        ctx, replies = make_ctx(args=["Radiohead"])
        await plugin.handle_request(ctx)
        text = "\n".join(replies)
        assert "Radiohead" in text
        assert "testuser" in plugin._sessions

    async def test_request_search_no_results(self, plugin):
        plugin._api.search_artist.return_value = []
        ctx, replies = make_ctx(args=["zzzznonexistent"])
        await plugin.handle_request(ctx)
        assert any("No artists found" in r for r in replies)

    async def test_request_search_api_error(self, plugin):
        plugin._api.search_artist.side_effect = LidarrError("connection refused")
        ctx, replies = make_ctx(args=["Radiohead"])
        await plugin.handle_request(ctx)
        assert any("unavailable" in r.lower() for r in replies)

    async def test_select_without_session(self, plugin):
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        assert any("No active search" in r for r in replies)

    async def test_select_missing_args(self, plugin):
        plugin._sessions["testuser"] = {
            "results": SAMPLE_ARTISTS,
            "media_type": "music",
            "timestamp": 9999999999.0,
        }
        ctx, replies = make_ctx(args=[])
        await plugin.handle_select(ctx)
        assert any("Usage" in r for r in replies)

    async def test_select_non_number(self, plugin):
        plugin._sessions["testuser"] = {
            "results": SAMPLE_ARTISTS,
            "media_type": "music",
            "timestamp": 9999999999.0,
        }
        ctx, replies = make_ctx(args=["abc"])
        await plugin.handle_select(ctx)
        assert any("valid number" in r.lower() for r in replies)

    async def test_select_out_of_range(self, plugin):
        plugin._sessions["testuser"] = {
            "results": SAMPLE_ARTISTS,
            "media_type": "music",
            "timestamp": 9999999999.0,
        }
        ctx, replies = make_ctx(args=["99"])
        await plugin.handle_select(ctx)
        assert any("Invalid" in r or "between" in r.lower() for r in replies)

    async def test_select_valid_adds_artist(self, plugin):
        plugin._sessions["testuser"] = {
            "results": SAMPLE_ARTISTS,
            "media_type": "music",
            "timestamp": 9999999999.0,
        }
        plugin._api.get_artists.return_value = []
        plugin._api.add_artist.return_value = {}
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        text = "\n".join(replies)
        assert "Artist added" in text
        assert "Radiohead" in text
        plugin._api.add_artist.assert_called_once_with(
            "Radiohead", "a74b1b7f-71a5-4011-9441-d0b5e4122711"
        )
        plugin._db.execute.assert_called_once()
        assert "testuser" not in plugin._sessions

    async def test_select_already_monitored(self, plugin):
        plugin._sessions["testuser"] = {
            "results": SAMPLE_ARTISTS,
            "media_type": "music",
            "timestamp": 9999999999.0,
        }
        plugin._api.get_artists.return_value = [
            {"foreignArtistId": "a74b1b7f-71a5-4011-9441-d0b5e4122711"}
        ]
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        text = "\n".join(replies)
        assert "already in your library" in text.lower()
        plugin._api.add_artist.assert_not_called()
        assert "testuser" not in plugin._sessions

    async def test_status_shows_requests(self, plugin):
        plugin._db.fetch_all.return_value = [
            {
                "media_title": "Radiohead",
                "media_type": "music",
                "requested_at": "2026-02-28 12:00:00",
            }
        ]
        ctx, replies = make_ctx()
        await plugin.handle_status(ctx)
        text = "\n".join(replies)
        assert "Radiohead" in text

    async def test_status_no_requests(self, plugin):
        plugin._db.fetch_all.return_value = []
        ctx, replies = make_ctx()
        await plugin.handle_status(ctx)
        assert any("no recent music requests" in r.lower() for r in replies)

    async def test_on_unload_closes_api(self, plugin):
        await plugin.on_unload()
        plugin._api.close.assert_called_once()
