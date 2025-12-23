"""WebSocket routes for the RPi Gardener application."""
import asyncio
from datetime import datetime
from typing import Any, Callable

from starlette.websockets import WebSocket, WebSocketDisconnect

from rpi import logging
from rpi.lib.config import POLLING_FREQUENCY_SEC
from rpi.lib.db import (
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)
from rpi.lib.params import parse_hours

_logger = logging.getLogger("websockets")


async def _stream_data(
    websocket: WebSocket,
    fetch_fn: Callable[[], Any],
    endpoint: str,
) -> None:
    """Stream data to a WebSocket client at regular intervals."""
    await websocket.accept()
    client_id = id(websocket)
    _logger.info("Client %s connected to %s", client_id, endpoint)

    try:
        while True:
            await asyncio.sleep(POLLING_FREQUENCY_SEC)
            try:
                await websocket.send_json(fetch_fn())
            except WebSocketDisconnect:
                raise
            except Exception as e:
                _logger.error("Error streaming to client %s: %s", client_id, e)
    except WebSocketDisconnect:
        _logger.info("Client %s disconnected", client_id)


def _parse_hours(websocket: WebSocket) -> datetime:
    """Parse hours query param and return from_time datetime."""
    _, from_time = parse_hours(websocket.query_params, strict=False)
    return from_time


async def ws_dht_latest(websocket: WebSocket) -> None:
    """Stream latest DHT sensor readings."""
    await _stream_data(websocket, get_latest_dht_data, "/dht/latest")


async def ws_dht_stats(websocket: WebSocket) -> None:
    """Stream DHT sensor statistics."""
    from_time = _parse_hours(websocket)
    await _stream_data(
        websocket,
        lambda: get_stats_dht_data(from_time),
        "/dht/stats",
    )


async def ws_pico_latest(websocket: WebSocket) -> None:
    """Stream latest Pico sensor readings."""
    await _stream_data(websocket, get_latest_pico_data, "/pico/latest")
