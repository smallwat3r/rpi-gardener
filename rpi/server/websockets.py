"""Websocket routes for the RPi Gardener application."""
import json
from datetime import datetime, timedelta
from time import sleep
from typing import Any, Callable

from flask import request
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from rpi import logging
from rpi.lib.config import POLLING_FREQUENCY_SEC
from rpi.lib.db import (
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)

logger = logging.getLogger("websockets")

_DEFAULT_HOURS = 3


def _get_from_time() -> datetime:
    """Parse hours from query string and return the from_time datetime."""
    try:
        hours = int(request.args.get("hours", _DEFAULT_HOURS))
    except ValueError:
        hours = _DEFAULT_HOURS
    return datetime.utcnow() - timedelta(hours=max(1, min(24, hours)))


def _websocket_loop(
    sock: Sock,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """A generic websocket loop that sends data to the client.

    Handles client disconnection gracefully and logs connection events.
    """
    client_id = id(sock)
    logger.info("WebSocket client %s connected", client_id)
    try:
        while True:
            sleep(POLLING_FREQUENCY_SEC)
            try:
                data = func(*args, **kwargs)
                sock.send(json.dumps(data))
            except Exception as e:
                logger.error("Error fetching data for client %s: %s", client_id, e)
    except ConnectionClosed:
        logger.info("WebSocket client %s disconnected", client_id)
    except Exception as e:
        logger.error("WebSocket error for client %s: %s", client_id, e)
    finally:
        logger.debug("WebSocket loop ended for client %s", client_id)


def init_websockets(sock: Sock) -> None:
    """Initialize the websocket routes."""

    @sock.route("/dht/latest")
    def latest(sock: Sock) -> None:
        _websocket_loop(sock, get_latest_dht_data)

    @sock.route("/dht/stats")
    def stats(sock: Sock) -> None:
        from_time = _get_from_time()
        _websocket_loop(sock, get_stats_dht_data, from_time)

    @sock.route("/pico/latest")
    def pico_latest(sock: Sock) -> None:
        _websocket_loop(sock, get_latest_pico_data)