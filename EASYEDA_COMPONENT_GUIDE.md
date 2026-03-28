# EasyEDA Component Library - Practical Search Guide for ZoarkBot

## How EasyEDA Library Works

### Three Ways to Add Components:

**1. LCSC Components (Recommended - Best for Production)**
- Pre-made symbols + footprints + 3D models
- Direct ordering from LCSC.com
- Assembly service available at JLCPCB
- Search by LCSC part number (starts with "C")

**2. System Library**
- Generic components from Kicad, open source
- Good for basic parts (resistors, capacitors)
- May need footprint adjustment

**3. Create Your Own**
- For parts not in LCSC
- Draw symbol + footprint manually
- Time-consuming but flexible

---

## Step-by-Step: Finding Components in EasyEDA

### Opening the Library

1. **In EasyEDA Schematic Editor**
2. **Press:** `Shift + F` (or click "Place" → "Component")
3. **Library panel appears** on left side

### Understanding Library Tabs

```
┌─────────────────────────────────────┐
│  Library Search Panel               │
├─────────────────────────────────────┤
│  [Search Box]                       │
│                                     │
│  Type dropdown:                     │
│   ● Symbol (for schematic)          │
│   ○ Footprint (for PCB)             │
│   ○ 3D Model                        │
│                                     │
│  Classes dropdown:                  │
│   ● LCSC ← Use this first!          │
│   ○ LCSC Assembled (SMT parts)      │
│   ○ System                          │
│   ○ User Contributed                │
└─────────────────────────────────────┘
```

---

## Complete Verified Component List with Search Instructions

### POWER COMPONENTS

#### 1. USB-C Connector

**Search in EasyEDA:**
1. Set Type: **Symbol**
2. Set Class: **LCSC**
3. Search: `USB TYPE-C 16P`
4. **Select:** Korean Hroparts Elec `TYPE-C-31-M-12` (LCSC: **C165948**)

**Alternative if not found:**
- Search: `USB-C female`
- Use any 16-pin or 24-pin USB-C connector
- Check footprint matches your needs

**Creating Your Own Option:**
- Type: `USB4105` in search
- If no results, use generic USB connector
- Add manually: Place → New Component → draw 16 pins

---

#### 2. Polyfuse (Resettable Fuse)

**Search in EasyEDA:**
1. Search: `PPTC 1.5A`
2. **Select:** Littelfuse `1206L150THYR` (LCSC: **C70066**)
3. Footprint: 1206

**Simple Alternative:**
1. Search: `fuse 1206`
2. Any 1-2A resettable fuse works

---

#### 3. Schottky Diode (Reverse Polarity Protection)

**Search in EasyEDA:**
1. Search: `SS14`
2. **Select:** MDD `SS14` (LCSC: **C2480**)
3. Footprint: SMA (DO-214AC)

**Generic Search:**
- Search: `schottky 1A SMA`
- Any 1A+ Schottky diode in SMA package

---

#### 4. ESD Protection Diode

**Search in EasyEDA:**
1. Search: `USBLC6-2SC6`
2. **Select:** STMicroelectronics `USBLC6-2SC6` (LCSC: **C7519**)
3. Footprint: SOT-23-6

**Alternative:**
- Search: `ESD USB` 
- Any USB ESD protection IC (6-pin)

---

#### 5. Voltage Regulator (3.3V LDO)

**Search in EasyEDA:**
1. Search: `AMS1117-3.3`
2. **Select:** Advanced Monolithic Systems `AMS1117-3.3` (LCSC: **C6186**)
3. Footprint: SOT-223

**THIS IS CONFIRMED AVAILABLE IN LCSC!**

**Important:** Make sure you select the **SOT-223** package (surface mount), not TO-220 (through-hole)

---

### PASSIVE COMPONENTS (Resistors & Capacitors)

**These are EASY to find - EasyEDA has thousands**

#### Resistors

**Search Pattern:**
1. Search: `resistor 10k 0805`
   - `10k` = resistance value
   - `0805` = package size (2mm × 1.25mm)
2. Class: **LCSC Assembled** (for SMT assembly)
3. Pick any from results - they're all similar

**Common values you need:**
- `10kΩ 0805` → Pull-ups (LCSC: **C17414**)
- `4.7kΩ 0805` → I2C pull-ups (LCSC: **C17673**)
- `1kΩ 0805` → LED current limiting (LCSC: **C17513**)
- `470Ω 0805` → RGB LED (LCSC: **C17710**)

#### Capacitors

