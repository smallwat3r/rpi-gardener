# This module uses Micropython and needs to be set-up on the Raspberry Pico
# board, to read values from capacitative soil moisture sensors (v1.2).
#
# Requirements:
# ------------
#
#   Use mpremote to connect remotely and install the ssd1306 lib to the Pico.
#
#      mpremote a0
#      mpremote mip install ssd1306
#
#   Create a secrets.py file on the Pico, in the same directory than the
#   main.py file, this file will contain secret values in order to
#   communicate with our main Rpi board.
#
#      SSID=<ssid name>
#      SSID_PASSWORD=<ssid password>
#      RPI_HOST=192.168.1.XXX

import gc
import network
import ujson
import urequests
import utime
from machine import ADC, Pin, I2C

from ssd1306 import SSD1306_I2C

import secrets

PLANT_TO_PIN_MAPPING = (
    ("plant-1", ADC(Pin(26))),
    ("plant-2", ADC(Pin(27))),
    ("plant-3", ADC(Pin(28))),
)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(secrets.SSID, secrets.SSID_PASSWORD)


class Display(SSD1306_I2C):
    def __init__(self, *args, **kwargs) -> None:
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


class Calibration:
    def __init__(self) -> None:
        self.min = 17000
        self.max = 47000

    @property
    def diff(self):
        return self.max - self.min


cal = Calibration()
display = Display(128, 64, I2C(0, scl=Pin(1), sda=Pin(0), freq=200000))
display_failure = False

while True:
    try:
        display.clear()
        display_failure = False
    except OSError:
        display_failure = True
    readings = {}
    for plant, pin in PLANT_TO_PIN_MAPPING:
        reading = round((cal.max - pin.read_u16()) * 100 / cal.diff, 2)
        readings[plant] = reading
        if not display_failure:
            display.add_content(f"[{plant[-1]}]: {reading} %")
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
