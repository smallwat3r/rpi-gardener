"""LCD service that displays active alerts with scrolling text.

Subscribes to the event bus ALERT topic and maintains a display of
currently active alerts on a 16x2 character LCD.
"""

import asyncio
from contextlib import suppress

from rpi.lcd.display import DisplayProtocol
from rpi.lib.alerts import AlertEvent, Namespace
from rpi.lib.config import MeasureName, get_settings
from rpi.lib.eventbus import EventSubscriber, Topic
from rpi.lib.service import run_service
from rpi.logging import get_logger

logger = get_logger("lcd.service")


def _create_display() -> DisplayProtocol:
    """Create display based on configuration."""
    if get_settings().mock_sensors:
        from rpi.lib.mock import MockLCDDisplay

        logger.info("Using mock LCD display")
        return MockLCDDisplay()

    from rpi.lcd.display import Display

    return Display()


def _make_alert_key(event: AlertEvent) -> str:
    """Create a unique key for an alert."""
    return f"{event.namespace.value}:{event.sensor_name}"


def _format_alert(event: AlertEvent) -> str:
    """Format an alert event for LCD display."""
    if event.namespace == Namespace.PICO:
        return f"P{event.sensor_name} dry"

    if event.namespace == Namespace.DHT:
        if event.sensor_name == MeasureName.TEMPERATURE:
            if event.threshold and event.value < event.threshold:
                return "Temp low"
            return "Temp high"
        if event.sensor_name == MeasureName.HUMIDITY:
            if event.threshold and event.value < event.threshold:
                return "Humid low"
            return "Humid high"

    return f"{event.sensor_name}"


class AlertManager:
    """Manages active alerts and updates the LCD display."""

    def __init__(self, display: DisplayProtocol) -> None:
        self._display = display
        self._active_alerts: dict[str, str] = {}

    def handle_event(self, event: AlertEvent) -> None:
        """Handle an alert event (add or remove from active alerts)."""
        key = _make_alert_key(event)

        if event.is_resolved:
            if key in self._active_alerts:
                del self._active_alerts[key]
                logger.info("Alert resolved: %s", key)
        else:
            self._active_alerts[key] = _format_alert(event)
            logger.info("Alert triggered: %s", key)

        self._update_display()

    def _update_display(self) -> None:
        """Update the LCD with current alert status."""
        if not self._active_alerts:
            self._display.show_ok()
        else:
            self._display.show_alerts(list(self._active_alerts.values()))

    def has_alerts(self) -> bool:
        """Check if there are any active alerts."""
        return bool(self._active_alerts)


async def _scroll_loop(
    display: DisplayProtocol,
    manager: AlertManager,
    stop_event: asyncio.Event,
) -> None:
    """Background task that scrolls the LCD text."""
    cfg = get_settings().lcd
    delay = cfg.scroll_delay_sec

    while not stop_event.is_set():
        if manager.has_alerts():
            display.scroll_step()
        await asyncio.sleep(delay)


async def run() -> None:
    """Run the LCD service."""
    with _create_display() as display:
        manager = AlertManager(display)
        stop_event = asyncio.Event()

        display.show_ok()

        scroll_task = asyncio.create_task(
            _scroll_loop(display, manager, stop_event)
        )

        try:
            async with EventSubscriber(topics=[Topic.ALERT]) as subscriber:
                logger.info("LCD service started")
                async for _topic, data in subscriber.receive():
                    try:
                        event = AlertEvent.from_dict(data)
                        manager.handle_event(event)
                    except (KeyError, ValueError, TypeError):
                        logger.exception("Failed to parse alert event")
        finally:
            stop_event.set()
            scroll_task.cancel()
            with suppress(asyncio.CancelledError):
                await scroll_task

    logger.info("LCD service stopped")


def main() -> None:
    """Entry point for the LCD service."""
    run_service(run, enabled=lambda: get_settings().lcd.enabled, name="lcd")


if __name__ == "__main__":
    main()
