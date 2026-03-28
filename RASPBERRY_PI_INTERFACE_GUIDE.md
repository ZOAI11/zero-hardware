# Raspberry Pi Interface & Audio System - Complete Build Guide

## Overview

This section adds the Raspberry Pi interface, audio system, and expansion headers for future sensors and actuators:
- Raspberry Pi 40-pin header (includes camera CSI support)
- I2S microphone (INMP441)
- I2S audio amplifier (MAX98357A) + speaker
- ESP32 GPIO expansion header
- Servo/PWM expansion header
- Camera/GPS expansion header

---

## Components Needed

| Ref | Component | Value/Part | LCSC | Search Term |
|-----|-----------|------------|------|-------------|
| J_PI | Raspberry Pi header | 40-pin 2×20 female 2.54mm | C2685 | `header female 2x20` |
| J_MIC | Microphone header | 5-pin female 2.54mm | Search | `header female 1x5` |
| J_AMP | Amplifier header | 5-pin female 2.54mm | Search | `header female 1x5` |
| J_SPK | Speaker connector | 2-pin terminal | C157932 | `terminal 2 pin` |
| J7 | ESP32 expansion | 10-pin female 2.54mm | Search | `header female 1x10` |
| J8 | Servo expansion | 6-pin female 2.54mm | Search | `header female 1x6` |
| J9 | Camera/GPS expansion | 8-pin female 2.54mm | Search | `header female 1x8` |

**Note:** Using headers for INMP441 and MAX98357A modules (not bare ICs) - easier assembly and testing.

---

## Section 1: Raspberry Pi 40-Pin Header

### Why the 40-Pin Header?

**Provides access to:**
- Camera CSI interface (ribbon cable connector on Pi)
- UART communication (ESP32 ↔ Pi)
- I2S audio bus (shared with ESP32)
- GPIO for servos, sensors, expansion
- Power connections (5V and 3.3V)
- Ground pins

### Raspberry Pi Zero 2 W Pinout Reference

**Key pins we'll use:**

```
Pin 1:  3.3V       Pin 2:  5V
Pin 3:  GPIO2      Pin 4:  5V
Pin 5:  GPIO3      Pin 6:  GND
Pin 7:  GPIO4      Pin 8:  GPIO14 (UART TX)
Pin 9:  GND        Pin 10: GPIO15 (UART RX)
Pin 11: GPIO17     Pin 12: GPIO18 (I2S BCK)
Pin 13: GPIO27     Pin 14: GND
Pin 15: GPIO22     Pin 16: GPIO23
Pin 17: 3.3V       Pin 18: GPIO24
Pin 19: GPIO10     Pin 20: GND
Pin 21: GPIO9      Pin 22: GPIO25
Pin 23: GPIO11     Pin 24: GPIO8
Pin 25: GND        Pin 26: GPIO7
Pin 27: ID_SD      Pin 28: ID_SC
Pin 29: GPIO5      Pin 30: GND
Pin 31: GPIO6      Pin 32: GPIO12 (I2S LRCK)
Pin 33: GPIO13     Pin 34: GND
Pin 35: GPIO19     Pin 36: GPIO16
Pin 37: GPIO26     Pin 38: GPIO20 (I2S DIN)
Pin 39: GND        Pin 40: GPIO21 (I2S DOUT)
```

---

## Section 2: I2S Audio System

### What is I2S?

**Inter-IC Sound** - digital audio protocol with 3 signals:
- **BCK (Bit Clock):** Timing for each bit
- **LRCK (Word Select):** Left/Right channel selection
- **DIN (Data In):** Audio data from microphone to processor
- **DOUT (Data Out):** Audio data from processor to amplifier

### I2S Bus Sharing

**ESP32 and Pi will share I2S bus:**
- Both can talk to microphone (INMP441)
- Both can talk to amplifier (MAX98357A)
- Control via software (select which device is active)

### I2S Pin Assignments

