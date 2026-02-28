import logging
from pathlib import Path

import aiohttp_jinja2
from aiohttp import web
from aiohttp_session import get_session

from bot.web.auth import check_password
from bot.web.config_form import load_config_for_form, validate_config, save_config

logger = logging.getLogger(__name__)


def setup_routes(app: web.Application) -> None:
    """Register all route handlers on the app."""
    app.router.add_get("/", handle_config_page)
    app.router.add_get("/login", handle_login_page)
    app.router.add_post("/login", handle_login_submit)
    app.router.add_post("/save", handle_save_config)
    app.router.add_get("/logout", handle_logout)


@aiohttp_jinja2.template("config.html")
async def handle_config_page(request: web.Request) -> dict:
    """Render the main config page with current settings."""
    config_path: Path = request.app["config_path"]
    config = load_config_for_form(config_path)
    return {"config": config, "errors": [], "success": False}


@aiohttp_jinja2.template("login.html")
async def handle_login_page(request: web.Request) -> dict:
    """Render the login page."""
    return {"error": None}


async def handle_login_submit(request: web.Request) -> web.Response:
    """Process login form submission."""
    form = await request.post()
    password = form.get("password", "")
    password_hash: bytes = request.app["password_hash"]

    if check_password(password, password_hash):
        session = await get_session(request)
        session["authenticated"] = True
        raise web.HTTPFound("/")

    context = {"error": "Invalid password."}
    response = aiohttp_jinja2.render_template("login.html", request, context)
    response.set_status(401)
    return response


async def handle_save_config(request: web.Request) -> web.Response:
    """Process config form save."""
    config_path: Path = request.app["config_path"]
    form = await request.post()

    errors = validate_config(form)
    if errors:
        config = load_config_for_form(config_path)
        context = {"config": config, "errors": errors, "success": False}
        return aiohttp_jinja2.render_template("config.html", request, context)

    try:
        save_config(form, config_path)
    except Exception as e:
        logger.error(f"Config save failed: {e}")
        config = load_config_for_form(config_path)
        context = {"config": config, "errors": [f"Save failed: {e}"], "success": False}
        return aiohttp_jinja2.render_template("config.html", request, context)

    config = load_config_for_form(config_path)
    context = {"config": config, "errors": [], "success": True}
    return aiohttp_jinja2.render_template("config.html", request, context)


async def handle_logout(request: web.Request) -> web.Response:
    """Clear session and redirect to login."""
    session = await get_session(request)
    session.invalidate()
    raise web.HTTPFound("/login")
