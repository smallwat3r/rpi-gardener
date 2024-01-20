from time import sleep
from threading import Thread

from . import logging
from ._events import queue

logger = logging.getLogger("worker-thread")


def _work() -> None:
    event = queue.dequeue()
    logger.warning("Picked up %s", event)
    # TODO: this currently does nothing, implement alerting to communication
    #   channels (for ex: phone, email etc)


def _event_handler() -> None:
    while True:
        sleep(1)
        if queue.has_work:
            _work()


def start_worker() -> None:
    logger.info("Worker started in another thread...")
    Thread(target=_event_handler, daemon=True).start()
