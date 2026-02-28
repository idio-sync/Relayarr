import time
import pytest
from aioresponses import aioresponses
from bot.plugins.romm.igdb import IGDBClient


TOKEN_RESPONSE = {
    "access_token": "test-access-token",
    "expires_in": 3600,
    "token_type": "bearer",
}

SEARCH_RESPONSE = [
    {
        "id": 1020,
        "name": "The Legend of Zelda: Ocarina of Time",
        "first_release_date": 909014400,
        "genres": [{"name": "Adventure"}, {"name": "Role-playing (RPG)"}],
        "cover": {"url": "//images.igdb.com/igdb/image/upload/t_thumb/co1234.jpg"},
        "summary": "An epic adventure game.",
    }
]


@pytest.fixture
def client():
    return IGDBClient(client_id="test-client-id", client_secret="test-client-secret")


class TestIGDBAuthentication:
    async def test_authenticate_posts_credentials(self, client):
        with aioresponses() as m:
            m.post(
                "https://id.twitch.tv/oauth2/token",
                payload=TOKEN_RESPONSE,
            )
            # Trigger auth by calling search (which requires a token)
            m.post("https://api.igdb.com/v4/games", payload=[])
            await client.search_game("Zelda")

            token_call = list(m.requests.values())[0][0]
            assert token_call.kwargs["data"]["client_id"] == "test-client-id"
            assert token_call.kwargs["data"]["client_secret"] == "test-client-secret"
            assert token_call.kwargs["data"]["grant_type"] == "client_credentials"

        await client.close()

    async def test_token_stored_after_auth(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=[])
            await client.search_game("Zelda")

        assert client._access_token == "test-access-token"
        await client.close()

    async def test_token_reused_on_second_call(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=[])
            m.post("https://api.igdb.com/v4/games", payload=[])
            await client.search_game("Zelda")
            await client.search_game("Mario")

            token_requests = [
                k for k in m.requests.keys()
                if "twitch.tv" in str(k)
            ]
            assert len(token_requests) == 1

        await client.close()

    async def test_token_refreshed_when_expired(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=[])
            await client.search_game("Zelda")

        # Force expiry
        client._token_expires_at = time.time() - 1

        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload={**TOKEN_RESPONSE, "access_token": "new-token"})
            m.post("https://api.igdb.com/v4/games", payload=[])
            await client.search_game("Mario")

        assert client._access_token == "new-token"
        await client.close()


class TestIGDBSearch:
    async def test_search_returns_results(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=SEARCH_RESPONSE)
            results = await client.search_game("Zelda")

        assert len(results) == 1
        assert results[0]["name"] == "The Legend of Zelda: Ocarina of Time"
        await client.close()

    async def test_search_empty_results(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=[])
            results = await client.search_game("xyznonexistentgame")

        assert results == []
        await client.close()

    async def test_search_sends_correct_headers(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=[])
            await client.search_game("Zelda")

            # Find the IGDB games call in requests
            game_calls = [
                call for key, calls in m.requests.items()
                for call in calls
                if "igdb.com" in str(key)
            ]
            assert len(game_calls) >= 1
            call = game_calls[0]
            assert call.kwargs["headers"]["Client-ID"] == "test-client-id"
            assert call.kwargs["headers"]["Authorization"] == "Bearer test-access-token"

        await client.close()

    async def test_search_query_body(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=[])
            await client.search_game("Ocarina", limit=5)

            game_calls = [
                call for key, calls in m.requests.items()
                for call in calls
                if "igdb.com" in str(key)
            ]
            body = game_calls[0].kwargs["data"]
            assert 'search "Ocarina"' in body
            assert "limit 5" in body
            assert "fields name,first_release_date,genres.name,cover.url,summary" in body

        await client.close()

    async def test_search_with_platform_filter(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=SEARCH_RESPONSE)
            results = await client.search_game("Zelda", platform_slug="n64")

            game_calls = [
                call for key, calls in m.requests.items()
                for call in calls
                if "igdb.com" in str(key)
            ]
            body = game_calls[0].kwargs["data"]
            assert "where platforms = (4)" in body

        assert len(results) == 1
        await client.close()

    async def test_search_with_unknown_platform_omits_filter(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=[])
            await client.search_game("Zelda", platform_slug="unknown-platform")

            game_calls = [
                call for key, calls in m.requests.items()
                for call in calls
                if "igdb.com" in str(key)
            ]
            body = game_calls[0].kwargs["data"]
            assert "where platforms" not in body

        await client.close()

    async def test_search_error_returns_empty_list(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", status=500)
            results = await client.search_game("Zelda")

        assert results == []
        await client.close()

    async def test_auth_error_returns_empty_list(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", status=401)
            results = await client.search_game("Zelda")

        assert results == []
        await client.close()


class TestIGDBClose:
    async def test_close_closes_session(self, client):
        with aioresponses() as m:
            m.post("https://id.twitch.tv/oauth2/token", payload=TOKEN_RESPONSE)
            m.post("https://api.igdb.com/v4/games", payload=[])
            await client.search_game("Zelda")

        await client.close()
        assert client._session is None or client._session.closed

    async def test_close_without_session_is_safe(self, client):
        # Should not raise even if no session was created
        await client.close()
