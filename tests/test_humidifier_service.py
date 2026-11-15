"""Tests for the humidifier service and the shared service runner."""

import asyncio
import os
import signal
import time
from unittest.mock import AsyncMock

import pytest

from rpi.humidifier import service as humidifier
from rpi.lib.alerts import AlertTracker
from rpi.lib.service import run_service


def _plug(*, switches: bool = True) -> AsyncMock:
    plug = AsyncMock()
    plug.turn_on.return_value = switches
    plug.turn_off.return_value = switches
    return plug


class TestSyncPlug:
    @pytest.mark.asyncio
    async def test_switches_on_and_publishes_state(self):
        plug, publisher = _plug(), AsyncMock()

        is_on = await humidifier._sync_plug(True, False, plug, publisher)

        assert is_on is True
        plug.turn_on.assert_awaited_once()
        assert publisher.publish.await_args.args[0].is_on is True

    @pytest.mark.asyncio
    async def test_unknown_state_is_switched_off(self):
        """A plug left on by a crashed run is turned off at startup."""
        plug = _plug()

        assert await humidifier._sync_plug(False, None, plug, AsyncMock()) is (
            False
        )
        plug.turn_off.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failed_switch_keeps_old_state_so_it_is_retried(self):
        plug, publisher = _plug(switches=False), AsyncMock()

        is_on = await humidifier._sync_plug(False, True, plug, publisher)
        assert is_on is True
        publisher.publish.assert_not_awaited()

        plug.turn_off.return_value = True
        assert await humidifier._sync_plug(False, is_on, plug, publisher) is (
            False
        )

    @pytest.mark.asyncio
    async def test_in_sync_plug_is_left_alone(self):
        plug = _plug()

        assert await humidifier._sync_plug(True, True, plug, AsyncMock())
        plug.turn_on.assert_not_awaited()


class TestDemand:
    @pytest.mark.asyncio
    async def test_follows_readings_with_hysteresis(self):
        """Default thresholds: on below 40%, off again from 43%."""
        tracker = AlertTracker(confirmation_count=1)
        demand = humidifier._Demand()

        await humidifier._update_demand({"humidity": 35.0}, tracker, demand)
        assert demand.wanted is True

        await humidifier._update_demand({"humidity": 41.0}, tracker, demand)
        assert demand.wanted is True  # inside the hysteresis band

        await humidifier._update_demand({"humidity": 43.0}, tracker, demand)
        assert demand.wanted is False

    @pytest.mark.asyncio
    async def test_reading_without_humidity_is_ignored(self):
        demand = humidifier._Demand(last_reading=0.0)

        await humidifier._update_demand({}, AlertTracker(), demand)

        assert demand.last_reading == 0.0

    def test_goes_stale_when_readings_stop(self):
        fresh = humidifier._Demand()
        old = humidifier._Demand(
            last_reading=time.monotonic() - humidifier._STALE_AFTER_SEC - 1
        )

        assert not fresh.is_stale()
        assert old.is_stale()


def test_run_service_runs_cleanup_on_sigterm():
    """SIGTERM must unwind the service, that is what turns the plug off."""
    cleaned_up = False

    async def main() -> None:
        nonlocal cleaned_up
        loop = asyncio.get_running_loop()
        loop.call_later(0.05, os.kill, os.getpid(), signal.SIGTERM)
        try:
            await asyncio.sleep(30)
        finally:
            cleaned_up = True

    run_service(main, name="test")

    assert cleaned_up
