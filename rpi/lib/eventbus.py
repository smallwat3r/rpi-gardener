"""Redis-based event bus for real-time sensor data broadcasting.

Provides pub/sub messaging between polling services (publishers) and
the web server/notification service (subscribers) for real-time updates.

Includes automatic reconnection with exponential backoff on connection failures.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

import redis
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from rpi.lib.config import Unit, get_settings
from rpi.logging import get_logger

logger = get_logger("lib.eventbus")

# Reconnection settings
_INITIAL_BACKOFF_SEC = 1.0
_MAX_BACKOFF_SEC = 60.0
_BACKOFF_MULTIPLIER = 2.0


class Topic(StrEnum):
    """Event bus topics for pub/sub channels."""

    DHT_READING = "dht.reading"
    PICO_READING = "pico.reading"
    ALERT = "alert"
    HUMIDIFIER_STATE = "humidifier.state"


@dataclass(frozen=True, slots=True)
class _Event(ABC):
    """Base class for all event bus payloads."""

    @property
    @abstractmethod
    def topic(self) -> Topic:
        """Topic this event should be published to."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""


@dataclass(frozen=True, slots=True)
class DHTReadingEvent(_Event):
    """DHT sensor reading event."""

    temperature: float
    humidity: float
    recording_time: datetime

    @property
    def topic(self) -> Topic:
        return Topic.DHT_READING

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.topic,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "recording_time": self.recording_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "epoch": int(self.recording_time.timestamp() * 1000),
        }


@dataclass(frozen=True, slots=True)
class PicoReadingEvent(_Event):
    """Single plant moisture reading."""

    plant_id: int
    moisture: float
    recording_time: datetime

    @property
    def topic(self) -> Topic:
        return Topic.PICO_READING

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.topic,
            "plant_id": self.plant_id,
            "moisture": self.moisture,
            "recording_time": self.recording_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "epoch": int(self.recording_time.timestamp() * 1000),
        }


@dataclass(frozen=True, slots=True)
class AlertEventPayload(_Event):
    """Alert event for threshold violations and resolutions."""

    namespace: str
    sensor_name: str | int
    value: float
    unit: Unit
    threshold: float | None
    recording_time: datetime
    is_resolved: bool = False

    @property
    def topic(self) -> Topic:
        return Topic.ALERT

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.topic,
            "namespace": self.namespace,
            "sensor_name": self.sensor_name,
            "value": self.value,
            "unit": self.unit,
            "threshold": self.threshold,
            "recording_time": self.recording_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "is_resolved": self.is_resolved,
        }


@dataclass(frozen=True, slots=True)
class HumidifierStateEvent(_Event):
    """Humidifier on/off state change event."""

    is_on: bool
    recording_time: datetime

    @property
    def topic(self) -> Topic:
        return Topic.HUMIDIFIER_STATE

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.topic,
            "is_on": self.is_on,
            "recording_time": self.recording_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }


# Type alias for any concrete event type
type _AnyEvent = (
    DHTReadingEvent
    | PicoReadingEvent
    | AlertEventPayload
    | HumidifierStateEvent
)


