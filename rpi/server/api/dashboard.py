import logging
from sqlite3 import DatabaseError

from flask import Blueprint, Response, jsonify, request

from rpi.lib.db import (
    get_initial_dht_data,
    get_initial_pico_data,
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)
from rpi.server.views._utils import BadParameter, get_qs

logger = logging.getLogger(__name__)

dashboard_api = Blueprint("dashboard_api", __name__, url_prefix="/api")


@dashboard_api.get("/dashboard")
def get_dashboard_data() -> tuple[Response, int]:
    """Return dashboard data as JSON for SPA consumption."""
    try:
        hours, from_time = get_qs(request)
    except BadParameter as err:
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
