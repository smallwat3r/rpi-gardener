import logging
from sqlite3 import DatabaseError

from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.db import (
    get_initial_dht_data,
    get_initial_pico_data,
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)
from rpi.server.params import InvalidParameter, parse_hours

logger = logging.getLogger(__name__)


async def get_dashboard(request: Request) -> JSONResponse:
    """Return dashboard data as JSON for SPA consumption."""
    try:
        hours, from_time = parse_hours(request.query_params)
    except InvalidParameter as err:
        return JSONResponse({"error": str(err)}, status_code=400)

    try:
        return JSONResponse({
            "hours": hours,
            "data": get_initial_dht_data(from_time),
            "stats": get_stats_dht_data(from_time),
            "latest": get_latest_dht_data(),
            "pico_data": get_initial_pico_data(from_time),
            "pico_latest": get_latest_pico_data(),
        })
    except DatabaseError:
        logger.exception("Database error fetching dashboard data")
        return JSONResponse({"error": "Database unavailable"}, status_code=503)
