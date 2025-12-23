"""Database queries for the RPi Gardener application."""
from datetime import datetime

from sqlitey import Sql, SqlRow, dict_factory

from rpi.lib.config import db_with_config


def init_db() -> None:
    """Initialize database schema (tables and indexes).

    Safe to call multiple times - uses IF NOT EXISTS clauses.
    """
    with db_with_config() as db:
        db.execute(Sql.raw("PRAGMA journal_mode=WAL"))
        db.execute(Sql.template("init_reading_table.sql"))
        db.execute(Sql.template("idx_reading.sql"))
        db.execute(Sql.template("init_pico_reading_table.sql"))
        db.execute(Sql.template("idx_pico_reading.sql"))


def get_initial_dht_data(from_time: datetime) -> list[SqlRow]:
    """Return all DHT22 sensor data from a given time."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchall(Sql.template("dht_chart.sql"), (from_time, ))


def get_latest_dht_data() -> SqlRow:
    """Return the latest DHT22 sensor data."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchone(Sql.template("dht_latest_recording.sql"))


def get_stats_dht_data(from_time: datetime) -> SqlRow:
    """Return statistics for the DHT22 sensor data from a given time."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchone(Sql.template("dht_stats.sql"), (from_time, ))


def get_initial_pico_data(from_time: datetime) -> list[SqlRow]:
    """Return all Pico sensor data from a given time, grouped by epoch."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchall(Sql.template("pico_chart.sql"), (from_time, ))


def get_latest_pico_data() -> SqlRow:
    """Return the latest Pico sensor data."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchall(Sql.template("pico_latest_recording.sql"))
