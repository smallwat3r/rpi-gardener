import json
from datetime import datetime, timedelta
from os import environ
from time import sleep
from typing import Callable

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sock import Sock

from ._config import FLASK_SECRET_KEY, POLLING_FREQUENCY_SEC
from ._db import Db, Sql, SqlRow

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = bool(environ.get("RELOAD"))
app.secret_key = FLASK_SECRET_KEY

sock = Sock(app)


def _get_initial_data(hours: int) -> list[SqlRow]:
    from_time = datetime.now() - timedelta(hours=hours)
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("chart.sql"), (from_time,)).fetchall()


def _get_latest_data() -> SqlRow:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("latest_recording.sql")).fetchone()


def _get_average_data() -> SqlRow:
    with Db(dict_row_factory=True) as db:
        return db.query(Sql.from_file("average.sql"),
                        (datetime.now() - timedelta(hours=7),)).fetchone()


@app.get("/")
def index() -> str:
    try:
        hours = int(request.args.get("hours", 1))
    except ValueError:
        flash("Parameter needs to be an integer")
        return redirect(url_for("index"))
    if hours > 24:
        flash("Can't look past 24 hours")
        return redirect(url_for("index"))
    return render_template("index.html",
                           hours=hours,
                           data=_get_initial_data(hours),
                           average=_get_average_data(),
                           latest=_get_latest_data())


def _websocket_loop(sock: Sock, func: Callable) -> None:
    while True:
        sleep(POLLING_FREQUENCY_SEC)
        sock.send(json.dumps(func()))


@sock.route("/latest")
def latest(sock: Sock) -> None:
    _websocket_loop(sock, _get_latest_data)


@sock.route("/average")
def average(sock: Sock) -> None:
    _websocket_loop(sock, _get_average_data)
