import pytest
from pathlib import Path
from aiohttp.test_utils import TestClient, TestServer
import yaml

from bot.web.server import create_web_app
from bot.web.auth import hash_password


@pytest.fixture
def config_path(tmp_path):
    """Create a temporary config file."""
    config = {
        "irc": {
            "server": "irc.test.com",
            "port": 6697,
            "ssl": True,
            "nickname": "TestBot",
            "channels": ["#test"],
            "command_prefix": "!",
        },
        "auth": {"admins": [], "users": [], "default_role": "user"},
        "overseerr": {"url": "http://localhost:5055", "api_key": "test-key-123"},
        "plugins": {"enabled": ["overseerr"]},
        "database": {"path": "/data/bot.db"},
        "session": {"timeout_seconds": 300},
        "formatting": {"irc_colors": True},
        "web": {"port": 9090},
    }
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)
    return path


@pytest.fixture
def password_hash():
    return hash_password("testpass123")


@pytest.fixture
async def client(config_path, password_hash):
    app = create_web_app(config_path, password_hash)
    async with TestClient(TestServer(app)) as client:
        yield client


async def _login(client):
    """Helper to authenticate a test client session."""
    await client.post("/login", data={"password": "testpass123"})


class TestLoginPage:
    async def test_get_login_returns_200(self, client):
        """GET /login returns 200 and contains 'Login' in body."""
        resp = await client.get("/login")
        assert resp.status == 200
        text = await resp.text()
        assert "Login" in text

    async def test_post_login_wrong_password_returns_401(self, client):
        """POST /login with wrong password returns 401."""
        resp = await client.post("/login", data={"password": "wrongpass"})
        assert resp.status == 401

    async def test_post_login_correct_password_redirects(self, client):
        """POST /login with correct password redirects to / (302)."""
        resp = await client.post(
            "/login", data={"password": "testpass123"}, allow_redirects=False
        )
        assert resp.status == 302
        assert resp.headers["Location"] == "/"


class TestConfigPage:
    async def test_get_root_without_auth_redirects_to_login(self, client):
        """GET / without auth redirects to /login (302)."""
        resp = await client.get("/", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/login"

    async def test_get_root_with_auth_returns_200(self, client):
        """GET / with auth returns 200 and contains 'IRC' tab."""
        await _login(client)
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "IRC" in text


class TestSaveConfig:
    async def test_post_save_valid_config(self, client):
        """POST /save with valid config returns 200 and contains 'saved'."""
        await _login(client)
        resp = await client.post(
            "/save",
            data={
                "irc.server": "irc.test.com",
                "irc.port": "6697",
                "irc.ssl": "on",
                "irc.nickname": "TestBot",
                "irc.channels": "#test",
                "irc.command_prefix": "!",
                "auth.default_role": "user",
                "overseerr.url": "http://localhost:5055",
                "overseerr.api_key": "test-key-123",
                "plugins.enabled": "overseerr",
                "database.path": "/data/bot.db",
                "session.timeout_seconds": "300",
                "formatting.irc_colors": "on",
                "web.port": "9090",
            },
        )
        assert resp.status == 200
        text = await resp.text()
        assert "saved" in text.lower() or "Configuration saved" in text

    async def test_post_save_invalid_config_shows_errors(self, client):
        """POST /save with invalid config returns 200 and contains error message."""
        await _login(client)
        resp = await client.post(
            "/save",
            data={
                "irc.server": "",
                "irc.port": "6697",
                "irc.nickname": "",
                "irc.channels": "",
                "irc.command_prefix": "!",
                "auth.default_role": "user",
                "database.path": "/data/bot.db",
                "session.timeout_seconds": "300",
                "web.port": "9090",
            },
        )
        assert resp.status == 200
        text = await resp.text()
        assert "required" in text.lower() or "error" in text.lower()


class TestLogout:
    async def test_logout_redirects_to_login(self, client):
        """GET /logout redirects to /login (302)."""
        await _login(client)
        resp = await client.get("/logout", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/login"
