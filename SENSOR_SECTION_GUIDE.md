# Sensor & Display Section - Complete Build Guide

## Overview

This section adds all the sensors, displays, and output devices that give your ZoarkBot its personality and awareness:
- 2× OLED displays (eyes)
- MPU6050 IMU (balance/motion sensing)
- Haptic motor (vibration feedback)
- Activity LED (status indicator)

---

## Components Needed

| Ref | Component | Value/Part | Component | Search Term | LCSC |
|-----|-----------|------------|-----------|-------------|------|
| J3 | OLED Left header | 4-pin **female** 2.54mm | `header female 1x4` | C492393 |
| J4 | OLED Right header | 4-pin **female** 2.54mm | `header female 1x4` | C492393 |
| J5 | MPU6050 header | 8-pin **female** 2.54mm | `header female 1x8` | C50950 |
| R3 | I2C pull-up (SCL) | 4.7kΩ 0805 | C17673 | `4.7k 0805` |
| R4 | I2C pull-up (SDA) | 4.7kΩ 0805 | C17673 | `4.7k 0805` |
| R5 | LED current limit | 1kΩ 0805 | C17513 | `1k 0805` |
| Q1 | Haptic motor driver | 2N7002 SOT-23 | C8545 | `2N7002` |
| D2 | Flyback diode | 1N4148 SOD-123 | C81598 | `1N4148` |
| R6 | MOSFET gate resistor | 1kΩ 0805 | C17513 | `1k 0805` |
| LED1 | Activity LED | Green 0805 | C2297 | `LED 0805 green` |
| J6 | Haptic motor connector | 2-pin JST | C157932 | `JST PH 2P` |

---

## Section 1: OLED Displays (Headers for External Modules)

### Why Headers Instead of Bare ICs?

**Using external OLED modules is MUCH easier:**
- You already have working SSD1306 OLED modules
- Bare OLED IC design requires complex circuits (128×64 matrix, charge pumps, etc.)
- Modules are pre-tested and proven
- Can upgrade to bare ICs in v2.0 after proving concept

### OLED Left Eye (J3) - Connected to ESP32

**Pin Configuration:**
```
J3 (4-pin header):
Pin 1: GND
Pin 2: VCC (3.3V)
Pin 3: SCL (I2C Clock)
Pin 4: SDA (I2C Data)
```

**Connections:**
```
J3 Pin 1 → GND
J3 Pin 2 → VCC_3V3
J3 Pin 3 → ESP32 Pin 36 (IO22) + R3 (4.7kΩ pull-up to VCC_3V3)
J3 Pin 4 → ESP32 Pin 33 (IO21) + R4 (4.7kΩ pull-up to VCC_3V3)
```

**I2C Address:** 0x3C (default for most SSD1306 modules)

---

### OLED Right Eye (J4) - Connected to ESP32

**Pin Configuration:**
```
J4 (4-pin header):
Pin 1: GND
Pin 2: VCC (3.3V)
Pin 3: SCL (I2C Clock)
Pin 4: SDA (I2C Data)
```

**Connections:**
```
J4 Pin 1 → GND
J4 Pin 2 → VCC_3V3
J4 Pin 3 → ESP32 Pin 9 (IO33) - Separate I2C bus
J4 Pin 4 → ESP32 Pin 8 (IO32) - Separate I2C bus
```

**Why separate I2C bus?** Both OLEDs have same I2C address (0x3C), so we use two I2C buses to control them independently.

**I2C Address:** 0x3C (same as left, but on different bus)

---

### Step-by-Step: Adding OLED Headers

#### Step 1: Add J3 (Left OLED Header)

1. **Search:** `header female 1x4` or `socket 1x4`
2. **Select:** 4-pin straight **female** header socket (LCSC C492393)
3. **Place:** To the right of ESP32 on schematic
4. **Label:** Change designator to `J3`
5. **Add text label:** "OLED_LEFT" near connector

**Note:** Female headers are sockets that receive the male pins on your OLED module.

#### Step 2: Wire J3 Connections

```
J3 Pin 1 → GND symbol
J3 Pin 2 → VCC_3V3 net
J3 Pin 3 → (will connect to SCL net)
J3 Pin 4 → (will connect to SDA net)
```

#### Step 3: Add I2C Pull-up Resistors

**Why pull-ups?** I2C is an open-drain protocol - requires pull-up resistors on SCL and SDA lines.

1. **Add R3 (4.7kΩ):**
   - Search: `4.7k 0805`
   - Place near J3
   - One end → VCC_3V3
   - Other end → Junction (will connect to SCL)
   - Label: `R3`

