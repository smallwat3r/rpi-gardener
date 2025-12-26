"""Basic authentication utilities for the admin interface."""

import base64
import hashlib
import secrets
from collections.abc import Awaitable, Callable
from contextlib import suppress
from functools import wraps

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Realm shown in browser's auth dialog
AUTH_REALM = "rpi-gardener admin"
AUTH_USERNAME = "admin"


def hash_password(password: str) -> str:
    """Hash a password using scrypt.

    Returns a string in the format: salt$hash
    """
    salt = secrets.token_hex(16)
    key = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=32
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        salt, key_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    key = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=32
    )
    return secrets.compare_digest(key.hex(), key_hex)


def _parse_basic_auth(request: Request) -> str | None:
    """Extract password from Basic auth header if username matches.

    Returns the password if valid, None otherwise.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return None
    with suppress(ValueError, UnicodeDecodeError):
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        if ":" in decoded:
            username, password = decoded.split(":", 1)
            if username == AUTH_USERNAME:
                return password
    return None


def _unauthorized_response() -> Response:
    """Return 401 response that triggers browser's auth dialog."""
    return Response(
        content="Unauthorized",
        status_code=401,
        headers={"WWW-Authenticate": f'Basic realm="{AUTH_REALM}"'},
    )


def require_auth[R: Response](
    handler: Callable[[Request], Awaitable[R]],
) -> Callable[[Request], Awaitable[Response]]:
    """Decorator to require basic authentication for an endpoint."""

    @wraps(handler)
    async def wrapper(request: Request) -> Response:
        from rpi.lib.db import get_admin_password_hash

        stored_hash = await get_admin_password_hash()
        if stored_hash is None:
            return JSONResponse(
                {"error": "Admin not configured"}, status_code=503
            )

        password = _parse_basic_auth(request)
        if password is None or not verify_password(password, stored_hash):
            return _unauthorized_response()

        return await handler(request)

    return wrapper
