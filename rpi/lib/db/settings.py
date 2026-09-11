"""Runtime settings stored in the database."""

from __future__ import annotations

from rpi.lib.config import SettingsKey
from rpi.lib.db.connection import get_db


async def get_all_settings() -> dict[SettingsKey, str]:
    """Get all settings as a dictionary."""
    async with get_db() as db:
        rows = await db.fetchall("SELECT key, value FROM settings")
    return {row["key"]: row["value"] for row in rows}


async def set_settings_batch(
    settings: dict[SettingsKey, str],
) -> dict[SettingsKey, str]:
    """Set multiple settings in one transaction, return the full settings."""
    async with get_db() as db, db.transaction():
        await db.executemany(
            """INSERT INTO settings (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = excluded.updated_at""",
            list(settings.items()),
        )
        rows = await db.fetchall("SELECT key, value FROM settings")
    return {row["key"]: row["value"] for row in rows}
