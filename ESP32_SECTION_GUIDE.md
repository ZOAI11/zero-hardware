# ESP32 Microcontroller Section - Step-by-Step Build Guide

## Overview

This section adds the ESP32-WROOM-32 module with all supporting circuitry for:
- Power supply and decoupling
- Reset and boot functionality
- Programming interface
- GPIO pin access

---

## Components Needed for This Section

| Ref | Component | Value/Part | LCSC | Search Term |
|-----|-----------|------------|------|-------------|
| U2 | ESP32-WROOM-32-N4 | WiFi module | C82899 | `ESP32-WROOM-32` |
| SW1 | Reset button | Tactile switch | C318884 | `TS-1187A` or `tactile 6x6` |
| SW2 | Boot button | Tactile switch | C318884 | `TS-1187A` or `tactile 6x6` |
| R1 | Pull-up resistor | 10kΩ 0805 | C17414 | `10k 0805` |
| R2 | Pull-up resistor | 10kΩ 0805 | C17414 | `10k 0805` |
| C4 | Decoupling cap | 100nF 0805 | C49678 | `100nF 0805` |
| C5 | Decoupling cap | 100nF 0805 | C49678 | `100nF 0805` |
| C6 | Decoupling cap | 100nF 0805 | C49678 | `100nF 0805` |
| C7 | Decoupling cap | 100nF 0805 | C49678 | `100nF 0805` |
| C8 | Bulk cap | 10µF 0805 | C19702 | `10uF 0805` |
| J2 | Programming header | 6-pin male 2.54mm | C492405 | `header 1x6` |

---

## Step 1: Add ESP32-WROOM-32 Module

### Finding the Component in EasyEDA

1. **Press:** `Shift + F` (open library)
2. **Set Type:** Symbol
3. **Set Class:** LCSC
4. **Search:** `ESP32-WROOM-32`
5. **Look for:** Espressif Systems ESP32-WROOM-32-N4 (or N8)
6. **Verify:** LCSC Part shows **C82899** (N4) or **C529582** (N8)
7. **Check preview:** Should show 38 pins (19 on each side)
8. **Click "Place"**

### Placing the Module

1. **Move to right side** of your power section
2. **Click to place** - leave space around it for other components
3. **Press ESC** when done
4. **Right-click module** → Properties → Change Designator to `U2`

### Understanding ESP32 Pinout

**Important pins you'll use:**
```
Left side (top to bottom):
GND (pin 1, 15, 38) - Ground
3V3 (pin 2) - Power input
EN (pin 3) - Enable/Reset
GPIO36-39 (pins 4-7) - Input only
GPIO34-35 (pins 8-9) - Input only
GPIO32-33 (pins 10-11) - I2C bus for right OLED
GPIO25-27 (pins 12-14) - Haptic motor
GPIO14,12,13 (pins 16-18) - Spare

Right side (top to bottom):
GPIO23 (pin 19) - Spare
GPIO22 (pin 20) - I2C SCL (left OLED + MPU)
TXD0 (pin 21) - UART to Pi
RXD0 (pin 22) - UART from Pi
GPIO21 (pin 23) - I2C SDA (left OLED + MPU)
GND (pin 24) - Ground
GPIO19 (pin 25) - Spare
GPIO18 (pin 26) - Spare
GPIO5 (pin 27) - Spare
GPIO17 (pin 28) - UART TX to Pi (alternate)
GPIO16 (pin 29) - UART RX from Pi (alternate)
GPIO4 (pin 30) - Activity LED
GPIO0 (pin 31) - Boot button
GPIO2 (pin 32) - Built-in LED
GPIO15 (pin 33) - Spare
GND (pin 34) - Ground
3V3 (pin 35) - Power
```

---

## Step 2: Connect Power to ESP32

### Add Power Connections

**Connect VCC_3V3 to ESP32:**
1. **Click:** Wire tool (or press `W`)
2. **Connect:** VCC_3V3 net → U2 pin 2 (3V3)
3. **Also connect:** VCC_3V3 → U2 pin 35 (3V3)

**Why two power pins?** ESP32 has multiple power pins for stability - connect all of them!

**Connect GND to ESP32:**
1. **Place GND symbol** near U2 pin 1
2. **Wire:** U2 pin 1 → GND symbol
3. **Repeat for:** Pins 15, 24, 34, 38 (all GND pins)

**Pro tip:** You can connect all GND pins to nearby GND symbols, they auto-connect to same net.

---

## Step 3: Add Decoupling Capacitors

### Why Decoupling Caps?

ESP32 WiFi radio draws sudden bursts of current. Capacitors filter noise and provide local charge reservoir.

### Placement Strategy

**Place capacitors VERY CLOSE to ESP32 power pins:**

