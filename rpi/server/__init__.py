from starlette.applications import Starlette
from starlette.routing import Mount, Route, WebSocketRoute

from .api.dashboard import get_dashboard
from .api.health import health_check
from .api.pico import receive_pico_data
from .spa import serve_spa, serve_static
from .websockets import ws_dht_latest, ws_dht_stats, ws_pico_latest

routes = [
    Route("/health", health_check),
    Route("/pico", receive_pico_data, methods=["POST"]),
    Route("/api/dashboard", get_dashboard),
    WebSocketRoute("/dht/latest", ws_dht_latest),
    WebSocketRoute("/dht/stats", ws_dht_stats),
    WebSocketRoute("/pico/latest", ws_pico_latest),
    Route("/", serve_spa),
    Route("/{path:path}", serve_static),
]

app = Starlette(routes=routes)
