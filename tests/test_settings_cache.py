"""Tests for the settings cache with cross-process invalidation."""

from contextlib import asynccontextmanager
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rpi.lib.config import SettingsKey
from rpi.lib.db import (
    _get_settings_version,
    _increment_settings_version,
    _settings_cache,
    _SettingsCache,
    get_all_settings,
    set_settings_batch,
)


class TestSettingsCache:
    """Tests for _SettingsCache class."""

    def test_get_returns_none_when_empty(self):
        """Empty cache returns None."""
        cache = _SettingsCache()
        assert cache.get(current_version=0) is None

    def test_get_returns_cached_data_when_version_matches(self):
        """Cache returns data when version matches."""
        cache = _SettingsCache()
        cache.set({"key": "value"}, version=1)

        result = cache.get(current_version=1)
        assert result == {"key": "value"}

    def test_get_returns_none_when_version_differs(self):
        """Cache returns None when version has changed."""
        cache = _SettingsCache()
        cache.set({"key": "value"}, version=1)

        result = cache.get(current_version=2)
        assert result is None

    def test_invalidate_clears_cache(self):
        """Invalidate clears all cached data."""
        cache = _SettingsCache()
        cache.set({"key": "value"}, version=1)

        cache.invalidate()

        assert cache.get(current_version=1) is None
        assert cache._cache is None
        assert cache._cached_version == 0


class TestGetSettingsVersion:
    """Tests for _get_settings_version function."""

    @pytest.mark.asyncio
    async def test_returns_version_from_redis(self):
        """Returns version stored in Redis."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=b"5")

        @asynccontextmanager
        async def mock_from_url(*args, **kwargs):
            yield mock_client

        with patch("redis.asyncio.from_url", mock_from_url):
            version = await _get_settings_version()

        assert version == 5

    @pytest.mark.asyncio
    async def test_returns_zero_when_key_missing(self):
        """Returns 0 when version key doesn't exist."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)

        @asynccontextmanager
        async def mock_from_url(*args, **kwargs):
            yield mock_client

        with patch("redis.asyncio.from_url", mock_from_url):
            version = await _get_settings_version()

        assert version == 0

    @pytest.mark.asyncio
    async def test_returns_none_on_redis_error(self):
        """Returns None when Redis is unavailable to bypass cache."""
        from redis.exceptions import RedisError

        @asynccontextmanager
        async def mock_from_url(*args, **kwargs):
            raise RedisError("Connection failed")
            yield  # pragma: no cover

        with patch("redis.asyncio.from_url", mock_from_url):
            version = await _get_settings_version()

        assert version is None


class TestIncrementSettingsVersion:
    """Tests for _increment_settings_version function."""

    @pytest.mark.asyncio
    async def test_increments_and_returns_new_version(self):
        """Increments version in Redis and returns new value."""
        mock_client = AsyncMock()
        mock_client.incr = AsyncMock(return_value=6)

        @asynccontextmanager
        async def mock_from_url(*args, **kwargs):
            yield mock_client

        with patch("redis.asyncio.from_url", mock_from_url):
            version = await _increment_settings_version()

        assert version == 6
        mock_client.incr.assert_called_once_with(
            _SettingsCache._REDIS_VERSION_KEY
        )

    @pytest.mark.asyncio
    async def test_returns_zero_on_redis_error(self):
        """Returns 0 when Redis is unavailable."""
        from redis.exceptions import RedisError

        @asynccontextmanager
        async def mock_from_url(*args, **kwargs):
            raise RedisError("Connection failed")
            yield  # pragma: no cover

        with patch("redis.asyncio.from_url", mock_from_url):
            version = await _increment_settings_version()

        assert version == 0


class TestGetAllSettingsCache:
    """Tests for get_all_settings cache behavior."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset the settings cache before each test."""
        _settings_cache.invalidate()
        yield
        _settings_cache.invalidate()

    @pytest.mark.asyncio
    async def test_uses_cache_when_version_matches(self):
        """Returns cached data without DB query when version matches."""
        _settings_cache.set({"cached_key": "cached_value"}, version=1)

        with (
            patch("rpi.lib.db._get_settings_version", return_value=1),
            patch("rpi.lib.db.get_db") as mock_get_db,
        ):
            result = await get_all_settings()

        assert result == {"cached_key": "cached_value"}
        mock_get_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_from_db_when_version_changes(self):
        """Fetches fresh data when Redis version has changed."""
        _settings_cache.set({"old_key": "old_value"}, version=1)

        mock_db = MagicMock()
        mock_db.fetchall = AsyncMock(
            return_value=[{"key": "new_key", "value": "new_value"}]
        )

        @asynccontextmanager
        async def mock_get_db():
            yield mock_db

        with (
            patch("rpi.lib.db._get_settings_version", return_value=2),
            patch("rpi.lib.db.get_db", mock_get_db),
        ):
            result = await get_all_settings()

        assert result == {"new_key": "new_value"}
        mock_db.fetchall.assert_called_once()


class TestSetSettingsBatchCache:
    """Tests for set_settings_batch cache behavior."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset the settings cache before each test."""
        _settings_cache.invalidate()
        yield
        _settings_cache.invalidate()

    @pytest.mark.asyncio
    async def test_increments_version_after_update(self):
        """Increments Redis version after updating settings."""
        mock_db = MagicMock()
        mock_db.executemany = AsyncMock()
        mock_db.fetchall = AsyncMock(
            return_value=[{"key": "test_key", "value": "test_value"}]
        )

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_db.transaction = mock_transaction

        @asynccontextmanager
        async def mock_get_db():
            yield mock_db

        with (
            patch("rpi.lib.db.get_db", mock_get_db),
            patch(
                "rpi.lib.db._increment_settings_version", return_value=5
            ) as mock_incr,
        ):
            await set_settings_batch(
                cast(dict[SettingsKey, str], {"test_key": "test_value"})
            )

        mock_incr.assert_called_once()
        assert _settings_cache._cached_version == 5

    @pytest.mark.asyncio
    async def test_updates_cache_with_new_settings(self):
        """Updates local cache with new settings after batch update."""
        mock_db = MagicMock()
        mock_db.executemany = AsyncMock()
        mock_db.fetchall = AsyncMock(
            return_value=[
                {"key": "key1", "value": "value1"},
                {"key": "key2", "value": "value2"},
            ]
        )

        @asynccontextmanager
        async def mock_transaction():
            yield

        mock_db.transaction = mock_transaction

        @asynccontextmanager
        async def mock_get_db():
            yield mock_db

        with (
            patch("rpi.lib.db.get_db", mock_get_db),
            patch("rpi.lib.db._increment_settings_version", return_value=10),
        ):
            result = await set_settings_batch(
                cast(dict[SettingsKey, str], {"key1": "value1"})
            )

        assert result == {"key1": "value1", "key2": "value2"}
        # Cache should have the new data
        cached = _settings_cache.get(current_version=10)
        assert cached == {"key1": "value1", "key2": "value2"}