2. **Add R4 (4.7kΩ):**
   - Search: `4.7k 0805`
   - Place near J3
   - One end → VCC_3V3
   - Other end → Junction (will connect to SDA)
   - Label: `R4`

#### Step 4: Connect I2C Bus to ESP32

**Create SCL net:**
1. Wire from R3 junction → J3 Pin 3
2. Wire from same junction → ESP32 Pin 36 (IO22)
3. Click junction, press `N`, name net: `I2C_SCL` or `SCL_LEFT`

**Create SDA net:**
1. Wire from R4 junction → J3 Pin 4
2. Wire from same junction → ESP32 Pin 33 (IO21)
3. Click junction, press `N`, name net: `I2C_SDA` or `SDA_LEFT`

#### Step 5: Add J4 (Right OLED Header)

1. **Search:** `header female 1x4`
2. **Select:** 4-pin **female** header socket (LCSC C492393)
3. **Place:** Below or next to J3
4. **Label:** Change to `J4`
5. **Add text label:** "OLED_RIGHT"

#### Step 6: Wire J4 Connections

**Right OLED uses separate I2C bus (no pull-ups needed if short wires):**

```
J4 Pin 1 → GND
J4 Pin 2 → VCC_3V3
J4 Pin 3 → ESP32 Pin 9 (IO33) - Label net: SCL_RIGHT
J4 Pin 4 → ESP32 Pin 8 (IO32) - Label net: SDA_RIGHT
```

**Note:** If your OLED modules are more than 10cm away from PCB, add 4.7kΩ pull-ups on SCL_RIGHT and SDA_RIGHT too.

---

## Section 2: MPU6050 IMU (Motion Sensor)

### Using Module Header (Recommended)

**MPU6050 module has 8 pins, but we only use 6:**

```
J5 (8-pin header) - or use 6-pin if your module has 6:
Pin 1: VCC (3.3V)
Pin 2: GND
Pin 3: SCL (shares I2C with left OLED)
Pin 4: SDA (shares I2C with left OLED)
Pin 5: XDA (leave unconnected)
Pin 6: XCL (leave unconnected)
Pin 7: AD0 (I2C address select)
Pin 8: INT (interrupt - optional)
```

### Step-by-Step: Adding MPU6050 Header

#### Step 1: Add J5 Header

1. **Search:** `header female 1x8` (or `header female 1x6` if your module has 6 pins)
2. **Select:** **Female** header socket (LCSC C50950 for 8-pin, or C124413 for 6-pin)
3. **Place:** Near J3 (left OLED area)
4. **Label:** Change to `J5`
5. **Add text:** "MPU6050_IMU"

**Note:** Female socket receives the male pins on your MPU6050 module.

#### Step 2: Wire MPU6050 Connections

```
J5 Pin 1 (VCC) → VCC_3V3
J5 Pin 2 (GND) → GND
J5 Pin 3 (SCL) → I2C_SCL net (shared with left OLED)
J5 Pin 4 (SDA) → I2C_SDA net (shared with left OLED)
J5 Pin 5 (XDA) → Leave unconnected
J5 Pin 6 (XCL) → Leave unconnected
J5 Pin 7 (AD0) → GND (sets I2C address to 0x68)
J5 Pin 8 (INT) → Leave unconnected (or connect to ESP32 GPIO if you want interrupts)
```

**Why share I2C bus with left OLED?** MPU6050 has different I2C address (0x68) than OLED (0x3C), so they can coexist on same bus.

---

## Section 3: Haptic Motor Circuit

### Circuit Function

Drives a small vibration motor (3V DC) using ESP32 GPIO with MOSFET switching.

### Complete Circuit

```
ESP32 Pin 10 (IO25) → R6 (1kΩ) → Q1 Gate (2N7002)
                                  Q1 Drain → J6 Pin 1 (Motor +)
                                           → D2 Cathode (flyback)
                                  Q1 Source → GND
                                  
VCC_3V3 → J6 Pin 2 (Motor +) → D2 Anode
```

**Components:**
- Q1: N-channel MOSFET (2N7002) - switches motor on/off
- D2: Flyback diode (1N4148) - protects MOSFET from motor back-EMF
- R6: Gate resistor (1kΩ) - limits current to MOSFET gate
- J6: 2-pin JST connector for motor

### Step-by-Step: Building Haptic Motor Circuit

#### Step 1: Add MOSFET (Q1)

1. **Search:** `2N7002` or `2N7002 SOT-23`
2. **Select:** 2N7002 MOSFET (LCSC C8545)
3. **Place:** In empty area of schematic
4. **Label:** Change to `Q1`

