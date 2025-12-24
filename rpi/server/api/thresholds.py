"""Thresholds API endpoint."""

from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.config import settings


async def get_thresholds(request: Request) -> JSONResponse:
    """Return current threshold configuration."""
    thresholds = settings.thresholds
    return JSONResponse({
        "temperature": {
            "min": thresholds.min_temperature,
            "max": thresholds.max_temperature,
        },
        "humidity": {
            "min": thresholds.min_humidity,
            "max": thresholds.max_humidity,
        },
        "moisture": thresholds.plant_moisture_thresholds,
    })
