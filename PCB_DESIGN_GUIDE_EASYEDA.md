# ZoarkBot Edge Device - Production PCB Design Guide (EasyEDA)

## 🎉 Congratulations on Getting Your Prototype Working!

Now let's turn your breadboard prototype into a professional, manufacturable product.

---

## Table of Contents
1. [Production Requirements Overview](#production-requirements-overview)
2. [EasyEDA Setup & Project Creation](#easyeda-setup--project-creation)
3. [Complete Production Schematic Design](#complete-production-schematic-design)
4. [PCB Layout Step-by-Step](#pcb-layout-step-by-step)
5. [Manufacturing Preparation](#manufacturing-preparation)
6. [Production BOM with Part Numbers](#production-bom-with-part-numbers)
7. [Testing & Quality Control](#testing--quality-control)

---

## Production Requirements Overview

### What Makes It Production-Grade?

**Your breadboard prototype has:**
- ✅ ESP32 + sensors working
- ✅ Raspberry Pi + audio working
- ✅ Basic connections

**Production PCB adds:**
- ✅ **Voltage regulation** - Clean, stable power
- ✅ **Protection circuits** - ESD, reverse polarity, overcurrent
- ✅ **Decoupling capacitors** - Noise filtering
- ✅ **Status LEDs** - Power, activity, error indication
- ✅ **Servo motor control** - Camera/face rotation
- ✅ **Camera interface** - Pi Camera connector
- ✅ **Professional connectors** - JST, USB-C, headers
- ✅ **Proper grounding** - Ground planes, EMI reduction
- ✅ **Mounting holes** - For enclosure attachment
- ✅ **Silkscreen labels** - Assembly and debugging
- ✅ **Test points** - Manufacturing test and debug

### New Features vs Breadboard

| Feature | Breadboard | Production PCB |
|---------|-----------|----------------|
| Power input | USB cables | USB-C PD, barrel jack, battery |
| Voltage regulation | None (direct USB) | LDO regulators (5V→3.3V) |
| Protection | None | Reverse polarity, ESD, fuses |
| Audio quality | Basic | LC filters, dedicated ground |
| Camera | Not included | Pi Camera CSI connector |
| Servo control | Not included | PWM driver, power switch |
| Indicators | Only power LEDs | Status RGB LED, activity LEDs |
| Size | Breadboard (large) | Compact PCB (~100×80mm) |
| Reliability | Wires can disconnect | Soldered, professional |

---

## EasyEDA Setup & Project Creation

### Step 1: Create EasyEDA Account

1. **Go to:** https://easyeda.com/
2. **Click:** "Sign Up" (top right)
3. **Use:** Your email or Google account
4. **Verify:** Email confirmation

### Step 2: Install EasyEDA (Choose One)

**Option A: Web Version (Recommended for beginners)**
- No installation needed
- Works in browser
- Auto-saves to cloud
- **Click:** "Open Editor" from easyeda.com

**Option B: Desktop Version (Better for production)**
- **Download:** https://easyeda.com/page/download
- **Install:** Windows/Mac/Linux client
- **Better performance** for large designs
- **Offline work** capability

### Step 3: Create New Project

1. **Click:** "File" → "New" → "Project"
2. **Name:** `ZoarkBot_EdgeDevice_v1`
3. **Type:** Select "PCB Project"
4. **Click:** "Create"

You'll now have an empty project with three tabs:
- **Schematic** (circuit diagram)
- **PCB** (board layout)
- **BOM** (bill of materials)

---

## Complete Production Schematic Design

### Understanding the Schematic Structure

We'll divide the schematic into functional blocks:

```
┌─────────────────────────────────────────────────────┐
│                 POWER MANAGEMENT                    │
│  USB-C → Protection → 5V Buck → 3.3V LDO → Rails   │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│              MICROCONTROLLER SECTION                │
│        ESP32-WROOM-32 + Reset + Boot + UART         │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│                  SENSOR SECTION                     │
│      2× OLED + MPU6050 + Haptic Motor Driver       │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│              RASPBERRY PI INTERFACE                 │
│   UART + I2S Audio + Camera + Power Distribution    │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│               SERVO & INDICATORS                    │
│     Servo Driver + RGB LED + Status LEDs            │
└─────────────────────────────────────────────────────┘
```

---

### Block 1: Power Management Section

**Step 1: Add USB-C Connector**

1. In EasyEDA, click **"Place"** → **"Component"**
2. Search: `USB4105-GF-A` (USB-C connector with mounting holes)
3. Place on schematic at top-left
4. **Label:** `J1` (connector J1)

**Step 2: Add USB-C CC Resistors**

The USB4105-GF-A connector requires two resistors on the CC pins so that any USB-C charger recognises the board as a power sink and supplies VBUS. Without these the charger may refuse to deliver power.

Components:
- **R_CC1**: 5.1kΩ resistor — USB-C CC1 pin → GND
- **R_CC2**: 5.1kΩ resistor — USB-C CC2 pin → GND

```
USB4105 CC1 → R_CC1 (5.1kΩ) → GND
USB4105 CC2 → R_CC2 (5.1kΩ) → GND
```

These are the standard Rd values for a USB-C sink. The charger uses its own pull-up (Rp) to advertise its current capability — a 3A charger will supply up to 3A even with 5.1kΩ Rd on our side.

**Step 3: Add Protection Circuit**

Components needed:
- **F1**: Polyfuse 2A (PTC resettable fuse) - `MF-MSMF200-2`
- **D1**: Schottky diode (reverse polarity + OR-ing) - `SS14`
- **TVS1**: ESD protection on USB data lines - `USBLC6-2SC6`

**Schematic connections:**
```
USB-C VBUS → F1 (fuse) → D1 anode
                          D1 cathode → VIN_5V node
USB-C D+/D- → TVS1 USBLC6-2SC6 → continues to data path
USB-C GND   → GND

VIN_5V → D4 anode (SS14)
          D4 cathode → VCC_5V   ← OR-ing diode: USB contributes to VCC_5V rail
```

> **Do not remove TVS1.** Early schematic revisions dropped the USBLC6-2SC6. It must stay — the USB4105 has minimal built-in ESD headroom for the data lines.

**Step 4: Add Battery Power Path**

This section adds an alternative 5V source so the board runs untethered. The AMS1117 (3.3V) must be fed from VCC_5V — not VIN_5V — so it is powered whether the source is USB or battery.

Components:
- **J_BAT**: 2-pin JST connector — battery input 7–12V
- **D3**: Schottky SS14 — reverse-polarity protection on battery input
- **J_Buck**: 4-pin header for LM2596-5V buck module (external module handles switching circuit)
- **C9**: 1000µF electrolytic — bulk capacitance on VCC_5V rail
- **D4**: Schottky SS14 — OR-ing diode from USB path into VCC_5V

```
J_BAT (+) → D3 (SS14) → BAT_PROT net → J_Buck input
J_BAT (-)  → GND
J_Buck output → C9 (1000µF to GND) → VCC_5V rail

VIN_5V (USB side) → D4 (SS14) → VCC_5V rail

VCC_5V → MAX98357A, Pi 40-pin header VCC, servo header VCC
```

**Step 5: Add 5V to 3.3V Regulator**

> **Critical:** Connect AMS1117 input to **VCC_5V**, not VIN_5V. VIN_5V is only live when USB is connected. Connecting to VCC_5V ensures 3.3V is available from both USB and battery power sources.

Components:
- **U1**: AMS1117-3.3 (LDO voltage regulator) - `AMS1117-3.3`
- **C1**: 10µF electrolytic capacitor (AMS1117 input)
- **C_BULK**: 470µF electrolytic capacitor (VCC_5V bulk, before AMS1117 input) — absorbs ESP32 WiFi current spikes (~500mA pulses) when running on USB without a battery attached
- **C2**: 10µF electrolytic capacitor (AMS1117 output)
- **C3**: 100nF ceramic capacitor (AMS1117 output, noise filter)

**Schematic:**
```
VCC_5V → C_BULK (470µF to GND)
VCC_5V → C1 (10µF) → U1 pin 1 (VIN)   ← input from VCC_5V, NOT VIN_5V
         U1 pin 2 (GND) → GND
         U1 pin 3 (VOUT) → C2 (10µF) + C3 (100nF) → VCC_3V3
```

**Thermal note:** At 5V in, 3.3V out, 500mA load the AMS1117 dissipates ~0.85W. In PCB layout expose a large copper pour pad under the SOT-223 tab and connect it to GND — this is the heatsink. Do not place the AMS1117 in a tight corner with no copper.

**Why these components?**
- **Polyfuse**: Protects against overcurrent (resets automatically)
- **SS14 D1 + D4**: Reverse polarity protection + dual-source OR-ing
- **D3**: Reverse polarity on battery connector
- **TVS1**: Protects USB D+/D- lines from static discharge
- **AMS1117**: Reliable, cheap 3.3V regulator (1A max)
- **C_BULK 470µF**: Prevents voltage sag during ESP32 WiFi TX bursts
- **C9 1000µF**: Stabilises VCC_5V rail, especially under servo/Pi load

---

### Block 2: ESP32 Microcontroller Section

**Step 1: Add ESP32-WROOM-32 Module**

1. Search in EasyEDA: `ESP32-WROOM-32`
2. Place module - it has **38 pins**
3. **Label:** `U2`

**Step 2: Add Boot and Reset Circuitry**

Components:
- **SW1**: Tactile switch (RESET) - `TS-1187A-B-A-B`
- **SW2**: Tactile switch (BOOT/GPIO0) - `TS-1187A-B-A-B`
- **R1**: 10kΩ pull-up resistor (EN pin)
- **R2**: 10kΩ pull-up resistor (GPIO0)
- **C4**: 100nF capacitor (EN debounce)

**Connections:**
```
ESP32 EN → R1 (10kΩ) → VCC_3V3
ESP32 EN → SW1 → GND
ESP32 EN → C4 (100nF) → GND

ESP32 GPIO0 → R2 (10kΩ) → VCC_3V3
ESP32 GPIO0 → SW2 → GND
```

**Step 3: Add Decoupling Capacitors**

Place near ESP32 power pins:
- **C5, C6, C7**: 100nF ceramic capacitors (one per power pin)
- **C8**: 10µF electrolytic capacitor

```
ESP32 VCC (pin 2) → C5, C6, C7, C8 → GND
```

**Why?** Filters high-frequency noise from WiFi radio

**Step 4: Add Programming Header**

Components:
- **J2**: 6-pin header 2.54mm - `Header-Male-2.54_1x6`

**Pinout:**
```
1. GND
2. TXD (ESP32 GPIO1)
3. RXD (ESP32 GPIO3)
4. GPIO0 (shared with SW2)
5. EN (shared with SW1)
6. VCC_3V3
```

This allows programming via USB-UART adapter (FTDI, CP2102)

> **Warning — silkscreen required:** Add the text **"3.3V ONLY — NOT 5V TOLERANT"** to the silkscreen next to J2. Many common USB-UART adapters (CP2102 breakout boards, CH340 modules) default to 5V logic. Connecting a 5V adapter to J2 without checking will permanently damage the ESP32 GPIO pins. The label must be visible on the assembled board.

---

### Block 3: Sensor & Display Section

**Step 1: Add OLED Displays**

Components:
- **U3**: SSD1306 OLED left eye - `SSD1306 128x64`
- **U4**: SSD1306 OLED right eye - `SSD1306 128x64`
- **R3, R4**: 4.7kΩ I2C pull-up resistors (I2C bus 0)
- **R5, R6**: 4.7kΩ I2C pull-up resistors (I2C bus 1)

**Connections:**
```
OLED Left (U3):
  VCC → VCC_3V3
  GND → GND
  SDA → ESP32 GPIO21 (also connect R3 4.7kΩ to VCC_3V3)
  SCL → ESP32 GPIO22 (also connect R4 4.7kΩ to VCC_3V3)

OLED Right (U4):
  VCC → VCC_3V3
  GND → GND
  SDA → ESP32 GPIO32 (also connect R5 4.7kΩ to VCC_3V3)
  SCL → ESP32 GPIO33 (also connect R6 4.7kΩ to VCC_3V3)
```

**Why pull-ups?** I2C requires pull-up resistors on SDA/SCL lines

**Step 2: Add MPU6050 IMU**

Components:
- **U5**: MPU6050 module or IC - `MPU-6050`
- Uses same I2C bus as OLED Left (already has pull-ups)

**Connections:**
```
MPU6050 VCC → VCC_3V3
MPU6050 GND → GND
MPU6050 SDA → ESP32 GPIO21 (shared with OLED Left)
MPU6050 SCL → ESP32 GPIO22 (shared with OLED Left)
MPU6050 AD0 → GND (sets I2C address to 0x68)
```

**Step 3: Add Haptic Motor Driver**

Components:
- **Q1**: N-channel MOSFET - `2N7002` (SOT-23 package, surface mount)
- **R7**: 10kΩ pull-down resistor
- **R8**: 1kΩ gate resistor
- **D2**: Flyback diode - `1N4148`
- **M1**: Vibration motor connector - `Header-Male-2.54_1x2`

**Connections:**
```
ESP32 GPIO25 → R8 (1kΩ) → Q1 Gate
Q1 Gate → R7 (10kΩ) → GND (pull-down)
Q1 Source → GND
Q1 Drain → M1 pin 1 (motor -)
M1 pin 2 (motor +) → VCC_3V3
D2 cathode → VCC_3V3
D2 anode → Q1 Drain (across motor)
```

**Production upgrade:** Using MOSFET instead of BJT (more efficient, less heat)

---

### Block 4: Raspberry Pi Interface

**Step 1: Add Raspberry Pi Connector**

Components:
- **J3**: 40-pin female header 2.54mm - `Header-Female-2.54_2x20`

**Key connections:**
```
Pin 1  → VCC_3V3
Pin 2  → VCC_5V (power to Pi — must be VCC_5V, not VIN_5V)
Pin 4  → VCC_5V
Pin 6  → GND (and all other GND pins)
Pin 8  → ESP32 GPIO16 (UART RX from Pi TX)
Pin 10 → ESP32 GPIO17 (UART TX to Pi RX)
Pin 12 → Pi GPIO18 (I2S CLK) [to audio section]
Pin 35 → Pi GPIO19 (I2S WS) [to audio section]
Pin 38 → Pi GPIO20 (I2S DIN) [to mic]
Pin 40 → Pi GPIO21 (I2S DOUT) [to speaker]
```

**Add bulk decoupling at the Pi header — mandatory:**

Place these physically close to the 40-pin header pins 2/4:
- **C_PI_BULK**: 220µF electrolytic — VCC_5V to GND
- **C_PI_DEC**: 100nF ceramic — VCC_5V to GND

Without local bulk capacitance the Pi's power rails will sag during CPU load spikes through the connector's inductance.

**Add ESD protection on UART lines:**

Components:
- **TVS_UART**: PRTR5V0U2X or equivalent dual-rail TVS array (SOT-363)

```
UART_PI_TX → TVS_UART → continues to ESP32 RXD0
UART_PI_RX → TVS_UART → continues to ESP32 TXD0
TVS_UART GND → GND
```

Hot-plugging the Pi header during development (very common) will otherwise inject voltage transients directly into ESP32 GPIO.

**Step 2: Add I2S Microphone**

Components:
- **U6**: INMP441 I2S microphone - `INMP441`
- **C9**: 100nF decoupling capacitor

**Connections:**
```
INMP441 VDD → VCC_3V3
INMP441 GND → GND_AUDIO (separate audio ground)
INMP441 SCK → Pi GPIO18
INMP441 WS → Pi GPIO19
INMP441 SD → Pi GPIO20
INMP441 L/R → GND
C9 across VDD and GND
```

**Step 3: Add I2S Termination Resistors**

I2S runs at ~3MHz between the Pi and both audio modules. Without termination, the signals ring on the trace ends causing audio glitches, especially when traces exceed 5cm.

Add series termination resistors at the **source end** of each I2S line (at the Pi header side):

Components:
- **R_BCK**: 33Ω resistor — I2S_BCK line (Pi GPIO18)
- **R_LRCK**: 33Ω resistor — I2S_LRCK line (Pi GPIO19)
- **R_DIN**: 33Ω resistor — I2S_DIN line (Pi GPIO20, mic data)
- **R_DOUT**: 33Ω resistor — I2S_DOUT line (Pi GPIO21, speaker data)

```
Pi header pin 12 → R_BCK (33Ω) → I2S_BCK net
Pi header pin 35 → R_LRCK (33Ω) → I2S_LRCK net
Pi header pin 38 → R_DIN (33Ω) → I2S_DIN net
Pi header pin 40 → R_DOUT (33Ω) → I2S_DOUT net
```

In PCB layout keep all four I2S traces the same length and route them together as a bundle. Do not cross digital or power traces through the bundle.

**Step 4: Add I2S Speaker Amplifier**

Components:
- **U7**: MAX98357A I2S amplifier - `MAX98357AETE+T`
- **C10**: 100µF electrolytic (power supply)
- **C11**: 100nF ceramic (decoupling)
- **L1**: 10µH ferrite bead (noise filter)
- **J4**: Speaker connector 2-pin JST - `JST-PH-2P`

**Connections:**
```
MAX98357A VIN → L1 → VCC_5V   ← use VCC_5V not VIN_5V
MAX98357A GND → GND_AUDIO
MAX98357A BCLK → I2S_BCK (after R_BCK)
MAX98357A LRC  → I2S_LRCK (after R_LRCK)
MAX98357A DIN  → I2S_DOUT (after R_DOUT)
MAX98357A SD   → VCC_3V3 (shutdown pin — always on)
MAX98357A OUT+ → J4 pin 1 (speaker +)
MAX98357A OUT- → J4 pin 2 (speaker -)
C10, C11 across VIN and GND
```

**Step 4: Add Camera Connector**

Components:
- **J5**: 15-pin FFC connector 1.0mm pitch - `FPC-15P-1.0mm`

**Connections:**
```
Camera connector → Directly to Pi Camera CSI pins
(These connect to specific pins on the 40-pin header)
```

**Note:** This is a pass-through - the camera plugs into Pi, but we route signals through PCB for cleaner design

---

### Block 5: Servo Motor & Indicator LEDs

**Step 1: Add Servo Motor Driver**

Components:
- **U8**: PCA9685 PWM driver (optional for multiple servos) OR simple transistor driver
- **Simple option**: Direct GPIO control
- **Q2**: N-channel MOSFET for servo power switching - `AO3400A`
- **R9**: 10kΩ pull-down
- **J6**: Servo connector 3-pin - `Header-Male-2.54_1x3`

**Connections (simple version):**
```
ESP32 GPIO26 → Servo signal (J6 pin 1)
VIN_5V → Q2 Drain → J6 pin 2 (servo VCC)
GND → J6 pin 3 (servo GND)
ESP32 GPIO27 → R9 → Q2 Gate (power enable)
Q2 Source → GND
```

**Why power switching?** Servos draw high current; switch them off when not moving to save power

**Step 2: Add RGB Status LED**

Components:
- **LED1**: WS2812B RGB LED (smart LED) - `WS2812B-V5`
- **C12**: 100nF decoupling capacitor
- **R10**: 470Ω resistor (data line)

**Connections:**
```
WS2812B VDD → VCC_3V3
WS2812B GND → GND
WS2812B DIN → R10 → ESP32 GPIO13
C12 across VDD and GND
```

**Why WS2812B?** Single data line controls full RGB color - shows status (booting=blue, connected=green, error=red)

**Step 3: Add Simple Status LEDs**

Components:
- **LED2**: Power indicator (green) - `LED-0805-G`
- **LED3**: Activity indicator (blue) - `LED-0805-B`
- **R11**: 1kΩ resistor (power LED current limit)
- **R12**: 1kΩ resistor (activity LED current limit)

**Connections:**
```
VCC_3V3 → R11 → LED2 anode → LED2 cathode → GND   (always-on power indicator)
ESP32 GPIO4 → R12 → LED3 anode → LED3 cathode → GND  (GPIO-driven activity LED)
```

> **Common mistake:** Both ends of each LED circuit must be connected — anode to the driving source (VCC_3V3 or GPIO) through the resistor, and cathode directly to GND. A floating anode or cathode will leave the LED permanently off with no error during DRC. Double-check both connections in EasyEDA before proceeding.

---

### Block 6: Test Points and Debug Headers

**Add test points for manufacturing:**

- **TP1**: VCC_3V3
- **TP2**: VIN_5V
- **TP3**: VCC_5V
- **TP4**: BAT_PROT (battery after reverse-polarity diode D3)
- **TP5**: GND
- **TP6**: ESP32 GPIO0 (boot mode)
- **TP7**: ESP32 EN (reset)
- **TP8**: I2C_SDA (GPIO21 — left bus)
- **TP9**: I2C_SCL (GPIO22 — left bus)
- **TP10**: I2C_SDA_RIGHT (GPIO32)
- **TP11**: UART_PI_TX
- **TP12**: UART_PI_RX

**These are small pads for oscilloscope probes or multimeter. Place TP1–TP5 near the power section, TP6–TP7 near the ESP32, TP8–TP12 near their respective connectors.**

> Having VCC_5V and BAT_PROT as separate test points lets you verify the battery path works independently from the USB path — critical for debugging the dual-source power circuit.

---

## Complete Schematic Checklist

Before moving to PCB layout, verify:

- [ ] All components have unique reference designators (U1, R1, C1, etc.)
- [ ] All power nets labeled (VCC_3V3, VIN_5V, VCC_5V, BAT_PROT, GND, GND_AUDIO)
- [ ] All signal nets labeled (I2C_SDA, I2C_SCL, I2C_SDA_RIGHT, I2C_SCL_RIGHT, UART_PI_TX, UART_PI_RX, etc.)
- [ ] All capacitors have voltage ratings noted (16V for 5V rail, 10V for 3.3V rail)
- [ ] All resistors have power ratings (1/4W is standard)
- [ ] Ground symbols used consistently (not just GND net labels)
- [ ] Decoupling capacitors placed at every IC power pin
- [ ] No unconnected pins — mark NC explicitly if truly unused
- [ ] **AMS1117 U1 input connected to VCC_5V (not VIN_5V)**
- [ ] **USBLC6-2SC6 TVS1 connected to USB D+/D- lines — not removed**
- [ ] **USB CC resistors R_CC1/R_CC2 (5.1kΩ) present on CC1 and CC2 pins**
- [ ] **D4 OR-ing diode connects VIN_5V → VCC_5V**
- [ ] **C_BULK (470µF) on VCC_5V rail before AMS1117 input**
- [ ] **C9 (1000µF) on VCC_5V rail from battery buck converter**
- [ ] **Both OLED I2C buses have pull-up resistors (left: R3/R4, right: R9/R10)**
- [ ] **I2S series termination resistors (33Ω) on BCK, LRCK, DIN, DOUT**
- [ ] **C_PI_BULK + C_PI_DEC at Pi 40-pin header power pins**
- [ ] **TVS_UART on UART_PI_TX and UART_PI_RX lines**
- [ ] **LED2 anode and cathode both connected (not floating)**
- [ ] **LED3 anode and cathode both connected (not floating)**
- [ ] **J2 silkscreen note "3.3V ONLY" added**
- [ ] **All 12 test points placed on critical nets**

---

## PCB Layout Step-by-Step

### Phase 1: Board Setup

**Step 1: Create PCB from Schematic**

1. In EasyEDA, click **"Design"** → **"Convert Schematic to PCB"**
2. All components appear in a pile on the right side
3. **Set board size:** 100mm × 80mm (compact but manufacturable)
4. **Set layers:** 2-layer board (top + bottom copper)

**Step 1b: Define Ground Plane Before Placing Anything**

Do this immediately after creating the PCB, before touching component placement:

1. Select the **Bottom Copper** layer
2. Click **"Copper Area"** tool
3. Draw a polygon covering the entire board outline
4. Set net: **GND** | Clearance: **0.3mm** | Fill: **Solid**
5. Click **"Rebuild All Copper Area"**

A continuous ground plane on the bottom layer is essential for WiFi signal integrity and EMI. If you route first and add the plane later, you risk creating ground plane cuts under sensitive traces. **Do not skip this step.**

**Step 2: Define Board Outline**

1. Click **"PCB Tools"** → **"Board Outline"**
2. Draw rectangle: 100mm × 80mm
3. Add rounded corners (radius 3mm) for professional look
4. Add 4× mounting holes (3mm diameter) at corners (5mm from edges)

**Step 3: Set Design Rules**

Click **"Design"** → **"Design Rules"**

```
Track Width: 0.3mm (default), 0.5mm (power), 0.8mm (high current)
Clearance: 0.3mm (space between traces)
Via Size: 0.6mm drill, 1.0mm pad
Min Hole Size: 0.3mm
Solder Mask: Green (or your preference)
Silkscreen: White text
Surface Finish: HASL (cheap) or ENIG (better quality)
```

---

### Phase 2: Component Placement Strategy

**General Rule: Group by function, minimize trace lengths**

**Step 1: Power Section (Top-Left)**

Place in order:
```
J1 (USB-C) → F1 → D1 → C1 → U1 (regulator) → C2, C3
```
Keep all power components close together

**Step 2: ESP32 Section (Center)**

```
Place U2 (ESP32 module) in center of board
Surround with decoupling caps C5-C8
Place SW1 (reset) and SW2 (boot) on top edge (accessible)
Place J2 (programming header) on top edge
```

**ESP32 WiFi Antenna Keep-out Zone — mandatory:**

The ESP32-WROOM-32 module has a PCB antenna that extends ~3mm beyond the module edge on one side (the end without the row of castellated pads). This antenna area requires a keep-out zone on **all copper layers**:

1. In EasyEDA select the **Document** layer
2. Draw a rectangle covering the antenna overhang area: 3mm beyond the antenna end of the module, full module width
3. Label it "NO COPPER — ANTENNA KEEP-OUT"
4. On every copper layer: ensure no traces, pours, vias, or pads exist inside this zone
5. In the GND copper pour settings, exclude this rectangle

Violating the keep-out reduces WiFi range by 40–60% and may cause RF compliance failure. Orient the module so the antenna faces the nearest PCB edge and hangs over open air if possible.

**Step 3: Sensor Section (Around ESP32)**

```
U3 (OLED Left) → Top-left of ESP32
U4 (OLED Right) → Top-right of ESP32
U5 (MPU6050) → Near ESP32, short I2C traces
Q1 + M1 (haptic motor) → Bottom-right corner
```

**Step 4: Raspberry Pi Section (Bottom)**

```
J3 (40-pin header) → Bottom edge, centered
U6 (INMP441 mic) → Left of J3
U7 (MAX98357 amp) → Right of J3
J4 (speaker) → Far right edge
J5 (camera FFC) → Far left edge
```

**Step 5: Servo & LEDs (Right Side)**

```
J6 (servo connector) → Right edge, top
Q2 (servo MOSFET) → Near J6
LED1 (RGB) → Top-right corner (visible)
LED2, LED3 → Top edge near USB-C
```

**Step 6: Test Points**

```
Scatter test points near relevant components
Place TP1-TP3 (power) near voltage regulator
Place TP4-TP5 (boot/reset) near ESP32
```

**Visual Layout Concept:**
```
┌─────────────────────────────────────────────┐
│ [USB-C] [F1][U1] [LED2][LED3]        [RGB] │ TOP
│                                      [SW1]  │
│  [U3 OLED]    ╔═══════════╗    [U4 OLED]   │
│               ║           ║                 │
│               ║   ESP32   ║            [J6] │
│  [U5 MPU]     ║    U2     ║           Servo │
│               ╚═══════════╝                 │
│                                        [Q1] │
│ [J5 CAM] [U6 MIC] [J3 Pi 40pin] [U7 AMP] [J4 SPK]
└─────────────────────────────────────────────┘
  BOTTOM
```

---

### Phase 3: Routing (Connecting Components)

**Step 1: Route Power Planes**

1. **Click:** "Copper Area" tool
2. **Draw:** Polygon covering entire bottom layer
3. **Set net:** GND
4. **Clearance:** 0.3mm

Repeat for top layer but smaller areas:
- **Top layer:** VCC_3V3 pour (avoid under ESP32 antenna area!)
- **Bottom layer:** Full GND pour

**Why ground plane?** Better noise immunity, heat dissipation, easier routing

**Step 2: Route Critical Signals First**

**Order of priority:**
1. Power traces (VIN_5V, VCC_3V3) - Use 0.8mm width
2. I2C buses (SDA, SCL) - Keep traces short, equal length
3. I2S audio (BCLK, WS, DIN, DOUT) - Keep together, avoid crossing digital signals
4. UART (TX, RX) - Can be longer, add series resistors if needed
5. GPIO signals - Last priority

**Step 3: Routing Best Practices**

```
✅ DO:
- Route traces at 45° angles (not 90°)
- Keep high-speed signals short
- Route I2S lines (BCK, LRCK, DIN, DOUT) as a bundle, equal length, same layer
- Use vias to switch layers when needed
- Keep analog (audio) and digital signals on separate areas of the board
- Place AMS1117 (U1) with large exposed copper pour pad tied to GND on bottom
  layer — this is the heatsink (0.85W dissipation at full load)
- Place 33Ω I2S series resistors within 5mm of the Pi header pins

❌ DON'T:
- Route under ESP32 antenna keep-out zone on any layer
- Run traces under oscillators
- Create acute angles (< 45°)
- Run power and ground as thin traces — use copper pours
- Cross I2S signal traces with power or GPIO traces
- Place the AMS1117 in a corner with no copper flood around it
```

**AMS1117 Thermal Pad in EasyEDA:**

1. Select U1 (AMS1117) footprint
2. On the bottom copper layer, draw a copper area 10mm × 8mm centred on the SOT-223 tab pad
3. Set net: **GND**
4. Add 4 thermal vias (0.4mm drill) inside this copper area to connect top and bottom GND pours
5. This copper area acts as a heat spreader — without it the LDO will throttle or fail under sustained load

**Step 4: Add Via Stitching**

Place vias around ground pour edges to connect top and bottom ground planes:
- **Spacing:** Every 5-10mm along ground boundaries
- **Purpose:** Reduces EMI, better ground continuity

---

### Phase 4: Silkscreen and Final Touches

**Step 1: Add Labels**

Click **"Text"** tool and add:
```
- Component labels (auto-generated, but verify readable)
- "ZoarkBot Edge v1.0" (your brand)
- "Made in [Your Country]"
- Pin 1 indicators (dots next to ICs)
- Polarity marks on LEDs (+/-)
- "+" and "-" on all connectors
```

**Step 2: Add Assembly Notes**

On back silkscreen:
```
- "USB-C Input: 5V 2A (MF-MSMF200-2 fuse)"
- "Battery Input: 7-12V DC via J_BAT"
- "3.3V Output: 800mA max"
- "Servo/Pi: 5V from VCC_5V rail"
- Website or GitHub URL
- License info (if open source)
```

On front silkscreen (mandatory safety labels):
```
- Next to J2 (programming header): "3.3V ONLY — NOT 5V TOLERANT"
- Next to J_BAT (battery connector): "+ / -" polarity markers
- Next to J4 (speaker connector): "+ / -" polarity markers
- Next to all electrolytic capacitors: "+" marker on positive pad
```

**Step 3: Design Rule Check (DRC)**

1. Click **"Tools"** → **"Design Rule Check"**
2. Fix all errors (red)
3. Review warnings (yellow) - some might be OK
4. Common issues:
   - Traces too close
   - Drill holes too small
   - Silkscreen over pads

**Step 4: 3D Preview**

1. Click **"3D View"** button
2. Rotate and inspect board
3. Check component heights don't conflict
4. Verify connector positions match enclosure plan

---

## Manufacturing Preparation

### Generate Production Files (Gerbers)

**Step 1: Export Gerber Files**

1. Click **"Fabrication"** → **"Generate Gerber"**
2. EasyEDA creates ZIP file with:
   - `.GTL` - Top copper layer
   - `.GBL` - Bottom copper layer
   - `.GTS` - Top solder mask
   - `.GBS` - Bottom solder mask
   - `.GTO` - Top silkscreen
   - `.GBO` - Bottom silkscreen
   - `.TXT` - Drill file
   - `.GML` - Board outline

**Step 2: Order from JLCPCB (Integrated with EasyEDA)**

1. Click **"Fabrication"** → **"Order at JLCPCB"**
2. Set specifications:
   ```
   PCB Qty: 5 (minimum for testing)
   Layers: 2
   Dimensions: 100×80mm (auto-detected)
   PCB Thickness: 1.6mm
   PCB Color: Green (or black for premium look)
   Silkscreen: White
   Surface Finish: HASL (leadfree) or ENIG
   Outer Copper Weight: 1oz
   Via Covering: Tented
   Remove Order Number: Yes (specify location)
   ```

3. **Cost estimate:** ~$2-5 for 5 boards + shipping

**Step 3: Generate BOM & CPL for Assembly**

If using JLCPCB SMT assembly:

1. Click **"Fabrication"** → **"Generate BOM"**
2. Click **"Fabrication"** → **"Generate Pick and Place"**
3. Upload both files to JLCPCB assembly service
4. **Select components** from JLCPCB library (cheaper if in stock)
5. Components NOT in library: You'll hand-solder later

**Typical assembly split:**
- **JLCPCB assembles:** Resistors, capacitors, small ICs, LEDs
- **You solder:** ESP32 module, connectors, through-hole parts

---

## Production BOM with Part Numbers

### Complete Bill of Materials (Manufacturer Part Numbers)

| Ref | Qty | Description | Manufacturer | Part Number | JLCPCB Code | Unit Price |
|-----|-----|-------------|--------------|-------------|-------------|------------|
| **POWER — USB PATH** | | | | | | |
| J1 | 1 | USB-C Receptacle 16-pin | Korean Hroparts | USB4105-GF-A | C168688 | $0.50 |
| R_CC1, R_CC2 | 2 | Resistor 5.1kΩ (USB-C CC Rd) | Yageo | RC0805FR-075K1L | C27834 | $0.01 |
| F1 | 1 | Polyfuse 2A resettable | Bourns | MF-MSMF200-2 | C17363 | $0.12 |
| D1, D4 | 2 | Schottky Diode SS14 (protection + OR-ing) | MDD | SS14 | C2480 | $0.03 |
| TVS1 | 1 | ESD Protection USB D+/D- | STMicro | USBLC6-2SC6 | C7519 | $0.08 |
| C_BULK | 1 | Capacitor 470µF 10V electrolytic (VCC_5V bulk) | Panasonic | EEE-FT1A471P | C176673 | $0.08 |
| U1 | 1 | LDO Regulator 3.3V 1A SOT-223 | AMS | AMS1117-3.3 | C6186 | $0.15 |
| C1, C2 | 2 | Capacitor 10µF 16V | Samsung | CL21A106KAYNNNE | C19702 | $0.02 |
| C3 | 1 | Capacitor 100nF 50V | Yageo | CC0805KRX7R9BB104 | C49678 | $0.01 |
| **POWER — BATTERY PATH** | | | | | | |
| J_BAT | 1 | JST PH 2-pin battery connector | JST | B2B-PH-K-S | C157932 | $0.08 |
| D3 | 1 | Schottky SS14 (battery reverse polarity) | MDD | SS14 | C2480 | $0.03 |
| J_Buck | 1 | 4-pin header for LM2596-5V module | Nextron | PZ254V-11-04P | C492405 | $0.03 |
| C9 | 1 | Capacitor 1000µF 10V electrolytic (VCC_5V bulk) | Panasonic | EEE-FT1A102P | C176674 | $0.12 |
| **ESP32** | | | | | | |
| U2 | 1 | ESP32-WROOM-32 Module | Espressif | ESP32-WROOM-32 | C82899 | $3.50 |
| SW1, SW2 | 2 | Tactile Switch | Xunpu | TS-1187A-B-A-B | C318884 | $0.03 |
| R1, R2 | 2 | Resistor 10kΩ 1/4W | Yageo | RC0805FR-0710KL | C17414 | $0.01 |
| C4-C8 | 5 | Capacitor 100nF 50V | Yageo | CC0805KRX7R9BB104 | C49678 | $0.01 |
| J2 | 1 | Header 1×6 2.54mm | Nextron | PZ254V-11-06P | C492404 | $0.05 |
| **DISPLAYS & SENSORS** | | | | | | |
| U3, U4 | 2 | OLED SSD1306 128×64 (module headers) | Generic | SSD1306 0.96" | - | $3.00 |
| R3, R4 | 2 | Resistor 4.7kΩ I2C pull-up (left bus) | Yageo | RC0805FR-074K7L | C17673 | $0.01 |
| R9, R10 | 2 | Resistor 4.7kΩ I2C pull-up (right bus) | Yageo | RC0805FR-074K7L | C17673 | $0.01 |
| U5 | 1 | MPU6050 IMU Module (module header) | InvenSense | MPU-6050 | C24112 | $2.00 |
| **HAPTIC MOTOR** | | | | | | |
| Q1 | 1 | N-MOSFET SOT-23 | Diodes Inc | 2N7002 | C8545 | $0.03 |
| R5 | 1 | Resistor 1kΩ (gate) | Yageo | RC0805FR-071KL | C17513 | $0.01 |
| D2 | 1 | Diode 1N4148W flyback | Changjiang | 1N4148W | C81598 | $0.01 |
| J6 | 1 | JST PH 2-pin motor connector | JST | S2B-PH-K-S-GW | C157932 | $0.08 |
| **RASPBERRY PI INTERFACE** | | | | | | |
| J_PI | 1 | Header 2×20 Female 2.54mm | Nextron | AXK6F40547YG | C50981 | $0.30 |
| C_PI_BULK | 1 | Capacitor 220µF 10V (Pi header bulk) | Panasonic | EEE-FT1A221P | C176671 | $0.06 |
| C_PI_DEC | 1 | Capacitor 100nF 50V (Pi header decoupling) | Yageo | CC0805KRX7R9BB104 | C49678 | $0.01 |
| TVS_UART | 1 | Dual TVS array SOT-363 (UART ESD) | Nexperia | PRTR5V0U2X | C12333 | $0.06 |
| **AUDIO** | | | | | | |
| J_MIC | 1 | 5-pin header for INMP441 module | Nextron | PZ254V-11-05P | C492406 | $0.03 |
| J_Amp | 1 | 8-pin header for MAX98357A module | Nextron | PZ254V-11-08P | C492408 | $0.04 |
| R_BCK, R_LRCK, R_DIN, R_DOUT | 4 | Resistor 33Ω (I2S series termination) | Yageo | RC0805FR-0733RL | C114082 | $0.01 |
| C10 | 1 | Capacitor 100µF 10V (amp supply) | Panasonic | EEE-FT1A101P | C176670 | $0.05 |
| C11 | 1 | Capacitor 100nF 50V (amp decoupling) | Yageo | CC0805KRX7R9BB104 | C49678 | $0.01 |
| L1 | 1 | Ferrite Bead 600Ω@100MHz | Murata | BLM21PG601SN1D | C1017 | $0.03 |
| J4 | 1 | JST PH 2-pin speaker connector | JST | PH-2P | C2688780 | $0.08 |
| J5 | 1 | FFC Connector 15-pin 1mm (camera) | DEALON | FFC-15P-1.0mm | C2912289 | $0.15 |
| **SERVO & EXPANSION** | | | | | | |
| J8 | 1 | Header 1×8 servo PWM | Nextron | PZ254V-11-08P | C492408 | $0.04 |
| J9 | 1 | Header 1×8 camera/GPS expansion | Nextron | PZ254V-11-08P | C492408 | $0.04 |
| **INDICATORS** | | | | | | |
| LED1 | 1 | WS2812B RGB LED | Worldsemi | WS2812B-V5 | C2761795 | $0.12 |
| R_RGB | 1 | Resistor 470Ω (WS2812B data line) | Yageo | RC0805FR-07470RL | C22775 | $0.01 |
| C_RGB | 1 | Capacitor 100nF (WS2812B decoupling) | Yageo | CC0805KRX7R9BB104 | C49678 | $0.01 |
| LED2 | 1 | LED Green 0805 (power indicator) | Hubei KENTO | KT-0805ZG | C2297 | $0.01 |
| LED3 | 1 | LED Blue 0805 (activity indicator) | Hubei KENTO | KT-0805QB | C2293 | $0.01 |
| R11, R12 | 2 | Resistor 1kΩ (LED current limit) | Yageo | RC0805FR-071KL | C17513 | $0.01 |
| **TEST POINTS** | | | | | | |
| TP1–TP12 | 12 | Test Point Pad SMD | Generic | TP-SMD-1.0 | - | $0.01 |

**Total Component Cost:** ~$25-30 per board (for 100 qty, prices drop ~20%)

---

## Assembly & Testing Strategy

### Phase 1: PCB Assembly

**Option A: Full SMT Assembly (JLCPCB)**
- Upload BOM + CPL files
- Select all components in JLCPCB library
- They solder everything except:
  - ESP32 module (you solder)
  - OLEDs (you solder)
  - Connectors (you solder)

**Cost:** ~$15-30 per board (setup fee + component cost)

**Option B: DIY Assembly**
- Order bare PCBs
- Hand-solder all components
- Requires: Soldering iron, solder paste (for SMD), hot air station
- **Time:** 2-3 hours per board

### Phase 2: Bring-Up Testing

**Test sequence (do in order):**

1. **Visual inspection** - No solder bridges, all components oriented correctly
2. **Power test** - Measure voltages before connecting anything
   ```
   Multimeter: VIN_5V should be ~5V
   Multimeter: VCC_3V3 should be 3.25-3.35V
   ```
3. **ESP32 test** - Connect USB-UART, upload blink sketch
4. **OLED test** - Upload eye animation firmware
5. **Sensor test** - Read MPU6050 values
6. **Audio test** - Play test tone through speaker
7. **Servo test** - Move servo through full range
8. **Integration test** - Full system with Raspberry Pi

### Phase 3: Quality Control Checklist

**Power verification (do before connecting any modules):**
- [ ] VIN_5V present when USB connected: 4.7–5.1V
- [ ] VCC_5V present from battery path: 4.9–5.1V
- [ ] VCC_3V3 present on USB power: 3.25–3.35V
- [ ] VCC_3V3 present on battery-only power: 3.25–3.35V ← critical, was 0V before fix
- [ ] BAT_PROT = VCC_5V minus one diode drop (~0.3V less than BAT_VIN)
- [ ] AMS1117 (U1) not hot after 30s at full load (should be warm, not burning)

**Functional tests:**
- [ ] All voltages within ±5% tolerance
- [ ] No excessive heat from regulators (U1 tab below 70°C)
- [ ] LEDs light up correctly (LED2 power on, LED3 toggles with GPIO4)
- [ ] WS2812B RGB LED responds to firmware color commands
- [ ] Both I2C buses detected: `i2cdetect -y 0` shows 0x3C + 0x68, `i2cdetect -y 1` shows 0x3C
- [ ] UART communication ESP32 ↔ Pi working at 115200
- [ ] Audio capture: INMP441 records cleanly at 16kHz (no hum/hiss)
- [ ] Audio playback: MAX98357A plays without distortion
- [ ] WiFi connects reliably (ESP32 connects in < 5s, signal > -70dBm)
- [ ] Haptic motor vibrates on GPIO25 HIGH command
- [ ] Board operates normally on battery-only (no USB connected)

---

## Advanced Production Considerations

### Certifications (If Selling Commercially)

**FCC (USA):**
- Required for devices with WiFi/Bluetooth
- Cost: $2,000-5,000 for testing
- Consider pre-certified modules (ESP32-WROOM-32 is already certified)

**CE (Europe):**
- Similar to FCC for European market
- Cost: €1,000-3,000

**RoHS Compliance:**
- Restrict hazardous substances
- Use lead-free solder (HASL leadfree)
- Check component datasheets

### Cost Optimization

**Volume pricing (100 units):**
```
PCB fabrication: $1.50/board
Components: $18/board
Assembly: $8/board
Testing: $2/board
Enclosure: $5/board (3D printed nylon)
TOTAL: ~$35 per unit

Suggested retail: $150-200
```

### Firmware Flash & Provisioning

For production:
1. Use **pogo pin programmer** - contacts test points, no manual plugging
2. Flash firmware in 30 seconds per board
3. Flash unique WiFi credentials/IDs
4. Store in database for support/warranty

---

## Next Steps: 3D Enclosure Design Preview

**Your monkey design requirements:**

```
┌──────────────────────────────────┐
│   MONKEY FACE ENCLOSURE          │
│                                  │
│   ┌────────────────────┐         │
│   │  [OLED]  [OLED]   │ ← Eyes  │
│   │    👁      👁     │         │
│   │       [CAM]        │ ← Camera│
│   │        🔊          │ ← Speaker hole
│   └────────────────────┘         │
│         ↕ Servo rotation         │
│                                  │
│   Base contains PCB + Pi         │
└──────────────────────────────────┘
```

**We'll design this in the next document!**

**3D printing plan:**
- **Material:** PETG or nylon (durable)
- **Head rotation:** 180° servo movement
- **Mounting:** PCB screws into base
- **Eyes:** Acrylic lenses over OLEDs
- **Size:** ~150mm tall, fits on desk

---

## Summary & Action Items

**You've learned:**
- ✅ Complete production schematic design
- ✅ PCB layout strategy in EasyEDA
- ✅ Manufacturing file generation
- ✅ Component selection with part numbers
- ✅ Assembly and testing procedures

**Next actions:**

1. **Open EasyEDA** and create project
2. **Draw schematic** following this guide (start with power section)
3. **Verify schematic** with checklist
4. **Convert to PCB** and place components
5. **Route traces** following best practices
6. **Run DRC** and fix errors
7. **Export Gerbers** and order from JLCPCB

**Estimated time:**
- Schematic: 4-6 hours
- PCB layout: 6-8 hours
- Review & fixes: 2 hours
- **Total:** 2-3 days of work

**Ready to start?** Let me know when you have questions during the design process!

---

---

## Schematic Corrections Log

This section documents all issues found during design review (schematic + screenshot analysis) and their resolutions.

| # | Severity | Issue | Fix Applied |
|---|---|---|---|
| 1 | **P0** | AMS1117 input connected to VIN_5V — no 3.3V on battery-only power | AMS1117 input moved to VCC_5V |
| 2 | **P1** | USBLC6-2SC6 TVS removed from corrected schematic | TVS1 restored on USB D+/D- lines |
| 3 | **P1** | No bulk capacitance on VCC_5V before AMS1117 | C_BULK 470µF added on VCC_5V |
| 4 | **P1** | Right OLED (J4) had no I2C pull-up resistors | R9/R10 4.7kΩ added on I2C_SDA_RIGHT/SCL_RIGHT |
| 5 | **P1** | LED1/LED2/LED3 anode floating in initial schematic | Both ends of each LED circuit explicitly connected |
| 6 | **P1** | No ground plane defined before routing | Step 1b added: GND pour on bottom layer first |
| 7 | **P1** | ESP32 WiFi antenna keep-out zone undefined | Keep-out zone procedure added to Phase 2 |
| 8 | **P2** | USB CC pins missing — charger may not supply power | R_CC1/R_CC2 5.1kΩ Rd added on CC1/CC2 |
| 9 | **P2** | No decoupling at Pi 40-pin header | C_PI_BULK 220µF + C_PI_DEC 100nF added at J_PI |
| 10 | **P2** | No I2S signal termination — ringing on BCK/LRCK/DIN/DOUT | 33Ω series resistors R_BCK/R_LRCK/R_DIN/R_DOUT added |
| 11 | **P2** | AMS1117 no thermal pad — 0.85W dissipation with no heatsink | Copper pour GND pad + thermal vias added in layout guide |
| 12 | **P2** | J2 programming header has no 5V warning | Silkscreen "3.3V ONLY" label added |
| 13 | **P2** | MAX98357A powered from VIN_5V (USB-only) | Changed to VCC_5V |
| 14 | **P3** | No ESD on UART lines between ESP32 and Pi | TVS_UART PRTR5V0U2X added on UART_PI_TX/RX |
| 15 | **P3** | Test points covered VIN_5V only — missing VCC_5V, BAT_PROT | TP3 VCC_5V and TP4 BAT_PROT added (12 total TPs) |

*Document Version: 2.0 | ZoarkBot Production PCB Guide | Updated 2026-03-28 | Next: 3D Enclosure Design*