class EventPublisher:
    """Publishes sensor readings to the event bus.

    Used by polling services (DHT, Pico) to broadcast new readings.
    Automatically reconnects on connection failures.
    """

    def __init__(self) -> None:
        self._redis_url = get_settings().eventbus.redis_url
        self._client: redis.Redis[bytes] | None = None

    def connect(self) -> None:
        """Connect to Redis."""
        self._client = redis.from_url(self._redis_url)
        logger.info("Event publisher connected to Redis")

    def _reconnect(self) -> bool:
        """Attempt to reconnect to Redis.

        Returns True if reconnection succeeded, False otherwise.
        """
        try:
            self.close()
            self.connect()
            return True
        except RedisError as e:
            logger.warning("Failed to reconnect to Redis: %s", e)
            return False

    def publish(self, data: _Event | Sequence[_Event]) -> None:
        """Publish event(s) to the event bus.

        The topic is derived from the event's topic property.
        Attempts to reconnect once on connection failure.
        """
        if self._client is None:
            first = data if isinstance(data, _Event) else data[0]
            logger.warning(
                "Cannot publish to %s: Redis client not connected. "
                "Call connect() first.",
                first.topic,
            )
            return

        if isinstance(data, _Event):
            topic = data.topic
            payload: list[dict[str, Any]] | dict[str, Any] = data.to_dict()
        else:
            topic = data[0].topic
            payload = [event.to_dict() for event in data]

        message = json.dumps(payload)

        try:
            self._client.publish(topic, message)
            logger.debug("Published to %s: %s", topic, message)
        except RedisError as e:
            logger.warning("Publish failed, attempting reconnect: %s", e)
            if self._reconnect():
                try:
                    self._client.publish(topic, message)
                    logger.debug("Published to %s after reconnect", topic)
                except RedisError as retry_error:
                    logger.error(
                        "Publish failed after reconnect: %s", retry_error
                    )
            else:
                logger.error(
                    "Could not publish to %s: reconnect failed", topic
                )

    def close(self) -> None:
        """Close the publisher connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
        logger.info("Event publisher closed")

    def __enter__(self) -> Self:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        """Context manager exit."""
        self.close()


class EventSubscriber:
    """Subscribes to sensor readings from the event bus.

    Used by the web server and notification service to receive real-time updates.
    Automatically reconnects with exponential backoff on connection failures.
    """

    def __init__(self, topics: list[Topic] | None = None) -> None:
        """Initialize subscriber.

        Args:
            topics: List of topics to subscribe to. If None, subscribes to all.
        """
        self._redis_url = get_settings().eventbus.redis_url
        self._topics = topics or list(Topic)
        self._client: aioredis.Redis[bytes] | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._backoff = _INITIAL_BACKOFF_SEC

    async def connect(self) -> None:
        """Connect to Redis and subscribe to topics."""
        self._client = aioredis.from_url(self._redis_url)
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(*self._topics)
        self._backoff = _INITIAL_BACKOFF_SEC  # Reset on successful connect
        logger.info(
            "Event subscriber connected to Redis, topics: %s", self._topics
        )

    async def _reconnect(self) -> None:
        """Reconnect to Redis with exponential backoff."""
        await self.close()

        while True:
            logger.info(
                "Reconnecting to Redis in %.1f seconds...", self._backoff
            )
            await asyncio.sleep(self._backoff)

            try:
                await self.connect()
                logger.info("Successfully reconnected to Redis")
                return
            except (RedisError, OSError) as e:
                logger.warning("Reconnection attempt failed: %s", e)
                self._backoff = min(
                    self._backoff * _BACKOFF_MULTIPLIER, _MAX_BACKOFF_SEC
                )

    async def receive(self) -> AsyncIterator[tuple[Topic, dict[str, Any]]]:
        """Async iterator that yields (topic, data) tuples as they arrive.

        Automatically reconnects on connection failures and resumes listening.
        """
        while self._pubsub is not None:
            try:
                async for message in self._pubsub.listen():
                    if message["type"] != "message":
                        continue

                    try:
                        topic = Topic(message["channel"].decode())
                        data = json.loads(message["data"].decode())
                        yield topic, data
                    except (ValueError, json.JSONDecodeError) as e:
                        logger.warning("Invalid message: %s", e)
                return  # Iterator exhausted (e.g., connection closed cleanly)
            except (RedisError, OSError) as e:
                logger.error("Redis connection lost: %s", e)
                await self._reconnect()

    async def close(self) -> None:
        """Close the subscriber connection."""
        if self._pubsub is not None:
            # Ignore errors if connection already broken
            with suppress(RedisError, OSError):
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
            self._pubsub = None
        if self._client is not None:
            # Ignore errors if connection already broken
            with suppress(RedisError, OSError):
                await self._client.close()
            self._client = None
        logger.info("Event subscriber closed")

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Async context manager exit."""
        await self.close()
