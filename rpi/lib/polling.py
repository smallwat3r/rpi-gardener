"""Generic async polling service abstraction.

Provides a reusable base class for sensor polling services that follow
the poll → audit → persist pattern with configurable intervals and cleanup.
"""
import asyncio
import signal
from abc import ABC, abstractmethod
from datetime import timedelta
from types import FrameType
from typing import Generic, TypeVar

from rpi.lib.config import get_settings
from rpi.lib.utils import utcnow
from rpi.logging import get_logger

logger = get_logger("lib.polling")

# Type variable for the reading type
T = TypeVar("T")


class PollingService(ABC, Generic[T]):
    """Abstract base class for async sensor polling services.

    Implements the common polling loop pattern with:
    - Configurable polling frequency
    - Periodic cleanup of old data
    - Graceful shutdown handling
    - Error recovery
    """

    def __init__(
        self,
        name: str,
        frequency_sec: int | None = None,
        cleanup_interval_cycles: int | None = None,
        cleanup_retention_days: int | None = None,
    ) -> None:
        """Initialize the polling service.

        Args:
            name: Service name for logging.
            frequency_sec: Polling frequency in seconds.
            cleanup_interval_cycles: Run cleanup every N poll cycles.
            cleanup_retention_days: Delete data older than this many days.
        """
        self.name = name
        polling_cfg = get_settings().polling
        self.frequency_sec = frequency_sec or polling_cfg.frequency_sec
        self.cleanup_interval_cycles = cleanup_interval_cycles or polling_cfg.cleanup_interval_cycles
        self.cleanup_retention_days = cleanup_retention_days or polling_cfg.cleanup_retention_days
        self._shutdown_requested = False
        self._logger = get_logger(f"polling.{name}")

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
    async def persist(self, reading: T) -> None:
        """Persist the reading to the database.

        Args:
            reading: The validated reading to persist.
        """

    async def clear_old_records(self) -> None:
        """Clear historical data older than retention period.

        Override this method to implement cleanup logic for your sensor type.
        Default implementation does nothing.
        """

    def on_poll_error(self, error: Exception) -> None:
        """Handle an error that occurred during polling.

        Override to customize error handling. Default logs the error.
        """
        self._logger.debug("%s poll error: %s", self.name, error)

    def get_cutoff_time(self):
        """Get the cutoff datetime for cleanup operations."""
        return utcnow() - timedelta(days=self.cleanup_retention_days)

    def _handle_shutdown(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals gracefully."""
        signal_name = signal.Signals(signum).name
        self._logger.info("Received %s, initiating graceful shutdown...", signal_name)
        self._shutdown_requested = True

    def _setup_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    async def _poll_cycle(self) -> None:
        """Execute a single poll → audit → persist cycle."""
        reading = await self.poll()
        if reading is not None:
            if await self.audit(reading):
                await self.persist(reading)

    async def _run_loop(self) -> None:
        """Run the async polling loop with precise timing."""
        await self.initialize()
        self._logger.info("%s polling service started", self.name)

        loop = asyncio.get_event_loop()
        poll_count = 0

        try:
            while not self._shutdown_requested:
                cycle_start = loop.time()

                # Run cleanup periodically
                if poll_count % self.cleanup_interval_cycles == 0:
                    self._logger.info(
                        "Running cleanup (data older than %d days)...",
                        self.cleanup_retention_days
                    )
                    await self.clear_old_records()

                # Poll → Audit → Persist
                try:
                    await self._poll_cycle()
                except Exception as e:
                    self.on_poll_error(e)

                poll_count += 1

                # Sleep only the remaining time to maintain consistent intervals
                elapsed = loop.time() - cycle_start
                sleep_time = max(0, self.frequency_sec - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
        finally:
            self._logger.info("Cleaning up resources...")
            await self.cleanup()
            self._logger.info("%s shutdown complete", self.name)

    def run(self) -> None:
        """Run the polling loop.

        This is the main entry point. It:
        1. Sets up signal handlers for graceful shutdown
        2. Calls initialize()
        3. Enters the polling loop (poll → audit → persist)
        4. Periodically runs cleanup
        5. Calls cleanup() on exit
        """
        self._setup_signal_handlers()
        asyncio.run(self._run_loop())
