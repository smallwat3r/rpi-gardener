"""Logging configuration for the RPi Gardener application."""

import logging
import sys

_configured = False

LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s - %(message)s"


def configure(level: int = logging.INFO) -> None:
    """Configure logging for the application.

    Safe to call multiple times - only configures once.
    """
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root = logging.getLogger("rpi")
    root.setLevel(level)
    root.addHandler(handler)

    # Configure uvicorn root logger to use the same format
    # (child loggers like uvicorn.error propagate to this)
    uv_log = logging.getLogger("uvicorn")
    uv_log.handlers.clear()
    uv_log.addHandler(handler)

    # Silence verbose websocket connection open/close logs from uvicorn
    # (we have our own more detailed logs in rpi.server.websockets)
    logging.getLogger("uvicorn.protocols.websockets").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger under the 'rpi' namespace.

    Args:
        name: Logger name (will be prefixed with 'rpi.')

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(f"rpi.{name}")
