from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute

from rpi.lib.db import close_async_db, get_async_db
from rpi.logging import configure

from .api.dashboard import get_dashboard
from .api.health import health_check
from .api.thresholds import get_thresholds
from .websockets import ws_dht_latest, ws_dht_stats, ws_pico_latest


@asynccontextmanager
async def lifespan(app):
    """Configure logging and database on startup, cleanup on shutdown."""
    configure()
    # Initialize the async database connection pool
    await get_async_db()
    yield
    # Close the database connection on shutdown
    await close_async_db()


routes = [
    Route("/health", health_check),
    Route("/api/dashboard", get_dashboard),
    Route("/api/thresholds", get_thresholds),
    WebSocketRoute("/dht/latest", ws_dht_latest),
    WebSocketRoute("/dht/stats", ws_dht_stats),
    WebSocketRoute("/pico/latest", ws_pico_latest),
]

app = Starlette(routes=routes, lifespan=lifespan)
