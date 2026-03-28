# ZoarkBot Edge Device - Complete Hardware Assembly Reference

## Table of Contents
1. [Components Checklist](#components-checklist)
2. [Power Rails Setup](#power-rails-setup)
3. [ESP32 Connections](#esp32-connections)
4. [Raspberry Pi Connections](#raspberry-pi-connections)
5. [Troubleshooting Guide](#troubleshooting-guide)

---

## Components Checklist

### Required Components:
- [ ] ESP32 DevKit board
- [ ] Raspberry Pi Zero W (or Zero 2 W)
- [ ] 2× OLED displays (SSD1306 0.96" 128×64)
- [ ] MPU-6050 gyroscope/accelerometer
- [ ] INMP441 I2S microphone
- [ ] MAX98357A I2S amplifier
- [ ] Small speaker (8Ω, 1W)
- [ ] Coin vibration motor (10mm)
- [ ] 2N2222 NPN transistor
- [ ] 100Ω resistor
- [ ] 1N4148 diode
- [ ] Breadboard (830 tie-points)
- [ ] Jumper wires (assorted colors)
- [ ] USB cables for power

---

## Power Rails Setup

### Step 1: Insert ESP32 into Breadboard
- Place ESP32 straddling the center gap of the breadboard
- Left pins in columns a-e, right pins in columns f-j
- USB port should face you for easy access

### Step 2: Connect Power Rails
```
ESP32 GND (any ground pin) → Breadboard BLUE (-) rail [BLACK wire]
ESP32 3.3V pin → Breadboard RED (+) rail [RED wire]
```

**Important:** These rails now provide +3.3V and GND to all components

---

## ESP32 Connections

### Left OLED Display (Eye #1)

| OLED Pin | Connect To | Wire Color | ESP32 Pin |
|----------|-----------|------------|-----------|
| GND | Blue (-) rail | Black | - |
| VCC | Red (+) rail | Red | - |
| SDA | ESP32 GPIO 21 | Yellow/Green | GPIO21 |
| SCL | ESP32 GPIO 22 | Blue/White | GPIO22 |

### Right OLED Display (Eye #2)

| OLED Pin | Connect To | Wire Color | ESP32 Pin |
|----------|-----------|------------|-----------|
| GND | Blue (-) rail | Black | - |
| VCC | Red (+) rail | Red | - |
| SDA | ESP32 GPIO 32 | Yellow/Green | GPIO32 |
| SCL | ESP32 GPIO 33 | Blue/White | GPIO33 |

**Note:** Different GPIO pins to use separate I2C buses

### MPU-6050 Motion Sensor

| MPU Pin | Connect To | Wire Color | Notes |
|---------|-----------|------------|-------|
| VCC | Red (+) rail | Red | +3.3V |
| GND | Blue (-) rail | Black | Ground |
| SDA | ESP32 GPIO 21 | Yellow/Green | **Shares bus with Left OLED** |
| SCL | ESP32 GPIO 22 | Blue/White | **Shares bus with Left OLED** |

**Why same pins as Left OLED?** Different I2C addresses (OLED=0x3C, MPU=0x68)

### Haptic Motor Circuit

**Circuit Diagram:**
```
ESP32 GPIO25 → 100Ω resistor → 2N2222 Base
                                    ↓
                               Collector → Motor (+)
                                    ↓
                               Emitter → GND

Motor (-) → GND
1N4148 diode across motor (Cathode to +, Anode to GND)
```

**Transistor Pin Identification (2N2222):**
Hold flat side facing you, legs down: **E-B-C** (Emitter-Base-Collector)

**Connections Table:**

| Component | Connect To | Wire Color |
|-----------|-----------|------------|
| Resistor end 1 | ESP32 GPIO 25 | Orange |
| Resistor end 2 | Transistor Base | - |
| Transistor Emitter | Blue (-) rail | Black |
| Transistor Collector | Motor (+) wire | Red |
| Motor (-) wire | Blue (-) rail | Black |
| Diode Cathode (band) | Transistor Collector | - |
| Diode Anode | Blue (-) rail | - |

---

## Raspberry Pi Connections

### UART to ESP32 (Serial Communication)

**CRITICAL: This is a crossover connection!**

| ESP32 Pin | Direction | Pi Zero Pin | Pi GPIO |
|-----------|-----------|-------------|---------|
| GPIO 17 (TX) | → | Pin 10 | GPIO15 (RX) |
| GPIO 16 (RX) | ← | Pin 8 | GPIO14 (TX) |
| GND | - | Pin 6 | GND |

**Color coding suggestion:**
- ESP32 TX → Pi RX: GREEN wire
- Pi TX → ESP32 RX: BLUE wire  
- GND to GND: BLACK wire

### INMP441 Microphone (I2S)

**Pi Zero GPIO Header (Pin numbering):**
```
Pin 1 (3.3V) is closest to SD card slot
Count pins carefully!
```

| INMP441 Pin | Pi Zero Pin | Pi GPIO | Wire Color |
|-------------|-------------|---------|------------|
| VDD | Pin 1 | 3.3V | Red |
| GND | Pin 6 | GND | Black |
| SD | Pin 38 | GPIO20 (PCM_DIN) | Yellow |
| WS | Pin 35 | GPIO19 (PCM_FS) | Green |
| SCK | Pin 12 | GPIO18 (PCM_CLK) | Blue |
| L/R | Pin 6 | GND | Black |

**Note:** L/R tied to GND = mono left channel

### MAX98357A Speaker Amplifier (I2S)

| MAX98357A Pin | Pi Zero Pin | Pi GPIO | Wire Color |
|---------------|-------------|---------|------------|
| VIN | Pin 2 | 5V | Red |
| GND | Pin 6 | GND | Black |
| DIN | Pin 40 | GPIO21 (PCM_DOUT) | Orange |
| LRC | Pin 35 | GPIO19 (PCM_FS) | Green |
| BCLK | Pin 12 | GPIO18 (PCM_CLK) | Blue |

**Speaker Connections:**
- Speaker (+) red wire → MAX98357A OUT+
- Speaker (-) black wire → MAX98357A OUT−

**Note:** BCLK and LRC are SHARED with microphone (this is correct!)

---

## Power Options

### Option A: Separate Power (Recommended for Testing)

**ESP32:**
- USB cable to ESP32 micro-USB port
- Connect to computer or 5V USB adapter

**Raspberry Pi:**
- USB cable to Pi Zero "PWR IN" port (near HDMI)
- Use 5V 2A power adapter (minimum)

### Option B: Shared Power (Portable)

```
LiPo 3.7V → TP4056 charger → MT3608 boost (5V) → Split:
                                                   ├─ ESP32 5V pin
                                                   └─ Pi Zero Pin 2 (5V)
```

**For initial testing, use Option A!**

---

## Complete Connection Checklist

### ESP32 Connections
- [ ] ESP32 in breadboard straddling center gap
- [ ] ESP32 GND → blue (-) rail
- [ ] ESP32 3.3V → red (+) rail
- [ ] Left OLED: GND→(-), VCC→(+), SDA→GPIO21, SCL→GPIO22
- [ ] Right OLED: GND→(-), VCC→(+), SDA→GPIO32, SCL→GPIO33
- [ ] MPU-6050: GND→(-), VCC→(+), SDA→GPIO21, SCL→GPIO22
- [ ] Haptic: GPIO25→100Ω→transistor base
- [ ] Transistor emitter→(-), collector→motor(+)
- [ ] Motor(-)→(-), diode across motor
- [ ] ESP32 TX17→Pi RX (Pin10)
- [ ] ESP32 RX16→Pi TX (Pin8)
- [ ] ESP32 GND→Pi GND (Pin6)

### Raspberry Pi Connections
- [ ] INMP441 VDD→Pin1, GND→Pin6, SD→Pin38, WS→Pin35, SCK→Pin12, L/R→Pin6
- [ ] MAX98357A VIN→Pin2, GND→Pin6, DIN→Pin40, LRC→Pin35, BCLK→Pin12
- [ ] Speaker→MAX98357A OUT+/OUT−

---

## Troubleshooting Guide

### Current LED Status Meanings

**ESP32:**
- **Red LED ON**: Power OK ✅
- **Blue LED OFF**: No firmware loaded (normal for new board)
- **Blue LED BLINKING**: Firmware running ✅

**MPU-6050:**
- **Red LED ON**: 3.3V power OK ✅

**Raspberry Pi:**
- **Red LED ON (constant)**: Power OK ✅
- **Green LED BLINKING**: SD card activity ✅

### Expected Behavior BEFORE Firmware Upload

| Component | Status | Why |
|-----------|--------|-----|
| ESP32 red LED | ON | Power connected |
| ESP32 blue LED | OFF | No firmware yet |
| MPU red LED | ON | 3.3V rail working |
| Both OLEDs | DARK | Need firmware to initialize |
| Haptic motor | No vibration | Need firmware command |
| Pi red LED | ON | Power connected |
| Pi green LED | Blinking | OS booting |

**This is NORMAL! OLEDs require firmware to work.**

### Expected Behavior AFTER Firmware Upload

| Component | Status | What You'll See |
|-----------|--------|-----------------|
| ESP32 blue LED | BLINKING | Program running |
| Both OLEDs | DISPLAYING | Eye graphics, blinking animation |
| Haptic motor | Vibrates when shaken | Responds to motion |
| Serial monitor | SHOWING | Boot messages, "OLED ready" |

### Common Issues

**Issue: OLEDs don't light up after firmware upload**

Solutions:
1. Check I2C connections (SDA/SCL might be swapped)
2. Verify 3.3V on OLED VCC pins with multimeter
3. Try swapping left/right OLED connections
4. Run I2C scanner code to detect addresses

**Issue: Can't upload firmware - "Port not found"**

Solutions:
1. Install USB drivers (CP2102 or CH340)
2. Check USB cable (must be data cable, not power-only)
3. Try different USB port
4. Hold BOOT button while connecting

**Issue: Pi doesn't boot (green LED doesn't blink)**

Solutions:
1. Check SD card is properly inserted
2. Verify SD card has Raspberry Pi OS flashed
3. Use 5V 2A power supply (minimum)
4. Try different USB cable

**Issue: Haptic motor doesn't vibrate**

Solutions:
1. Check transistor orientation (E-B-C from left, flat side front)
2. Verify 100Ω resistor between GPIO25 and base
3. Check diode polarity (band toward motor +)
4. Test GPIO25 with multimeter (should be 3.3V when active)

---

## Pin Reference Quick Guide

### ESP32 Pin Assignments
```
GPIO 21 → Left OLED SDA + MPU SDA
GPIO 22 → Left OLED SCL + MPU SCL
GPIO 32 → Right OLED SDA
GPIO 33 → Right OLED SCL
GPIO 25 → Haptic motor control
GPIO 17 → UART TX to Pi
GPIO 16 → UART RX from Pi
```

### Raspberry Pi Pin Assignments (Physical Pin Numbers)
```
Pin 1  → 3.3V (INMP441 VDD)
Pin 2  → 5V (MAX98357A VIN)
Pin 6  → GND (common ground)
Pin 8  → GPIO14 TXD (to ESP32 RX)
Pin 10 → GPIO15 RXD (from ESP32 TX)
Pin 12 → GPIO18 PCM_CLK (I2S clock - shared)
Pin 35 → GPIO19 PCM_FS (I2S frame select - shared)
Pin 38 → GPIO20 PCM_DIN (mic data in)
Pin 40 → GPIO21 PCM_DOUT (speaker data out)
```

---

## Next Steps After Hardware Assembly

### 1. Upload ESP32 Firmware
```bash
cd C:\Users\vamsi\zoarkbot\zoarkbot_hardware\zoark_edge_device\esp32_firmware
pip install platformio
pio run
pio run --target upload
pio device monitor --baud 115200
```

### 2. Configure Raspberry Pi
```bash
python C:\Users\vamsi\zoarkbot\zoarkbot_hardware\setup_pi.py
```

### 3. Run Diagnostics
```bash
python C:\Users\vamsi\zoarkbot\zoarkbot_hardware\check_pi.py
```

### 4. Deploy Server to VPS
```bash
# Upload server backend to VPS at 157.173.210.131
scp -r zoark_edge_device/server_backend/ root@157.173.210.131:/opt/zoark-edge-server/
```

---

## Safety Reminders

1. ⚠️ **Never connect/disconnect components while powered**
2. ⚠️ **Check no shorts between + and - before power-on**
3. ⚠️ **Use correct voltage: 3.3V for sensors, 5V for Pi/amplifier**
4. ⚠️ **Don't reverse polarity on diodes or transistors**
5. ⚠️ **If anything gets hot, disconnect power immediately**

---

## Support Resources

**Project Files:**
- Master Plan: `zoark_edge_device/MASTER_PLAN.md`
- Setup Script: `setup_pi.py`
- Diagnostic Script: `check_pi.py`
- ESP32 Firmware: `zoark_edge_device/esp32_firmware/`
- Pi Client: `zoark_edge_device/pi_zero_client/pi_main.py`
- Server: `zoark_edge_device/server_backend/server.py`

**Connection Credentials:**
- Pi Zero IP: `192.168.1.181`
- Pi Username: `zero`
- Pi Password: `1234567890`
- VPS IP: `157.173.210.131`

---

*Document Version: 1.0 | Last Updated: Mar 25, 2026 | ZoarkBot Hardware Project*
