"""ZeroMQ-based event bus for real-time sensor data broadcasting.

Provides pub/sub messaging between polling services (publishers) and
the web server (subscriber) for real-time WebSocket updates.
"""
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

import zmq
import zmq.asyncio

from rpi.lib.config import get_settings
from rpi.logging import get_logger

logger = get_logger("lib.eventbus")


class Topic(StrEnum):
    """Event bus topics."""
    DHT_READING = "dht.reading"
    PICO_READING = "pico.reading"
    ALERT = "alert"


@dataclass(frozen=True, slots=True)
class Event(ABC):
    """Base class for all event bus payloads."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""


@dataclass(frozen=True, slots=True)
class DHTReadingEvent(Event):
    """DHT sensor reading event."""
    temperature: float
    humidity: float
    recording_time: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature": self.temperature,
            "humidity": self.humidity,
            "recording_time": self.recording_time.strftime("%Y-%m-%d %H:%M:%S"),
            "epoch": int(self.recording_time.timestamp() * 1000),
        }


@dataclass(frozen=True, slots=True)
class PicoReadingEvent(Event):
    """Single plant moisture reading."""
    plant_id: int
    moisture: float
    recording_time: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "plant_id": self.plant_id,
            "moisture": self.moisture,
            "recording_time": self.recording_time.strftime("%Y-%m-%d %H:%M:%S"),
            "epoch": int(self.recording_time.timestamp() * 1000),
        }


@dataclass(frozen=True, slots=True)
class AlertEventPayload(Event):
    """Alert event for threshold violations and resolutions."""
    namespace: str
    sensor_name: str | int
    value: float
    unit: str
    threshold: float | None
    recording_time: datetime
    is_resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "sensor_name": self.sensor_name,
            "value": self.value,
            "unit": self.unit,
            "threshold": self.threshold,
            "recording_time": self.recording_time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_resolved": self.is_resolved,
        }


class EventPublisher:
    """Publishes sensor readings to the event bus.

    Used by polling services (DHT, Pico) to broadcast new readings.
    Non-blocking: if no subscribers are connected, messages are dropped.
    """

    def __init__(self) -> None:
        self._socket_path = get_settings().eventbus.socket_path
        self._context: zmq.Context | None = None
        self._socket: zmq.Socket | None = None

    def connect(self) -> None:
        """Connect to the event bus as a publisher."""
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.PUB)
        self._socket.connect(self._socket_path)
        logger.info("Event publisher connected to %s", self._socket_path)

    def publish(self, topic: Topic, data: Event | list[Event]) -> None:
        """Publish a message to the event bus.

        Args:
            topic: The topic to publish to (e.g., Topic.DHT_READING).
            data: Event or list of Events to publish.
        """
        if self._socket is None:
            return

        if isinstance(data, list):
            payload = [event.to_dict() for event in data]
        else:
            payload = data.to_dict()

        message = json.dumps(payload)
        self._socket.send_multipart([topic.encode(), message.encode()])
        logger.debug("Published to %s: %s", topic, message)

    def close(self) -> None:
        """Close the publisher connection."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        if self._context is not None:
            self._context.term()
            self._context = None
        logger.info("Event publisher closed")


class EventSubscriber:
    """Subscribes to sensor readings from the event bus.

    Used by the web server to receive real-time updates for WebSocket broadcast.
    """

    def __init__(self, topics: list[Topic] | None = None) -> None:
        """Initialize subscriber.

        Args:
            topics: List of topics to subscribe to. If None, subscribes to all.
        """
        self._socket_path = get_settings().eventbus.socket_path
        self._topics = topics or list(Topic)
        self._context: zmq.asyncio.Context | None = None
        self._socket: zmq.asyncio.Socket | None = None

    def connect(self) -> None:
        """Bind to the event bus as a subscriber.

        The subscriber binds (stable endpoint) while publishers connect.
        This allows multiple publishers to send to a single subscriber.
        """
        self._context = zmq.asyncio.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.bind(self._socket_path)

        for topic in self._topics:
            self._socket.setsockopt_string(zmq.SUBSCRIBE, topic)
            logger.debug("Subscribed to topic: %s", topic)

        logger.info("Event subscriber bound to %s", self._socket_path)

    async def receive(self) -> AsyncIterator[tuple[Topic, dict[str, Any]]]:
        """Async iterator that yields (topic, data) tuples as they arrive."""
        if self._socket is None:
            return

        while True:
            try:
                parts = await self._socket.recv_multipart()
                if len(parts) != 2:
                    logger.warning("Invalid message format: %s", parts)
                    continue

                topic_bytes, message_bytes = parts
                topic = Topic(topic_bytes.decode())
                data = json.loads(message_bytes.decode())
                yield topic, data
            except zmq.ZMQError as e:
                if e.errno == zmq.ETERM:
                    break
                logger.error("ZMQ error: %s", e)
                raise

    def close(self) -> None:
        """Close the subscriber connection."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        if self._context is not None:
            with suppress(zmq.ZMQError):
                self._context.term()
            self._context = None
        logger.info("Event subscriber closed")


# Global publisher instance (initialized by polling services)
_publisher: EventPublisher | None = None


def get_publisher() -> EventPublisher:
    """Get or create the global publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher()
    return _publisher


def reset_publisher() -> None:
    """Reset the global publisher (for testing)."""
    global _publisher
    if _publisher is not None:
        _publisher.close()
    _publisher = None
