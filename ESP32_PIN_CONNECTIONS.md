# ESP32-WROOM-32 Complete Pin Connection Guide

## Pin-by-Pin Reference (Based on Your EasyEDA Symbol)

### LEFT SIDE (Top to Bottom)

| Pin # | Label | Function | Your Connection |
|-------|-------|----------|-----------------|
| 1 | GND | Ground | → GND symbol ✅ REQUIRED |
| 2 | 3V3 | 3.3V Power | → VCC_3V3 ✅ REQUIRED |
| 3 | EN | Enable/Reset | → Reset circuit (SW1 + R1) ✅ REQUIRED |
| 4 | SENSOR_VP | GPIO36 (Input only) | Leave unconnected for now |
| 5 | SENSOR_VN | GPIO39 (Input only) | Leave unconnected for now |
| 6 | IO34 | GPIO34 (Input only) | Leave unconnected for now |
| 7 | IO35 | GPIO35 (Input only) | Leave unconnected for now |
| 8 | IO32 | GPIO32 | For I2C (right OLED) - later |
| 9 | IO33 | GPIO33 | For I2C (right OLED) - later |
| 10 | IO25 | GPIO25 | For haptic motor - later |
| 11 | IO26 | GPIO26 | Spare GPIO |
| 12 | IO27 | GPIO27 | Spare GPIO |
| 13 | IO14 | GPIO14 | Spare GPIO |
| 14 | IO12 | GPIO12 | Spare GPIO |
| 15 | GND | Ground | → GND symbol ✅ REQUIRED |
| 16 | IO13 | GPIO13 | Spare GPIO |
| 17 | SHD/SD2 | GPIO9 (SD card) | Leave unconnected |
| 18 | SWP/SD3 | GPIO10 (SD card) | Leave unconnected |
| 19 | SCS/CMD | GPIO11 (SD card) | Leave unconnected |

### RIGHT SIDE (Top to Bottom)

| Pin # | Label | Function | Your Connection |
|-------|-------|----------|-----------------|
| 39 | GND | Ground | → GND symbol ✅ REQUIRED |
| 38 | GND | Ground | → GND symbol ✅ REQUIRED |
| 37 | GND | Ground | → GND symbol ✅ REQUIRED |
| 36 | IO23 | GPIO23 | Spare GPIO |
| 35 | IO22 | GPIO22 | For I2C SCL (left OLED + MPU) - later |
| 34 | TXD0 | UART TX (GPIO1) | → J2 Pin 2 ✅ REQUIRED |
| 33 | RXD0 | UART RX (GPIO3) | → J2 Pin 3 ✅ REQUIRED |
| 32 | IO21 | GPIO21 | For I2C SDA (left OLED + MPU) - later |
| 31 | NC | Not Connected | Leave unconnected |
| 30 | IO19 | GPIO19 | Spare GPIO |
| 29 | IO18 | GPIO18 | Spare GPIO |
| 28 | IO5 | GPIO5 | Spare GPIO |
| 27 | IO17 | GPIO17 | Spare GPIO |
| 26 | IO16 | GPIO16 | Spare GPIO |
| 25 | IO4 | GPIO4 | For activity LED - later |
| 24 | IO0 | GPIO0 (Boot pin) | → Boot circuit (SW2 + R2) ✅ REQUIRED |
| 23 | IO2 | GPIO2 (Built-in LED) | Spare or status LED |
| 22 | IO15 | GPIO15 | Spare GPIO |
| 21 | SDI/SD1 | GPIO7 (SD card) | Leave unconnected |
| 20 | SDO/SD0 | GPIO8 (SD card) | Leave unconnected |
| 40 | SCK/CLK | GPIO6 (SD card) | Leave unconnected |

---

## REQUIRED CONNECTIONS FOR ESP32 SECTION

### Power Connections (CRITICAL - Must Connect)

```
Pin 2 (3V3) → VCC_3V3 net
Pin 1 (GND) → GND symbol
Pin 15 (GND) → GND symbol
Pin 37 (GND) → GND symbol
Pin 38 (GND) → GND symbol
Pin 39 (GND) → GND symbol
```

