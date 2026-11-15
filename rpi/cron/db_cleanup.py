"""Database cleanup script for scheduled execution via cron.

Deletes records older than the configured retention period.

Run via cron, e.g.: 0 3 * * * python -m rpi.cron.db_cleanup
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from rpi.lib.config import SettingsKey, get_settings
from rpi.lib.db import Database
from rpi.lib.exceptions import RpiGardenerError
from rpi.logging import configure, get_logger

logger = get_logger("db_cleanup")


async def cleanup() -> None:
    """Run database cleanup."""
    settings = get_settings()
    cleanup_cfg = settings.cleanup
    db_path = Path(settings.db_path)

    if not db_path.exists():
        logger.info("Database does not exist, skipping cleanup")
        return

    async with Database() as db:
        # The settings UI value wins over the environment default
        override = await db.fetchone(
            "SELECT value FROM settings WHERE key = ?",
            (SettingsKey.RETENTION_DAYS,),
        )
        retention_days = (
            int(override["value"]) if override else cleanup_cfg.retention_days
        )
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        cutoff_epoch = int(cutoff.timestamp())
        logger.info("Starting cleanup (retention: %d days)", retention_days)

        # Databases created before auto_vacuum was set early enough report 0
        # here. One VACUUM rebuilds the file with it enabled.
        mode = await db.fetchone("PRAGMA auto_vacuum")
        if mode is not None and mode["auto_vacuum"] == 0:
            await db.execute("VACUUM")
            logger.info("Enabled incremental auto_vacuum")

        async with db.transaction():
            dht_deleted = await db.execute(
                "DELETE FROM reading WHERE recording_time < ?", (cutoff_epoch,)
            )
            pico_deleted = await db.execute(
                "DELETE FROM pico_reading WHERE recording_time < ?",
                (cutoff_epoch,),
            )

        if dht_deleted > 0 or pico_deleted > 0:
            # Fetch the rows, the pragma frees one page per step and stops
            # after the first if the result is never read
            await db.fetchall("PRAGMA incremental_vacuum(500)")
            logger.info(
                "Cleanup complete: deleted %d DHT records and %d Pico records "
                "(older than %s)",
                dht_deleted,
                pico_deleted,
                cutoff.isoformat(),
            )
        else:
            logger.info("Cleanup complete: no records to delete")


def main() -> int:
    """Entry point for the cleanup script."""
    configure()
    try:
        asyncio.run(cleanup())
        return 0
    except RpiGardenerError, aiosqlite.Error, OSError:
        logger.exception("Cleanup failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
