import logging
from pathlib import Path

import aiohttp_jinja2
import aiohttp_session
import jinja2
from aiohttp import web
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography.fernet import Fernet

from bot.web.auth import auth_middleware
from bot.web.routes import setup_routes

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def create_web_app(config_path: Path, password_hash: bytes, secret_key: bytes | None = None) -> web.Application:
    """Create and configure the aiohttp web application.

    Args:
        config_path: Path to the bot's YAML config file.
        password_hash: bcrypt hash of the web UI password.
        secret_key: 32-byte Fernet key for cookie encryption. Generated if not provided.
    """
    app = web.Application()

    # Session setup with encrypted cookies (must be registered before auth middleware)
    if secret_key is None:
        secret_key = Fernet.generate_key()
    fernet_key = secret_key[:32] if len(secret_key) > 32 else secret_key
    aiohttp_session.setup(app, EncryptedCookieStorage(fernet_key))

    # Auth middleware runs after session middleware so get_session() works
    app.middlewares.append(auth_middleware)

    # Jinja2 templates
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)))

    # Store shared state on the app
    app["config_path"] = config_path
    app["password_hash"] = password_hash

    # Static files
    app.router.add_static("/static/", path=str(STATIC_DIR), name="static")

    # Route handlers
    setup_routes(app)

    return app


async def run_web_server(app: web.Application, host: str = "0.0.0.0", port: int = 9090) -> web.AppRunner:
    """Start the web server using AppRunner (non-blocking, suitable for asyncio.gather).

    Returns the runner so the caller can clean it up on shutdown.
    """
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"Web UI listening on http://{host}:{port}")
    return runner
