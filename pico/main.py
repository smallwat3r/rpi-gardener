# This module uses Micropython and needs to be set-up on the Raspberry Pico
# board, to read values from capacitative soil moisture sensors (v1.2).
import gc
import network
import ujson
import urequests
import utime
from machine import ADC, Pin, I2C

from ssd1306 import SSD1306_I2C

import secrets

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(secrets.SSID, secrets.SSID_PASSWORD)


class Plant:
    def __init__(self, name, adc_pin, calibration):
        self.name = name
        self.pin = adc_pin
        self.cal = calibration

    @property
    def id(self):
        return self.name[-1]


class Calibration:
    def __init__(self, cmin, cmax):
        self.min = cmin
        self.max = cmax

    @property
    def diff(self):
        return self.max - self.min


# after some testing, it seems calibration change from device to device,
# so I've calibrated them independently to ensure we get the most sensible
# readings.
plants = (
    Plant("plant-1", ADC(Pin(26)), Calibration(15600, 43500)),
    Plant("plant-2", ADC(Pin(27)), Calibration(15600, 43500)),
    Plant("plant-3", ADC(Pin(28)), Calibration(14500, 44000)),
)


class Display(SSD1306_I2C):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._content = []

    def clear(self):
        self._content = []
        self.fill(0)
        self.show()

    def add_content(self, text):
        self._content.append(text)

    def display_content(self):
        start, offset = 10, 10
        for text in self._content:
            self.text(text, 0, start + offset)
            offset += 10
        self.show()


display = Display(128, 64, I2C(0, scl=Pin(1), sda=Pin(0), freq=200000))
display_failure = False

while True:
    try:
        display.clear()
        display_failure = False
    except OSError:
        display_failure = True
    readings = {}
    for plant in plants:
        reading = round((plant.cal.max - plant.pin.read_u16())
                        * 100 / plant.cal.diff, 2)
        if reading < 0:
            reading = 0
        elif reading > 100:
            reading = 100
        readings[plant.name] = reading
        if not display_failure:
            display.add_content(f"[{plant.id}]: {reading} %")
    if not display_failure:
        try:
            display.display_content()
        except OSError:
            pass
    response = urequests.post(f"{secrets.RPI_HOST}/pico",
                              headers={'content-type': 'application/json'},
                              data=ujson.dumps(readings))
    utime.sleep(2)
    gc.collect()
