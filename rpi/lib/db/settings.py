"""Settings cache and database operations."""

from __future__ import annotations

import time
from typing import cast

import aiosqlite

from rpi.lib.config import SettingsKey, get_settings
from rpi.lib.db.connection import get_db
from rpi.logging import get_logger

_logger = get_logger("lib.db.settings")


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

    The version is incremented BEFORE the DB transaction to ensure cache
    invalidation even if the process crashes after DB commit. This guarantees
    other processes will refetch from the database rather than serving stale
    cached data.
    """
    # Increment version FIRST to invalidate caches in other processes.
    # This ensures that even if we crash after DB commit but before updating
    # local cache, other processes will see the version change and refetch.
    new_version = await _increment_settings_version()

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

    _settings_cache.set(cast(dict[str, str], all_settings), new_version)
    return all_settings
