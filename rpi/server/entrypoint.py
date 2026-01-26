"""Application factory for the web server."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

import redis.asyncio as aioredis
from starlette.applications import Starlette
from starlette.routing import Route

from rpi.lib.config import get_settings
from rpi.lib.db import close_db, get_db
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.logging import configure, get_logger
from rpi.server.api.admin import get_admin_settings, update_admin_settings
from rpi.server.api.dashboard import get_dashboard
from rpi.server.api.health import health_check
from rpi.server.api.thresholds import get_thresholds
from rpi.server.sse import (
    HUMIDIFIER_STATE_KEY,
    sse_dht_latest,
    sse_humidifier_state,
    sse_pico_latest,
)

_logger = get_logger("server.entrypoint")


async def _store_humidifier_state(data: dict[str, Any]) -> None:
    """Store humidifier state in Redis for retrieval on SSE connect."""
    try:
        async with aioredis.from_url(get_settings().redis_url) as client:
            await client.set(HUMIDIFIER_STATE_KEY, json.dumps(data))
    except (aioredis.RedisError, OSError) as e:
        _logger.warning("Failed to store humidifier state: %s", e)


async def _humidifier_state_task(subscriber: EventSubscriber) -> None:
    """Background task that stores humidifier state for new client connections."""
    async for topic, data in subscriber.receive():
        if topic == Topic.HUMIDIFIER_STATE:
            await _store_humidifier_state(data)
            _logger.debug("Stored humidifier state")


async def _init_db_pool() -> None:
    """Pre-warm database connection pool with optimized settings."""
    async with get_db() as db:
        await db.execute_pragma("PRAGMA journal_mode=WAL")
        await db.execute_pragma("PRAGMA synchronous=NORMAL")
        await db.execute_pragma("PRAGMA cache_size=-64000")  # 64MB
    _logger.info("Database connection pool initialized")


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    """Application lifespan manager for startup/shutdown tasks."""
    await _init_db_pool()

    # Subscribe only to humidifier state to store it for new connections
    async with EventSubscriber(topics=[Topic.HUMIDIFIER_STATE]) as subscriber:
        subscriber_task = asyncio.create_task(_humidifier_state_task(subscriber))
        _logger.info("Humidifier state subscriber started")

        try:
            yield
        finally:
            subscriber_task.cancel()
            with suppress(asyncio.CancelledError):
                await subscriber_task
            _logger.info("Humidifier state subscriber stopped")
            await close_db()
            _logger.info("Database connections closed")


def create_app() -> Starlette:
    """Create and configure the Starlette application.

    Database connections are created per-request via get_db() context manager,
    which provides better concurrency and isolation for the web server.
    Polling services use init_db() for persistent connections instead.

    Returns:
        Configured Starlette application instance.
    """
    configure()

    routes = [
        Route("/health", health_check),
        Route("/api/dashboard", get_dashboard),
        Route("/api/thresholds", get_thresholds),
        Route("/api/admin/settings", get_admin_settings),
        Route("/api/admin/settings", update_admin_settings, methods=["PUT"]),
        Route("/sse/dht/latest", sse_dht_latest),
        Route("/sse/pico/latest", sse_pico_latest),
        Route("/sse/humidifier/state", sse_humidifier_state),
    ]

    return Starlette(routes=routes, lifespan=lifespan)