**Total:** 1 power pin, 5 ground pins

---

### Reset Circuit (CRITICAL)

```
VCC_3V3 → R1 (10kΩ) → Junction → Pin 3 (EN)
                        ↓
                       SW1
                        ↓
                       GND
```

**Components:**
- R1: 10kΩ resistor (0805)
- SW1: Tactile switch

**How it works:** Normally EN pin is HIGH (3.3V) through R1. Pressing SW1 pulls EN to GND → ESP32 resets.

---

### Boot Circuit (CRITICAL)

```
VCC_3V3 → R2 (10kΩ) → Junction → Pin 24 (IO0)
                        ↓
                       SW2
                        ↓
                       GND
```

**Components:**
- R2: 10kΩ resistor (0805)
- SW2: Tactile switch

**How it works:** Normally IO0 is HIGH through R2 → Normal boot. Hold SW2 during reset → IO0 is LOW → Bootloader mode.

---

### Programming Header (CRITICAL)

```
J2 Pin 1 → GND
J2 Pin 2 → Pin 34 (TXD0) - ESP32 transmit
J2 Pin 3 → Pin 33 (RXD0) - ESP32 receive
J2 Pin 4 → Pin 24 (IO0) via BOOT net
J2 Pin 5 → Pin 3 (EN) via EN net
J2 Pin 6 → VCC_3V3
```

**Why this wiring?**
- Pins 2,3: Serial communication for uploading code
- Pin 4: Auto-boot mode when programming
- Pin 5: Auto-reset when programming
- Pins 1,6: Power for external devices

---

### Decoupling Capacitors (CRITICAL)

Place **5 capacitors** near ESP32:

```
C4: 100nF (0805) - VCC_3V3 to GND
C5: 100nF (0805) - VCC_3V3 to GND
C6: 100nF (0805) - VCC_3V3 to GND
C7: 100nF (0805) - VCC_3V3 to GND
C8: 10µF (0805 or electrolytic) - VCC_3V3 to GND
```

**Why?** ESP32 WiFi draws sudden current bursts. Capacitors filter noise and provide local power reservoir.

---

## CHECKING YOUR CURRENT SCHEMATIC

### ✅ What I Can Confirm is Correct:

1. **Reset circuit:** R1 → EN junction → SW1 → GND ✅
2. **5 capacitors present:** C4, C5, C6, C7, C8 ✅
3. **Power rail:** VCC_3V3 distributed ✅
4. **Boot circuit:** R2 → BOOT junction → SW2 → GND ✅

### ⚠️ What I Need You to Verify:

#### Check 1: Pin 2 (3V3) Connection
**Look at pin 2 on left side of U2**
- **Question:** Is there a wire from pin 2 to VCC_3V3 net?
- **Should be:** Wire from pin 2 → VCC_3V3 (green wire in your schematic)

#### Check 2: All 5 GND Pins Connected
**Look at pins 1, 15, 37, 38, 39 on U2**
- Pin 1 (left side, top)
- Pin 15 (left side, middle)
- Pin 37 (right side, top)
- Pin 38 (right side, top)
- Pin 39 (right side, top)

**Each should have wire to GND symbol**

#### Check 3: Boot Circuit to Pin 24 (IO0)
**Look at pin 24 on right side of U2**
- **Question:** Does BOOT junction connect to pin 24?
- **Should be:** Wire from BOOT junction → Pin 24 (IO0)

#### Check 4: Programming Header Wiring
**Look at J2 and trace each wire:**
- J2 Pin 2 → Pin 34 (TXD0) on right side
- J2 Pin 3 → Pin 33 (RXD0) on right side
- J2 Pin 4 → Pin 24 (IO0) via BOOT net
- J2 Pin 5 → Pin 3 (EN) via EN net

---

## STEP-BY-STEP VERIFICATION PROCEDURE

### Step 1: Check Pin 2 Power
1. Click on pin 2 (labeled "3V3" on left side)
2. Look for green wire
3. Should connect to VCC_3V3 net
4. ✅ or ❌?

