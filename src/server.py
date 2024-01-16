from flask import Flask, render_template

from ._utils import Db, epoch_to_datetime

app = Flask(__name__)


def _get_data() -> dict[str, float | int]:
    with Db() as db:
        return db.fetchall("chart.sql")


@app.get("/")
def index() -> str:
    return render_template("index.j2", data=_get_data(),
                           epoch_to_datetime=epoch_to_datetime)
