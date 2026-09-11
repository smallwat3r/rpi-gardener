from sqlite3 import DatabaseError

import aiosqlite
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.db.queries import get_dashboard_data
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
        data = await get_dashboard_data(query.from_time)
    except (DatabaseError, aiosqlite.Error):
        logger.exception("Database error fetching dashboard data")
        return JSONResponse({"error": "Database unavailable"}, status_code=503)

    return JSONResponse({"hours": query.hours, **data})
