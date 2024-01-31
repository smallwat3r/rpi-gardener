import json
from time import sleep
from typing import Callable

from flask import request
from flask_sock import Sock

from rpi.lib.config import POLLING_FREQUENCY_SEC

from ._queries import get_latest_dht_data, get_stats_dht_data
from ._utils import get_qs
from .dashboard import dashboard

sock = Sock(dashboard)


def _websocket_loop(sock: Sock, func: Callable, *args, **kwargs) -> None:
    while True:
        sleep(POLLING_FREQUENCY_SEC)
        sock.send(json.dumps(func(*args, **kwargs)))


@sock.route("/dht/latest")
def latest(sock: Sock) -> None:
    _websocket_loop(sock, get_latest_dht_data)


@sock.route("/dht/stats")
def stats(sock: Sock) -> None:
    _, from_time = get_qs(request)
    _websocket_loop(sock, get_stats_dht_data, from_time)
