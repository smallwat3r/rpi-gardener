import json
from time import sleep
from typing import Callable

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_sock import Sock

from rpi.lib.config import POLLING_FREQUENCY_SEC
from rpi.server.views._queries import (
    get_initial_dht_data,
    get_initial_pico_data,
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)
from rpi.server.views._utils import BadParameter, get_qs

dashboard = Blueprint("dashboard", __name__)


@dashboard.get("/")
def index() -> str:
    try:
        hours, from_time = get_qs(request)
    except BadParameter as err:
        flash(str(err))
        return redirect(url_for("index"))
    return render_template(
        "index.html",
        hours=hours,
        data=get_initial_dht_data(from_time),
        stats=get_stats_dht_data(from_time),
        latest=get_latest_dht_data(),
        pico_data=get_initial_pico_data(from_time),
        pico_latest=get_latest_pico_data(),
    )


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


@sock.route("/pico/latest")
def pico_latest(sock: Sock) -> None:
    _websocket_loop(sock, get_latest_pico_data)
