import pytest
from aioresponses import aioresponses
from bot.plugins.overseerr.api import OverseerrClient


@pytest.fixture
def api():
    return OverseerrClient(base_url="http://overseerr:5055", api_key="test-key")


SEARCH_RESPONSE = {
    "results": [
        {
            "id": 157336, "title": "Interstellar", "releaseDate": "2014-11-05",
            "overview": "A team of explorers travel through a wormhole in space.",
            "voteAverage": 8.6, "mediaType": "movie", "posterPath": "/poster.jpg",
            "mediaInfo": {"status": 5},
        },
        {
            "id": 399404, "title": "Interstellar Wars", "releaseDate": "2016-06-02",
            "overview": "Aliens attack Earth.",
            "voteAverage": 2.1, "mediaType": "movie", "posterPath": None,
            "mediaInfo": None,
        },
    ]
}

REQUEST_RESPONSE = {"id": 42, "status": 2, "media": {"tmdbId": 399404, "status": 2}}

STATUS_RESPONSE = {
    "pageInfo": {"pages": 1, "page": 1, "results": 1},
    "results": [
        {
            "id": 42, "status": 2,
            "media": {"tmdbId": 399404, "mediaType": "movie"},
            "requestedBy": {"displayName": "testuser"},
            "createdAt": "2026-02-28T12:00:00.000Z",
        }
    ],
}


class TestOverseerrSearch:
    async def test_search_returns_results(self, api):
        with aioresponses() as m:
            m.get("http://overseerr:5055/api/v1/search?query=Interstellar&page=1&language=en", payload=SEARCH_RESPONSE)
            results = await api.search("Interstellar")
            assert len(results) == 2
            assert results[0]["title"] == "Interstellar"

    async def test_search_sends_api_key_header(self, api):
        with aioresponses() as m:
            m.get("http://overseerr:5055/api/v1/search?query=test&page=1&language=en", payload={"results": []})
            await api.search("test")
            call = list(m.requests.values())[0][0]
            assert call.kwargs["headers"]["X-Api-Key"] == "test-key"

    async def test_search_empty_results(self, api):
        with aioresponses() as m:
            m.get("http://overseerr:5055/api/v1/search?query=zzzznonexistent&page=1&language=en", payload={"results": []})
            results = await api.search("zzzznonexistent")
            assert results == []


class TestOverseerrRequest:
    async def test_request_movie(self, api):
        with aioresponses() as m:
            m.post("http://overseerr:5055/api/v1/request", payload=REQUEST_RESPONSE)
            result = await api.request_media(media_id=399404, media_type="movie")
            assert result["id"] == 42


class TestOverseerrStatus:
    async def test_get_requests(self, api):
        with aioresponses() as m:
            m.get("http://overseerr:5055/api/v1/request?take=20&skip=0&sort=added", payload=STATUS_RESPONSE)
            results = await api.get_requests()
            assert len(results) == 1
            assert results[0]["id"] == 42


class TestOverseerrErrorHandling:
    async def test_api_error_raises(self, api):
        with aioresponses() as m:
            m.get("http://overseerr:5055/api/v1/search?query=test&page=1&language=en", status=500)
            with pytest.raises(Exception, match="API error"):
                await api.search("test")
