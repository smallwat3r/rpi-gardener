# This module uses Micropython and needs to be set-up on the Raspberry Pico
# board, to read values from capacitive soil moisture sensors (v1.2).
import gc
import network
import ujson
import urequests
import utime
from machine import ADC, Pin, I2C

from ssd1306 import SSD1306_I2C

import secrets

# Configuration
POLLING_INTERVAL_SEC = 2
WIFI_CONNECT_TIMEOUT_SEC = 10
WIFI_RETRY_DELAY_SEC = 5
HTTP_TIMEOUT_SEC = 10

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
        return self.name[-1]


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
        self.show()

    def add_content(self, text):
        self._content.append(text)

    def display_content(self):
        y_pos = DISPLAY_TEXT_START_Y
        for text in self._content:
            self.text(text, 0, y_pos)
            y_pos += DISPLAY_TEXT_LINE_HEIGHT
        self.show()


def connect_wifi():
    """Connect to WiFi with retry logic."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        return wlan

    print("Connecting to WiFi...")
    wlan.connect(secrets.SSID, secrets.SSID_PASSWORD)

    start = utime.time()
    while not wlan.isconnected():
        if utime.time() - start > WIFI_CONNECT_TIMEOUT_SEC:
            print("WiFi connection timeout")
            return None
        utime.sleep(0.5)

    print(f"Connected: {wlan.ifconfig()[0]}")
    return wlan


def ensure_wifi_connected(wlan):
    """Ensure WiFi is connected, reconnect if necessary."""
    if wlan is None or not wlan.isconnected():
        print("WiFi disconnected, reconnecting...")
        return connect_wifi()
    return wlan


def send_readings(readings):
    """Send readings to RPi server with error handling."""
    response = None
    try:
        response = urequests.post(
            f"{secrets.RPI_HOST}/pico",
            headers={"content-type": "application/json"},
            data=ujson.dumps(readings),
        )
        if response.status_code != 201:
            print(f"Server error: {response.status_code}")
    except OSError as e:
        print(f"HTTP request failed: {e}")
    finally:
        if response:
            response.close()


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
        print("Display not available")
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
    """Main loop for reading sensors and sending data."""
    wlan = connect_wifi()
    display = init_display()

    while True:
        wlan = ensure_wifi_connected(wlan)

        readings = {}
        for plant in plants:
            readings[plant.name] = read_moisture(plant)

        update_display(display, readings)

        if wlan and wlan.isconnected():
            send_readings(readings)
        else:
            print("Skipping send: no WiFi")

        utime.sleep(POLLING_INTERVAL_SEC)
        gc.collect()


if __name__ == "__main__":
    main()