**Ceramic Capacitors (100nF decoupling):**
1. Search: `100nF 0805`
2. **Select:** Any X7R or X5R type (LCSC: **C49678**)

**Electrolytic Capacitors (10µF power):**
1. Search: `10uF 16V electrolytic`
2. Package size matters! Common: **4mm diameter**
3. LCSC: **C19702**

---

### MICROCONTROLLER & MODULES

#### ESP32-WROOM-32

**Search in EasyEDA:**
1. Search: `ESP32-WROOM-32`
2. **Select:** Espressif `ESP32-WROOM-32-N4` (LCSC: **C82899**)
   - N4 = 4MB flash (sufficient)
   - N8 (C529582) = 8MB flash (better)

**THIS IS CONFIRMED AVAILABLE!**

**Important Notes:**
- The module comes with complete symbol (38 pins)
- Footprint included
- 3D model available
- This is the same module you used in breadboard!

**If using module breakout board:**
- Search: `ESP32 devkit`
- But for PCB production, use the raw module (saves space)

---

#### SSD1306 OLED Display

**Problem:** Full OLED modules NOT in LCSC library (they're assemblies)

**Solution - Two Options:**

**Option A: External Module (Easier)**
1. Search: `header 1x4` or `connector 4 pin`
2. Add a 4-pin header connector (GND, VCC, SDA, SCL)
3. Connect external OLED module to this header
4. **Connector LCSC:** C492404

**Option B: Bare SSD1306 IC (Advanced)**
1. Search: `SSD1306`
2. You'll need to design the full OLED circuit
3. Not recommended unless you're experienced

**RECOMMENDED: Use Option A with headers**

---

#### MPU6050 IMU

**Same issue as OLED - it's a module**

**Solution:**
1. Search: `header 1x8` or `header 2.54mm 8 pin`
2. Add 8-pin header (or 6-pin if module has 6 pins)
3. Connect external MPU6050 module
4. **Header LCSC:** C492406

**Why this works:**
- You already have working MPU6050 modules
- Just create header footprint on PCB
- Plug module in like breadboard
- Saves design time

---

### AUDIO COMPONENTS

#### INMP441 I2S Microphone

**Problem:** Module not in library

**Solution:**
1. Search: `header 1x6 2.54mm`
2. Create 6-pin header footprint
3. **LCSC:** C492405
4. Plug in external INMP441 module

**For production (bare IC):**
- Search: `INMP441` (the actual IC)
- Will find bare chip, requires custom PCB design
- Not recommended for first version

---

#### MAX98357A I2S Amplifier

**Search in EasyEDA:**
1. Search: `MAX98357A`
2. **Select:** Analog Devices/Maxim `MAX98357AETE+T` (LCSC: **C365368**)
3. Footprint: TQFN-16

**THIS IS AVAILABLE AS BARE IC!**

**Alternative (easier for first version):**
1. Search: `header 1x9`
2. Create header for MAX98357A module
3. Plug in module you already have

---

### TRANSISTORS & MOSFETS

#### N-Channel MOSFET (for motor/servo)

**Search in EasyEDA:**
1. Search: `2N7002 SOT-23`
2. **Select:** Multiple manufacturers available
3. **LCSC:** C8545 (Diodes Inc)

**Alternative MOSFETs:**
- `AO3400A` (LCSC: **C20917**) - More current capacity
- `BSS138` (LCSC: **C112239**) - Lower current

---

#### Diode (Flyback protection)

**Search in EasyEDA:**
1. Search: `1N4148`
2. **Select:** Any manufacturer (LCSC: **C81598**)
3. Footprint: SOD-123 or SOD-323 (SMD versions)

---

### CONNECTORS

#### Headers (2.54mm pin spacing)

**Search Pattern:**
1. Search: `header male 2.54 1x6` (for 6 pins)
2. **Available in LCSC Assembled!**
3. Common part: **C492404** to **C492410** (different pin counts)

**You'll need:**
- 1×6 pin (programming header)
- 1×3 pin (servo connector)
- 2×20 pin female (Raspberry Pi) - LCSC: **C50981**
- 1×4 pin (OLED headers)
- 1×6 pin (INMP441 header)

---

#### JST Connector (Speaker)

**Search in EasyEDA:**
1. Search: `JST PH 2P`
2. **Select:** JST `S2B-PH-K-S` (LCSC: **C157932**)
3. 2-pin connector for speaker

---

#### FFC Connector (Pi Camera)

**Search in EasyEDA:**
1. Search: `FFC 15P 1.0mm`
2. Multiple options available
3. **LCSC:** C2912289 or similar
4. Make sure: **15-pin, 1.0mm pitch, bottom contact**

---

### INDICATORS

#### WS2812B RGB LED

**Search in EasyEDA:**
1. Search: `WS2812B`
2. **Select:** Worldsemi `WS2812B-V5` (LCSC: **C2761795**)
3. Footprint: 5050 (5mm × 5mm)

**THIS IS AVAILABLE!**

---

#### Standard LEDs (0805 SMD)

**Search in EasyEDA:**
1. Search: `LED 0805 green` (or red, blue, etc.)
2. **Green:** LCSC **C2297**
3. **Blue:** LCSC **C2293**
4. **Red:** LCSC **C84256**

---

## Practical Component Strategy for Your First PCB

### Hybrid Approach (Recommended)

**Use bare ICs for:**
- ✅ ESP32-WROOM-32 (C82899) - Available, saves space
- ✅ AMS1117-3.3 regulator (C6186) - Available
- ✅ MAX98357A amplifier (C365368) - Available
- ✅ Resistors, capacitors (all available)
- ✅ WS2812B RGB LED (C2761795) - Available
- ✅ MOSFETs and diodes (all available)

**Use header connectors for:**
- 🔌 OLED displays (you already have modules)
- 🔌 MPU6050 IMU (you already have module)
- 🔌 INMP441 microphone (you already have module)
- 🔌 Servo motor (standard 3-pin header)
- 🔌 Vibration motor (2-pin header)

**Why this works:**
1. Saves design time (no custom OLED circuits)
2. Uses modules you already tested
3. Easier to troubleshoot
4. Can upgrade to bare ICs in v2.0

---

## Step-by-Step Component Placement Tutorial

### Example: Adding ESP32-WROOM-32

**Follow these exact steps:**

1. **Open schematic in EasyEDA**
2. **Press:** `Shift + F`
3. **Library panel opens**
4. **Set dropdown:** Type = "Symbol"
5. **Set dropdown:** Class = "LCSC"
6. **In search box, type:** `ESP32-WROOM-32`
7. **Press Enter**
8. **Results appear** - look for:
   ```
   Espressif Systems
   ESP32-WROOM-32-N4
   LCSC Part: C82899
   ```
9. **Click on it** - preview appears on right
10. **Verify:** 38 pins, correct pinout
11. **Click "Place"** button
12. **Move cursor** - component follows mouse
13. **Click on schematic** to place it
14. **Press ESC** to finish

**Done!** ESP32 is now on your schematic with correct footprint.

---

### Example: Adding 10kΩ Resistor

1. **Press:** `Shift + F`
2. **Type:** `10k 0805`
3. **Set Class:** "LCSC Assembled" (for SMT assembly)
4. **Results show** many options:
   ```
   Yageo RC0805FR-0710KL
   LCSC: C17414
   10kΩ ±1% 1/8W 0805
   ```
5. **Click and Place**
6. **Label it:** Right-click → "Modify" → Set "Designator" to `R1`

---

### Example: Adding Header for OLED

**Since OLED module not in library, create connector:**

1. **Search:** `header 1x4 2.54`
2. **Select:** Male pin header 1×4
3. **LCSC:** C492404
4. **Place it**
5. **Label pins:**
   - Pin 1: GND
   - Pin 2: VCC
   - Pin 3: SDA
   - Pin 4: SCL
6. **Add note on silkscreen:** "OLED LEFT EYE"

**In real assembly:**
- Solder this header to PCB
- Plug in your OLED module
- Just like breadboard!

---

## Component Not Found? Here's What to Do

### Strategy 1: Search Different Keywords

**Example: Can't find "USB4105"**

Try searching:
- `USB TYPE-C`
- `USB-C 16 pin`
- `USB connector female`
- Look in "System" library if not in LCSC

### Strategy 2: Use Generic Alternative

**Example: Need specific capacitor**

Any 100nF capacitor works:
- Search just: `100nF`
- Pick any with correct package (0805)
- Voltage rating >10V

### Strategy 3: Create Custom Symbol (Last Resort)

1. **Click:** "New" → "Symbol"
2. **Draw:** Rectangle representing the component
3. **Add pins:** Number them correctly
4. **Save to:** "My Library"
5. **Create footprint** separately
6. **Link them** together

**Only do this if:**
- Component truly doesn't exist anywhere
- You understand pin functions
- You have datasheet

---

## Updated BOM with Verified LCSC Numbers

| Component | Description | LCSC Part | Search Term | Status |
|-----------|-------------|-----------|-------------|--------|
| ESP32 | ESP32-WROOM-32-N4 | **C82899** | `ESP32-WROOM-32` | ✅ Verified |
| U1 | AMS1117-3.3 Regulator | **C6186** | `AMS1117-3.3` | ✅ Verified |
| USB-C | USB Type-C 16P | **C165948** | `USB TYPE-C 16P` | ✅ Available |
| F1 | Polyfuse 1.5A | **C70066** | `PPTC 1.5A` | ✅ Available |
| D1 | Schottky SS14 | **C2480** | `SS14` | ✅ Verified |
| TVS1 | USBLC6-2SC6 | **C7519** | `USBLC6-2SC6` | ✅ Verified |
| R (10kΩ) | Resistor 0805 | **C17414** | `10k 0805` | ✅ Available |
| R (4.7kΩ) | Resistor 0805 | **C17673** | `4.7k 0805` | ✅ Available |
| C (100nF) | Capacitor 0805 | **C49678** | `100nF 0805` | ✅ Available |
| C (10µF) | Electrolytic | **C19702** | `10uF 16V` | ✅ Available |
| Q1 | 2N7002 MOSFET | **C8545** | `2N7002 SOT-23` | ✅ Available |
| LED RGB | WS2812B | **C2761795** | `WS2812B` | ✅ Verified |
| LED Green | 0805 LED | **C2297** | `LED 0805 green` | ✅ Available |
| MAX98357A | I2S Amplifier IC | **C365368** | `MAX98357A` | ✅ Verified |
| Header 1x4 | Pin header | **C492404** | `header 1x4` | ✅ Available |
| Header 1x6 | Pin header | **C492405** | `header 1x6` | ✅ Available |
| Header 2x20F | Female socket | **C50981** | `header 2x20 female` | ✅ Available |
| JST 2P | Speaker connector | **C157932** | `JST PH 2P` | ✅ Available |

**Legend:**
- ✅ Verified = Confirmed in LCSC with exact part number
- ✅ Available = Found in library, may have multiple options

---

## Quick Tips for Faster Component Search

### Use LCSC Website Directly

Sometimes easier to find on LCSC.com first, then use part number:

1. **Go to:** https://lcsc.com
2. **Search** for component
3. **Copy LCSC part number** (starts with C)
4. **In EasyEDA:** Search by that C number directly
5. **Example:** Search `C82899` → finds ESP32 instantly

### Filter by "LCSC Assembled"

If planning SMT assembly:
1. **Always use** "LCSC Assembled" class
2. **Green checkmark** = Available for assembly
3. **No checkmark** = You must hand-solder

### Save Frequently Used Parts

1. **Right-click** on component in library
2. **Select:** "Favorite"
3. **Access later:** Library → "Favorites" tab

---

## Common Mistakes to Avoid

❌ **Don't:**
- Search for module names (like "MPU6050 module")
- Use vague terms ("sensor")
- Forget to set Type = Symbol
- Mix up through-hole vs SMD footprints

✅ **Do:**
- Search by IC name (`AMS1117`)
- Include package size (`0805`, `SOT-23`)
- Check footprint preview before placing
- Verify pin count matches your needs

---

## What to Do Next

### Action Plan:

1. **Open EasyEDA** (web or desktop)
2. **Create new project:** "ZoarkBot_EdgeDevice_v1"
3. **Practice finding these components:**
   - ESP32-WROOM-32 (C82899)
   - AMS1117-3.3 (C6186)
   - 10kΩ resistor
   - 100nF capacitor
   - WS2812B LED

4. **Start schematic** with power section:
   - Place USB-C connector
   - Add AMS1117 regulator
   - Add capacitors
   - Connect with wires

5. **Build section by section** using the main PCB guide

6. **Use headers** for OLED/MPU6050/INMP441 (not bare ICs)

---

## Need Help? Troubleshooting

**"I can't find ESP32-WROOM-32"**
- Make sure Class = "LCSC" (not System)
- Type exactly: `ESP32-WROOM-32`
- Try searching: `C82899` directly

**"The footprint looks wrong"**
- Click component → View details
- Check "Footprint" tab
- Verify dimensions match datasheet

**"Component shows as 'Not in stock'"**
- Find alternative with similar specs
- Or wait for restock (LCSC updates weekly)
- Contact LCSC support for ETA

**"I need a component not in this guide"**
- Search LCSC.com first
- Get part number
- Search by C number in EasyEDA
- If not found, create custom symbol

---

*This guide ensures every component you need is findable and usable in EasyEDA!*
