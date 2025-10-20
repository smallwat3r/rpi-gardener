"""Database queries for the RPi Gardener application."""
from datetime import datetime
from sqlite3 import Cursor

from sqlitey import Sql, SqlRow, dict_factory

from rpi.lib.config import db_with_config


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


def _pico_dict_factory(cursor: Cursor, row: tuple) -> SqlRow:
    """A custom dict factory for the Pico sensor data."""
    plant_id, moisture, epoch = row
    return {plant_id: moisture, "epoch": epoch}


def get_initial_pico_data(from_time: datetime) -> list[SqlRow]:
    """Return all Pico sensor data from a given time."""
    with db_with_config(row_factory=_pico_dict_factory) as db:
        return db.fetchall(Sql.template("pico_chart.sql"), (from_time, ))


def get_latest_pico_data() -> SqlRow:
    """Return the latest Pico sensor data."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchall(Sql.template("pico_latest_recording.sql"))