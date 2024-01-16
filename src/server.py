from flask import Flask, render_template

from ._utils import Db

app = Flask(__name__)


def _get_data() -> dict[str, float | int]:
    with Db() as db:
        return db.fetchall("chart.sql")


@app.get("/")
def index() -> str:
    return render_template("index.html", data=_get_data())
