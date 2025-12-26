# This module uses Micropython and needs to be set-up on the Raspberry Pico
# board, to read values from capacitive soil moisture sensors (v1.2).
import gc

import ujson
import utime
from machine import ADC, I2C, WDT, Pin
from ssd1306 import SSD1306_I2C

# Configuration
POLLING_INTERVAL_SEC = 2

# Display configuration
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
DISPLAY_I2C_FREQ = 200000
DISPLAY_TEXT_START_Y = 10
DISPLAY_TEXT_LINE_HEIGHT = 10


class Plant:
    def __init__(self, name, adc_pin, calibration):
        self.name = name
        self.pin = adc_pin
        self.cal = calibration

    @property
    def id(self):
        return self.name.split("-")[-1]


class Calibration:
    def __init__(self, cmin, cmax):
        self.min = cmin
        self.max = cmax

    @property
    def diff(self):
        return self.max - self.min


# After some testing, it seems calibration changes from device to device,
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

    def add_content(self, text):
        self._content.append(text)

    def display_content(self):
        y_pos = DISPLAY_TEXT_START_Y
        for text in self._content:
            self.text(text, 0, y_pos)
            y_pos += DISPLAY_TEXT_LINE_HEIGHT
        self.show()


def read_moisture(plant):
    """Read moisture level from a plant sensor, clamped to 0-100%."""
    raw = plant.pin.read_u16()
    reading = round((plant.cal.max - raw) * 100 / plant.cal.diff, 2)
    return max(0, min(100, reading))


def init_display():
    """Initialize display, return None if not available."""
    try:
        i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=DISPLAY_I2C_FREQ)
        return Display(DISPLAY_WIDTH, DISPLAY_HEIGHT, i2c)
    except OSError:
        return None


def update_display(display, readings):
    """Update display with current readings."""
    if display is None:
        return
    try:
        display.clear()
        for plant in plants:
            display.add_content(f"[{plant.id}]: {readings[plant.name]} %")
        display.display_content()
    except OSError:
        pass


def main():
    """Main loop for reading sensors and sending data via USB serial."""
    display = init_display()
    wdt = WDT(timeout=8000)
    readings = {plant.name: 0 for plant in plants}

    while True:
        for plant in plants:
            readings[plant.name] = read_moisture(plant)

        update_display(display, readings)

        # Send JSON over USB serial (stdout)
        print(ujson.dumps(readings))

        utime.sleep(POLLING_INTERVAL_SEC)
        gc.collect()
        wdt.feed()


if __name__ == "__main__":
    main()
