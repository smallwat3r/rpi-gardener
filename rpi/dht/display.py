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
from rpi.lib.config import get_settings

_font: ImageFont.FreeTypeFont | None = None


def _get_font() -> ImageFont.FreeTypeFont:
    """Get the font, loading it lazily on first use."""
    global _font
    if _font is None:
        s = get_settings()
        _font = ImageFont.truetype(s.display.font_path, s.display.font_size)
    return _font


class Display(SSD1306_I2C):
    """OLED display for rendering DHT22 sensor readings."""

    def __init__(self) -> None:
        """Initialize the display with I2C connection."""
        cfg = get_settings().display
        super().__init__(cfg.width, cfg.height, I2C(SCL, SDA))

    def clear(self) -> None:
        """Clear the display."""
        self.fill(0)
        self.show()

    def render_reading(self, reading: Reading) -> None:
        """Render a reading on the display."""
        cfg = get_settings().display
        image = Image.new("1", (cfg.width, cfg.height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, cfg.width, cfg.height))
        draw.text(
            (cfg.text_x_offset, cfg.text_y_temp),
            f"T: {reading.temperature}",
            font=_get_font(),
            fill=255
        )
        draw.text(
            (cfg.text_x_offset, cfg.text_y_humidity),
            f"H: {reading.humidity}",
            font=_get_font(),
            fill=255
        )
        self.image(image)
        self.show()


_display: Display | None = None


def get_display() -> Display:
    """Get the display instance, creating it lazily."""
    global _display
    if _display is None:
        _display = Display()
    return _display


@atexit.register
def _clear_display():
    """Hook to clear the display screen when the program exits."""
    if _display is not None:
        _display.clear()