**ESP32 I2S Pins:**
- BCK: IO26
- LRCK: IO25 (shared with haptic motor - use different pin)
- DIN: IO22 (conflict with I2C SCL - use different pin)
- DOUT: IO21 (conflict with I2C SDA - use different pin)

**Updated ESP32 I2S Pins (avoiding conflicts):**
- BCK: IO26
- LRCK: IO27
- DIN: IO34 (input only - perfect for microphone)
- DOUT: IO12

**Raspberry Pi I2S Pins (fixed):**
- BCK: GPIO18 (Pin 12)
- LRCK: GPIO19 (Pin 35)
- DIN: GPIO20 (Pin 38)
- DOUT: GPIO21 (Pin 40)

---

## Section 3: Component Connections Overview

### Microphone (INMP441) - J_MIC

```
J_MIC Pin Layout:
1: VCC (3.3V)
2: GND
3: WS (Word Select / LRCK)
4: SCK (Serial Clock / BCK)
5: SD (Serial Data / DIN)
```

**Connections:**
- VCC → VCC_3V3
- GND → GND
- WS → ESP32 IO27 + Pi GPIO19
- SCK → ESP32 IO26 + Pi GPIO18
- SD → ESP32 IO34 + Pi GPIO20

### Amplifier (MAX98357A) - J_AMP

```
J_AMP Pin Layout:
1: VCC (3.3V or 5V - check module)
2: GND
3: DIN (Data In from processor)
4: BCLK (Bit Clock)
5: LRC (Left/Right Clock)
```

**Connections:**
- VCC → VCC_3V3 (or VCC_5V if module requires)
- GND → GND
- DIN → ESP32 IO12 + Pi GPIO21
- BCLK → ESP32 IO26 + Pi GPIO18
- LRC → ESP32 IO27 + Pi GPIO19

**Note:** BCK and LRCK shared between mic and amp (same timing).

---

## Section 4: Expansion Headers

### J7: ESP32 General Expansion (10-pin)

**Exposes unused ESP32 GPIO for future use:**

```
Pin 1:  VCC_3V3
Pin 2:  GND
Pin 3:  IO13 (GPIO/UART RX2)
Pin 4:  IO14 (GPIO/PWM)
Pin 5:  IO15 (GPIO/PWM)
Pin 6:  IO16 (GPIO/PWM/UART RX)
Pin 7:  IO17 (GPIO/PWM/UART TX)
Pin 8:  IO18 (GPIO/PWM/SPI)
Pin 9:  IO19 (GPIO/SPI MISO)
Pin 10: IO23 (GPIO/SPI MOSI)
```

**Future uses:**
- GPS module (UART on IO16/IO17)
- Additional sensors (I2C, SPI, analog)
- Extra LEDs or outputs

### J8: Servo/PWM Expansion (6-pin)

**For camera pan/tilt or other servo motors:**

```
Pin 1:  VCC_5V (servo power - add later)
Pin 2:  GND
Pin 3:  PWM1 → ESP32 IO15 or Pi GPIO12
Pin 4:  PWM2 → ESP32 IO14 or Pi GPIO13
Pin 5:  PWM3 → ESP32 IO13 (optional)
Pin 6:  PWM4 → Pi GPIO18 (optional)
```

**Note:** Servos typically need 5V power. You'll add external 5V supply or regulator later.

### J9: Camera/Sensor Expansion (8-pin)

**Multi-purpose expansion:**

```
Pin 1:  VCC_3V3
Pin 2:  GND
Pin 3:  I2C_SCL (shared with sensors)
Pin 4:  I2C_SDA (shared with sensors)
Pin 5:  UART_TX → ESP32 IO17
Pin 6:  UART_RX → ESP32 IO16
Pin 7:  GPIO1 → ESP32 IO13
Pin 8:  GPIO2 → ESP32 IO23
```

**Future uses:**
- GPS module (UART TX/RX)
- OV7670 camera (I2C control)
- Additional I2C sensors
- General GPIO expansion

---

## Step-by-Step Build Instructions

