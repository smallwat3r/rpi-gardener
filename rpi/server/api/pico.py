from datetime import datetime

from flask import Blueprint, request
from sqlitey import Sql

from rpi import logging
from rpi.lib.config import db_with_config
from rpi.lib.reading import Measure, PicoReading, Unit

logger = logging.getLogger("pico-bp")
pico = Blueprint("pico", __name__)


def _persist(reading: PicoReading) -> None:
    with db_with_config() as db:
        db.commit(Sql.raw("INSERT INTO pico_reading VALUES (?, ?, ?)"),
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
