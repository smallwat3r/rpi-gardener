import atexit

from adafruit_ssd1306 import SSD1306_I2C
from board import SCL, SDA
from busio import I2C
from PIL import Image, ImageDraw, ImageFont

from rpi.lib.reading import Reading

_width = 128
_height = 64
_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 17)


class _Display(SSD1306_I2C):
    def clear(self) -> None:
        self.fill(0)
        self.show()

    def render_reading(self, reading: Reading) -> None:
        image = Image.new("1", (_width, _height))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, _width, _height))
        draw.text((23, 0), f"T: {reading.temperature}",
                  font=_font, fill=255)
        draw.text((23, 20), f"H: {reading.humidity}",
                  font=_font, fill=255)
        self.image(image)
        self.show()


display = _Display(_width, _height, I2C(SCL, SDA))


@atexit.register
def _clear_display():
    """Hook to clear the display screen when the program exits."""
    display.clear()