### STEP 1: Raspberry Pi 40-Pin Header (J_PI)

#### Part A: Add the Header

**1. Search for Component:**
- Press `Shift + F`
- Type: `header female 2x20` or search `C2685`
- Select: 40-pin 2×20 female header (2.54mm pitch)

**Alternative if not found:**
- Use two 20-pin single-row headers side by side
- Or use generic CONN symbol with 40 pins

**2. Place Component:**
- Place in large empty area of schematic
- This is a big component - give it space
- Orient horizontally or vertically (your choice)

**3. Label:**
- Change designator to: `J_PI`
- Add text label: "RASPBERRY_PI_ZERO_2W"

#### Part B: Wire Power Connections

**Pi provides and receives power:**

**From Pi to PCB (Pi powered externally via USB):**
- Pi Pin 2 (5V) → Can provide 5V to PCB (optional)
- Pi Pin 4 (5V) → Same 5V rail
- Pi Pins 1, 17 (3.3V) → Pi's 3.3V regulator (don't use - use PCB's 3.3V)

**From PCB to Pi (Pi powered by PCB):**
- VCC_3V3 → Pi Pin 1 (3.3V) - if you want PCB to power Pi (not recommended)

**Recommended approach:**
- **Leave power pins unconnected for now**
- Power Pi separately via USB
- Power PCB via USB
- **Ground pins MUST be connected** for signal integrity

**Ground connections:**
- Connect **all GND pins** on Pi header to PCB GND:
  - Pins 6, 9, 14, 20, 25, 30, 34, 39 → GND symbol

#### Part C: Wire UART Connections (ESP32 ↔ Pi Communication)

**For ESP32 to talk to Pi:**

**Pi side:**
- Pi Pin 8 (GPIO14 / UART TX) → connects to ESP32 RX
- Pi Pin 10 (GPIO15 / UART RX) → connects to ESP32 TX

**ESP32 side:**
- ESP32 Pin 34 (RXD0) - Already used for programming header
- **Use UART2 instead:**
  - ESP32 IO16 (Pin 27) → UART RX
  - ESP32 IO17 (Pin 28) → UART TX

**Connections:**
- Pi Pin 8 (GPIO14 TX) → ESP32 IO16 (RX)
- Pi Pin 10 (GPIO15 RX) → ESP32 IO17 (TX)
- Label nets: `PI_TX`, `PI_RX`

**This allows bidirectional communication between Pi and ESP32.**

#### Part D: Wire I2S Audio Connections

**Shared I2S bus - Pi and ESP32 both connect to same signals:**

**From Pi:**
- Pi Pin 12 (GPIO18 / BCK) → I2S_BCK net
- Pi Pin 35 (GPIO19 / LRCK) → I2S_LRCK net
- Pi Pin 38 (GPIO20 / DIN) → I2S_DIN net (microphone data)
- Pi Pin 40 (GPIO21 / DOUT) → I2S_DOUT net (to amplifier)

**From ESP32 (same nets):**
- ESP32 IO26 → I2S_BCK net
- ESP32 IO27 → I2S_LRCK net
- ESP32 IO34 → I2S_DIN net
- ESP32 IO12 → I2S_DOUT net

**Create net labels for these four signals - they'll connect to mic and amp later.**

---

### STEP 2: Microphone Header (J_MIC)

#### Part A: Add Header

**1. Search:**
- Type: `header female 1x5`
- Or use 4-pin or 6-pin if 5-pin not available

**2. Place:**
- Place near audio section

**3. Label:**
- Designator: `J_MIC`
- Text: "INMP441_MIC"

#### Part B: Wire Microphone

**Connections:**
```
J_MIC Pin 1 (VCC) → VCC_3V3
J_MIC Pin 2 (GND) → GND
J_MIC Pin 3 (WS/LRCK) → I2S_LRCK net
J_MIC Pin 4 (SCK/BCK) → I2S_BCK net
J_MIC Pin 5 (SD/DIN) → I2S_DIN net
```

