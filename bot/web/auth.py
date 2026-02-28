import bcrypt
from aiohttp import web
from aiohttp_session import get_session

PUBLIC_PATHS = {"/login"}


def hash_password(plain: str) -> bytes:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())


def check_password(plain: str, hashed: bytes) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed)


@web.middleware
async def auth_middleware(request: web.Request, handler):
    """Redirect unauthenticated requests to /login. Allow public paths and static assets."""
    path = request.path

    if path == "/login" or path.startswith("/static/"):
        return await handler(request)

    session = await get_session(request)
    if not session.get("authenticated"):
        raise web.HTTPFound("/login")

    return await handler(request)
