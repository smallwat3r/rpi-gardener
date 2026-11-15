"""Humidifier service that controls humidity via a TP-Link Kasa smart plug.

Subscribes to DHT readings on the event bus and switches a smart plug so
the humidifier runs while humidity is below the minimum threshold.

- Humidifier turns ON when humidity is confirmed below the threshold
- Humidifier turns OFF once humidity recovers past the hysteresis band
- Humidifier turns OFF when readings stop arriving (sensor or polling down)
- Humidifier turns OFF on service shutdown (safety measure)

The plug follows the readings, not the alert events. An alert is published
once per transition and pub/sub does not replay, so a missed "resolved"
would leave the humidifier running. Here the wanted state is compared with
the plug every few seconds, so a missed or failed switch is retried.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from rpi.lib.alerts import AlertState, AlertTracker, Namespace
from rpi.lib.config import (
    MeasureName,
    ThresholdType,
    Unit,
    get_effective_thresholds,
    get_settings,
)
from rpi.lib.config.constants import HYSTERESIS_HUMIDITY
from rpi.lib.eventbus import (
    EventPublisher,
    EventSubscriber,
    HumidifierStateEvent,
    Topic,
)
from rpi.lib.service import run_service
from rpi.lib.smartplug import SmartPlugProtocol, create_smartplug_controller
from rpi.logging import get_logger

logger = get_logger("humidifier.service")

# Readings arrive every ~2s. With none for this long the sensor or the
# polling service is down, and the humidifier must not run blind.
_STALE_AFTER_SEC = 60.0

# How often the plug is compared with the wanted state. A failed switch is
# retried at this pace, on top of the retries inside the controller.
_CONTROL_INTERVAL_SEC = 5.0


@dataclass(slots=True)
class _Demand:
    """What the latest readings ask of the humidifier."""

    wanted: bool = False
    last_reading: float = field(default_factory=time.monotonic)

    def is_stale(self) -> bool:
        """Whether readings stopped arriving."""
        return time.monotonic() - self.last_reading > _STALE_AFTER_SEC


async def _update_demand(
    data: dict[str, Any], tracker: AlertTracker, demand: _Demand
) -> None:
    """Fold one DHT reading into the demand.

    The tracker supplies the same hysteresis and confirmation window as the
    alerts, so one bad sensor reading does not toggle the plug.
    """
    humidity = data.get("humidity")
    if isinstance(humidity, bool) or not isinstance(humidity, int | float):
        logger.warning("Ignoring DHT reading without humidity: %s", data)
        return
    thresholds = await get_effective_thresholds()
    state = await tracker.check(
        namespace=Namespace.DHT,
        sensor_name=MeasureName.HUMIDITY,
        value=humidity,
        unit=Unit.PERCENT,
        threshold=thresholds.min_humidity,
        threshold_type=ThresholdType.MIN,
        hysteresis=HYSTERESIS_HUMIDITY,
        recording_time=datetime.now(UTC),
    )
    demand.wanted = state == AlertState.IN_ALERT
    demand.last_reading = time.monotonic()


async def _sync_plug(
    wanted: bool,
    is_on: bool | None,
    controller: SmartPlugProtocol,
    publisher: EventPublisher,
) -> bool | None:
    """Switch the plug if it differs from the wanted state.

    Returns the plug state afterwards. A failed switch returns the old
    state, so the next call tries again.
    """
    if wanted == is_on:
        return is_on
    logger.info("Turning humidifier %s", "ON" if wanted else "OFF")
    switched = await (
        controller.turn_on() if wanted else controller.turn_off()
    )
    if not switched:
        return is_on
    await publisher.publish(
        HumidifierStateEvent(is_on=wanted, recording_time=datetime.now(UTC))
    )
    return wanted


async def _listen(
    subscriber: EventSubscriber, tracker: AlertTracker, demand: _Demand
) -> None:
    """Keep the demand current from the DHT reading stream."""
    async for _topic, data in subscriber.receive():
        await _update_demand(data, tracker, demand)
    # Fail rather than idle, the task group then stops the service, which
    # turns the plug off and lets supervisord restart it
    raise ConnectionError("DHT reading stream ended")


async def _control(
    controller: SmartPlugProtocol, publisher: EventPublisher, demand: _Demand
) -> None:
    """Hold the plug at the wanted state."""
    # Unknown until the first switch, which also turns off a plug left on
    # by a crashed previous run
    is_on: bool | None = None
    while True:
        stale = demand.is_stale()
        if stale and is_on:
            logger.warning(
                "No DHT reading for %.0fs, turning humidifier OFF",
                _STALE_AFTER_SEC,
            )
        is_on = await _sync_plug(
            demand.wanted and not stale, is_on, controller, publisher
        )
        await asyncio.sleep(_CONTROL_INTERVAL_SEC)


async def run() -> None:
    """Run the humidifier service."""
    cfg = get_settings().humidifier

    if not cfg.host:
        logger.warning("HUMIDIFIER_HOST not configured, service exiting")
        return

    # turn_off_on_close ensures humidifier is OFF when service stops
    controller = create_smartplug_controller(cfg.host, turn_off_on_close=True)
    demand = _Demand()

    async with (
        EventPublisher() as publisher,
        controller,
        EventSubscriber(topics=[Topic.DHT_READING]) as subscriber,
        asyncio.TaskGroup() as tasks,
    ):
        logger.info("Humidifier service started")
        tasks.create_task(_listen(subscriber, AlertTracker(), demand))
        tasks.create_task(_control(controller, publisher, demand))

    logger.info("Humidifier service stopped")


def main() -> None:
    """Entry point for the humidifier service."""
    run_service(
        run,
        enabled=lambda: get_settings().humidifier.enabled,
        name="humidifier",
    )


if __name__ == "__main__":
    main()