**Your INMP441 module plugs into this header.**

---

### STEP 3: Audio Amplifier Header (J_AMP)

#### Part A: Add Header

**1. Search:**
- Type: `header female 1x5`

**2. Place:**
- Near J_MIC

**3. Label:**
- Designator: `J_AMP`
- Text: "MAX98357A_AMP"

#### Part B: Wire Amplifier

**Connections:**
```
J_AMP Pin 1 (VCC) → VCC_3V3 (or VCC_5V if your module needs it)
J_AMP Pin 2 (GND) → GND
J_AMP Pin 3 (DIN) → I2S_DOUT net
J_AMP Pin 4 (BCLK) → I2S_BCK net
J_AMP Pin 5 (LRC) → I2S_LRCK net
```

---

### STEP 4: Speaker Connector (J_SPK)

#### Part A: Add Connector

**1. Search:**
- Type: `terminal 2 pin` or `JST 2 pin`
- Select: Screw terminal or JST connector

**2. Place:**
- Near J_AMP

**3. Label:**
- Designator: `J_SPK`
- Text: "SPEAKER"

#### Part B: Wire Speaker

**Speaker connects directly to amplifier module:**
- Amplifier module has speaker output pins
- J_SPK is just a convenient PCB connector
- Wire J_SPK to amplifier module off-PCB with wires

**For schematic completeness:**
```
J_SPK Pin 1 → Label: SPK+
J_SPK Pin 2 → Label: SPK-
```

**Note:** Actual speaker wiring happens during assembly (module to speaker).

---

### STEP 5: Expansion Headers

#### Part A: J7 (ESP32 Expansion)

**1. Add 10-pin female header:**
- Search: `header female 1x10`
- Place in expansion area
- Label: `J7`, text: "ESP32_EXPANSION"

**2. Wire J7:**
```
Pin 1:  VCC_3V3
Pin 2:  GND
Pin 3:  ESP32 IO13
Pin 4:  ESP32 IO14
Pin 5:  ESP32 IO15
Pin 6:  ESP32 IO16 (shares with Pi UART)
Pin 7:  ESP32 IO17 (shares with Pi UART)
Pin 8:  ESP32 IO18
Pin 9:  ESP32 IO19
Pin 10: ESP32 IO23
```

#### Part B: J8 (Servo Expansion)

**1. Add 6-pin female header:**
- Search: `header female 1x6`
- Place near expansion area
- Label: `J8`, text: "SERVO_PWM"

**2. Wire J8:**
```
Pin 1:  VCC_5V (leave unconnected for now - add 5V rail later)
Pin 2:  GND
Pin 3:  ESP32 IO15 (PWM1)
Pin 4:  ESP32 IO14 (PWM2)
Pin 5:  ESP32 IO13 (PWM3 - optional)
Pin 6:  ESP32 IO2 (PWM4 - optional)
```

**Note:** VCC_5V rail will be added in power expansion section if needed.

#### Part C: J9 (Camera/GPS Expansion)

**1. Add 8-pin female header:**
- Search: `header female 1x8`
- Place near expansion area
- Label: `J9`, text: "CAM_GPS_EXP"

**2. Wire J9:**
```
Pin 1:  VCC_3V3
Pin 2:  GND
Pin 3:  I2C_SCL (shared with sensors)
Pin 4:  I2C_SDA (shared with sensors)
Pin 5:  ESP32 IO17 (UART TX / shares with J7)
Pin 6:  ESP32 IO16 (UART RX / shares with J7)
Pin 7:  ESP32 IO13 (GPIO / shares with J7)
Pin 8:  ESP32 IO23 (GPIO / shares with J7)
```

---

## Updated ESP32 Pin Usage Summary

