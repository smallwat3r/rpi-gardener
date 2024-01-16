from dataclasses import asdict

from flask import Flask

from ._utils import Db, Reading

app = Flask(__name__)


@app.get("/")
def index():
    with Db() as db:
        reading = Reading(*db.fetchone(
            "SELECT * FROM reading ORDER BY recording_time DESC LIMIT 1"))
    return asdict(reading)
