"""Cohesive service for the DHT22 sensor.

The service is responsible for:
- Polling the sensor for new data
- Displaying the data on the OLED screen
- Auditing the data against predefined thresholds
- Sending notifications when thresholds are crossed
- Persisting the data in the database
"""
import atexit
import ssl
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from email.message import EmailMessage
from smtplib import SMTP
from threading import Thread
from time import sleep
from typing import Deque

from adafruit_ssd1306 import SSD1306_I2C
from board import SCL, SDA
from busio import I2C
from PIL import Image, ImageDraw, ImageFont

from rpi import logging
from rpi.lib.config import (
    GmailConfig,
    NOTIFICATION_SERVICE_ENABLED,
    THRESHOLD_RULES,
)
from rpi.lib.reading import Measure, Reading, State

logger = logging.getLogger("dht-service")

_width = 128
_height = 64
_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                           17)


@dataclass(frozen=True)
class Event:
    """A simple event that can be enqueued and processed by the worker."""
    measure: Measure
    threshold: "Threshold"
    recording_time: datetime


class _Queue:
    """A simple in-memory queue for events."""

    def __init__(self) -> None:
        self._events: Deque[Event] = deque()

    @property
    def has_work(self) -> bool:
        """Return True if there are events in the queue."""
        return bool(self._events)

    def enqueue(self, event: Event) -> None:
        """Enqueue a new event."""
        logger.info("Queuing event %s", id(event))
        self._events.append(event)

    def dequeue(self) -> Event:
        """Dequeue an event."""
        event = self._events.popleft()
        logger.info("Picking up event %s", id(event))
        return event


queue = _Queue()

MESSAGE = ("Sensor alert! A threshold has been crossed at {recording_time}, "
           "value recorded: {value}, threshold {threshold_name} bound was: "
           "{threshold}{unit}.")


class _AbstractNotification(ABC):
    """Abstract base class for notifications."""

    def __init__(self, event: Event) -> None:
        self.event = event

    @abstractmethod
    def send(self) -> None:
        """Send the notification."""
        ...

    @property
    def message(self) -> str:
        """Return the message to be sent."""
        return MESSAGE.format(threshold_name=self.event.threshold.name,
                              value=str(self.event.measure),
                              unit=self.event.measure.unit,
                              **asdict(self.event))


class Gmail(_AbstractNotification):
    """Gmail notification handler."""

    def _build_message(self) -> EmailMessage:
        msg = EmailMessage()
        msg.add_header("From", GmailConfig.SENDER)
        msg.add_header("To", GmailConfig.RECIPIENTS)
        msg.add_header("Subject", GmailConfig.SUBJECT)
        msg.set_content(self.message)
        return msg

    def send(self) -> None:
        """Send the email."""
        message = self._build_message()
        context = ssl.create_default_context()
        with SMTP("smtp.gmail.com", 587, timeout=5) as server:
            server.starttls(context=context)
            server.login(GmailConfig.USERNAME, GmailConfig.PASSWORD)
            server.send_message(message)
        logger.info("Sent email notification for event %s", id(self.event))


def _work() -> None:
    """Process a single event from the queue."""
    event = queue.dequeue()
    if NOTIFICATION_SERVICE_ENABLED:
        return Gmail(event).send()
    logger.info("Ignoring event %s, notification service is off", id(event))


def _event_handler() -> None:
    """Continuously process events from the queue."""
    while True:
        sleep(1)
        if queue.has_work:
            _work()


def start_worker() -> None:
    """Start the worker thread."""
    Thread(target=_event_handler, daemon=True).start()


class _Display(SSD1306_I2C):
    """A display for the DHT22 sensor."""

    def clear(self) -> None:
        """Clear the display."""
        self.fill(0)
        self.show()

    def render_reading(self, reading: Reading) -> None:
        """Render a reading on the display."""
        image = Image.new("1", (_width, _height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, _width, _height))
        draw.text((23, 0), f"T: {reading.temperature}", font=_font, fill=255)
        draw.text((23, 20), f"H: {reading.humidity}", font=_font, fill=255)
        self.image(image)
        self.show()


display = _Display(_width, _height, I2C(SCL, SDA))


@atexit.register
def _clear_display():
    """Hook to clear the display screen when the program exits."""
    display.clear()


@dataclass
class _StateTracker:
    """A simple state tracker for the DHT22 sensor."""
    temperature: State = State.OK
    humidity: State = State.OK


def audit_reading(reading: Reading) -> None:
    """Audit reading value, and enqueue notification events."""
    tracker = _StateTracker()
    for name, rules in THRESHOLD_RULES.items():
        for rule in rules:
            comparator, threshold = rule
            measure = getattr(reading, name)
            if comparator(measure.value, threshold):
                setattr(tracker, name, State.IN_ALERT)
                if not getattr(reading, name).state == State.IN_ALERT:
                    queue.enqueue(
                        Event(measure, threshold, reading.recording_time))
                break
        getattr(reading, name).state = getattr(tracker, name)