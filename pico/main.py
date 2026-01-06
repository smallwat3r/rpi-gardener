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
# Yellow zone: 0-15, Blue zone: 16-63
DISPLAY_HEADER_Y = 4
DISPLAY_VALUES_START_Y = 20
DISPLAY_VALUES_LINE_HEIGHT = 14


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

    def clear(self):
        self.fill(0)

    def render(self, readings):
        """Render readings with yellow header and blue values."""
        self.clear()
        # Yellow zone: Header
        self.text("SOIL MOISTURE", 16, DISPLAY_HEADER_Y)
        # Blue zone: Plant readings
        y_pos = DISPLAY_VALUES_START_Y
        for plant in plants:
            pct = readings[plant.name]["pct"]
            self.text(f"P{plant.id}: {pct:5.1f}%", 0, y_pos)
            y_pos += DISPLAY_VALUES_LINE_HEIGHT
        self.show()


def read_moisture(plant):
    """Read moisture level from a plant sensor, clamped to 0-100%."""
    raw = plant.pin.read_u16()
    pct = round((plant.cal.max - raw) * 100 / plant.cal.diff, 2)
    return {"pct": max(0, min(100, pct)), "raw": raw}


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
        display.render(readings)
    except OSError:
        pass


def main():
    """Main loop for reading sensors and sending data via USB serial."""
    display = init_display()
    wdt = WDT(timeout=8000)
    readings = {plant.name: {"pct": 0, "raw": 0} for plant in plants}

    while True:
        for plant in plants:
            readings[plant.name] = read_moisture(plant)

        update_display(display, readings)

        # Send JSON over USB serial (stdout)
        print(ujson.dumps(readings))

        utime.sleep(POLLING_INTERVAL_SEC)
        gc.collect()
        wdt.feed()


main()
