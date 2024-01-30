# This module uses micropython and needs to be set-up on the Rpi Pico board, to
# read values from capacitative soil moisture sensors (v1.2).
#
# Requirements:
# ------------
#
#   Use mpremote to connect remotely and install the ssd1306 lib to the Pico.
#
#      mpremote a0
#      mpremote mip install ssd1306
#
# TODO: set up network connect to send HTTP requests to the main Rpi board.
#   wlan = network.WLAN(network.STA_IF)
#   wlan.active(True)
#   wlan.connect("", "")
#   assert wlan.isconnected()

import utime
from machine import ADC, Pin, I2C

from ssd1306 import SSD1306_I2C

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
            self.text(text, 35, start + offset)
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
sensors = ADC(Pin(26)), ADC(Pin(27)), ADC(Pin(28))

while True:
    display.clear()
    for sensor in sensors:
        reading = (cal.max - sensor.read_u16()) * 100 / cal.diff
        display.add_content(f"{round(reading, 2)} %")
    display.display_content()
    utime.sleep(2)
