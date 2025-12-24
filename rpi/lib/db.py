"""Async database operations for the RPi Gardener application.

Provides async database operations using aiosqlite for non-blocking
database access throughout the application.
"""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

import aiosqlite

from rpi.lib.config import settings

# SQL templates directory
_SQL_DIR = Path(__file__).resolve().parent / "sql"


def _load_template(name: str) -> str:
    """Load a SQL template file."""
    return (_SQL_DIR / name).read_text()


# Pre-load SQL templates
_INIT_READING_SQL = _load_template("init_reading_table.sql")
_IDX_READING_SQL = _load_template("idx_reading.sql")
_INIT_PICO_SQL = _load_template("init_pico_reading_table.sql")
_IDX_PICO_SQL = _load_template("idx_pico_reading.sql")
_DHT_CHART_SQL = _load_template("dht_chart.sql")
_DHT_LATEST_SQL = _load_template("dht_latest_recording.sql")
_DHT_STATS_SQL = _load_template("dht_stats.sql")
_PICO_CHART_SQL = _load_template("pico_chart.sql")
_PICO_LATEST_SQL = _load_template("pico_latest_recording.sql")


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
    plant_id: int
    moisture: float
    recording_time: str
    epoch: int


class PicoChartDataPoint(TypedDict, total=False):
    """Pico chart data point with dynamic plant columns."""
    epoch: int


def _dict_factory(cursor: aiosqlite.Cursor, row: tuple) -> dict[str, Any]:
    """Convert a row to a dictionary using column names."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class AsyncDatabase:
    """Async database connection manager."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or settings.db_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open the database connection."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self._db_path)
            self._connection.row_factory = _dict_factory

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> "AsyncDatabase":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a SQL statement and commit."""
        if self._connection is None:
            raise RuntimeError("Database not connected")
        await self._connection.execute(sql, params)
        await self._connection.commit()

    async def executemany(self, sql: str, params_seq: list[tuple]) -> None:
        """Execute a SQL statement with multiple parameter sets and commit."""
        if self._connection is None:
            raise RuntimeError("Database not connected")
        await self._connection.executemany(sql, params_seq)
        await self._connection.commit()

    async def executescript(self, sql: str) -> None:
        """Execute multiple SQL statements."""
        if self._connection is None:
            raise RuntimeError("Database not connected")
        await self._connection.executescript(sql)

    async def fetchone(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """Fetch a single row."""
        if self._connection is None:
            raise RuntimeError("Database not connected")
        async with self._connection.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Fetch all rows."""
        if self._connection is None:
            raise RuntimeError("Database not connected")
        async with self._connection.execute(sql, params) as cursor:
            return await cursor.fetchall()


# Module-level database instance for connection reuse
_db: AsyncDatabase | None = None


async def get_async_db() -> AsyncDatabase:
    """Get the async database instance, creating if needed."""
    global _db
    if _db is None:
        _db = AsyncDatabase()
        await _db.connect()
    return _db


async def close_async_db() -> None:
    """Close the async database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def init_db() -> None:
    """Initialize database schema (tables and indexes).

    Safe to call multiple times - uses IF NOT EXISTS clauses.
    """
    db = await get_async_db()
    if db._connection is None:
        raise RuntimeError("Database not connected")
    await db._connection.execute("PRAGMA journal_mode=WAL")
    await db._connection.execute(_INIT_READING_SQL)
    await db.executescript(_IDX_READING_SQL)
    await db._connection.execute(_INIT_PICO_SQL)
    await db.executescript(_IDX_PICO_SQL)


async def get_initial_dht_data(from_time: datetime) -> list[DHTReading]:
    """Return all DHT22 sensor data from a given time."""
    db = await get_async_db()
    return await db.fetchall(_DHT_CHART_SQL, (from_time,))


async def get_latest_dht_data() -> DHTReading | None:
    """Return the latest DHT22 sensor data."""
    db = await get_async_db()
    return await db.fetchone(_DHT_LATEST_SQL)


async def get_stats_dht_data(from_time: datetime) -> DHTStats | None:
    """Return statistics for the DHT22 sensor data from a given time."""
    db = await get_async_db()
    return await db.fetchone(_DHT_STATS_SQL, (from_time,))


async def get_initial_pico_data(from_time: datetime) -> list[PicoChartDataPoint]:
    """Return all Pico sensor data from a given time, pivoted by plant_id."""
    db = await get_async_db()
    rows = await db.fetchall(_PICO_CHART_SQL, (from_time,))

    # Pivot: group by epoch, with plant_id as columns
    pivoted: dict[int, PicoChartDataPoint] = defaultdict(dict)
    for row in rows:
        epoch = row["epoch"]
        pivoted[epoch]["epoch"] = epoch
        pivoted[epoch][row["plant_id"]] = row["moisture"]

    return list(pivoted.values())


async def get_latest_pico_data() -> list[PicoReading]:
    """Return the latest Pico sensor data for each plant."""
    db = await get_async_db()
    return await db.fetchall(_PICO_LATEST_SQL)
