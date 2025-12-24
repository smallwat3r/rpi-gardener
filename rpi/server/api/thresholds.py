"""Thresholds API endpoint."""

from starlette.requests import Request
from starlette.responses import JSONResponse

from rpi.lib.config import (MAX_HUMIDITY, MAX_TEMPERATURE, MIN_HUMIDITY,
                            MIN_TEMPERATURE, PLANT_MOISTURE_THRESHOLDS)


async def get_thresholds(request: Request) -> JSONResponse:
    """Return current threshold configuration."""
    return JSONResponse({
        "temperature": {
            "min": MIN_TEMPERATURE,
            "max": MAX_TEMPERATURE,
        },
        "humidity": {
            "min": MIN_HUMIDITY,
            "max": MAX_HUMIDITY,
        },
        "moisture": PLANT_MOISTURE_THRESHOLDS,
    })
