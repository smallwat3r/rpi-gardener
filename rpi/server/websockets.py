"""Websocket routes for the RPi Gardener application."""
import json
from time import sleep
from typing import Callable

from flask_sock import Sock
from simple_websocket import ConnectionClosed

from rpi import logging
from rpi.lib.config import POLLING_FREQUENCY_SEC
from rpi.lib.db import (
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)
from rpi.server.views._utils import get_qs

logger = logging.getLogger("websockets")


def _websocket_loop(sock: Sock, func: Callable, *args, **kwargs) -> None:
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
        _, from_time = get_qs(sock.request)
        _websocket_loop(sock, get_stats_dht_data, from_time)

    @sock.route("/pico/latest")
    def pico_latest(sock: Sock) -> None:
        _websocket_loop(sock, get_latest_pico_data)