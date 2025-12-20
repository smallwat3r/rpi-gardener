"""Health check endpoint for monitoring service status."""
from datetime import datetime

from flask import Blueprint, Response, jsonify

from rpi import logging
from rpi.lib.config import db_with_config
from rpi.lib.db import get_latest_dht_data, get_latest_pico_data

logger = logging.getLogger("health")
health = Blueprint("health", __name__)


def _check_database() -> tuple[bool, str]:
    """Check if database is accessible."""
    try:
        with db_with_config() as db:
            db.fetchone("SELECT 1")
        return True, "ok"
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False, str(e)


def _check_dht_sensor() -> tuple[bool, str | None]:
    """Check if DHT sensor has recent data (within last 5 minutes)."""
    try:
        latest = get_latest_dht_data()
        if latest is None:
            return False, "no data"
        return True, latest.get("recording_time")
    except Exception as e:
        logger.error("DHT sensor health check failed: %s", e)
        return False, str(e)


def _check_pico_sensor() -> tuple[bool, str | None]:
    """Check if Pico sensor has recent data."""
    try:
        latest = get_latest_pico_data()
        if not latest:
            return False, "no data"
        return True, latest[0].get("recording_time") if latest else None
    except Exception as e:
        logger.error("Pico sensor health check failed: %s", e)
        return False, str(e)


@health.get("/health")
def healthcheck() -> tuple[Response, int]:
    """Return health status of the application and its dependencies."""
    db_ok, db_status = _check_database()
    dht_ok, dht_last = _check_dht_sensor()
    pico_ok, pico_last = _check_pico_sensor()

    status = {
        "status": "healthy" if db_ok else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": {"ok": db_ok, "status": db_status},
            "dht_sensor": {"ok": dht_ok, "last_reading": dht_last},
            "pico_sensor": {"ok": pico_ok, "last_reading": pico_last},
        },
    }

    http_status = 200 if db_ok else 503
    return jsonify(status), http_status
