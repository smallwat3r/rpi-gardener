# RPi Gardener HAT PCB

A custom PCB that combines a Raspberry Pi HAT with an integrated Raspberry Pi Pico for the RPi Gardener project.

## Overview

This PCB serves as a unified interface board that:
- Mounts directly on a Raspberry Pi as a HAT (Hardware Attached on Top)
- Integrates a Raspberry Pi Pico for analog sensor readings
- Provides connectors for all sensors and displays

## Board Specifications

| Property | Value |
|----------|-------|
| Dimensions | 65mm x 56mm (standard RPi HAT size) |
| Layers | 2 (F.Cu, B.Cu) |
| Thickness | 1.6mm |
| Mounting Holes | 4x M3 at standard HAT positions |
| Ground Planes | Both layers (unified GND net) |
| KiCad Version | 9.x |

## Components

### Connectors

| Ref | Description | Pins | Connection |
|-----|-------------|------|------------|
| J1 | RPi GPIO Header | 2x20 | Raspberry Pi 40-pin GPIO |
| J2 | OLED Display (RPi) | 1x4 | I2C SSD1306 128x64 |
| J3 | LCD Display | 1x4 | I2C 1602A with PCF8574 |
| J4 | DHT22 Sensor | 1x3 | Temperature/Humidity |
| J5 | OLED Display (Pico) | 1x4 | I2C SSD1306 128x64 |
| J6 | Moisture Sensor 1 | 1x3 | Capacitive soil sensor |
| J7 | Moisture Sensor 2 | 1x3 | Capacitive soil sensor |
| J8 | Moisture Sensor 3 | 1x3 | Capacitive soil sensor |

### Modules

| Ref | Description | Footprint |
|-----|-------------|-----------|
| U1 | Raspberry Pi Pico | Through-hole (40 pins) |

### Mounting

| Ref | Description |
|-----|-------------|
| H1-H4 | M3 mounting holes at standard HAT positions |

## Pin Assignments

### Raspberry Pi GPIO (directly from J1)

| Function | GPIO | Pin |
|----------|------|-----|
| I2C SDA | GPIO2 | 3 |
| I2C SCL | GPIO3 | 5 |
| DHT22 Data | GPIO17 | 11 |
| 3.3V Power | - | 1, 17 |
| 5V Power | - | 2, 4 |
| Ground | - | 6, 9, 14, 20, 25, 30, 34, 39 |

### Raspberry Pi Pico (U1)

| Function | GPIO | Pin |
|----------|------|-----|
| OLED SDA | GP0 | 1 |
| OLED SCL | GP1 | 2 |
| Moisture 1 | GP26/ADC0 | 31 |
| Moisture 2 | GP27/ADC1 | 32 |
| Moisture 3 | GP28/ADC2 | 34 |
| 3.3V Out | 3V3 | 36 |
| Ground | GND | 3, 8, 13, 18, 23, 28, 33, 38 |

## Connector Pinouts

### J2 - OLED RPi (SSD1306 I2C)
```
Pin 1: VCC (3.3V)
Pin 2: GND
Pin 3: SDA (GPIO2)
Pin 4: SCL (GPIO3)
```

### J3 - LCD I2C (1602A with PCF8574)
```
Pin 1: VCC (5V)
Pin 2: GND
Pin 3: SDA (GPIO2)
Pin 4: SCL (GPIO3)
```

### J4 - DHT22 Sensor
```
Pin 1: VCC (3.3V)
Pin 2: DATA (GPIO17)
Pin 3: GND
```

### J5 - OLED Pico (SSD1306 I2C)
```
Pin 1: VCC (Pico 3.3V)
Pin 2: GND
Pin 3: SDA (GP0)
Pin 4: SCL (GP1)
```

### J6, J7, J8 - Moisture Sensors
```
Pin 1: VCC (Pico 3.3V)
Pin 2: SIG (GP26/GP27/GP28)
Pin 3: GND
```

## I2C Bus Configuration

The board has two separate I2C buses:

### RPi I2C Bus (GPIO2/GPIO3)
- OLED Display (J2) - typically address 0x3C
- LCD Display (J3) - typically address 0x27 or 0x3F

### Pico I2C Bus (GP0/GP1)
- OLED Display (J5) - typically address 0x3C

## USB Passthrough

The Pico's USB port is accessible at the board edge for:
- Serial communication with the Raspberry Pi
- Firmware updates
- Debugging

Connect using a USB-A to Micro-USB cable from any RPi USB port to the Pico.

## Files

| File | Description |
|------|-------------|
| `rpi-gardener-hat.kicad_pro` | KiCad project file |
| `rpi-gardener-hat.kicad_sch` | Schematic |
| `rpi-gardener-hat.kicad_pcb` | PCB layout |
| `rpi-gardener-hat.pretty/` | Custom footprint library |
| `gerber.zip` | Manufacturing files (Gerber + drill) |
| `BOM.txt` | Bill of materials with pin assignments |
| `rpi-gardener-base.scad` | OpenSCAD source for 3D printable base |
| `rpi-gardener-base.stl` | 3D printable mounting base |

