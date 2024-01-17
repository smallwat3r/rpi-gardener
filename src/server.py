from flask import Flask, render_template

from ._config import Threshold
from ._utils import Db, epoch_to_datetime

app = Flask(__name__)


def _get_data() -> dict[str, float | int]:
    with Db() as db:
        return db.fetchall("chart.sql")


@app.context_processor
def context_processor() -> dict[str, int]:
    return {"threshold": Threshold}


@app.get("/")
def index() -> str:
    return render_template("index.j2", data=_get_data(),
                           epoch_to_datetime=epoch_to_datetime)
