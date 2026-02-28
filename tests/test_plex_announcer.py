import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.plugins.plex.announcer import RecentlyAddedAnnouncer
from bot.plugins.plex.plex_client import PlexClient, PlexError
from bot.plugins.plex.formatters import PlexFormatter


@pytest.fixture
def mock_plex_api():
    api = AsyncMock(spec=PlexClient)
    api.get_recently_added = AsyncMock(return_value=[])
    return api


@pytest.fixture
def mock_send():
    return AsyncMock()


@pytest.fixture
def formatter():
    return PlexFormatter(irc_colors=False)


@pytest.fixture
def announcer(mock_plex_api, mock_send, formatter):
    return RecentlyAddedAnnouncer(
        plex_api=mock_plex_api,
        formatter=formatter,
        send_callback=mock_send,
        channel="#media",
        interval=10,
    )


class TestRecentlyAddedAnnouncer:
    async def test_first_poll_does_not_announce(self, announcer, mock_plex_api, mock_send):
        mock_plex_api.get_recently_added.return_value = [
            {"title": "Old Movie", "addedAt": 1000, "type": "movie", "librarySectionTitle": "Movies"}
        ]
        await announcer._poll()
        mock_send.assert_not_called()
        assert announcer._last_seen_timestamp == 1000

    async def test_second_poll_announces_new_items(self, announcer, mock_plex_api, mock_send):
        # First poll — sets baseline
        mock_plex_api.get_recently_added.return_value = [
            {"title": "Old Movie", "addedAt": 1000, "type": "movie", "librarySectionTitle": "Movies"}
        ]
        await announcer._poll()

        # Second poll — new item
        mock_plex_api.get_recently_added.return_value = [
            {"title": "New Movie", "addedAt": 2000, "type": "movie", "year": 2026, "librarySectionTitle": "Movies"},
            {"title": "Old Movie", "addedAt": 1000, "type": "movie", "librarySectionTitle": "Movies"},
        ]
        await announcer._poll()
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == "#media"
        assert "New Movie" in call_args[0][1]

    async def test_no_new_items_no_announce(self, announcer, mock_plex_api, mock_send):
        mock_plex_api.get_recently_added.return_value = [
            {"title": "Old Movie", "addedAt": 1000, "type": "movie", "librarySectionTitle": "Movies"}
        ]
        await announcer._poll()
        await announcer._poll()
        mock_send.assert_not_called()

    async def test_api_error_does_not_crash(self, announcer, mock_plex_api, mock_send):
        mock_plex_api.get_recently_added.side_effect = PlexError("connection refused")
        await announcer._poll()  # Should not raise
        mock_send.assert_not_called()
        assert announcer._consecutive_errors == 1

    async def test_error_count_resets_on_success(self, announcer, mock_plex_api, mock_send):
        mock_plex_api.get_recently_added.side_effect = PlexError("error")
        await announcer._poll()
        assert announcer._consecutive_errors == 1

        mock_plex_api.get_recently_added.side_effect = None
        mock_plex_api.get_recently_added.return_value = [
            {"title": "Movie", "addedAt": 1000, "type": "movie", "librarySectionTitle": "Movies"}
        ]
        await announcer._poll()
        assert announcer._consecutive_errors == 0

    async def test_start_and_stop(self, announcer):
        announcer.start()
        assert announcer._task is not None
        assert not announcer._task.done()
        await announcer.stop()
        assert announcer._task.done()
