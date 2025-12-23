"""Database queries for the RPi Gardener application."""
from datetime import datetime
from sqlite3 import Cursor
from threading import Lock

from cachetools import TTLCache
from sqlitey import Sql, SqlRow, dict_factory

from rpi.lib.config import db_with_config
from rpi.lib.utils import register_sqlite_adapters

# Cache TTL in seconds - stats don't change frequently, so cache for 5 seconds
_STATS_CACHE_TTL_SEC = 5.0
_STATS_CACHE_MAX_SIZE = 100

# Register adapters on module import
register_sqlite_adapters()


def init_db() -> None:
    """Initialize database schema (tables and indexes).

    Safe to call multiple times - uses IF NOT EXISTS clauses.
    """
    with db_with_config() as db:
        db.execute(Sql.template("init_reading_table.sql"))
        db.execute(Sql.template("idx_reading.sql"))
        db.execute(Sql.template("init_pico_reading_table.sql"))
        db.execute(Sql.template("idx_pico_reading.sql"))


_stats_cache = TTLCache(maxsize=_STATS_CACHE_MAX_SIZE, ttl=_STATS_CACHE_TTL_SEC)
_stats_cache_lock = Lock()


def get_initial_dht_data(from_time: datetime) -> list[SqlRow]:
    """Return all DHT22 sensor data from a given time."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchall(Sql.template("dht_chart.sql"), (from_time, ))


def get_latest_dht_data() -> SqlRow:
    """Return the latest DHT22 sensor data."""
    with db_with_config(row_factory=dict_factory) as db:
        return db.fetchone(Sql.template("dht_latest_recording.sql"))


def get_stats_dht_data(from_time: datetime) -> SqlRow:
    """Return statistics for the DHT22 sensor data from a given time.

    Results are cached with a TTL to reduce database load when multiple
    WebSocket clients are connected.
    """
    cache_key = from_time.isoformat()
    with _stats_cache_lock:
        if cache_key in _stats_cache:
            return _stats_cache[cache_key]

    with db_with_config(row_factory=dict_factory) as db:
        result = db.fetchone(Sql.template("dht_stats.sql"), (from_time, ))

    with _stats_cache_lock:
        _stats_cache[cache_key] = result
    return result


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