### Step 2: Check Ground Pins
1. Click on pin 1 (GND, left top) → Should have wire to GND ✅ or ❌
2. Click on pin 15 (GND, left middle) → Should have wire to GND ✅ or ❌
3. Click on pin 37 (GND, right top) → Should have wire to GND ✅ or ❌
4. Click on pin 38 (GND, right top) → Should have wire to GND ✅ or ❌
5. Click on pin 39 (GND, right top) → Should have wire to GND ✅ or ❌

### Step 3: Check Boot to IO0
1. Click on pin 24 (labeled "IO0" on right side)
2. Trace wire back
3. Should connect to BOOT junction (where R2 and SW2 meet)
4. ✅ or ❌?

### Step 4: Check Programming Header
1. Click J2 pin 2 → Should go to pin 34 (TXD0) ✅ or ❌
2. Click J2 pin 3 → Should go to pin 33 (RXD0) ✅ or ❌
3. Click J2 pin 4 → Should go to BOOT net (pin 24) ✅ or ❌
4. Click J2 pin 5 → Should go to EN net (pin 3) ✅ or ❌

---

## VISUAL DIAGRAM - Complete ESP32 Connections

```
                    VCC_3V3
                      │
         ┌────────────┼────────────┐
         │            │            │
        R1           R2          (to capacitors)
       (10K)        (10K)
         │            │
    ┌────┴────┐  ┌────┴────┐
    │         │  │         │
   EN       SW1 BOOT      SW2
           (reset)      (boot)
            │            │
           GND          GND

       ╔════════════════════════════╗
       ║   ESP32-WROOM-32 (U2)      ║
       ║                            ║
LEFT   ║  Pin 1: GND → GND          ║  Pin 39: GND → GND   RIGHT
SIDE   ║  Pin 2: 3V3 → VCC_3V3      ║  Pin 38: GND → GND   SIDE
       ║  Pin 3: EN ← Reset ckt     ║  Pin 37: GND → GND
       ║  ...                       ║  Pin 34: TXD0 → J2-2
       ║  Pin 15: GND → GND         ║  Pin 33: RXD0 → J2-3
       ║  ...                       ║  ...
       ║                            ║  Pin 24: IO0 ← Boot ckt
       ╚════════════════════════════╝

       C4   C5   C6   C7   C8
       │    │    │    │    │
     (100nF capacitors + 10µF)
       │    │    │    │    │
      GND  GND  GND  GND  GND

    J2 (Programming Header)
    ┌─────┬─────────────┐
    │ 1   │ GND         │
    │ 2   │ TXD (pin 34)│
    │ 3   │ RXD (pin 33)│
    │ 4   │ IO0 (pin 24)│
    │ 5   │ EN (pin 3)  │
    │ 6   │ VCC_3V3     │
    └─────┴─────────────┘
```

---

## YOUR ACTION CHECKLIST

Please check each item and respond:

- [ ] **Pin 2 (3V3)** connected to VCC_3V3? (Yes/No)
- [ ] **Pin 1 (GND)** connected to GND? (Yes/No)
- [ ] **Pin 15 (GND)** connected to GND? (Yes/No)
- [ ] **Pin 37 (GND)** connected to GND? (Yes/No)
- [ ] **Pin 38 (GND)** connected to GND? (Yes/No)
- [ ] **Pin 39 (GND)** connected to GND? (Yes/No)
- [ ] **Pin 3 (EN)** connected to reset circuit (SW1 + R1)? (Yes/No)
- [ ] **Pin 24 (IO0)** connected to boot circuit (SW2 + R2)? (Yes/No)
- [ ] **Pin 34 (TXD0)** connected to J2 pin 2? (Yes/No)
- [ ] **Pin 33 (RXD0)** connected to J2 pin 3? (Yes/No)
- [ ] **J2 pin 4** connected to BOOT net (pin 24)? (Yes/No)
- [ ] **J2 pin 5** connected to EN net (pin 3)? (Yes/No)
- [ ] All **5 capacitors** (C4-C8) present? (Yes/No)

**Just answer Yes/No for each and I'll tell you if it's perfect or what needs fixing!**

---

*Pin-by-Pin Connection Reference Complete*
