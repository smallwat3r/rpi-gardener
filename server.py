import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime

from fastapi import FastAPI

app = FastAPI()


@dataclass(frozen=True)
class Reading:
    temperature: float
    humidity: float
    recording_time: datetime


@app.get("/")
def index():
    con = sqlite3.connect("dht.db")
    temperature, humidity, recording_time = con.execute(
        "SELECT * FROM reading "
        "ORDER BY recording_time DESC LIMIT 1").fetchone()
    return asdict(Reading(temperature, humidity, recording_time))
