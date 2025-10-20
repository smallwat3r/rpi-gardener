"""Websocket routes for the RPi Gardener application."""
import json
from time import sleep
from typing import Callable

from flask_sock import Sock

from rpi.lib.config import POLLING_FREQUENCY_SEC
from rpi.lib.db import (
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)
from rpi.server.views._utils import get_qs


def _websocket_loop(sock: Sock, func: Callable, *args, **kwargs) -> None:
    """A generic websocket loop that sends data to the client."""
    while True:
        sleep(POLLING_FREQUENCY_SEC)
        sock.send(json.dumps(func(*args, **kwargs)))


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