import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.plugins.overseerr.plugin import OverseerrPlugin
from bot.plugins.base import CommandContext

MOCK_SEARCH_RESULTS = [
    {
        "id": 157336, "title": "Interstellar", "releaseDate": "2014-11-05",
        "overview": "A team of explorers travel through a wormhole.",
        "voteAverage": 8.6, "mediaType": "movie",
        "mediaInfo": {"status": 5},
    },
    {
        "id": 399404, "title": "Interstellar Wars", "releaseDate": "2016-06-02",
        "overview": "Aliens attack Earth.",
        "voteAverage": 2.1, "mediaType": "movie",
        "mediaInfo": None,
    },
]


@pytest.fixture
def plugin():
    api = AsyncMock()
    db = AsyncMock()
    p = OverseerrPlugin(api=api, db=db, irc_colors=False, session_timeout=300)
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


class TestOverseerrPluginCommands:
    def test_registers_commands(self, plugin):
        commands = plugin.register_commands()
        names = {c.name for c in commands}
        assert "request" in names
        assert "select" in names
        assert "status" in names

    async def test_request_missing_args(self, plugin):
        ctx, replies = make_ctx(args=[])
        await plugin.handle_request(ctx)
        assert any("Usage" in r for r in replies)

    async def test_request_invalid_type(self, plugin):
        ctx, replies = make_ctx(args=["anime", "test"])
        await plugin.handle_request(ctx)
        assert any("movie" in r.lower() or "tv" in r.lower() for r in replies)

    async def test_request_search_returns_results(self, plugin):
        plugin._api.search.return_value = MOCK_SEARCH_RESULTS
        ctx, replies = make_ctx(args=["movie", "Interstellar"])
        await plugin.handle_request(ctx)
        text = "\n".join(replies)
        assert "Interstellar" in text
        assert "testuser" in plugin._sessions

    async def test_request_search_no_results(self, plugin):
        plugin._api.search.return_value = []
        ctx, replies = make_ctx(args=["movie", "zzzznonexistent"])
        await plugin.handle_request(ctx)
        assert any("No" in r and "results" in r.lower() for r in replies)

    async def test_select_without_session(self, plugin):
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        assert any("search first" in r.lower() for r in replies)

    async def test_select_valid(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "media_type": "movie",
        }
        plugin._api.request_media.return_value = {"id": 42, "status": 2}
        ctx, replies = make_ctx(args=["2"])
        await plugin.handle_select(ctx)
        text = "\n".join(replies)
        assert "Request submitted" in text
        plugin._api.request_media.assert_called_once_with(media_id=399404, media_type="movie")

    async def test_select_already_available(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "media_type": "movie",
        }
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        text = "\n".join(replies)
        assert "already available" in text.lower()

    async def test_select_out_of_range(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "media_type": "movie",
        }
        ctx, replies = make_ctx(args=["99"])
        await plugin.handle_select(ctx)
        assert any("Invalid" in r or "between" in r.lower() for r in replies)

    async def test_select_non_number(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "media_type": "movie",
        }
        ctx, replies = make_ctx(args=["abc"])
        await plugin.handle_select(ctx)
        assert any("number" in r.lower() for r in replies)

    async def test_status_shows_requests(self, plugin):
        plugin._db.fetch_all.return_value = [
            {"media_title": "Interstellar Wars", "media_type": "movie", "requested_at": "2026-02-28 12:00:00"}
        ]
        ctx, replies = make_ctx()
        await plugin.handle_status(ctx)
        text = "\n".join(replies)
        assert "Interstellar Wars" in text

    async def test_status_no_requests(self, plugin):
        plugin._db.fetch_all.return_value = []
        ctx, replies = make_ctx()
        await plugin.handle_status(ctx)
        assert any("no" in r.lower() and "request" in r.lower() for r in replies)
