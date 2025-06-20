import atexit
from collections import namedtuple

from adafruit_ssd1306 import SSD1306_I2C
from board import SCL, SDA
from busio import I2C
from PIL import Image, ImageDraw, ImageFont

from rpi.lib.reading import Reading

_ScreenSize = namedtuple("ScreenSize", "w h")
_size = _ScreenSize(128, 64)
_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 17)


class _Display(SSD1306_I2C):
    def clear(self) -> None:
        self.fill(0)
        self.show()

    def render_reading(self, reading: Reading) -> None:
        image = Image.new("1", _size)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, _size.w, _size.h))
        draw.text((23, 0), f"T: {reading.temperature}",
                  font=_font, fill=255)
        draw.text((23, 20), f"H: {reading.humidity}",
                  font=_font, fill=255)
        self.image(image)
        self.show()


display = _Display(_size.w, _size.h, I2C(SCL, SDA))


@atexit.register
def _clear_display():
    """Hook to clear the display screen when the program exits."""
    display.clear()
