import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientResponseError

from bot.plugins.plex.plex_client import PlexClient, PlexError


@pytest.fixture
def client():
    return PlexClient(base_url="http://plex:32400", token="test-token")


class TestPlexClient:
    async def test_get_libraries(self, client):
        mock_data = {
            "MediaContainer": {
                "Directory": [
                    {"key": "1", "title": "Movies", "type": "movie"},
                    {"key": "2", "title": "TV Shows", "type": "show"},
                ]
            }
        }
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await client.get_libraries()
        assert len(result) == 2
        assert result[0]["title"] == "Movies"

    async def test_get_library_details(self, client):
        mock_data = {
            "MediaContainer": {
                "totalSize": 1234,
            }
        }
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await client.get_library_details("1")
        assert result["totalSize"] == 1234

    async def test_get_recently_added(self, client):
        mock_data = {
            "MediaContainer": {
                "Metadata": [
                    {"title": "The Matrix", "type": "movie", "addedAt": 1700000000},
                ]
            }
        }
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await client.get_recently_added(count=5)
        assert len(result) == 1
        assert result[0]["title"] == "The Matrix"

    async def test_get_sessions(self, client):
        mock_data = {
            "MediaContainer": {
                "Metadata": [
                    {"title": "Breaking Bad", "User": {"title": "jake"}},
                ]
            }
        }
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await client.get_sessions()
        assert len(result) == 1
        assert result[0]["User"]["title"] == "jake"

    async def test_get_sessions_empty(self, client):
        mock_data = {"MediaContainer": {}}
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await client.get_sessions()
        assert result == []

    async def test_get_recently_added_since(self, client):
        mock_data = {
            "MediaContainer": {
                "Metadata": [
                    {"title": "Old Movie", "addedAt": 1000},
                    {"title": "New Movie", "addedAt": 2000},
                ]
            }
        }
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await client.get_recently_added(count=10, since_timestamp=1500)
        assert len(result) == 1
        assert result[0]["title"] == "New Movie"

    async def test_get_error_raises_plex_error(self, client):
        with patch.object(client, "_get_session", new_callable=AsyncMock) as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 401
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=False)
            session = MagicMock()
            session.get.return_value = mock_resp
            mock_session.return_value = session
            with pytest.raises(PlexError, match="401"):
                await client.get_libraries()

    async def test_token_passed_as_query_param(self, client):
        with patch.object(client, "_get_session", new_callable=AsyncMock) as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"MediaContainer": {"Directory": []}})
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=False)
            session = MagicMock()
            session.get.return_value = mock_resp
            mock_session.return_value = session
            await client.get_libraries()
            call_kwargs = session.get.call_args
            assert "X-Plex-Token" in call_kwargs.kwargs.get("params", {})

    async def test_close(self, client):
        client._session = AsyncMock()
        client._session.closed = False
        await client.close()
        client._session.close.assert_called_once()
