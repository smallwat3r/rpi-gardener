from sqlite3 import DatabaseError

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.db import (
    get_initial_dht_data,
    get_initial_pico_data,
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)
from rpi.logging import get_logger
from rpi.server.validators import HoursQuery

logger = get_logger("server.api.dashboard")


async def get_dashboard(request: Request) -> JSONResponse:
    """Return dashboard data as JSON for SPA consumption."""
    try:
        query = HoursQuery.from_params(dict(request.query_params))
    except (ValueError, ValidationError) as err:
        return JSONResponse({"error": str(err)}, status_code=400)

    try:
        return JSONResponse(
            {
                "hours": query.hours,
                "data": await get_initial_dht_data(query.from_time),
                "stats": await get_stats_dht_data(query.from_time),
                "latest": await get_latest_dht_data(),
                "pico_data": await get_initial_pico_data(query.from_time),
                "pico_latest": await get_latest_pico_data(),
            }
        )
    except DatabaseError:
        logger.exception("Database error fetching dashboard data")
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