**C4, C5, C6, C7 (100nF ceramic):**
1. **Search:** `100nF 0805` in LCSC library
2. **Select:** Any X7R ceramic capacitor (C49678 recommended)
3. **Place:** 4 capacitors near U2 corners
4. **Wire each:**
   - One side → VCC_3V3 (or directly to ESP32 3V3 pins)
   - Other side → GND

**C8 (10µF electrolytic or ceramic):**
1. **Search:** `10uF 0805` or `10uF electrolytic`
2. **Place:** Near U2
3. **Wire:**
   - Positive (+) → VCC_3V3
   - Negative (-) → GND

### Schematic Layout

```
        VCC_3V3                VCC_3V3
           │                      │
   C4 ─────┤              C5 ─────┤
   │       │              │       │
   GND   U2 Pin2        GND    U2 Pin35

   C8 (10µF)            C6, C7 near other pins
```

---

## Step 4: Add Reset Button (SW1)

### Function

Pressing this button resets the ESP32 (reboots it).

### Finding the Component

1. **Search:** `tactile switch` or `TS-1187A` or `button 6x6`
2. **Look for:** 4-pin tactile switch (2 pins on each side)
3. **LCSC:** C318884 or any similar tactile switch
4. **Place** above or to the left of U2

### Wiring Reset Circuit

**Components:**
- SW1 (tactile switch)
- R1 (10kΩ resistor)
- C4 (100nF capacitor) - already placed, can share with decoupling

**Connections:**
```
VCC_3V3 ──→ R1 (10kΩ) ──┬──→ U2 Pin 3 (EN)
                        │
                      SW1 (one side)
                        │
                      SW1 (other side) → GND

Optional: Add 100nF cap from EN to GND for debouncing
```

**How it works:**
- R1 pulls EN pin HIGH (3.3V) normally → ESP32 runs
- Pressing SW1 connects EN to GND → ESP32 resets
- Releasing SW1 → EN goes HIGH again → ESP32 boots

### Step-by-Step in EasyEDA

1. **Add R1 (10kΩ resistor):**
   - Search: `10k 0805`
   - Place near U2 pin 3
   - One end → VCC_3V3
   - Other end → U2 pin 3 (EN)

2. **Add SW1 (tactile switch):**
   - Place near R1
   - Wire: Junction between R1 and EN pin → SW1 pin 1
   - Wire: SW1 pin 2 → GND

3. **Label the net** between R1 and EN:
   - Click wire junction
   - Press `N` for net label
   - Name: `EN` or `RESET`

---

## Step 5: Add Boot Button (SW2)

### Function

Hold this button while pressing reset to enter bootloader mode (for firmware upload).

### Wiring Boot Circuit

**Components:**
- SW2 (tactile switch)
- R2 (10kΩ resistor)

**Connections:**
```
VCC_3V3 ──→ R2 (10kΩ) ──┬──→ U2 Pin 31 (GPIO0)
                        │
                      SW2 (one side)
                        │
                      SW2 (other side) → GND
```

**How it works:**
- R2 pulls GPIO0 HIGH normally → ESP32 boots from flash
- Hold SW2 while resetting → GPIO0 LOW → ESP32 enters bootloader
- Release SW2 → Normal boot

### Step-by-Step in EasyEDA

1. **Add R2 (10kΩ resistor):**
   - Search: `10k 0805`
   - Place near U2 pin 31 (GPIO0)
   - One end → VCC_3V3
   - Other end → U2 pin 31

2. **Add SW2 (tactile switch):**
   - Place near R2
   - Wire: Junction between R2 and GPIO0 → SW2 pin 1
   - Wire: SW2 pin 2 → GND

3. **Label the net:**
   - Click wire junction
   - Press `N`
   - Name: `BOOT` or `GPIO0`

---

## Step 6: Add Programming Header (J2)

### Purpose

Allows programming ESP32 with USB-UART adapter (like CP2102, CH340).

### Pinout

```
J2 (6-pin header):
Pin 1: GND
Pin 2: TXD (ESP32 TX → Programmer RX)
Pin 3: RXD (ESP32 RX → Programmer TX)
Pin 4: GPIO0 (Boot pin, for auto-programming)
Pin 5: EN (Reset pin, for auto-reset)
Pin 6: VCC_3V3 (can power external devices)
```

### Finding Component

1. **Search:** `header 1x6` or `header male 2.54`
2. **Look for:** 6-pin straight male header
3. **LCSC:** C492405
4. **Place:** On top or bottom edge of schematic (easy PCB access)

### Wiring Programming Header

1. **Add J2 (6-pin header):**
   - Place component
   - Label designator: `J2`

