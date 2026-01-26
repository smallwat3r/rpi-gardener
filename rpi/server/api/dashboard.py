import json
from sqlite3 import DatabaseError
from typing import Any

import aiosqlite
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.db import get_db
from rpi.lib.db.queries import _calculate_bucket_size, _load_template
from rpi.logging import get_logger
from rpi.server.validators import HoursQuery

logger = get_logger("server.api.dashboard")


def _pivot_pico_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten pico rows with pre-pivoted plant data from SQL."""
    return [{"epoch": r["epoch"], **json.loads(r["plants"])} for r in rows]


async def get_dashboard(request: Request) -> JSONResponse:
    """Return dashboard data as JSON for SPA consumption."""
    try:
        query = HoursQuery.from_params(dict(request.query_params))
    except (ValueError, ValidationError) as err:
        return JSONResponse({"error": str(err)}, status_code=400)

    bucket = _calculate_bucket_size(query.from_time)
    from_epoch = int(query.from_time.timestamp())
    params = {"from_epoch": from_epoch, "bucket": bucket}

    try:
        async with get_db() as db:
            dht_data = await db.fetchall(
                _load_template("dht_chart.sql"), params
            )
            stats = await db.fetchone(
                _load_template("dht_stats.sql"), {"from_epoch": from_epoch}
            )
            latest = await db.fetchone(
                _load_template("dht_latest_recording.sql")
            )
            pico_rows = await db.fetchall(
                _load_template("pico_chart.sql"), params
            )
            pico_latest = await db.fetchall(
                _load_template("pico_latest_recording.sql")
            )
    except (DatabaseError, aiosqlite.Error):
        logger.exception("Database error fetching dashboard data")
        return JSONResponse({"error": "Database unavailable"}, status_code=503)

    return JSONResponse(
        {
            "hours": query.hours,
            "data": dht_data,
            "stats": stats,
            "latest": latest,
            "pico_data": _pivot_pico_data(pico_rows),
            "pico_latest": pico_latest,
        }
    )
