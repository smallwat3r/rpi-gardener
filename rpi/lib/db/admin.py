"""Admin password database operations."""

from __future__ import annotations

from rpi.lib.db.connection import get_db
from rpi.logging import get_logger

_logger = get_logger("lib.db.admin")


async def get_admin_password_hash() -> str | None:
    """Get the admin password hash."""
    async with get_db() as db:
        row = await db.fetchone("SELECT password_hash FROM admin WHERE id = 1")
        return row["password_hash"] if row else None


async def set_admin_password_hash(password_hash: str) -> None:
    """Set or update the admin password hash."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO admin (id, password_hash, updated_at)
               VALUES (1, ?, datetime('now'))
               ON CONFLICT(id) DO UPDATE SET
                   password_hash = excluded.password_hash,
                   updated_at = excluded.updated_at""",
            (password_hash,),
        )


async def _init_admin_password() -> None:
    """Initialize admin password from ADMIN_PASSWORD env var if not already set."""
    from os import environ

    from rpi.server.auth import hash_password

    existing = await get_admin_password_hash()
    if existing is not None:
        return

    admin_password = environ.get("ADMIN_PASSWORD", "")
    if not admin_password:
        _logger.warning(
            "No admin password configured. Set ADMIN_PASSWORD in .env to enable "
            "admin UI."
        )
        return

    password_hash = hash_password(admin_password)
    await set_admin_password_hash(password_hash)
    _logger.info("Admin password initialized from environment")
