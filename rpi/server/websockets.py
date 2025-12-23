"""WebSocket routes for the RPi Gardener application."""
import asyncio
from datetime import datetime, timedelta

from starlette.websockets import WebSocket, WebSocketDisconnect

from rpi import logging
from rpi.lib.config import POLLING_FREQUENCY_SEC
from rpi.lib.db import (
    get_latest_dht_data,
    get_latest_pico_data,
    get_stats_dht_data,
)

logger = logging.getLogger("websockets")

_DEFAULT_HOURS = 3


def _get_from_time(websocket: WebSocket) -> datetime:
    """Parse hours from query string and return the from_time datetime."""
    try:
        hours = int(websocket.query_params.get("hours", _DEFAULT_HOURS))
    except ValueError:
        hours = _DEFAULT_HOURS
    return datetime.utcnow() - timedelta(hours=max(1, min(24, hours)))


async def ws_dht_latest(websocket: WebSocket) -> None:
    """Stream latest DHT sensor readings."""
    await websocket.accept()
    client_id = id(websocket)
    logger.info("WebSocket client %s connected to /dht/latest", client_id)

    try:
        while True:
            await asyncio.sleep(POLLING_FREQUENCY_SEC)
            try:
                data = get_latest_dht_data()
                await websocket.send_json(data)
            except Exception as e:
                logger.error("Error fetching DHT data for client %s: %s", client_id, e)
    except WebSocketDisconnect:
        logger.info("WebSocket client %s disconnected", client_id)


async def ws_dht_stats(websocket: WebSocket) -> None:
    """Stream DHT sensor statistics."""
    await websocket.accept()
    client_id = id(websocket)
    from_time = _get_from_time(websocket)
    logger.info("WebSocket client %s connected to /dht/stats", client_id)

    try:
        while True:
            await asyncio.sleep(POLLING_FREQUENCY_SEC)
            try:
                data = get_stats_dht_data(from_time)
                await websocket.send_json(data)
            except Exception as e:
                logger.error("Error fetching DHT stats for client %s: %s", client_id, e)
    except WebSocketDisconnect:
        logger.info("WebSocket client %s disconnected", client_id)


async def ws_pico_latest(websocket: WebSocket) -> None:
    """Stream latest Pico sensor readings."""
    await websocket.accept()
    client_id = id(websocket)
    logger.info("WebSocket client %s connected to /pico/latest", client_id)

    try:
        while True:
            await asyncio.sleep(POLLING_FREQUENCY_SEC)
            try:
                data = get_latest_pico_data()
                await websocket.send_json(data)
            except Exception as e:
                logger.error("Error fetching Pico data for client %s: %s", client_id, e)
    except WebSocketDisconnect:
        logger.info("WebSocket client %s disconnected", client_id)
