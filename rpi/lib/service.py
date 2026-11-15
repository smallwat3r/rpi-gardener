"""Service runner utility for event-driven services."""

import asyncio
import signal
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress

from rpi.lib.db import close_db
from rpi.logging import configure, get_logger

# Longer than supervisord's default startsecs
_DISABLED_LINGER_SEC = 2.0


def run_service(
    main: Callable[[], Awaitable[None]],
    *,
    enabled: Callable[[], bool] | None = None,
    name: str = "service",
) -> None:
    """Run an async service with signal handling.

    Provides a standard entry point for event-driven services that:
    - Configures logging
    - Optionally checks if the service is enabled
    - Sets up graceful shutdown on SIGTERM/SIGINT
    - Runs the async service function

    Args:
        main: Async function to run (typically named ``run``).
        enabled: Optional callable that returns False to skip running.
        name: Service name for logging (used in disabled message).
    """
    logger = get_logger(f"{name}.service")

    configure()

    if enabled is not None and not enabled():
        logger.info("%s service is disabled, exiting", name.capitalize())
        # supervisord treats an exit within its startsecs (1s) as a failed
        # start and retries, so stay up just past it before the clean exit
        time.sleep(_DISABLED_LINGER_SEC)
        return

    async def run_until_signalled() -> None:
        # Cancel rather than stop the loop, so the service unwinds through
        # its context managers (plug off, display cleared) before exiting
        task = asyncio.current_task()
        assert task is not None
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, task.cancel)
        try:
            with suppress(asyncio.CancelledError):
                await main()
        finally:
            # Pooled connections run worker threads that keep the process
            # alive after main() returns, until supervisord has to kill it
            await close_db()

    asyncio.run(run_until_signalled())
