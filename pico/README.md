# Pico

This module uses Micropython and needs to be set-up on the Raspberry Pico
board, to read values from capacitative soil moisture sensors (v1.2).

## Installation

Install the `main.py` file onto the Pico.

Use `mpremote` to connect remotely to the Pico and install the `ssd1306` 
lib.

    mpremote a0
    mpremote mip install ssd1306

Create a `secrets.py` file on the Pico, in the same directory than the 
`main.py` file, this file needs to contain secret values in order to
communicate with our main RPi.

    SSID='<ssid name>'
    SSID_PASSWORD='<ssid password>'
    RPI_HOST='http://192.168.1.XXX'
