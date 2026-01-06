"""WebSocket routes for the RPi Gardener application.

WebSocket connections receive real-time updates via Redis pub/sub.
The event subscriber (in entrypoint.py) broadcasts new readings to clients.
"""

import asyncio
import json
from contextlib import suppress
from typing import Any

import redis.asyncio as aioredis
from starlette.websockets import WebSocket, WebSocketDisconnect

from rpi.lib.config import get_settings
from rpi.lib.db import get_latest_dht_data, get_latest_pico_data
from rpi.logging import get_logger

_logger = get_logger("server.websockets")

# Heartbeat interval in seconds (30s is typical for WebSocket keepalive)
_HEARTBEAT_INTERVAL_SEC = 30


class ConnectionManager:
    """Manages WebSocket connections for broadcasting and statistics."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, endpoint: str) -> int:
        """Accept a WebSocket connection and track it.

        Returns:
            A unique connection ID for this client.
        """
        await websocket.accept()
        if endpoint not in self._connections:
            self._connections[endpoint] = set()
        self._connections[endpoint].add(websocket)
        client_id = id(websocket)
        _logger.info(
            "Client %s connected to %s (total: %d)",
            client_id,
            endpoint,
            len(self._connections[endpoint]),
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
            id(websocket),
            endpoint,
            len(self._connections.get(endpoint, set())),
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
            except (
                WebSocketDisconnect,
                RuntimeError,
                ConnectionResetError,
                OSError,
            ):
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
        except WebSocketDisconnect:
            raise
        except (RuntimeError, ConnectionResetError, OSError):
            _logger.debug("Heartbeat failed for client %s", client_id)
            raise WebSocketDisconnect() from None


async def _maintain_connection(
    websocket: WebSocket,
    endpoint: str,
    initial_data: Any = None,
) -> None:
    """Maintain a WebSocket connection for receiving broadcasts.

    Sends initial data on connect, then keeps the connection alive with
    heartbeats. Real-time updates arrive via broadcast from the event bus.
    """
    client_id = await connection_manager.connect(websocket, endpoint)
    heartbeat_task: asyncio.Task[None] | None = None

    try:
        # Send initial data if available
        if initial_data is not None:
            await websocket.send_json(initial_data)

        # Start heartbeat task and wait for disconnect
        heartbeat_task = asyncio.create_task(
            _send_heartbeat(websocket, client_id)
        )
        await heartbeat_task
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        _logger.info("Connection to client %s cancelled (shutdown)", client_id)
        raise
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect):
                await heartbeat_task
        connection_manager.disconnect(websocket, endpoint)
        with suppress(Exception):
            await websocket.close()


async def ws_dht_latest(websocket: WebSocket) -> None:
    """Stream latest DHT sensor readings.

    Sends current reading on connect, then receives updates via event bus.
    """
    initial_data = await get_latest_dht_data()
    await _maintain_connection(websocket, "/dht/latest", initial_data)


async def ws_pico_latest(websocket: WebSocket) -> None:
    """Stream latest Pico sensor readings.

    Sends current readings on connect, then receives updates via event bus.
    """
    initial_data = await get_latest_pico_data()
    await _maintain_connection(websocket, "/pico/latest", initial_data)


async def _get_last_humidifier_state() -> dict[str, Any] | None:
    """Fetch the last stored humidifier state from Redis."""
    from .entrypoint import HUMIDIFIER_STATE_KEY

    try:
        async with aioredis.from_url(get_settings().redis_url) as client:
            data = await client.get(HUMIDIFIER_STATE_KEY)
            if data:
                result: dict[str, Any] = json.loads(data)
                return result
    except (aioredis.RedisError, OSError, json.JSONDecodeError) as e:
        _logger.warning("Failed to fetch humidifier state: %s", e)
    return None


async def ws_humidifier_state(websocket: WebSocket) -> None:
    """Stream humidifier on/off state changes.

    Sends last known state on connect, then receives updates via event bus.
    """
    initial_data = await _get_last_humidifier_state()
    await _maintain_connection(websocket, "/humidifier/state", initial_data)