| ESP32 Pin | Pin # | Function | Connected To |
|-----------|-------|----------|--------------|
| IO21 | 33 | I2C SDA | OLED Left + MPU6050 |
| IO22 | 36 | I2C SCL | OLED Left + MPU6050 |
| IO32 | 8 | I2C SDA Bus 2 | OLED Right |
| IO33 | 9 | I2C SCL Bus 2 | OLED Right |
| IO25 | 10 | PWM | Haptic motor |
| IO4 | 26 | Digital Out | Activity LED |
| **IO26** | **12** | **I2S BCK** | **Mic + Amp** |
| **IO27** | **13** | **I2S LRCK** | **Mic + Amp** |
| **IO34** | **6** | **I2S DIN** | **Microphone** |
| **IO12** | **14** | **I2S DOUT** | **Amplifier** |
| **IO16** | **27** | **UART RX** | **Pi + J7 + J9** |
| **IO17** | **28** | **UART TX** | **Pi + J7 + J9** |
| IO13 | 16 | GPIO/PWM | J7, J8, J9 expansion |
| IO14 | 13 | GPIO/PWM | J7, J8 expansion |
| IO15 | 15 | GPIO/PWM | J7, J8 expansion |
| IO18 | 29 | GPIO/SPI | J7 expansion |
| IO19 | 31 | GPIO/SPI | J7 expansion |
| IO23 | 37 | GPIO/SPI | J7, J9 expansion |
| IO2 | 24 | GPIO | J8 expansion (optional) |

---

## Raspberry Pi & Audio Section - Verification Checklist

### Raspberry Pi Header (J_PI):
- [ ] 40-pin header placed and labeled
- [ ] All GND pins connected (pins 6, 9, 14, 20, 25, 30, 34, 39)
- [ ] Pi GPIO14 (Pin 8) → ESP32 IO16 (UART)
- [ ] Pi GPIO15 (Pin 10) → ESP32 IO17 (UART)
- [ ] Pi GPIO18 (Pin 12) → I2S_BCK
- [ ] Pi GPIO19 (Pin 35) → I2S_LRCK
- [ ] Pi GPIO20 (Pin 38) → I2S_DIN
- [ ] Pi GPIO21 (Pin 40) → I2S_DOUT

### Audio System:
- [ ] J_MIC (microphone) header placed
- [ ] J_MIC connected to I2S bus (BCK, LRCK, DIN)
- [ ] J_AMP (amplifier) header placed
- [ ] J_AMP connected to I2S bus (BCK, LRCK, DOUT)
- [ ] J_SPK (speaker) connector placed
- [ ] ESP32 I2S pins connected to same nets as Pi

### Expansion Headers:
- [ ] J7 (10-pin) placed with ESP32 GPIO
- [ ] J8 (6-pin) placed for servo PWM
- [ ] J9 (8-pin) placed for camera/GPS

---

## Testing After Assembly

### Test 1: UART Communication (ESP32 ↔ Pi)
1. Upload serial echo program to ESP32
2. Configure Pi UART
3. Send data from Pi → ESP32
4. Should receive response

### Test 2: I2S Microphone
1. Run I2S recording test on ESP32 or Pi
2. Speak into INMP441 mic
3. Should capture audio data

### Test 3: I2S Audio Playback
1. Send test tone via I2S to MAX98357A
2. Should hear tone from speaker

### Test 4: Raspberry Pi Camera
1. Connect Pi Camera via CSI ribbon cable
2. Run `raspistill` or `libcamera-still` test
3. Should capture images

---

## Future Additions

### When Adding Servos:
1. Add 5V power supply (buck converter or external)
2. Connect to J8 VCC_5V pin
3. Add 1000µF capacitor near servos
4. Connect servo PWM signals to J8 pins 3-6

### When Adding GPS:
1. Connect GPS module to J9 pins 5-6 (UART)
2. Configure ESP32 UART2
3. Parse NMEA sentences in software

### When Adding Camera (OV7670):
1. Connect to J9 I2C pins for control
2. Connect parallel data to J7 GPIO pins
3. Requires 8+ GPIO pins for data capture

---

*Raspberry Pi Interface & Audio System Guide Complete!*
