"""Database query functions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from rpi.lib.db.connection import get_db
from rpi.lib.db.types import DHTReading, PicoReading

# SQL templates directory
_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def _load_template(name: str) -> str:
    """Load a SQL template file."""
    return (_SQL_DIR / name).read_text()


# Pre-load SQL templates for queries
_DHT_CHART_SQL = _load_template("dht_chart.sql")
_DHT_LATEST_SQL = _load_template("dht_latest_recording.sql")
_DHT_STATS_SQL = _load_template("dht_stats.sql")
_PICO_CHART_SQL = _load_template("pico_chart.sql")
_PICO_LATEST_SQL = _load_template("pico_latest_recording.sql")


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
        row = await db.fetchone(_DHT_LATEST_SQL)
        return cast(DHTReading | None, row)


async def get_latest_pico_data() -> list[PicoReading]:
    """Return the latest Pico sensor data for each plant."""
    async with get_db() as db:
        rows = await db.fetchall(_PICO_LATEST_SQL)
        return cast(list[PicoReading], rows)
