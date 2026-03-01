import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from bot.plugins.shelfmark.plugin import ShelfmarkPlugin
from bot.plugins.shelfmark.api import ShelfmarkError
from bot.plugins.base import CommandContext


MOCK_SEARCH_RESULTS = [
    {
        "id": "abc123", "title": "The Hobbit", "author": "J.R.R. Tolkien",
        "year": "1937", "format": "epub", "size": "2.1 MB", "content_type": "ebook",
    },
    {
        "id": "def456", "title": "The Lord of the Rings", "author": "J.R.R. Tolkien",
        "year": "1954", "format": "pdf", "size": "5.3 MB", "content_type": "ebook",
    },
]


@pytest.fixture
def plugin():
    api = AsyncMock()
    db = AsyncMock()
    return ShelfmarkPlugin(api=api, db=db, irc_colors=False, session_timeout=300)


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


class TestShelfmarkPluginRegistration:
    def test_name(self, plugin):
        assert plugin.name() == "shelfmark"

    def test_registers_commands(self, plugin):
        commands = plugin.register_commands()
        names = {c.name for c in commands}
        assert "request" in names
        assert "select" in names
        assert "status" in names


class TestShelfmarkRequest:
    async def test_request_missing_args(self, plugin):
        ctx, replies = make_ctx(args=[])
        await plugin.handle_request(ctx)
        assert any("Usage" in r for r in replies)

    async def test_request_search_returns_results(self, plugin):
        plugin._api.search.return_value = MOCK_SEARCH_RESULTS
        ctx, replies = make_ctx(args=["The", "Hobbit"])
        await plugin.handle_request(ctx)
        text = "\n".join(replies)
        assert "The Hobbit" in text
        assert "testuser" in plugin._sessions

    async def test_request_stores_content_type_in_session(self, plugin):
        plugin._api.search.return_value = MOCK_SEARCH_RESULTS
        ctx, replies = make_ctx(args=["The", "Hobbit"])
        await plugin.handle_request(ctx, content_type="audiobook")
        assert plugin._sessions["testuser"]["content_type"] == "audiobook"

    async def test_request_no_results(self, plugin):
        plugin._api.search.return_value = []
        ctx, replies = make_ctx(args=["nonexistent"])
        await plugin.handle_request(ctx)
        assert any("No" in r and "results" in r.lower() for r in replies)

    async def test_request_api_error(self, plugin):
        plugin._api.search.side_effect = ShelfmarkError("connection refused")
        ctx, replies = make_ctx(args=["test"])
        await plugin.handle_request(ctx)
        assert any("unavailable" in r.lower() for r in replies)

    async def test_request_limits_results_to_5(self, plugin):
        plugin._api.search.return_value = [
            {"id": f"id{i}", "title": f"Book {i}", "author": "Author", "year": "2020"}
            for i in range(10)
        ]
        ctx, replies = make_ctx(args=["books"])
        await plugin.handle_request(ctx)
        assert len(plugin._sessions["testuser"]["results"]) == 5


class TestShelfmarkSelect:
    async def test_select_without_session(self, plugin):
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        assert any("search first" in r.lower() for r in replies)

    async def test_select_valid(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "content_type": "ebook",
            "timestamp": 9999999999,
        }
        plugin._api.download.return_value = {"status": "queued"}
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        text = "\n".join(replies)
        assert "queued" in text.lower() or "download" in text.lower()
        plugin._api.download.assert_called_once_with("abc123")
        assert "testuser" not in plugin._sessions

    async def test_select_out_of_range(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "content_type": "ebook",
            "timestamp": 9999999999,
        }
        ctx, replies = make_ctx(args=["99"])
        await plugin.handle_select(ctx)
        assert any("Invalid" in r or "between" in r.lower() for r in replies)

    async def test_select_non_number(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "content_type": "ebook",
            "timestamp": 9999999999,
        }
        ctx, replies = make_ctx(args=["abc"])
        await plugin.handle_select(ctx)
        assert any("number" in r.lower() for r in replies)

    async def test_select_no_args(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "content_type": "ebook",
            "timestamp": 9999999999,
        }
        ctx, replies = make_ctx(args=[])
        await plugin.handle_select(ctx)
        assert any("Usage" in r for r in replies)

    async def test_select_logs_to_database(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "content_type": "ebook",
            "timestamp": 9999999999,
        }
        plugin._api.download.return_value = {"status": "queued"}
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        plugin._db.execute.assert_called_once()
        call_args = plugin._db.execute.call_args
        assert "shelfmark_requests" in call_args[0][0]
        assert call_args[0][1][0] == "testuser"

    async def test_select_download_failure(self, plugin):
        plugin._sessions["testuser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "content_type": "ebook",
            "timestamp": 9999999999,
        }
        plugin._api.download.side_effect = ShelfmarkError("server error")
        ctx, replies = make_ctx(args=["1"])
        await plugin.handle_select(ctx)
        assert any("failed" in r.lower() or "unavailable" in r.lower() for r in replies)


class TestShelfmarkStatus:
    async def test_status_shows_queue(self, plugin):
        plugin._api.get_status.return_value = {
            "active": [{"title": "The Hobbit", "status": "downloading", "progress": 45}],
            "queue": [],
        }
        ctx, replies = make_ctx()
        await plugin.handle_status(ctx)
        text = "\n".join(replies)
        assert "The Hobbit" in text

    async def test_status_empty(self, plugin):
        plugin._api.get_status.return_value = {"active": [], "queue": []}
        ctx, replies = make_ctx()
        await plugin.handle_status(ctx)
        assert any("no" in r.lower() for r in replies)

    async def test_status_api_error(self, plugin):
        plugin._api.get_status.side_effect = ShelfmarkError("timeout")
        ctx, replies = make_ctx()
        await plugin.handle_status(ctx)
        assert any("unavailable" in r.lower() or "error" in r.lower() for r in replies)


class TestShelfmarkSessionExpiry:
    async def test_expired_session_cleaned(self, plugin):
        plugin._sessions["olduser"] = {
            "results": MOCK_SEARCH_RESULTS,
            "content_type": "ebook",
            "timestamp": time.time() - 600,
        }
        ctx, replies = make_ctx(sender="olduser", args=["1"])
        await plugin.handle_select(ctx)
        assert any("search first" in r.lower() for r in replies)


class TestShelfmarkOnUnload:
    async def test_on_unload_closes_api(self, plugin):
        await plugin.on_unload()
        plugin._api.close.assert_called_once()
