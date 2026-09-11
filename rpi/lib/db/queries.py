"""Database query functions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from rpi.lib.db.connection import get_db, load_template
from rpi.lib.db.types import DHTReading, PicoReading


def _calculate_bucket_size(
    from_time: datetime, target_points: int = 500
) -> int:
    """Calculate time bucket size in seconds to achieve target data points.

    Returns bucket size that will aggregate readings into ~target_points.
    Minimum bucket is 1 second (no aggregation for short ranges).
    """
    total_seconds = int((datetime.now(UTC) - from_time).total_seconds())
    return max(1, total_seconds // target_points)


async def get_latest_dht_data() -> DHTReading | None:
    """Return the latest DHT22 sensor data."""
    async with get_db() as db:
        row = await db.fetchone(load_template("dht_latest_recording.sql"))
        return cast(DHTReading | None, row)


async def get_latest_pico_data() -> list[PicoReading]:
    """Return the latest Pico sensor data for each plant."""
    async with get_db() as db:
        rows = await db.fetchall(load_template("pico_latest_recording.sql"))
        return cast(list[PicoReading], rows)


async def get_dashboard_data(from_time: datetime) -> dict[str, Any]:
    """Return bucketed chart data and latest readings since from_time.

    Stats (avg/min/max) are computed client side from the chart data so
    they stay live with SSE updates, no separate stats query.
    """
    bucket = _calculate_bucket_size(from_time)
    params = {"from_epoch": int(from_time.timestamp()), "bucket": bucket}
    async with get_db() as db:
        dht_data = await db.fetchall(load_template("dht_chart.sql"), params)
        latest = await db.fetchone(load_template("dht_latest_recording.sql"))
        pico_rows = await db.fetchall(load_template("pico_chart.sql"), params)
        pico_latest = await db.fetchall(
            load_template("pico_latest_recording.sql")
        )
    return {
        "bucket_sec": bucket,
        "data": dht_data,
        "latest": latest,
        # plants column is a JSON object {plant_id: moisture} built in SQL
        "pico_data": [
            {"epoch": r["epoch"], **json.loads(r["plants"])} for r in pico_rows
        ],
        "pico_latest": pico_latest,
    }
