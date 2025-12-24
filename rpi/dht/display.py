"""OLED display module for rendering sensor readings.

Provides a Display class for rendering temperature and humidity readings
on an SSD1306 OLED display connected via I2C.
"""
import atexit

from adafruit_ssd1306 import SSD1306_I2C
from board import SCL, SDA
from busio import I2C
from PIL import Image, ImageDraw, ImageFont

from rpi.dht.models import Reading
from rpi.lib.config import (DISPLAY_FONT_PATH, DISPLAY_FONT_SIZE,
                            DISPLAY_HEIGHT, DISPLAY_TEXT_X_OFFSET,
                            DISPLAY_TEXT_Y_HUMIDITY, DISPLAY_TEXT_Y_TEMP,
                            DISPLAY_WIDTH)

_font = ImageFont.truetype(DISPLAY_FONT_PATH, DISPLAY_FONT_SIZE)


class Display(SSD1306_I2C):
    """OLED display for rendering DHT22 sensor readings."""

    def __init__(self) -> None:
        """Initialize the display with I2C connection."""
        super().__init__(DISPLAY_WIDTH, DISPLAY_HEIGHT, I2C(SCL, SDA))

    def clear(self) -> None:
        """Clear the display."""
        self.fill(0)
        self.show()

    def render_reading(self, reading: Reading) -> None:
        """Render a reading on the display."""
        image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT))
        draw.text(
            (DISPLAY_TEXT_X_OFFSET, DISPLAY_TEXT_Y_TEMP),
            f"T: {reading.temperature}",
            font=_font,
            fill=255
        )
        draw.text(
            (DISPLAY_TEXT_X_OFFSET, DISPLAY_TEXT_Y_HUMIDITY),
            f"H: {reading.humidity}",
            font=_font,
            fill=255
        )
        self.image(image)
        self.show()


# Global display instance
display = Display()


@atexit.register
def _clear_display():
    """Hook to clear the display screen when the program exits."""
    display.clear()