2. **Wire connections:**
   ```
   J2 Pin 1 → GND
   J2 Pin 2 → U2 Pin 21 (TXD0)
   J2 Pin 3 → U2 Pin 22 (RXD0)
   J2 Pin 4 → GPIO0 net (shared with SW2)
   J2 Pin 5 → EN net (shared with SW1)
   J2 Pin 6 → VCC_3V3
   ```

3. **Add pin labels** on the header:
   - Right-click J2 → Edit pins
   - Or add text labels near each pin for assembly reference

---

## Complete ESP32 Section Schematic

### Visual Layout

```
                VCC_3V3
                  │
         ┌────────┴────────┐
         │                 │
        R1 (10k)         R2 (10k)
         │                 │
  SW1 ──┼── EN        GPIO0 ──┼── SW2
         │                 │
        GND               GND

    ╔═══════════════════════════╗
    ║    ESP32-WROOM-32 (U2)    ║
    ║                           ║
    ║  Pin 2,35: 3V3 (power)    ║ ← VCC_3V3
    ║  Pin 1,15,24,34,38: GND   ║ ← GND
    ║  Pin 3: EN                ║ ← Reset circuit
    ║  Pin 31: GPIO0            ║ ← Boot circuit
    ║  Pin 21: TXD0             ║ ← J2 Pin 2
    ║  Pin 22: RXD0             ║ ← J2 Pin 3
    ╚═══════════════════════════╝
         │ │ │ │ │
        C4 C5 C6 C7 C8 (decoupling caps)
         │ │ │ │ │
        GND (all)

    J2 (Programming Header)
    1: GND
    2: TXD → U2 Pin 21
    3: RXD → U2 Pin 22
    4: GPIO0 → Boot circuit
    5: EN → Reset circuit
    6: VCC_3V3
```

---

## Verification Checklist

Before moving to next section, verify:

- [ ] U2 (ESP32) placed on schematic
- [ ] All VCC_3V3 pins connected (pins 2, 35)
- [ ] All GND pins connected (pins 1, 15, 24, 34, 38)
- [ ] 4× 100nF capacitors (C4-C7) from VCC_3V3 to GND near ESP32
- [ ] 1× 10µF capacitor (C8) from VCC_3V3 to GND
- [ ] SW1 (reset) + R1 (10k pull-up) connected to EN (pin 3)
- [ ] SW2 (boot) + R2 (10k pull-up) connected to GPIO0 (pin 31)
- [ ] J2 (6-pin header) wired correctly:
  - Pin 1 → GND ✅
  - Pin 2 → TXD0 ✅
  - Pin 3 → RXD0 ✅
  - Pin 4 → GPIO0 ✅
  - Pin 5 → EN ✅
  - Pin 6 → VCC_3V3 ✅

---

## Common Mistakes to Avoid

❌ **Don't:** Connect EN directly to VCC_3V3 without pull-up resistor  
✅ **Do:** Use R1 (10kΩ) between VCC_3V3 and EN

❌ **Don't:** Forget decoupling capacitors - ESP32 won't work reliably  
✅ **Do:** Place all 5 capacitors close to ESP32

❌ **Don't:** Swap TXD and RXD on programming header  
✅ **Do:** ESP32 TXD → Header Pin 2 (goes to programmer RX)

❌ **Don't:** Leave GPIO0 floating (unconnected)  
✅ **Do:** Pull-up with R2 (10kΩ) to VCC_3V3

---

## Testing This Section (After PCB Assembly)

### Test 1: Power Check
1. Power on PCB with 5V via USB-C
2. Measure VCC_3V3 at ESP32 pins → Should be 3.25-3.35V
3. Measure all GND pins → Should be 0V

### Test 2: Reset Function
1. Press SW1 (reset button)
2. ESP32 should reboot (you'll see this when firmware is loaded)

### Test 3: Boot Mode
1. Hold SW2 (boot button)
2. Press SW1 (reset)
3. Release both
4. ESP32 should be in bootloader mode (verify via serial monitor)

### Test 4: Programming
1. Connect USB-UART adapter to J2:
   - GND → J2 Pin 1
   - Adapter RX → J2 Pin 2
   - Adapter TX → J2 Pin 3
   - VCC (optional) → J2 Pin 6
2. Use esptool or Arduino IDE
3. Upload blink sketch
4. Should program successfully

---

## Next Steps

Once ESP32 section is complete, you'll add:

**Section 3: Displays & Sensors**
- 2× OLED displays (headers for modules)
- MPU6050 IMU (header for module)
- Haptic motor driver circuit

**Section 4: Raspberry Pi Interface**
- 40-pin header
- UART connections
- I2S audio interface

**Section 5: Audio & Indicators**
- Microphone header
- Speaker amplifier
- RGB LED
- Status LEDs

**Take a screenshot of your completed ESP32 section and I'll review it before moving forward!**

---

*ESP32 Section Complete - Ready for Sensors!*
