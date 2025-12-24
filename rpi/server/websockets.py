"""WebSocket routes for the RPi Gardener application."""
import asyncio
from contextlib import suppress
from datetime import datetime
from typing import Any, Awaitable, Callable

from starlette.websockets import WebSocket, WebSocketDisconnect

from rpi.lib.db import (get_latest_dht_data, get_latest_pico_data,
                        get_stats_dht_data)
from rpi.lib.config import settings
from rpi.logging import get_logger
from rpi.server.validators import parse_hours

_logger = get_logger("server.websockets")

# Type alias for async data fetchers
DataFetcher = Callable[[], Awaitable[Any]]

# Heartbeat interval in seconds (30s is typical for WebSocket keepalive)
_HEARTBEAT_INTERVAL_SEC = 30


class ConnectionManager:
    """Manages WebSocket connections for broadcasting and statistics."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._connection_count = 0

    async def connect(self, websocket: WebSocket, endpoint: str) -> int:
        """Accept a WebSocket connection and track it.

        Returns:
            A unique connection ID for this client.
        """
        await websocket.accept()
        if endpoint not in self._connections:
            self._connections[endpoint] = set()
        self._connections[endpoint].add(websocket)
        self._connection_count += 1
        client_id = id(websocket)
        _logger.info(
            "Client %s connected to %s (total: %d)",
            client_id, endpoint, len(self._connections[endpoint])
        )
        return client_id

    def disconnect(self, websocket: WebSocket, endpoint: str) -> None:
        """Remove a WebSocket connection from tracking."""
        if endpoint in self._connections:
            self._connections[endpoint].discard(websocket)
            if not self._connections[endpoint]:
                del self._connections[endpoint]
        _logger.info(
            "Client %s disconnected from %s (remaining: %d)",
            id(websocket), endpoint,
            len(self._connections.get(endpoint, set()))
        )

    def get_connection_count(self, endpoint: str | None = None) -> int:
        """Get the number of active connections.

        Args:
            endpoint: If specified, count only connections to this endpoint.
                     If None, count all connections.
        """
        if endpoint is not None:
            return len(self._connections.get(endpoint, set()))
        return sum(len(clients) for clients in self._connections.values())

    def get_endpoints(self) -> list[str]:
        """Get a list of endpoints with active connections."""
        return list(self._connections.keys())

    async def broadcast(self, endpoint: str, data: Any) -> int:
        """Broadcast data to all connections on an endpoint.

        Returns:
            The number of clients that received the message.
        """
        if endpoint not in self._connections:
            return 0

        sent_count = 0
        disconnected: list[WebSocket] = []

        for websocket in self._connections[endpoint]:
            try:
                await websocket.send_json(data)
                sent_count += 1
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self._connections[endpoint].discard(ws)

        return sent_count


# Global connection manager
connection_manager = ConnectionManager()


async def _send_heartbeat(websocket: WebSocket, client_id: int) -> None:
    """Send periodic heartbeat pings to detect dead connections."""
    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL_SEC)
        try:
            await websocket.send_json({"type": "ping"})
        except Exception:
            _logger.debug("Heartbeat failed for client %s", client_id)
            raise WebSocketDisconnect()


async def _stream_data(
    websocket: WebSocket,
    fetch_fn: DataFetcher,
    endpoint: str,
) -> None:
    """Stream data to a WebSocket client at regular intervals."""
    client_id = await connection_manager.connect(websocket, endpoint)
    heartbeat_task: asyncio.Task | None = None

    try:
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(_send_heartbeat(websocket, client_id))

        while True:
            await asyncio.sleep(settings.polling.frequency_sec)
            try:
                data = await fetch_fn()
                await websocket.send_json(data)
            except WebSocketDisconnect:
                raise
            except Exception as e:
                _logger.error("Error streaming to client %s: %s", client_id, e)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        _logger.info("Connection to client %s cancelled (shutdown)", client_id)
        raise
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
        connection_manager.disconnect(websocket, endpoint)
        with suppress(Exception):
            await websocket.close()


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

    async def fetch_stats():
        return await get_stats_dht_data(from_time)

    await _stream_data(websocket, fetch_stats, "/dht/stats")


async def ws_pico_latest(websocket: WebSocket) -> None:
    """Stream latest Pico sensor readings."""
    await _stream_data(websocket, get_latest_pico_data, "/pico/latest")
