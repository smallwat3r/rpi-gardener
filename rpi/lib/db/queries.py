"""Database query functions."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import cast

from rpi.lib.db.connection import get_db
from rpi.lib.db.types import DHTReading, PicoReading

# SQL templates directory
_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


@cache
def _load_template(name: str) -> str:
    """Load and cache a SQL template file.

    Templates are lazy-loaded on first access and cached for subsequent calls.

    Raises:
        FileNotFoundError: If the template file does not exist, with a message
            indicating the expected location.
    """
    path = _SQL_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"SQL template not found: {path}")
    return path.read_text()


def _calculate_bucket_size(
    from_time: datetime, target_points: int = 500
) -> int:
    """Calculate time bucket size in seconds to achieve target data points.

    Returns bucket size that will aggregate readings into ~target_points.
    Minimum bucket is 1 second (no aggregation for short ranges).
    """
    total_seconds = int((datetime.now(UTC) - from_time).total_seconds())
    bucket = max(1, total_seconds // target_points)
    return bucket


async def get_latest_dht_data() -> DHTReading | None:
    """Return the latest DHT22 sensor data."""
    async with get_db() as db:
        row = await db.fetchone(_load_template("dht_latest_recording.sql"))
        return cast(DHTReading | None, row)


async def get_latest_pico_data() -> list[PicoReading]:
    """Return the latest Pico sensor data for each plant."""
    async with get_db() as db:
        rows = await db.fetchall(_load_template("pico_latest_recording.sql"))
        return cast(list[PicoReading], rows)
