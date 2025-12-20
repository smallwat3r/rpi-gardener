"""Database queries for the RPi Gardener application."""
from datetime import datetime
from sqlite3 import Cursor
from threading import Lock
from time import monotonic
from typing import Any

from sqlitey import Sql, SqlRow, dict_factory

from rpi.lib.config import db_with_config

# Cache TTL in seconds - stats don't change frequently, so cache for 5 seconds
STATS_CACHE_TTL_SEC = 5.0


class _TTLCache:
    """A simple thread-safe TTL cache for database query results."""

    def __init__(self, ttl: float) -> None:
        self._ttl = ttl
        self._cache: dict[Any, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: Any) -> tuple[bool, Any]:
        """Get a value from cache. Returns (hit, value)."""
        with self._lock:
            if key in self._cache:
                timestamp, value = self._cache[key]
                if monotonic() - timestamp < self._ttl:
                    return True, value
                del self._cache[key]
        return False, None

    def set(self, key: Any, value: Any) -> None:
        """Set a value in cache."""
        with self._lock:
            self._cache[key] = (monotonic(), value)


_stats_cache = _TTLCache(STATS_CACHE_TTL_SEC)


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
    hit, cached_value = _stats_cache.get(cache_key)
    if hit:
        return cached_value

    with db_with_config(row_factory=dict_factory) as db:
        result = db.fetchone(Sql.template("dht_stats.sql"), (from_time, ))

    _stats_cache.set(cache_key, result)
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