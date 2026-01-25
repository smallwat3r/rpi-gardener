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

import asyncio
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict, cast

import aiosqlite

from rpi.lib.config import SettingsKey, get_settings

type SQLParams = tuple[Any, ...] | dict[str, Any]
"""SQL parameter types: positional tuple or named dict for query binding."""

from rpi.lib.exceptions import DatabaseNotConnectedError
from rpi.logging import get_logger

_logger = get_logger("lib.db")


class _SettingsCache:
    """TTL cache for settings with cross-process invalidation via Redis.

    Uses a version number stored in Redis to detect when settings have been
    modified by another process. This ensures all processes see updated settings
    immediately when changed via the admin API.
    """

    _REDIS_VERSION_KEY = "rpi:settings:version"

    def __init__(self, ttl_sec: float = 30.0) -> None:
        self._cache: dict[str, str] | None = None
        self._cache_time: float = 0.0
        self._cached_version: int = 0
        self._ttl_sec = ttl_sec

    def get(self, current_version: int | None) -> dict[str, str] | None:
        """Get cached settings if not expired and version matches.

        Returns None if current_version is None (Redis unavailable) to force
        a fresh fetch from the database.
        """
        if current_version is None:
            return None  # Redis unavailable, don't trust cache
        if self._cache is not None:
            version_valid = self._cached_version == current_version
            ttl_valid = (time.monotonic() - self._cache_time) < self._ttl_sec
            if version_valid and ttl_valid:
                return self._cache
        return None

    def set(self, settings: dict[str, str], version: int) -> None:
        """Update cache with fresh settings and version."""
        self._cache = settings
        self._cache_time = time.monotonic()
        self._cached_version = version

    def invalidate(self) -> None:
        """Clear the cache."""
        self._cache = None
        self._cache_time = 0.0
        self._cached_version = 0


_settings_cache = _SettingsCache()

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


class ConnectionPool:
    """Async connection pool with bounded concurrency.

    Limits concurrent database connections using a semaphore. Connections
    are reused when available, created on demand up to max_size.
    """

    def __init__(self, max_size: int = 5) -> None:
        self._max_size = max_size
        self._connections: list[Database] = []
        self._semaphore: asyncio.Semaphore | None = None
        self._closed = False

    def _get_semaphore(self) -> asyncio.Semaphore:
        # Lazy init: asyncio.Semaphore requires running event loop
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_size)
        return self._semaphore

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[Database]:
        """Acquire a connection from the pool."""
        if self._closed:
            raise DatabaseNotConnectedError("Connection pool is closed")
        async with self._get_semaphore():
            conn = self._connections.pop() if self._connections else Database()
            try:
                if conn._connection is None:
                    await conn.connect()
                yield conn
            except Exception:
                # Connection failed, close it to avoid returning a bad connection
                await conn.close()
                raise
            finally:
                self._connections.append(conn)

    async def close(self) -> None:
        """Close all pooled connections."""
        self._closed = True
        for conn in self._connections:
            await conn.close()
        count = len(self._connections)
        self._connections = []
        self._semaphore = None
        self._closed = False  # Allow pool reuse after close
        if count:
            _logger.info("Closed %d pooled connections", count)


# Module singletons
_persistent: Database | None = None
_pool = ConnectionPool()


class DHTReading(TypedDict):
    """DHT22 sensor reading from the database."""

    temperature: float
    humidity: float
    recording_time: str
    epoch: int


class PicoReading(TypedDict):
    """Pico moisture reading from the database."""

    plant_id: int
    moisture: float
    recording_time: str
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

    async def execute_pragma(self, pragma: str) -> None:
        """Execute a PRAGMA statement directly on the connection.

        Use this for connection-level settings like journal_mode, synchronous,
        or cache_size that need raw connection access.
        """
        if self._connection is None:
            raise DatabaseNotConnectedError()
        await self._connection.execute(pragma)


@asynccontextmanager
async def get_db() -> AsyncIterator[Database]:
    """Get a database connection.

    Uses persistent connection if init_db() was called, otherwise uses pool.

    Usage:
        async with get_db() as db:
            await db.execute("INSERT INTO ...")
    """
    if _persistent is not None:
        yield _persistent
    else:
        async with _pool.acquire() as db:
            yield db