## 3D Printable Base

A simple mounting base for securing the Raspberry Pi and HAT assembly using physical spacers.

### Base Specifications

| Property | Value |
|----------|-------|
| Dimensions | 90mm x 62mm x 3mm |
| Supports | Raspberry Pi 4 (85mm x 56mm) |
| Mounting Pattern | 58mm x 49mm (standard RPi/HAT) |
| Hole Diameter | 3.2mm (M3 clearance) |
| Holes | 4 (centered, aligned with RPi and HAT mounting holes) |

### Features
- Simple flat plate design (use your own spacers)
- 4x M3 mounting holes at standard RPi positions
- Ventilation slots for cooling
- USB cable cutout on the side

### Printing Settings
- Layer height: 0.2mm
- Infill: 20%
- Material: PLA or PETG
- Supports: Not required

### Regenerating STL
```bash
openscad -o rpi-gardener-base.stl rpi-gardener-base.scad
```

### Customization
Edit `rpi-gardener-base.scad` to adjust:
- `hole_diameter` - change hole size (default 3.2mm for M3)
- `vent_slots` - enable/disable ventilation
- `usb_cutout` - enable/disable cable cutout
- `base_thickness` - plate thickness (default 3mm)

## Assembly Instructions

### Required Hardware

| Item | Quantity | Notes |
|------|----------|-------|
| M3 x 25-30mm screws | 4 | Length depends on spacer height |
| M3 nuts | 4 | To secure on top |
| M3 spacers (5-6mm) | 4 | Between base and RPi |
| M3 spacers (10-12mm) | 4 | Between RPi and HAT |
| 2x20 pin socket header | 1 | For J1 (RPi GPIO) |
| 1x4 pin headers | 3 | For J2, J3, J5 |
| 1x3 pin headers | 4 | For J4, J6, J7, J8 |
| Pin headers for Pico | 2x20 | Or solder Pico directly |

### Assembly Steps

1. **Solder Headers**
   - Solder the 2x20 socket header (J1) first - ensure alignment
   - Solder 1x4 pin headers for J2, J3, J5
   - Solder 1x3 pin headers for J4, J6, J7, J8

2. **Mount Pico**
   - Option A: Solder Pico directly to PCB
   - Option B: Use pin headers for removable mounting

3. **Prepare Base**
   - 3D print the base plate
   - Insert M3 screws from bottom through the 4 holes

4. **Add First Spacers**
   - Thread 5-6mm spacers onto each screw
   - These provide clearance for RPi bottom components

5. **Mount Raspberry Pi**
   - Place RPi onto the spacers, aligning with screw holes
   - The RPi mounting holes are 58mm x 49mm (same as HAT)

6. **Add Second Spacers**
   - Thread 10-12mm spacers onto each screw above the RPi
   - These provide clearance for GPIO header and components

7. **Mount HAT**
   - Align HAT with RPi GPIO header
   - Lower onto spacers while seating the GPIO connector
   - Secure with M3 nuts on top

8. **Connect Sensors**
   - Connect displays to J2, J3, J5
   - Connect DHT22 to J4
   - Connect moisture sensors to J6, J7, J8

9. **USB Connection**
   - Connect Pico USB to RPi USB port for serial communication

## Manufacturing

### PCB Fabrication
Upload `gerber.zip` to your preferred PCB manufacturer (JLCPCB, PCBWay, OSHPark, etc.).

Recommended settings:
- Layers: 2
- Thickness: 1.6mm
- Surface finish: HASL or ENIG
- Copper weight: 1oz
- Solder mask: Any color
- Silkscreen: White

### Design Rules (used in this design)
- Min track width: 0.2mm
- Min clearance: 0.2mm
- Min via diameter: 0.6mm
- Min via drill: 0.3mm
- Min hole diameter: 0.3mm

## Troubleshooting

### I2C Devices Not Detected
- Check address conflicts (OLED typically 0x3C, LCD typically 0x27)
- Verify correct voltage (OLED: 3.3V, LCD: 5V)
- Use `i2cdetect -y 1` on RPi to scan bus

### Moisture Sensors Not Reading
- Verify Pico is powered (check 3V3 LED)
- Check USB serial connection to RPi
- Ensure sensors are connected to correct ADC pins

### DHT22 Not Responding
- Verify 3.3V power
- Check GPIO17 connection
- Some DHT22 modules need a pull-up resistor (4.7kΩ)

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | - | Initial design with fan support |
| 1.1 | - | Removed fan circuit |
| 1.2-compact | 2026-01-07 | Reduced to standard HAT size (65x56mm), added ground planes on both layers, unified ground nets, fixed GPIO header orientation, aligned connectors with 7mm spacing |

## License

This hardware design is provided as-is for the RPi Gardener project.
