"""Application factory for the web server."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute

from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.logging import configure, get_logger

from .api.admin import get_admin_settings, update_admin_settings
from .api.dashboard import get_dashboard
from .api.health import health_check
from .api.thresholds import get_thresholds
from .websockets import (
    connection_manager,
    ws_alerts,
    ws_dht_latest,
    ws_pico_latest,
)

_logger = get_logger("server.entrypoint")

# Map event bus topics to WebSocket endpoints
_TOPIC_TO_ENDPOINT = {
    Topic.DHT_READING: "/dht/latest",
    Topic.PICO_READING: "/pico/latest",
    Topic.ALERT: "/alerts",
}


async def _event_subscriber_task(subscriber: EventSubscriber) -> None:
    """Background task that receives events and broadcasts to WebSocket clients."""
    async for topic, data in subscriber.receive():
        endpoint = _TOPIC_TO_ENDPOINT.get(topic)
        if endpoint:
            count = await connection_manager.broadcast(endpoint, data)
            _logger.debug("Broadcast %s to %d clients", topic, count)


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    """Application lifespan manager for startup/shutdown tasks."""
    subscriber = EventSubscriber()
    await subscriber.connect()
    subscriber_task = asyncio.create_task(_event_subscriber_task(subscriber))
    _logger.info("Event bus subscriber started")

    try:
        yield
    finally:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
        await subscriber.close()
        _logger.info("Event bus subscriber stopped")


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
        WebSocketRoute("/dht/latest", ws_dht_latest),
        WebSocketRoute("/pico/latest", ws_pico_latest),
        WebSocketRoute("/alerts", ws_alerts),
    ]

    return Starlette(routes=routes, lifespan=lifespan)
