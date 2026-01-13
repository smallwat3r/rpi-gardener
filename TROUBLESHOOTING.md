# Troubleshooting

## Software

**Pico stops sending data**: The Pico can lose sync. Add a cron job to
restart it periodically:

    0 */3 * * * (cd /home/pi/rpi-gardener && make mprestart)

**Email notifications not working**: Ensure `GMAIL_PASSWORD` uses a
Gmail App Password (not your account password).

**Container won't start**: Check that I2C is enabled and devices exist:

    ls -la /dev/i2c-* /dev/gpiochip0 /dev/gpiomem /dev/ttyACM*

**Pico on different serial port**: The app auto-detects `/dev/ttyACM0` or
`/dev/ttyACM1`. You can also set `PICO_SERIAL_PORT` in `.env` to specify
a custom port.

## Hardware

**I2C devices not detected**:
- Check address conflicts (OLED typically 0x3C, LCD typically 0x27)
- Verify correct voltage (OLED: 3.3V, LCD: 5V)
- Use `i2cdetect -y 1` on RPi to scan bus

**Moisture sensors not reading**:
- Verify Pico is powered (check 3V3 LED)
- Check USB serial connection to RPi
- Ensure sensors are connected to correct ADC pins

**DHT22 not responding**:
- Verify 3.3V power
- Check GPIO17 connection
- Some DHT22 modules need a pull-up resistor (4.7kΩ)