async def init_db() -> None:
    """Initialize database with persistent connection and schema.

    Call this once at startup for polling services. Opens a long-lived
    connection reused by all get_db() calls. For web server (no init_db),
    get_db() uses the connection pool instead.
    """
    global _persistent
    if _persistent is None:
        _persistent = Database()
        await _persistent.connect()
        _logger.info(
            "Opened persistent database connection: %s", get_settings().db_path
        )

    await _persistent.execute_pragma("PRAGMA journal_mode=WAL")
    await _persistent.execute_pragma("PRAGMA auto_vacuum=INCREMENTAL")
    await _persistent.execute(_INIT_READING_SQL)
    await _persistent.executescript(_IDX_READING_SQL)
    await _persistent.execute(_INIT_PICO_SQL)
    await _persistent.executescript(_IDX_PICO_SQL)
    await _persistent.execute(_INIT_SETTINGS_SQL)
    await _persistent.execute(_INIT_ADMIN_SQL)
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
    """Close the persistent connection and connection pool."""
    global _persistent
    if _persistent is not None:
        await _persistent.close()
        _logger.info("Closed persistent database connection")
        _persistent = None

    await _pool.close()


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


async def get_latest_dht_data() -> DHTReading | None:
    """Return the latest DHT22 sensor data."""
    async with get_db() as db:
        row = await db.fetchone(_DHT_LATEST_SQL)
        return cast(DHTReading | None, row)


async def get_latest_pico_data() -> list[PicoReading]:
    """Return the latest Pico sensor data for each plant."""
    async with get_db() as db:
        rows = await db.fetchall(_PICO_LATEST_SQL)
        return cast(list[PicoReading], rows)


def _invalidate_settings_cache() -> None:
    """Invalidate the settings cache."""
    _settings_cache.invalidate()


async def _get_settings_version() -> int | None:
    """Get the current settings version from Redis.

    Returns None if Redis is unavailable, signaling that the cache should not
    be trusted (avoids version 0 collision with initial cache state).
    """
    import redis.asyncio as aioredis

    try:
        async with aioredis.from_url(get_settings().redis_url) as client:
            version = await client.get(_SettingsCache._REDIS_VERSION_KEY)
            return int(version) if version else 0
    except (aioredis.RedisError, OSError):
        # Redis unavailable - return None to bypass cache
        return None


async def _increment_settings_version() -> int:
    """Increment the settings version in Redis and return the new version."""
    import redis.asyncio as aioredis

    try:
        async with aioredis.from_url(get_settings().redis_url) as client:
            return await client.incr(_SettingsCache._REDIS_VERSION_KEY)
    except (aioredis.RedisError, OSError) as e:
        _logger.warning("Failed to increment settings version in Redis: %s", e)
        return 0


async def get_all_settings() -> dict[SettingsKey, str]:
    """Get all settings as a dictionary.

    Results are cached with cross-process invalidation via Redis version tracking.
    When settings are modified by any process, all processes see the update
    immediately on their next call.
    """
    version = await _get_settings_version()
    cached = _settings_cache.get(version)
    if cached is not None:
        return cached  # type: ignore[return-value]

    try:
        async with get_db() as db:
            rows = await db.fetchall("SELECT key, value FROM settings")
            result = {row["key"]: row["value"] for row in rows}
            # Only cache if we have a valid version from Redis
            if version is not None:
                _settings_cache.set(result, version)
    except (aiosqlite.Error, OSError) as e:
        _invalidate_settings_cache()
        _logger.warning("Failed to fetch settings, cache invalidated: %s", e)
        raise

    return result


async def set_settings_batch(
    settings: dict[SettingsKey, str],
) -> dict[SettingsKey, str]:
    """Set multiple settings in a single transaction.

    Returns the full settings dict after update. Increments the Redis version
    to invalidate caches in other processes.
    """
    async with get_db() as db, db.transaction():
        await db.executemany(
            """INSERT INTO settings (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = excluded.updated_at""",
            list(settings.items()),
        )
        # Fetch all settings within the same transaction for consistency
        rows = await db.fetchall("SELECT key, value FROM settings")
        all_settings: dict[SettingsKey, str] = {
            row["key"]: row["value"] for row in rows
        }

    # Increment version to invalidate caches in other processes
    new_version = await _increment_settings_version()
    _settings_cache.set(cast(dict[str, str], all_settings), new_version)
    return all_settings


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
