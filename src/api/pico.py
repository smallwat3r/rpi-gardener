from datetime import datetime

from flask import Blueprint, request

from .. import logging
from .._db import Db, Sql
from .._reading import Measure, PicoReading, Unit

logger = logging.getLogger("pico-bp")
pico = Blueprint("pico", __name__)


def _persist(reading: PicoReading) -> None:
    """Persist the reading values into the database."""
    with Db() as db:
        db.commit(Sql("INSERT INTO pico_reading VALUES (?, ?, ?)"),
                  (reading.plant_id, reading.moisture.value,
                   reading.recording_time))


@pico.post("/pico")
def receive():
    current_time = datetime.utcnow()
    data = request.get_json()
    logger.info("Received Pico values: %s", data)
    for key, value in data.items():
        _persist(PicoReading(key, Measure(value, Unit.PERCENT), current_time))
    return "", 201
