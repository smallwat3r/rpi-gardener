"""Async database operations for the RPi Gardener application.

Provides async database operations using aiosqlite for non-blocking
database access throughout the application.

Two connection patterns are supported:
- Persistent connection: Call init_db() at startup to open a connection
  that is reused for all queries. Used by polling services (DHT, Pico)
  to avoid connection overhead on their 2-second polling loops.
- Connection-per-request: If init_db() is not called, get_db() creates
  a temporary connection for each use. Used by the web server for
  concurrent request handling.
"""
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, TypedDict

type SQLParams = tuple | dict[str, Any]

import aiosqlite

from rpi.lib.config import get_settings
from rpi.logging import get_logger

_logger = get_logger("lib.db")

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

# Global persistent database connection
_db: Database | None = None


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


class Database:
    """Async database connection wrapper."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or get_settings().db_path
        self._connection: aiosqlite.Connection | None = None
        self._in_transaction = False

    async def connect(self) -> None:
        """Open the database connection."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(
                self._db_path,
                timeout=get_settings().db_timeout_sec,
            )
            self._connection.row_factory = _dict_factory

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> Database:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Context manager for database transactions.

        All operations within the context are committed together on success,
        or rolled back if an exception occurs.

        Usage:
            async with db.transaction():
                await db.execute("INSERT INTO ...")
                await db.execute("INSERT INTO ...")
        """
        if self._connection is None:
            raise RuntimeError("Database not connected")
        self._in_transaction = True
        await self._connection.execute("BEGIN")
        try:
            yield
            await self._connection.commit()
        except Exception:
            await self._connection.rollback()
            raise
        finally:
            self._in_transaction = False

    async def execute(self, sql: str, params: SQLParams = ()) -> None:
        """Execute a SQL statement.

        Auto-commits unless inside a transaction() context.
        Supports both positional (tuple) and named (dict) parameters.
        """
        if self._connection is None:
            raise RuntimeError("Database not connected")
        await self._connection.execute(sql, params)
        if not self._in_transaction:
            await self._connection.commit()

    async def executemany(self, sql: str, params_seq: list[SQLParams]) -> None:
        """Execute a SQL statement with multiple parameter sets.

        Auto-commits unless inside a transaction() context.
        Supports both positional (tuple) and named (dict) parameters.
        """
        if self._connection is None:
            raise RuntimeError("Database not connected")
        await self._connection.executemany(sql, params_seq)
        if not self._in_transaction:
            await self._connection.commit()

    async def executescript(self, sql: str) -> None:
        """Execute multiple SQL statements."""
        if self._connection is None:
            raise RuntimeError("Database not connected")
        await self._connection.executescript(sql)

    async def fetchone(self, sql: str, params: SQLParams = ()) -> dict[str, Any] | None:
        """Fetch a single row."""
        if self._connection is None:
            raise RuntimeError("Database not connected")
        async with self._connection.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: SQLParams = ()) -> list[dict[str, Any]]:
        """Fetch all rows."""
        if self._connection is None:
            raise RuntimeError("Database not connected")
        async with self._connection.execute(sql, params) as cursor:
            return await cursor.fetchall()


@asynccontextmanager
async def get_db() -> AsyncIterator[Database]:
    """Get a database connection.

    Uses the persistent connection if initialized via init_db(),
    otherwise creates a temporary connection (useful for tests).

    Usage:
        async with get_db() as db:
            await db.execute("INSERT INTO ...")
    """
    if _db is not None:
        # Use persistent connection (no close on exit)
        yield _db
    else:
        # Fallback: create temporary connection (for tests or pre-init usage)
        db = Database()
        await db.connect()
        try:
            yield db
        finally:
            await db.close()


async def init_db() -> None:
    """Initialize database with persistent connection and schema.

    Opens a persistent connection that will be reused for all queries.
    Safe to call multiple times - uses IF NOT EXISTS clauses.
    Call close_db() on shutdown to close the connection.
    """
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
        _logger.info("Opened persistent database connection: %s", get_settings().db_path)

    await _db._connection.execute("PRAGMA journal_mode=WAL")
    await _db._connection.execute("PRAGMA auto_vacuum=INCREMENTAL")
    await _db._connection.execute(_INIT_READING_SQL)
    await _db.executescript(_IDX_READING_SQL)
    await _db._connection.execute(_INIT_PICO_SQL)
    await _db.executescript(_IDX_PICO_SQL)


async def close_db() -> None:
    """Close the persistent database connection.

    Should be called on application shutdown.
    """
    global _db
    if _db is not None:
        await _db.close()
        _logger.info("Closed persistent database connection")
        _db = None


async def get_initial_dht_data(from_time: datetime) -> list[DHTReading]:
    """Return all DHT22 sensor data from a given time."""
    async with get_db() as db:
        return await db.fetchall(_DHT_CHART_SQL, (from_time,))


async def get_latest_dht_data() -> DHTReading | None:
    """Return the latest DHT22 sensor data."""
    async with get_db() as db:
        return await db.fetchone(_DHT_LATEST_SQL)


async def get_stats_dht_data(from_time: datetime) -> DHTStats | None:
    """Return statistics for the DHT22 sensor data from a given time."""
    async with get_db() as db:
        return await db.fetchone(_DHT_STATS_SQL, (from_time,))


async def get_initial_pico_data(from_time: datetime) -> list[PicoChartDataPoint]:
    """Return all Pico sensor data from a given time, pivoted by plant_id."""
    async with get_db() as db:
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
    async with get_db() as db:
        return await db.fetchall(_PICO_LATEST_SQL)
