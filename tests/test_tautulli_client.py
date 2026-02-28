import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.plugins.plex.tautulli_client import TautulliClient, TautulliError


@pytest.fixture
def client():
    return TautulliClient(base_url="http://tautulli:8181", api_key="test-key")


class TestTautulliClient:
    async def test_get_activity(self, client):
        mock_data = {
            "response": {
                "result": "success",
                "data": {
                    "stream_count": "2",
                    "sessions": [
                        {
                            "friendly_name": "jake",
                            "full_title": "The Matrix (1999)",
                            "media_type": "movie",
                            "progress_percent": "45",
                            "quality_profile": "1080p",
                            "transcode_decision": "direct play",
                            "bandwidth": "20000",
                            "state": "playing",
                        },
                    ],
                },
            }
        }
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await client.get_activity()
        assert result["stream_count"] == "2"
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["friendly_name"] == "jake"

    async def test_get_activity_empty(self, client):
        mock_data = {
            "response": {
                "result": "success",
                "data": {"stream_count": "0", "sessions": []},
            }
        }
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await client.get_activity()
        assert result["stream_count"] == "0"
        assert result["sessions"] == []

    async def test_api_error_raises(self, client):
        mock_data = {"response": {"result": "error", "message": "Invalid apikey"}}
        with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_data):
            with pytest.raises(TautulliError, match="Invalid apikey"):
                await client.get_activity()

    async def test_close(self, client):
        client._session = AsyncMock()
        client._session.closed = False
        await client.close()
        client._session.close.assert_called_once()
