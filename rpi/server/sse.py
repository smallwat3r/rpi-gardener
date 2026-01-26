"""Server-Sent Events routes for the RPi Gardener application.

SSE connections receive real-time updates via Redis pub/sub.
Each client gets its own subscription that yields events as they arrive.
"""

import json
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

import redis.asyncio as aioredis
from starlette.requests import Request
from starlette.responses import StreamingResponse

from rpi.lib.config import get_settings
from rpi.lib.db import get_latest_dht_data, get_latest_pico_data
from rpi.lib.eventbus import Topic
from rpi.logging import get_logger

_logger = get_logger("server.sse")

# Redis key for storing last humidifier state (shared with entrypoint.py)
HUMIDIFIER_STATE_KEY = "humidifier:last_state"


async def _subscribe_to_topic(topic: Topic) -> AsyncIterator[dict[str, Any]]:
    """Subscribe to a Redis topic and yield events as they arrive."""
    redis_url = get_settings().eventbus.redis_url
    client: aioredis.Redis[bytes] | None = None
    pubsub: aioredis.client.PubSub | None = None

    try:
        client = aioredis.from_url(redis_url)
        pubsub = client.pubsub()
        await pubsub.subscribe(str(topic))
        _logger.debug("Subscribed to Redis topic: %s", topic)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"].decode())
                yield data
            except (ValueError, json.JSONDecodeError) as e:
                _logger.warning("Invalid message on %s: %s", topic, e)
    except (aioredis.RedisError, OSError) as e:
        _logger.error("Redis connection error on %s: %s", topic, e)
    finally:
        if pubsub is not None:
            with suppress(aioredis.RedisError, OSError):
                await pubsub.unsubscribe()
                await pubsub.close()
        if client is not None:
            with suppress(aioredis.RedisError, OSError):
                await client.close()
        _logger.debug("Unsubscribed from topic: %s", topic)


def _sse_response(generator: AsyncIterator[str]) -> StreamingResponse:
    """Create an SSE streaming response."""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def _event_generator(
    request: Request,
    endpoint: str,
    topic: Topic,
    initial_data: Any = None,
) -> AsyncIterator[str]:
    """Generate SSE events for a client.

    Sends initial data if available, then streams updates from Redis pub/sub.
    """
    _logger.info("SSE client connected to %s", endpoint)
    try:
        if initial_data is not None:
            yield f"data: {json.dumps(initial_data)}\n\n"

        async for data in _subscribe_to_topic(topic):
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(data)}\n\n"
    finally:
        _logger.info("SSE client disconnected from %s", endpoint)


async def sse_dht_latest(request: Request) -> StreamingResponse:
    """Stream latest DHT sensor readings via SSE.

    Sends current reading on connect, then receives updates via Redis pub/sub.
    """
    initial_data = await get_latest_dht_data()
    return _sse_response(
        _event_generator(
            request, "/sse/dht/latest", Topic.DHT_READING, initial_data
        )
    )


async def sse_pico_latest(request: Request) -> StreamingResponse:
    """Stream latest Pico sensor readings via SSE.

    Sends current readings on connect, then receives updates via Redis pub/sub.
    """
    initial_data = await get_latest_pico_data()
    return _sse_response(
        _event_generator(
            request, "/sse/pico/latest", Topic.PICO_READING, initial_data
        )
    )


async def _get_last_humidifier_state() -> dict[str, Any] | None:
    """Fetch the last stored humidifier state from Redis."""
    try:
        async with aioredis.from_url(get_settings().redis_url) as client:
            data = await client.get(HUMIDIFIER_STATE_KEY)
            if data:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed
                _logger.warning("Humidifier state is not a dict: %s", type(parsed))
    except (aioredis.RedisError, OSError, json.JSONDecodeError) as e:
        _logger.warning("Failed to fetch humidifier state: %s", e)
    return None


async def sse_humidifier_state(request: Request) -> StreamingResponse:
    """Stream humidifier on/off state changes via SSE.

    Sends last known state on connect, then receives updates via Redis pub/sub.
    """
    initial_data = await _get_last_humidifier_state()
    return _sse_response(
        _event_generator(
            request, "/sse/humidifier/state", Topic.HUMIDIFIER_STATE, initial_data
        )
    )
