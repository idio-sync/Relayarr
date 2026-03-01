import pytest
from aioresponses import aioresponses

from bot.plugins.shelfmark.api import ShelfmarkClient, ShelfmarkError


@pytest.fixture
def api():
    return ShelfmarkClient(
        base_url="http://shelfmark:8080",
        username="botuser",
        password="secret",
    )


LOGIN_URL = "http://shelfmark:8080/api/auth/login"
LOGIN_SUCCESS = {"success": True}
LOGIN_FAIL = {"error": "Invalid credentials"}

SEARCH_RESULTS = [
    {
        "id": "abc123",
        "title": "The Hobbit",
        "author": "J.R.R. Tolkien",
        "year": "1937",
        "format": "epub",
        "size": "2.1 MB",
        "content_type": "ebook",
    },
    {
        "id": "def456",
        "title": "The Lord of the Rings",
        "author": "J.R.R. Tolkien",
        "year": "1954",
        "format": "epub",
        "size": "5.3 MB",
        "content_type": "ebook",
    },
]

DOWNLOAD_RESPONSE = {"status": "queued", "priority": 0}

STATUS_RESPONSE = {
    "active": [{"title": "The Hobbit", "status": "downloading", "progress": 45}],
    "queue": [{"title": "The Lord of the Rings", "status": "queued"}],
}

INFO_RESPONSE = {
    "id": "abc123",
    "title": "The Hobbit",
    "author": "J.R.R. Tolkien",
    "year": "1937",
    "description": "A children's fantasy novel.",
    "format": "epub",
}


class TestShelfmarkAuth:
    async def test_login_sends_credentials(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/search?content=ebook&query=test",
                payload=[],
            )
            await api.search("test")
            calls = list(m.requests.values())
            login_call = calls[0][0]
            body = login_call.kwargs["json"]
            assert body["username"] == "botuser"
            assert body["password"] == "secret"

    async def test_login_failure_raises(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, status=401, payload=LOGIN_FAIL)
            with pytest.raises(ShelfmarkError, match="Auth failed"):
                await api.search("test")

    async def test_reuses_session_after_login(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/search?content=ebook&query=test1",
                payload=[],
            )
            m.get(
                "http://shelfmark:8080/api/search?content=ebook&query=test2",
                payload=[],
            )
            await api.search("test1")
            await api.search("test2")
            post_calls = [k for k in m.requests if k[0] == "POST"]
            assert len(post_calls) == 1

    async def test_retries_login_on_401(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/search?content=ebook&query=test",
                status=401,
            )
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/search?content=ebook&query=test",
                payload=[{"title": "Test"}],
            )
            results = await api.search("test")
            assert len(results) == 1


class TestShelfmarkErrorHandling:
    async def test_server_error_raises(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/search?content=ebook&query=test",
                status=500,
            )
            with pytest.raises(ShelfmarkError, match="API error"):
                await api.search("test")


class TestShelfmarkSearch:
    async def test_search_returns_results(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/search?content=ebook&query=tolkien",
                payload=SEARCH_RESULTS,
            )
            results = await api.search("tolkien")
            assert len(results) == 2
            assert results[0]["title"] == "The Hobbit"

    async def test_search_with_content_type(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/search?content=audiobook&query=tolkien",
                payload=SEARCH_RESULTS,
            )
            await api.search("tolkien", content_type="audiobook")
            get_calls = [k for k in m.requests if k[0] == "GET"]
            call_url = str(get_calls[0][1])
            assert "content=audiobook" in call_url

    async def test_search_empty_results(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/search?content=ebook&query=nonexistent",
                payload=[],
            )
            results = await api.search("nonexistent")
            assert results == []


class TestShelfmarkDownload:
    async def test_download_queues_book(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/download?id=abc123",
                payload=DOWNLOAD_RESPONSE,
            )
            result = await api.download("abc123")
            assert result["status"] == "queued"

    async def test_download_sends_book_id(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/download?id=abc123",
                payload=DOWNLOAD_RESPONSE,
            )
            await api.download("abc123")
            get_calls = [k for k in m.requests if k[0] == "GET"]
            call_url = str(get_calls[0][1])
            assert "id=abc123" in call_url


class TestShelfmarkStatus:
    async def test_get_status(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get("http://shelfmark:8080/api/status", payload=STATUS_RESPONSE)
            result = await api.get_status()
            assert "active" in result
            assert len(result["active"]) == 1


class TestShelfmarkInfo:
    async def test_get_info(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/info?id=abc123",
                payload=INFO_RESPONSE,
            )
            result = await api.get_info("abc123")
            assert result["title"] == "The Hobbit"

    async def test_get_info_not_found(self, api):
        with aioresponses() as m:
            m.post(LOGIN_URL, payload=LOGIN_SUCCESS)
            m.get(
                "http://shelfmark:8080/api/info?id=nonexistent",
                status=404,
                payload={"error": "Book not found"},
            )
            with pytest.raises(ShelfmarkError, match="API error"):
                await api.get_info("nonexistent")
