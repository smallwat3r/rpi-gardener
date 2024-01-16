import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime

from flask import Flask

from .lib import db

app = Flask(__name__)


@dataclass(frozen=True)
class Reading:
    temperature: float
    humidity: float
    recording_time: datetime


@app.get("/")
def index():
    with closing(db()) as conn:
        cur = conn.cursor()
        temperature, humidity, recording_time = cur.execute(
            "SELECT * FROM reading "
            "ORDER BY recording_time DESC LIMIT 1").fetchone()
    return asdict(Reading(temperature, humidity, recording_time))
