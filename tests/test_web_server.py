from pathlib import Path

import aiohttp_jinja2
import jinja2
import pytest
from aiohttp import web
from cryptography.fernet import Fernet

from bot.web.auth import auth_middleware
from bot.web.server import create_web_app, run_web_server


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Provide a temporary config file path."""
    p = tmp_path / "config.yaml"
    p.write_text("server:\n  host: irc.example.com\n")
    return p


@pytest.fixture
def password_hash() -> bytes:
    return b"$2b$12$fakehashvaluefortesting000000000000000000000000000000"


@pytest.fixture
def secret_key() -> bytes:
    return Fernet.generate_key()


class TestCreateWebApp:
    def test_returns_application_instance(self, config_path: Path, password_hash: bytes):
        app = create_web_app(config_path, password_hash)
        assert isinstance(app, web.Application)

    def test_stores_config_path(self, config_path: Path, password_hash: bytes):
        app = create_web_app(config_path, password_hash)
        assert app["config_path"] is config_path

    def test_stores_password_hash(self, config_path: Path, password_hash: bytes):
        app = create_web_app(config_path, password_hash)
        assert app["password_hash"] is password_hash

    def test_auth_middleware_installed(self, config_path: Path, password_hash: bytes):
        app = create_web_app(config_path, password_hash)
        assert auth_middleware in app.middlewares

    def test_static_route_registered(self, config_path: Path, password_hash: bytes):
        app = create_web_app(config_path, password_hash)
        # Check that a resource matching /static/ exists in the router
        static_resources = [
            r for r in app.router.resources() if hasattr(r, "canonical") and r.canonical.startswith("/static")
        ]
        assert len(static_resources) > 0

    def test_explicit_secret_key(self, config_path: Path, password_hash: bytes, secret_key: bytes):
        app = create_web_app(config_path, password_hash, secret_key=secret_key)
        assert isinstance(app, web.Application)

    def test_jinja2_environment_configured(self, config_path: Path, password_hash: bytes):
        app = create_web_app(config_path, password_hash)
        env = aiohttp_jinja2.get_env(app)
        assert env is not None
        assert isinstance(env, jinja2.Environment)


class TestRunWebServer:
    async def test_starts_and_cleans_up(self, config_path: Path, password_hash: bytes):
        app = create_web_app(config_path, password_hash)
        runner = await run_web_server(app, host="127.0.0.1", port=0)
        try:
            assert isinstance(runner, web.AppRunner)
            # Verify the runner has active sites
            assert len(runner.addresses) > 0
        finally:
            await runner.cleanup()
