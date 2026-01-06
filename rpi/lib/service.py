"""Service runner utility for event-driven services."""

import asyncio
import signal
from collections.abc import Awaitable, Callable
from contextlib import suppress

from rpi.logging import configure, get_logger


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
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, loop.stop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(main())
    loop.close()
