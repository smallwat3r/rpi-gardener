"""Database cleanup script for scheduled execution via cron.

Deletes records older than the configured retention period.

Run via cron, e.g.: 0 3 * * * python -m rpi.db_cleanup
"""
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rpi.lib.config import get_settings
from rpi.lib.db import Database
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

    cutoff = datetime.now(UTC) - timedelta(days=cleanup_cfg.retention_days)
    logger.info("Starting cleanup (retention: %d days)", cleanup_cfg.retention_days)

    async with Database() as db:
        await db.execute("DELETE FROM reading WHERE recording_time < ?", (cutoff,))
        await db.execute("DELETE FROM pico_reading WHERE recording_time < ?", (cutoff,))
        await db.execute("PRAGMA incremental_vacuum(500)")

    logger.info("Cleanup complete, deleted records older than %s", cutoff.isoformat())


def main() -> int:
    """Entry point for the cleanup script."""
    configure()
    try:
        asyncio.run(cleanup())
        return 0
    except Exception as e:
        logger.error("Cleanup failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
