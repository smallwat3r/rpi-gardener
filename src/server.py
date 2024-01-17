import json
from time import sleep

from flask import Flask, render_template
from flask_sock import Sock

from ._config import POLLING_FREQUENCY_SEC, Threshold
from ._utils import Db

app = Flask(__name__)
sock = Sock(app)


def _get_initial_data() -> list[dict[str, float | int]]:
    with Db() as db:
        return db.fetchall("chart.sql")


def _get_latest_data() -> dict[str, float | int]:
    with Db() as db:
        return db.fetchone("latest_recording.sql")


@app.context_processor
def context_processor():
    return {"threshold": Threshold}


@app.get("/")
def index():
    return render_template("index.html", data=_get_initial_data(),
                           latest=_get_latest_data())


@sock.route("/latest")
def latest(sock: Sock):
    while True:
        sleep(POLLING_FREQUENCY_SEC)
        sock.send(json.dumps(_get_latest_data()))
