import json
from datetime import datetime, timedelta
from time import sleep
from typing import Callable

from flask import (Blueprint, Request, flash, redirect,
                   render_template, request, url_for)
from flask_sock import Sock

from rpi.lib.config import POLLING_FREQUENCY_SEC
from rpi.lib.db import Db, Sql, SqlRow

dashboard = Blueprint("dashboard", __name__)
sock = Sock(dashboard)


def _get_initial_dht_data(from_time: datetime) -> list[SqlRow]:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("dht_chart.sql"), (from_time,)).fetchall()


def _get_latest_dht_data() -> SqlRow:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("dht_latest_recording.sql")).fetchone()


def _get_stats_dht_data(from_time: datetime) -> SqlRow:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("dht_stats.sql"), (from_time,)).fetchone()


class BadParameter(Exception):
    ...


def _get_qs(request: Request) -> tuple[int, datetime]:
    try:
        hours = int(request.args.get("hours", 1))
    except ValueError as err:
        raise BadParameter("Parameter needs to be an integer") from err
    if hours > 24:
        raise BadParameter("Can't look past 24 hours")
    return hours, datetime.now() - timedelta(hours=hours)


@dashboard.get("/")
def index() -> str:
    try:
        hours, from_time = _get_qs(request)
    except BadParameter as err:
        flash(str(err))
        return redirect(url_for("index"))
    return render_template("index.html",
                           hours=hours,
                           data=_get_initial_dht_data(from_time),
                           stats=_get_stats_dht_data(from_time),
                           latest=_get_latest_dht_data())


def _websocket_loop(sock: Sock, func: Callable, *args, **kwargs) -> None:
    while True:
        sleep(POLLING_FREQUENCY_SEC)
        sock.send(json.dumps(func(*args, **kwargs)))


@sock.route("/dht/latest")
def latest(sock: Sock) -> None:
    _websocket_loop(sock, _get_latest_dht_data)


@sock.route("/dht/stats")
def stats(sock: Sock) -> None:
    _, from_time = _get_qs(request)
    _websocket_loop(sock, _get_stats_dht_data, from_time)
