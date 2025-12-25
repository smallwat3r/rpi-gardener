"""Application factory for the web server."""
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute

from rpi.logging import configure

from .api.dashboard import get_dashboard
from .api.health import health_check
from .api.thresholds import get_thresholds
from .websockets import ws_dht_latest, ws_dht_stats, ws_pico_latest


def create_app() -> Starlette:
    """Create and configure the Starlette application.

    Returns:
        Configured Starlette application instance.
    """
    configure()

    routes = [
        Route("/health", health_check),
        Route("/api/dashboard", get_dashboard),
        Route("/api/thresholds", get_thresholds),
        WebSocketRoute("/dht/latest", ws_dht_latest),
        WebSocketRoute("/dht/stats", ws_dht_stats),
        WebSocketRoute("/pico/latest", ws_pico_latest),
    ]

    return Starlette(routes=routes)
