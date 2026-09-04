"""Generic async polling service abstraction.

Provides a reusable base class for sensor polling services that follow
the poll → audit → persist pattern with configurable intervals.
"""

import asyncio
import signal
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from types import FrameType

from rpi.lib.config import get_settings

type _SignalHandler = Callable[[int, FrameType | None], None] | int | None
from rpi.logging import get_logger

logger = get_logger("lib.polling")


class PollingService[T](ABC):
    """Abstract base class for async sensor polling services.

    Implements the common polling loop pattern with:
    - Configurable polling frequency
    - Graceful shutdown handling
    - Error recovery
    """

    def __init__(
        self,
        name: str,
        frequency_sec: int | None = None,
    ) -> None:
        """Initialize the polling service.

        Args:
            name: Service name for logging.
            frequency_sec: Polling frequency in seconds.
        """
        self.name = name
        polling_cfg = get_settings().polling
        self.frequency_sec = frequency_sec or polling_cfg.frequency_sec
        self.persist_every = polling_cfg.persist_every
        self.flush_interval_sec = polling_cfg.flush_interval_sec
        self._cycle = 0
        self._buffer: list[T] = []
        self._last_flush = time.monotonic()
        self._shutdown_requested = False
        self._logger = get_logger(f"polling.{name}")
        self._previous_handlers: dict[signal.Signals, _SignalHandler] = {}

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize any resources needed before polling starts.

        Called once at the start of run(). Should initialize hardware,
        database connections, start background workers, etc.
        """

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources before exit.

        Called once when the polling loop exits. Should release hardware,
        close connections, clear displays, etc.
        """

    @abstractmethod
    async def poll(self) -> T | None:
        """Poll the sensor for a new reading.

        Returns:
            A reading object, or None if the reading failed and should be skipped.
        """

    @abstractmethod
    async def audit(self, reading: T) -> bool:
        """Audit the reading against thresholds.

        Args:
            reading: The sensor reading to audit.

        Returns:
            True if the reading is valid and should be persisted, False to skip.
        """

    @abstractmethod
    def publish(self, reading: T) -> None:
        """Publish the reading to the event bus for live consumers.

        Called every cycle, unlike persist() which is batched.
        """

    @abstractmethod
    async def persist(self, readings: list[T]) -> None:
        """Persist a batch of readings to the database in one transaction.

        Args:
            readings: Every Nth validated reading since the last flush.
        """

    async def flush(self) -> None:
        """Persist buffered readings, if any."""
        if self._buffer:
            await self.persist(self._buffer)
            self._buffer = []
        self._last_flush = time.monotonic()

    def on_poll_error(self, error: Exception) -> None:
        """Handle an error that occurred during polling.

        Override to customize error handling. Default logs the error.
        """
        self._logger.debug("%s poll error: %s", self.name, error)

    def _handle_shutdown(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals gracefully."""
        signal_name = signal.Signals(signum).name
        self._logger.info(
            "Received %s, initiating graceful shutdown...", signal_name
        )
        self._shutdown_requested = True

    def _setup_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            self._previous_handlers[sig] = signal.signal(
                sig, self._handle_shutdown
            )

    def _restore_signal_handlers(self) -> None:
        """Restore previous signal handlers."""
        for sig, handler in self._previous_handlers.items():
            if handler is not None:
                signal.signal(sig, handler)
        self._previous_handlers.clear()

    async def _poll_cycle(self) -> None:
        """Execute a single poll → audit → publish cycle, persisting in batches.

        Only every persist_every-th reading is kept, and kept readings are
        written together once per flush_interval_sec. Both cut SD card writes
        by orders of magnitude at the cost of up to one interval of history
        on power loss.
        """
        reading = await self.poll()
        if reading is None or not await self.audit(reading):
            return
        self.publish(reading)
        self._cycle += 1
        if self._cycle % self.persist_every == 0:
            self._buffer.append(reading)
        if time.monotonic() - self._last_flush >= self.flush_interval_sec:
            await self.flush()

    async def _run_loop(self) -> None:
        """Run the async polling loop with precise timing."""
        await self.initialize()
        self._logger.info("%s polling service started", self.name)

        loop = asyncio.get_running_loop()

        try:
            while not self._shutdown_requested:
                cycle_start = loop.time()

                try:
                    await self._poll_cycle()
                except Exception as e:
                    self.on_poll_error(e)

                # Sleep only the remaining time to maintain consistent intervals
                elapsed = loop.time() - cycle_start
                sleep_time = max(0, self.frequency_sec - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
        finally:
            self._logger.info("Cleaning up resources...")
            try:
                await self.flush()
            except Exception:
                self._logger.exception("Failed to flush readings on shutdown")
            await self.cleanup()
            self._logger.info("%s shutdown complete", self.name)

    def run(self) -> None:
        """Run the polling loop.

        This is the main entry point. It:
        1. Sets up signal handlers for graceful shutdown
        2. Calls initialize()
        3. Enters the polling loop (poll → audit → persist)
        4. Calls cleanup() on exit
        5. Restores previous signal handlers
        """
        self._setup_signal_handlers()
        try:
            asyncio.run(self._run_loop())
        finally:
            self._restore_signal_handlers()