**2N7002 Pinout (SOT-23):**
```
Pin 1: Gate (control input)
Pin 2: Source (to GND)
Pin 3: Drain (to load)
```

#### Step 2: Add Gate Resistor (R6)

1. **Search:** `1k 0805`
2. **Place:** Between ESP32 and Q1
3. **Wire:**
   - One end → ESP32 Pin 10 (IO25)
   - Other end → Q1 Pin 1 (Gate)
4. **Label:** `R6`
5. **Add net label:** `HAPTIC_CTRL` between R6 and Q1

#### Step 3: Add Flyback Diode (D2)

1. **Search:** `1N4148` or `1N4148 SOD-123`
2. **Select:** 1N4148 diode (LCSC C81598)
3. **Place:** Parallel to motor load
4. **Label:** `D2`

**Diode orientation (CRITICAL):**
```
Cathode (marked end) → Drain side (motor negative)
Anode → VCC_3V3 side (motor positive)
```

#### Step 4: Add Motor Connector (J6)

1. **Search:** `JST PH 2P` or `connector 2 pin`
2. **Select:** 2-pin JST connector (LCSC C157932)
3. **Place:** Near Q1
4. **Label:** `J6`
5. **Add text:** "HAPTIC_MOTOR"

#### Step 5: Wire Complete Circuit

**Connections:**
```
ESP32 Pin 10 (IO25) → R6 → Q1 Pin 1 (Gate)

Q1 Pin 2 (Source) → GND

Q1 Pin 3 (Drain) → Junction → J6 Pin 1 (Motor -)
                            → D2 Cathode

VCC_3V3 → Junction → J6 Pin 2 (Motor +)
                   → D2 Anode
```

**How it works:**
- IO25 HIGH → Q1 turns on → Motor runs → Vibration
- IO25 LOW → Q1 turns off → Motor stops
- D2 protects Q1 from voltage spike when motor turns off

---

## Section 4: Activity LED

### Simple Status Indicator

**Circuit:**
```
ESP32 Pin 26 (IO4) → R5 (1kΩ) → LED1 Anode
                                 LED1 Cathode → GND
```

### Step-by-Step: Adding Activity LED

#### Step 1: Add LED (LED1)

1. **Search:** `LED 0805 green` (or blue, red, etc.)
2. **Select:** Green 0805 LED (LCSC C2297)
3. **Place:** Near ESP32
4. **Label:** `LED1`

#### Step 2: Add Current Limiting Resistor (R5)

1. **Search:** `1k 0805`
2. **Place:** Between ESP32 and LED1
3. **Label:** `R5`

#### Step 3: Wire LED Circuit

```
ESP32 Pin 26 (IO4) → R5 → LED1 Anode (+)
                          LED1 Cathode (-) → GND
```

**LED polarity:**
- Anode (longer leg, + side) → to R5
- Cathode (shorter leg, - side) → to GND

**How it works:**
- IO4 HIGH → LED on
- IO4 LOW → LED off

---

## Complete Sensor Section Schematic Overview

