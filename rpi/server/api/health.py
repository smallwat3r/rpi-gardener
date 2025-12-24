"""Health check endpoint for monitoring service status."""
from datetime import UTC, datetime

from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.db import get_db, get_latest_dht_data, get_latest_pico_data
from rpi.logging import get_logger

logger = get_logger("server.api.health")


async def _check_database() -> tuple[bool, str]:
    """Check if database is accessible."""
    try:
        async with get_db() as db:
            await db.fetchone("SELECT 1")
        return True, "ok"
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False, str(e)


async def _check_dht_sensor() -> tuple[bool, str | None]:
    """Check if DHT sensor has recent data (within last 5 minutes)."""
    try:
        latest = await get_latest_dht_data()
        if latest is None:
            return False, "no data"
        return True, latest.get("recording_time")
    except Exception as e:
        logger.error("DHT sensor health check failed: %s", e)
        return False, str(e)


async def _check_pico_sensor() -> tuple[bool, str | None]:
    """Check if Pico sensor has recent data."""
    try:
        latest = await get_latest_pico_data()
        if not latest:
            return False, "no data"
        return True, latest[0].get("recording_time") if latest else None
    except Exception as e:
        logger.error("Pico sensor health check failed: %s", e)
        return False, str(e)


async def health_check(request: Request) -> JSONResponse:
    """Return health status of the application and its dependencies."""
    db_ok, db_status = await _check_database()
    dht_ok, dht_last = await _check_dht_sensor()
    pico_ok, pico_last = await _check_pico_sensor()

    status = {
        "status": "healthy" if db_ok else "unhealthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {
            "database": {"ok": db_ok, "status": db_status},
            "dht_sensor": {"ok": dht_ok, "last_reading": dht_last},
            "pico_sensor": {"ok": pico_ok, "last_reading": pico_last},
        },
    }

    return JSONResponse(status, status_code=200 if db_ok else 503)
