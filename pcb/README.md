# RPi Gardener HAT PCB

A custom PCB that combines a Raspberry Pi HAT with an integrated Raspberry Pi Pico for the RPi Gardener project.

## Overview

This PCB serves as a unified interface board that:
- Mounts directly on a Raspberry Pi as a HAT (Hardware Attached on Top)
- Integrates a Raspberry Pi Pico for analog sensor readings
- Provides connectors for all sensors and displays

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

### KiCad (`kicad/`)

| File | Description |
|------|-------------|
| `rpi-gardener-hat.kicad_pro` | KiCad project file |
| `rpi-gardener-hat.kicad_sch` | Schematic |
| `rpi-gardener-hat.kicad_pcb` | PCB layout |
| `rpi-gardener-hat.pretty/` | Custom footprint library |
| `gerber.zip` | Manufacturing files (Gerber + drill) |

### 3D Printable Parts (`case/`)

| File | Description |
|------|-------------|
| `rpi-gardener-base.scad` | OpenSCAD source for base plate |
| `rpi-gardener-base.stl` | Base plate STL |
| `rpi-gardener-display-plate.scad` | OpenSCAD source for display plate |
| `rpi-gardener-display-plate.stl` | Display plate STL |

## 3D Printable Base

A simple mounting base for securing the Raspberry Pi and HAT assembly using physical spacers.

### Base Specifications

| Property | Value |
|----------|-------|
| Dimensions | 90mm x 62mm x 1.5mm |
| Supports | Raspberry Pi 4 (85mm x 56mm) |
| Mounting Pattern | 58mm x 49.5mm (matches PCB) |
| Hole Diameter | 3.2mm (M3 clearance) |
| Holes | 4 (3.5mm from right edge, aligned with RPi and HAT mounting holes) |

### Regenerating STL
```bash
cd case
openscad -o rpi-gardener-base.stl rpi-gardener-base.scad
openscad -o rpi-gardener-display-plate.stl rpi-gardener-display-plate.scad
```

## Assembly Instructions

### Required Hardware

| Item | Quantity | Notes |
|------|----------|-------|
| M3 screws | 4 | Bottom, thread into F-M spacers |
| M3 screws | 4 | Top, thread into F-F spacers |
| M3 spacers (5-6mm, F-M) | 4 | Between base and RPi |
| M3 washers (1mm) | 4 | Between RPi and next spacer |
| M3 spacers (10mm, F-M) | 4 | Between RPi and HAT |
| M3 spacers (20mm, F-M) | 4 | Above HAT |
| M3 spacers (5-6mm, F-F) | 4 | Top, screws thread into these |
| Rubber bumpons (8-10mm) | 4 | Anti-slip feet under base plate |
| M2 x 1mm screws | 8 | To attach OLEDs to display plate |
| M2 nuts | 8 | To secure OLEDs |
| M3 screws (for LCD) | 4 | To attach LCD to display plate |
| M3 spacers (5-6mm, F-M) | 4 | Between display plate and LCD |
| M3 nuts (for LCD) | 4 | To secure LCD |
| 2x16 pin male-to-female header | 2 | For J1 (RPi GPIO), allows RPi plug/unplug |
| 1x4 pin male-to-female header | 3 | For J2, J5 (OLEDs) and J3 (LCD) |
| 1x3 pin male-to-female header | 1 | For J4 (DHT22) |
| Pin headers for Pico | 2x20 | Or solder Pico directly |
| Capacitive soil sensors | 3 | Solder directly to J6, J7, J8 |
| Small dupont wires (male-to-female) | - | Modules (OLED, LCD, DHT22) have male pins, HAT has female headers |

**Important note:** The RPi 4 has native M2.5 mounting holes. You may need to lightly drill or ream them to fit M3 screws.

### Stack Assembly

```
    ┌─────────────────────┐
    │   4x M3 screws      │  ← Thread into F-F spacers
    ├─────────────────────┤
    │   Display plate     │  ← Top plate with OLEDs + LCD
    ├─────────────────────┤
    │   4x spacers 5-6mm  │  ← F-F (top screws thread here)
    │ + 4x spacers 20mm   │  ← F-M
    ├─────────────────────┤
    │   HAT (PCB)         │  ← RPi Gardener HAT with Pico
    ├─────────────────────┤
    │   4x spacers 10mm   │  ← F-M
    ├─────────────────────┤
    │   4x washers 1mm    │  ← Fine adjustment
    ├─────────────────────┤
    │   Raspberry Pi      │  ← RPi 4
    ├─────────────────────┤
    │   4x spacers 5-6mm  │  ← F-M
    ├─────────────────────┤
    │   Base plate        │  ← 3D printed base
    ├─────────────────────┤
    │   4x M3 screws      │  ← Thread into F-M spacers
    └─────────────────────┘
```

### Assembly Steps

1. **Solder Components to HAT**
   - Solder 2x 16-pin male-to-female headers for J1 (RPi GPIO) - allows plugging/unplugging RPi
   - Solder 1x4 pin male-to-female headers for J2, J5 (OLEDs) and J3 (LCD)
   - Solder 1x3 pin male-to-female header for J4 (DHT22)
   - Solder capacitive soil sensors directly to J6, J7, J8 (or use pins if you want to remove them easily)
   - Mount Pico: solder directly or use pin headers for removable mounting

2. **Mount Displays to Plate**
   - Attach OLEDs using 8x M2 screws (1mm) and 8x M2 nuts
   - Attach LCD using 4x M3 screws, 4x M3 spacers (5-6mm F-M), and 4x M3 nuts

3. **Build the Stack**
   - Insert 4x M3 screws from bottom through the base plate into 4x 5-6mm F-M spacers
   - Place Raspberry Pi onto spacers
   - Add 4x 1mm washers
   - Add 4x 10mm F-M spacers
   - Mount HAT, seating GPIO connector onto RPi header
   - Add 4x 20mm F-M spacers
   - Add 4x 5-6mm F-F spacers

4. **Connect Peripherals**
   - Connect OLED displays to J2, J5 using dupont wires
   - Connect LCD 1602A to J3 using dupont wires
   - Connect DHT22 to J4 using dupont wires
   - Connect Pico USB to RPi USB port

5. **Secure Top Plate**
   - Place display plate on top
   - Secure with 4x M3 screws from top

## Manufacturing

### PCB Fabrication
Upload `gerber.zip` to your preferred PCB manufacturer (JLCPCB, PCBWay, etc.).

Recommended settings:
- Layers: 2
- Thickness: 1.6mm
- Surface finish: HASL (lead free) or ENIG
