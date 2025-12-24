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
from rpi.lib.config import settings

_font = ImageFont.truetype(settings.display.font_path, settings.display.font_size)


class Display(SSD1306_I2C):
    """OLED display for rendering DHT22 sensor readings."""

    def __init__(self) -> None:
        """Initialize the display with I2C connection."""
        display = settings.display
        super().__init__(display.width, display.height, I2C(SCL, SDA))

    def clear(self) -> None:
        """Clear the display."""
        self.fill(0)
        self.show()

    def render_reading(self, reading: Reading) -> None:
        """Render a reading on the display."""
        display = settings.display
        image = Image.new("1", (display.width, display.height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, display.width, display.height))
        draw.text(
            (display.text_x_offset, display.text_y_temp),
            f"T: {reading.temperature}",
            font=_font,
            fill=255
        )
        draw.text(
            (display.text_x_offset, display.text_y_humidity),
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
