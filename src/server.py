from flask import Flask, render_template

from ._utils import Db

app = Flask(__name__)


def _get_data() -> dict[str, float | int]:
    with Db() as db:
        return db.fetchall(
            "SELECT temperature, humidity, "
            "unixepoch(recording_time) * 1000 as 'epoch' "
            "FROM reading ORDER BY recording_time DESC LIMIT 5000")


@app.get("/")
def index() -> str:
    return render_template("index.html", data=_get_data())
