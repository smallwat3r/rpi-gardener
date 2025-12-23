import logging
from datetime import datetime, timedelta
from sqlite3 import DatabaseError

from flask import Blueprint, Response, jsonify, request

from rpi.lib.db import (
    get_initial_dht_data,
    get_initial_pico_data,
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)

logger = logging.getLogger(__name__)

_MIN_HOURS = 1
_MAX_HOURS = 24
_DEFAULT_HOURS = 3


class _BadParameter(Exception): ...


def _get_qs() -> tuple[int, datetime]:
    """Parse and validate hours query parameter."""
    try:
        hours = int(request.args.get("hours", _DEFAULT_HOURS))
    except ValueError as err:
        raise _BadParameter("Parameter needs to be an integer") from err
    if not (_MIN_HOURS <= hours <= _MAX_HOURS):
        raise _BadParameter(f"Hours must be between {_MIN_HOURS} and {_MAX_HOURS}")
    return hours, datetime.utcnow() - timedelta(hours=hours)

dashboard_api = Blueprint("dashboard_api", __name__, url_prefix="/api")


@dashboard_api.get("/dashboard")
def get_dashboard_data() -> tuple[Response, int]:
    """Return dashboard data as JSON for SPA consumption."""
    try:
        hours, from_time = _get_qs()
    except _BadParameter as err:
        return jsonify({"error": str(err)}), 400

    try:
        return jsonify({
            "hours": hours,
            "data": get_initial_dht_data(from_time),
            "stats": get_stats_dht_data(from_time),
            "latest": get_latest_dht_data(),
            "pico_data": get_initial_pico_data(from_time),
            "pico_latest": get_latest_pico_data(),
        }), 200
    except DatabaseError as err:
        logger.exception("Database error fetching dashboard data")
        return jsonify({"error": "Database unavailable"}), 503
