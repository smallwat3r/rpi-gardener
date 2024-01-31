from datetime import datetime

from flask import Blueprint, request

from rpi import logging
from rpi.lib.db import Db, Sql
from rpi.lib.reading import Measure, PicoReading, Unit

logger = logging.getLogger("pico-bp")
pico = Blueprint("pico", __name__)


def _persist(reading: PicoReading) -> None:
    with Db() as db:
        db.commit(Sql("INSERT INTO pico_reading VALUES (?, ?, ?)"),
                  (reading.plant_id, reading.moisture.value,
                   reading.recording_time))


@pico.post("/pico")
def receive():
    current_time = datetime.utcnow()
    data = request.get_json()
    logger.info("Received Pico data: %s", data)
    for key, value in data.items():
        _persist(PicoReading(key, Measure(value, Unit.PERCENT), current_time))
    return "", 201
