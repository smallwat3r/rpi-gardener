"""Database connection management.

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
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from functools import cache
from pathlib import Path
from typing import Any, cast

import aiosqlite

from rpi.lib.config import get_settings
from rpi.lib.db.types import SQLParams
from rpi.lib.exceptions import DatabaseNotConnectedError
from rpi.logging import get_logger

_logger = get_logger("lib.db")

# SQL templates directory
_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


@cache
def _load_template(name: str) -> str:
    """Load and cache a SQL template file.

    Templates are lazy-loaded on first access and cached for subsequent calls.

    Raises:
        FileNotFoundError: If the template file does not exist, with a message
            indicating the expected location.
    """
    path = _SQL_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"SQL template not found: {path}")
    return path.read_text()


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
    from .admin import _init_admin_password

    global _persistent
    if _persistent is None:
        _persistent = Database()
        await _persistent.connect()
        _logger.info(
            "Opened persistent database connection: %s", get_settings().db_path
        )

    await _persistent.execute_pragma("PRAGMA journal_mode=WAL")
    await _persistent.execute_pragma("PRAGMA auto_vacuum=INCREMENTAL")
    await _persistent.execute(_load_template("init_reading_table.sql"))
    await _persistent.executescript(_load_template("idx_reading.sql"))
    await _persistent.execute(_load_template("init_pico_reading_table.sql"))
    await _persistent.executescript(_load_template("idx_pico_reading.sql"))
    await _persistent.execute(_load_template("init_settings_table.sql"))
    await _persistent.execute(_load_template("init_admin_table.sql"))
    await _init_admin_password()


async def close_db() -> None:
    """Close the persistent connection and connection pool."""
    global _persistent
    if _persistent is not None:
        await _persistent.close()
        _logger.info("Closed persistent database connection")
        _persistent = None

    await _pool.close()
