"""Tests for the database connection pool."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.lib.db import ConnectionPool, get_db


class MockDB:
    """Mock database for concurrency tests."""

    def __init__(self, tracker: dict[str, int] | None = None):
        self._connection: bool | None = None
        self._tracker = tracker or {}

    async def connect(self) -> None:
        if "created" in self._tracker:
            self._tracker["created"] += 1
        if "current" in self._tracker:
            self._tracker["current"] += 1
            self._tracker["max"] = max(
                self._tracker["max"], self._tracker["current"]
            )
        self._connection = True

    async def close(self) -> None:
        if "current" in self._tracker:
            self._tracker["current"] -= 1


class TestConnectionPool:
    """Tests for ConnectionPool class."""

    @pytest.fixture
    def pool(self):
        """Create a fresh connection pool for each test."""
        return ConnectionPool(max_size=3)

    async def test_acquire_creates_connection_when_pool_empty(self, pool):
        """First acquire should create a new connection."""
        mock_db = MagicMock()
        mock_db._connection = None
        mock_db.connect = AsyncMock()

        with patch("rpi.lib.db.connection.Database", return_value=mock_db):
            async with pool.acquire() as conn:
                assert conn is mock_db
                mock_db.connect.assert_called_once()

    async def test_acquire_reuses_connection_from_pool(self, pool):
        """Second acquire should reuse the returned connection."""
        mock_db = MagicMock()
        mock_db._connection = True  # Already connected

        # Pre-populate the pool
        pool._connections.append(mock_db)

        async with pool.acquire() as conn:
            assert conn is mock_db

    async def test_connection_returned_to_pool_after_use(self, pool):
        """Connection should be returned to pool after context exits."""
        mock_db = MagicMock()
        mock_db._connection = None
        mock_db.connect = AsyncMock()

        with patch("rpi.lib.db.connection.Database", return_value=mock_db):
            async with pool.acquire():
                assert len(pool._connections) == 0

            # After exiting context, connection should be back in pool
            assert len(pool._connections) == 1
            assert pool._connections[0] is mock_db

    async def test_semaphore_limits_concurrent_connections(self):
        """Semaphore should limit concurrent connections to max_size."""
        tracker = {"created": 0, "current": 0, "max": 0}
        pool = ConnectionPool(max_size=3)

        async def worker() -> None:
            async with pool._get_semaphore():
                conn = (
                    pool._connections.pop()
                    if pool._connections
                    else MockDB(tracker)
                )
                if conn._connection is None:
                    await conn.connect()
                try:
                    await asyncio.sleep(0.02)
                finally:
                    pool._connections.append(conn)  # type: ignore[arg-type]

        await asyncio.gather(*[worker() for _ in range(10)])

        assert tracker["max"] <= 3, (
            f"Max concurrent {tracker['max']} exceeded limit 3"
        )

    async def test_connections_reused_under_load(self):
        """Pool should reuse connections, not create new ones for each request."""
        tracker = {"created": 0, "current": 0, "max": 0}
        pool = ConnectionPool(max_size=3)

        async def worker() -> None:
            async with pool._get_semaphore():
                conn = (
                    pool._connections.pop()
                    if pool._connections
                    else MockDB(tracker)
                )
                if conn._connection is None:
                    await conn.connect()
                try:
                    await asyncio.sleep(0.01)
                finally:
                    pool._connections.append(conn)  # type: ignore[arg-type]

        await asyncio.gather(*[worker() for _ in range(20)])

        assert tracker["created"] == 3, (
            f"Created {tracker['created']} connections, expected 3"
        )

    async def test_close_closes_all_connections(self, pool):
        """close() should close all pooled connections."""
        mock_db1 = AsyncMock()
        mock_db2 = AsyncMock()
        pool._connections = [mock_db1, mock_db2]

        await pool.close()

        mock_db1.close.assert_called_once()
        mock_db2.close.assert_called_once()
        assert pool._connections == []
        assert pool._semaphore is None

    async def test_close_on_empty_pool(self, pool):
        """close() should handle empty pool gracefully."""
        await pool.close()  # Should not raise
        assert pool._connections == []


class TestGetDb:
    """Tests for get_db() function."""

    @pytest.fixture
    def db_module(self):
        """Provide db module with automatic state restoration."""
        import rpi.lib.db.connection as db

        original_persistent = db._persistent
        original_pool = db._pool

        yield db

        db._persistent = original_persistent
        db._pool = original_pool

    async def test_uses_persistent_connection_when_available(self, db_module):
        """get_db() should use persistent connection if set."""
        mock_persistent = MagicMock()
        db_module._persistent = mock_persistent

        async with get_db() as conn:
            assert conn is mock_persistent

    async def test_uses_pool_when_no_persistent_connection(self, db_module):
        """get_db() should use pool when persistent is None."""
        mock_db = MagicMock()
        mock_db._connection = None
        mock_db.connect = AsyncMock()
        mock_db.close = AsyncMock()

        db_module._persistent = None
        db_module._pool = ConnectionPool(max_size=2)

        with patch("rpi.lib.db.connection.Database", return_value=mock_db):
            async with get_db() as conn:
                assert conn is mock_db

    async def test_concurrent_requests_limited_by_pool(self, db_module):
        """Concurrent get_db() calls should be limited by pool size."""
        tracker = {"created": 0, "current": 0, "max": 0}

        class MockDatabase(MockDB):
            def __init__(self, *args, **kwargs):
                super().__init__(tracker)

        db_module._persistent = None
        db_module._pool = ConnectionPool(max_size=2)

        with patch("rpi.lib.db.connection.Database", MockDatabase):

            async def worker() -> None:
                async with get_db():
                    await asyncio.sleep(0.01)

            await asyncio.gather(*[worker() for _ in range(10)])

        assert tracker["max"] <= 2
