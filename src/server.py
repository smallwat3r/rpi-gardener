import json
from datetime import datetime, timedelta
from os import environ
from time import sleep
from typing import Callable

from flask import (Flask, Request, flash, redirect, render_template,
                   request, url_for)
from flask_sock import Sock

from ._config import FLASK_SECRET_KEY, POLLING_FREQUENCY_SEC
from ._db import Db, Sql, SqlRow
from .api import pico

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = bool(environ.get("RELOAD"))
app.secret_key = FLASK_SECRET_KEY
app.register_blueprint(pico)

sock = Sock(app)


def _get_initial_data(from_time: datetime) -> list[SqlRow]:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("chart.sql"), (from_time,)).fetchall()


def _get_latest_data() -> SqlRow:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("latest_recording.sql")).fetchone()


def _get_stats_data(from_time: datetime) -> SqlRow:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("stats.sql"), (from_time,)).fetchone()


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


@app.get("/")
def index() -> str:
    try:
        hours, from_time = _get_qs(request)
    except BadParameter as err:
        flash(str(err))
        return redirect(url_for("index"))
    return render_template("index.html",
                           hours=hours,
                           data=_get_initial_data(from_time),
                           stats=_get_stats_data(from_time),
                           latest=_get_latest_data())


def _websocket_loop(sock: Sock, func: Callable, *args, **kwargs) -> None:
    while True:
        sleep(POLLING_FREQUENCY_SEC)
        sock.send(json.dumps(func(*args, **kwargs)))


@sock.route("/latest")
def latest(sock: Sock) -> None:
    _websocket_loop(sock, _get_latest_data)


@sock.route("/stats")
def stats(sock: Sock) -> None:
    _, from_time = _get_qs(request)
    _websocket_loop(sock, _get_stats_data, from_time)