```
┌─────────────────────────────────────────────────────────────┐
│  OLED LEFT (J3)              OLED RIGHT (J4)                │
│  ┌────────────┐              ┌────────────┐                 │
│  │ 1: GND     │              │ 1: GND     │                 │
│  │ 2: VCC_3V3 │              │ 2: VCC_3V3 │                 │
│  │ 3: SCL ←───┼─R3─VCC_3V3   │ 3: SCL ←───┼─── IO33        │
│  │ 4: SDA ←───┼─R4─VCC_3V3   │ 4: SDA ←───┼─── IO32        │
│  └────────────┘              └────────────┘                 │
│       │ │                                                    │
│       │ └─────── IO21 (ESP32)                               │
│       └───────── IO22 (ESP32)                               │
│                                                              │
│  MPU6050 (J5)                                               │
│  ┌────────────────┐                                         │
│  │ 1: VCC_3V3     │                                         │
│  │ 2: GND         │                                         │
│  │ 3: SCL (shared)│                                         │
│  │ 4: SDA (shared)│                                         │
│  │ 7: AD0 → GND   │                                         │
│  └────────────────┘                                         │
│                                                              │
│  HAPTIC MOTOR                                               │
│  IO25 → R6 → Q1(Gate)                                       │
│              Q1(Drain) → Motor- + D2                        │
│              Q1(Source) → GND                               │
│  VCC_3V3 → Motor+ + D2                                      │
│                                                              │
│  ACTIVITY LED                                               │
│  IO4 → R5 → LED1 → GND                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Summary for This Section

### Connectors (Headers for Modules)
- J3: 4-pin **female** header socket (OLED Left) - C492393
- J4: 4-pin **female** header socket (OLED Right) - C492393
- J5: 8-pin **female** header socket (MPU6050) - C50950 (or 6-pin C124413)
- J6: 2-pin JST (Haptic motor) - C157932

### Resistors
- R3: 4.7kΩ (I2C pull-up SCL) - C17673
- R4: 4.7kΩ (I2C pull-up SDA) - C17673
- R5: 1kΩ (LED current limit) - C17513
- R6: 1kΩ (MOSFET gate) - C17513

### Active Components
- Q1: 2N7002 MOSFET SOT-23 - C8545
- D2: 1N4148 diode SOD-123 - C81598
- LED1: Green LED 0805 - C2297

---

## ESP32 Pin Usage Summary

| ESP32 Pin | Pin # | Function | Connected To |
|-----------|-------|----------|--------------|
| IO21 | 33 | I2C SDA (Bus 1) | OLED Left + MPU6050 |
| IO22 | 36 | I2C SCL (Bus 1) | OLED Left + MPU6050 |
| IO32 | 8 | I2C SDA (Bus 2) | OLED Right |
| IO33 | 9 | I2C SCL (Bus 2) | OLED Right |
| IO25 | 10 | PWM Output | Haptic motor driver |
| IO4 | 26 | Digital Output | Activity LED |

---

## Verification Checklist

Before moving to next section, verify:

- [ ] J3 (OLED Left) - 4 pins: GND, VCC, SCL, SDA
- [ ] R3 (4.7kΩ) pull-up on SCL to VCC_3V3
- [ ] R4 (4.7kΩ) pull-up on SDA to VCC_3V3
- [ ] J3 SCL → ESP32 IO22 (Pin 36)
- [ ] J3 SDA → ESP32 IO21 (Pin 33)
- [ ] J4 (OLED Right) - 4 pins: GND, VCC, SCL, SDA
- [ ] J4 SCL → ESP32 IO33 (Pin 9)
- [ ] J4 SDA → ESP32 IO32 (Pin 8)
- [ ] J5 (MPU6050) - 8 pins (or 6)
- [ ] J5 SCL/SDA share bus with J3
- [ ] J5 AD0 → GND (sets address)
- [ ] Q1 (2N7002) placed
- [ ] R6 (1kΩ) from IO25 to Q1 gate
- [ ] D2 (1N4148) across motor, correct polarity
- [ ] J6 (2-pin JST) for motor
- [ ] LED1 (green 0805) placed
- [ ] R5 (1kΩ) from IO4 to LED1

---

## Common Mistakes to Avoid

❌ **Don't:** Connect both OLEDs to same I2C bus (they have same address!)  
✅ **Do:** Use two separate I2C buses (IO21/IO22 for left, IO32/IO33 for right)

❌ **Don't:** Forget pull-up resistors on I2C lines  
✅ **Do:** Add 4.7kΩ on SCL and SDA for left OLED/MPU bus

❌ **Don't:** Reverse flyback diode (D2) polarity  
✅ **Do:** Cathode to drain, anode to VCC

❌ **Don't:** Connect motor directly to ESP32 GPIO  
✅ **Do:** Use MOSFET (Q1) to switch motor

---

## Testing After PCB Assembly

### Test 1: I2C Device Detection
1. Upload I2C scanner sketch to ESP32
2. Should detect:
   - 0x3C (OLED Left on bus IO21/IO22)
   - 0x68 (MPU6050 on same bus)
   - 0x3C (OLED Right on bus IO32/IO33)

### Test 2: OLED Display
1. Upload test sketch with text/graphics
2. Both OLEDs should display independently

### Test 3: MPU6050
1. Read accelerometer/gyro data
2. Tilt board → values should change

### Test 4: Haptic Motor
1. Set IO25 HIGH
2. Motor should vibrate
3. Set IO25 LOW
4. Motor should stop

### Test 5: Activity LED
1. Set IO4 HIGH → LED on
2. Set IO4 LOW → LED off

---

## Next Steps

Once sensor section is complete, you'll add:

**Section 4: Raspberry Pi Interface**
- 40-pin header
- UART connections
- I2S audio bus
- Power connections

**Section 5: Audio**
- Microphone header (INMP441)
- Speaker amplifier (MAX98357A)
- Speaker connector

**Take your time building this section - it's the most complex so far!**

*Sensor Section Guide Complete - Ready to Build!*
