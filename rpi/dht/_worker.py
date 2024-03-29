from threading import Thread
from time import sleep

from rpi import logging
from rpi.dht._notifications import Gmail
from rpi.lib.config import NOTIFICATION_SERVICE_ENABLED
from rpi.lib.events import queue

logger = logging.getLogger("worker-thread")


def _work() -> None:
    event = queue.dequeue()
    if NOTIFICATION_SERVICE_ENABLED:
        return Gmail(event).send()
    logger.info("Ignoring event %s, notification service is off", id(event))


def _event_handler() -> None:
    while True:
        sleep(1)
        if queue.has_work:
            _work()


def start_worker() -> None:
    Thread(target=_event_handler, daemon=True).start()
