"""Database queries for the RPi Gardener application."""
from collections import defaultdict
from datetime import datetime
from typing import TypedDict

from sqlitey import Sql, dict_factory

from rpi.lib.config import db_with_config


class DHTReading(TypedDict):
    """DHT22 sensor reading from the database."""
    temperature: float
    humidity: float
    recording_time: str
    epoch: int


class DHTStats(TypedDict):
    """DHT22 sensor statistics."""
    avg_temperature: float
    min_temperature: float
    max_temperature: float
    avg_humidity: float
    min_humidity: float
    max_humidity: float


class PicoReading(TypedDict):
    """Pico moisture reading from the database."""
    plant_id: str
    moisture: float
    recording_time: str
    epoch: int


class PicoChartDataPoint(TypedDict, total=False):
    """Pico chart data point with dynamic plant columns."""
    epoch: int


def init_db() -> None:
    """Initialize database schema (tables and indexes).

    Safe to call multiple times - uses IF NOT EXISTS clauses.
    """
    with db_with_config() as db:
        db.execute(Sql.raw("PRAGMA journal_mode=WAL"))
        db.execute(Sql.template("init_reading_table.sql"))
        db.executescript(Sql.template("idx_reading.sql"))
        db.execute(Sql.template("init_pico_reading_table.sql"))
        db.executescript(Sql.template("idx_pico_reading.sql"))


def get_initial_dht_data(from_time: datetime) -> list[DHTReading]:
    """Return all DHT22 sensor data from a given time."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchall(Sql.template("dht_chart.sql"), (from_time, ))


def get_latest_dht_data() -> DHTReading | None:
    """Return the latest DHT22 sensor data."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchone(Sql.template("dht_latest_recording.sql"))


def get_stats_dht_data(from_time: datetime) -> DHTStats | None:
    """Return statistics for the DHT22 sensor data from a given time."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchone(Sql.template("dht_stats.sql"), (from_time, ))


def get_initial_pico_data(from_time: datetime) -> list[PicoChartDataPoint]:
    """Return all Pico sensor data from a given time, pivoted by plant_id."""
    with db_with_config(row_factory=dict_factory) as db:
        rows = db.fetchall(Sql.template("pico_chart.sql"), (from_time,))

    # Pivot: group by epoch, with plant_id as columns
    pivoted: dict[int, PicoChartDataPoint] = defaultdict(dict)
    for row in rows:
        epoch = row["epoch"]
        pivoted[epoch]["epoch"] = epoch
        pivoted[epoch][row["plant_id"]] = row["moisture"]

    return list(pivoted.values())


def get_latest_pico_data() -> list[PicoReading]:
    """Return the latest Pico sensor data for each plant."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchall(Sql.template("pico_latest_recording.sql"))
