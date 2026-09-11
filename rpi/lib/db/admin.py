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


async def init_admin_password() -> None:
    """Sync the stored admin password with the ADMIN_PASSWORD env var.

    Unset or empty removes the stored hash, so the settings UI is open.
    Set replaces it, so changing the password in .env takes effect on the
    next start.
    """
    from os import environ

    from rpi.server.auth import hash_password, verify_password

    admin_password = environ.get("ADMIN_PASSWORD", "")
    existing = await get_admin_password_hash()

    if not admin_password:
        if existing is not None:
            async with get_db() as db:
                await db.execute("DELETE FROM admin WHERE id = 1")
        _logger.info(
            "ADMIN_PASSWORD not set, settings UI is open without auth"
        )
        return

    if existing is not None and verify_password(admin_password, existing):
        return

    await set_admin_password_hash(hash_password(admin_password))
    _logger.info("Admin password set from environment")
