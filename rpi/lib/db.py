"""Async database operations for the RPi Gardener application.

Provides async database operations using aiosqlite for non-blocking
database access throughout the application.

Connection Patterns
-------------------
Two connection patterns are supported, chosen automatically by get_db():

1. **Persistent Connection** (polling services)
   - Call init_db() once at startup to open a long-lived connection
   - All subsequent get_db() calls reuse this connection
   - Avoids connection overhead on frequent polling loops (2-second intervals)
   - Used by: DHT polling service, Pico reader service
   - Call close_db() on shutdown to close the connection

   Example:
       await init_db()  # Once at startup
       async with get_db() as db:
           await db.execute(...)  # Uses persistent connection

2. **Connection Pool** (web server)
   - If init_db() was NOT called, get_db() uses a connection pool
   - Connections are reused across requests (up to pool_max_size)
   - Avoids overhead of creating new connections per request
   - Pool is closed when close_db() is called
   - Used by: Web server API endpoints

   Example:
       async with get_db() as db:  # Gets connection from pool
           await db.execute(...)
       # Connection returned to pool for reuse

The pattern is transparent to calling code - just use get_db() and the
appropriate connection type is selected based on whether init_db() was called.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict, cast

type SQLParams = tuple[Any, ...] | dict[str, Any]

import aiosqlite

from rpi.lib.config import SettingsKey, get_settings
from rpi.lib.exceptions import DatabaseNotConnectedError
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
_INIT_SETTINGS_SQL = _load_template("init_settings_table.sql")
_INIT_ADMIN_SQL = _load_template("init_admin_table.sql")

# Global persistent database connection (for polling services)
_db: Database | None = None

# Connection pool for web server (avoids creating new connections per request)
_pool: list[Database] = []
_pool_max_size = 5


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


def _dict_factory(
    cursor: aiosqlite.Cursor, row: tuple[Any, ...]
) -> dict[str, Any]:
    """Convert a row to a dictionary using column names."""
    desc: tuple[Any, ...] = cursor.description or ()
    return {col[0]: row[idx] for idx, col in enumerate(desc)}


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
            self._connection.row_factory = _dict_factory  # type: ignore[assignment]

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> Database:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
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
            raise DatabaseNotConnectedError()
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

    async def execute(self, sql: str, params: SQLParams = ()) -> int:
        """Execute a SQL statement.

        Auto-commits unless inside a transaction() context.
        Supports both positional (tuple) and named (dict) parameters.

        Returns:
            Number of rows affected by the statement.
        """
        if self._connection is None:
            raise DatabaseNotConnectedError()
        cursor = await self._connection.execute(sql, params)
        if not self._in_transaction:
            await self._connection.commit()
        return cursor.rowcount

    async def executemany(
        self, sql: str, params_seq: Sequence[SQLParams]
    ) -> None:
        """Execute a SQL statement with multiple parameter sets.

        Auto-commits unless inside a transaction() context.
        Supports both positional (tuple) and named (dict) parameters.
        """
        if self._connection is None:
            raise DatabaseNotConnectedError()
        await self._connection.executemany(sql, params_seq)
        if not self._in_transaction:
            await self._connection.commit()

    async def executescript(self, sql: str) -> None:
        """Execute multiple SQL statements."""
        if self._connection is None:
            raise DatabaseNotConnectedError()
        await self._connection.executescript(sql)

    async def fetchone(
        self, sql: str, params: SQLParams = ()
    ) -> dict[str, Any] | None:
        """Fetch a single row."""
        if self._connection is None:
            raise DatabaseNotConnectedError()
        async with self._connection.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return cast(dict[str, Any] | None, row)

    async def fetchall(
        self, sql: str, params: SQLParams = ()
    ) -> list[dict[str, Any]]:
        """Fetch all rows."""
        if self._connection is None:
            raise DatabaseNotConnectedError()
        async with self._connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return cast(list[dict[str, Any]], rows)


@asynccontextmanager
async def get_db() -> AsyncIterator[Database]:
    """Get a database connection using the appropriate pattern.

    This context manager automatically selects the connection pattern:
    - If init_db() was called: reuses the persistent connection
    - Otherwise: uses connection pool (reuses connections across requests)

    Calling code doesn't need to know which pattern is in use.

    Usage:
        async with get_db() as db:
            await db.execute("INSERT INTO ...")
    """
    if _db is not None:
        # Persistent connection mode: reuse existing connection
        yield _db
    else:
        # Pool mode: reuse connections from pool when available
        if _pool:
            db = _pool.pop()
        else:
            db = Database()
            await db.connect()

        try:
            yield db
        finally:
            # Return to pool if under max size, otherwise close
            if len(_pool) < _pool_max_size:
                _pool.append(db)
            else:
                await db.close()


async def init_db() -> None:
    """Initialize database with persistent connection and schema.

    Call this once at startup for services that make frequent database
    queries (e.g., polling services with 2-second intervals). This opens
    a persistent connection that will be reused by all get_db() calls,
    avoiding connection overhead on each query.

    For services that don't call init_db() (e.g., web server), get_db()
    will create temporary per-request connections instead.

    Safe to call multiple times - uses IF NOT EXISTS clauses.
    Call close_db() on shutdown to close the persistent connection.
    """
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
        _logger.info(
            "Opened persistent database connection: %s", get_settings().db_path
        )

    conn = _db._connection
    if conn is None:
        raise DatabaseNotConnectedError()
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
    await conn.execute(_INIT_READING_SQL)
    await _db.executescript(_IDX_READING_SQL)
    await conn.execute(_INIT_PICO_SQL)
    await _db.executescript(_IDX_PICO_SQL)
    await conn.execute(_INIT_SETTINGS_SQL)
    await conn.execute(_INIT_ADMIN_SQL)
    await _init_admin_password()


async def _init_admin_password() -> None:
    """Initialize admin password from ADMIN_PASSWORD env var if not already set."""
    from os import environ

    from rpi.server.auth import hash_password

    existing = await get_admin_password_hash()
    if existing is not None:
        return

    admin_password = environ.get("ADMIN_PASSWORD", "")
    if not admin_password:
        _logger.warning(
            "No admin password configured. Set ADMIN_PASSWORD in .env to enable admin UI."
        )
        return

    password_hash = hash_password(admin_password)
    await set_admin_password_hash(password_hash)
    _logger.info("Admin password initialized from environment")


async def close_db() -> None:
    """Close the persistent database connection and connection pool.

    Should be called on application shutdown.
    """
    global _db, _pool
    if _db is not None:
        await _db.close()
        _logger.info("Closed persistent database connection")
        _db = None

    # Close all pooled connections
    if _pool:
        for conn in _pool:
            await conn.close()
        _logger.info("Closed %d pooled database connections", len(_pool))
        _pool = []


def _calculate_bucket_size(
    from_time: datetime, target_points: int = 500
) -> int:
    """Calculate time bucket size in seconds to achieve target data points.

    Returns bucket size that will aggregate readings into ~target_points.
    Minimum bucket is 1 second (no aggregation for short ranges).
    """
    total_seconds = int((datetime.now(UTC) - from_time).total_seconds())
    bucket = max(1, total_seconds // target_points)
    return bucket


async def get_initial_dht_data(from_time: datetime) -> list[DHTReading]:
    """Return DHT22 sensor data from a given time, downsampled for charts."""
    bucket = _calculate_bucket_size(from_time)
    async with get_db() as db:
        rows = await db.fetchall(
            _DHT_CHART_SQL, {"from_time": from_time, "bucket": bucket}
        )
        return cast(list[DHTReading], rows)


async def get_latest_dht_data() -> DHTReading | None:
    """Return the latest DHT22 sensor data."""
    async with get_db() as db:
        row = await db.fetchone(_DHT_LATEST_SQL)
        return cast(DHTReading | None, row)


async def get_stats_dht_data(from_time: datetime) -> DHTStats | None:
    """Return statistics for the DHT22 sensor data from a given time."""
    async with get_db() as db:
        row = await db.fetchone(_DHT_STATS_SQL, (from_time,))
        return cast(DHTStats | None, row)


async def get_initial_pico_data(
    from_time: datetime,
) -> list[PicoChartDataPoint]:
    """Return Pico sensor data from a given time, downsampled and pivoted."""
    bucket = _calculate_bucket_size(from_time)
    async with get_db() as db:
        rows = await db.fetchall(
            _PICO_CHART_SQL, {"from_time": from_time, "bucket": bucket}
        )

    # Pivot: group by epoch, with plant_id as columns
    pivoted: dict[int, dict[str, Any]] = {}
    for row in rows:
        epoch: int = row["epoch"]
        if epoch not in pivoted:
            pivoted[epoch] = {"epoch": epoch}
        pivoted[epoch][str(row["plant_id"])] = row["moisture"]

    return cast(list[PicoChartDataPoint], list(pivoted.values()))


async def get_latest_pico_data() -> list[PicoReading]:
    """Return the latest Pico sensor data for each plant."""
    async with get_db() as db:
        rows = await db.fetchall(_PICO_LATEST_SQL)
        return cast(list[PicoReading], rows)


async def get_all_settings() -> dict[SettingsKey, str]:
    """Get all settings as a dictionary."""
    async with get_db() as db:
        rows = await db.fetchall("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in rows}


async def set_settings_batch(settings: dict[SettingsKey, str]) -> None:
    """Set multiple settings in a single transaction."""
    async with get_db() as db, db.transaction():
        for key, value in settings.items():
            await db.execute(
                """INSERT INTO settings (key, value, updated_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(key) DO UPDATE SET
                       value = excluded.value,
                       updated_at = excluded.updated_at""",
                (key, value),
            )


async def get_admin_password_hash() -> str | None:
    """Get the admin password hash."""
    async with get_db() as db:
        row = await db.fetchone("SELECT password_hash FROM admin WHERE id = 1")
        return row["password_hash"] if row else None


async def set_admin_password_hash(password_hash: str) -> None:
    """Set or update the admin password hash."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO admin (id, password_hash, updated_at)
               VALUES (1, ?, datetime('now'))
               ON CONFLICT(id) DO UPDATE SET
                   password_hash = excluded.password_hash,
                   updated_at = excluded.updated_at""",
            (password_hash,),
        )
