# ZoarkBot Perfboard/PCB Bring-Up Guide

## Your Current Situation — Summary

You moved all components from a working breadboard onto a perfboard (soldered).  
**What's broken:**
1. ESP32 + Pi can't share a single USB power source (voltage sag)
2. OLEDs not displaying (ESP32 was crash-looping due to I2C hang)
3. Left OLED appeared dead (it was working — just cleared to black before crash)
4. Robot not responding (Pi service needs verification)

**What's already confirmed working:**
- ESP32 boots fine on its own USB ✅
- Pi boots fine from the rail ✅
- Both boot simultaneously when powered from **separate** USB sources ✅
- All signal wires (UART, I2C) are connected correctly ✅
- IMU LED was blinking = ESP32 crash-looping (now fixed in firmware)

---

## PHASE 1: Flash Updated Firmware (Do This First)

The firmware has been updated with these fixes:
- **I2C bus timeouts** (50ms) — prevents infinite hangs on flaky connections
- **Hardware presence flags** — skips drawing to missing OLEDs instead of crashing
- **MPU6050 probe** — checks if IMU is actually connected before initializing
- **Graceful degradation** — if any component is missing, the rest still works

### Flash command:
```
cd C:\Users\vamsi\zoarkbot\zoarkbot_hardware\zoark_edge_device\esp32_firmware
pio run --target upload
```

### After flashing, open serial monitor:
```
pio device monitor --baud 115200
```

### Expected output (all components connected):
```
[ZoarkBot] Booting v3...
[OK] Left OLED
[OK] Right OLED
[OK] MPU6050
[ZoarkBot] Running v3!
```

### If any component is missing, you'll see:
```
[ZoarkBot] Booting v3...
[ERROR] Left OLED failed       ← this OLED has a wiring issue
[OK] Right OLED
[ERROR] MPU6050 not found at 0x68
[ZoarkBot] Running v3!         ← STILL BOOTS — no more crash loop
```

**The firmware now tells you exactly which component is broken.**

---

## PHASE 2: Power Solution (Permanent Fix)

### The Problem

| Source | Max Current | Pi Boot | ESP32 Boot | Total | Result |
|--------|------------|---------|------------|-------|--------|
| Computer USB | 500mA | 350mA | 450mA peak | 800mA | ❌ Sag |
| Phone charger 1A | 1000mA | 350mA | 450mA peak | 800mA | ⚠️ Marginal |
| Phone charger 2A | 2000mA | 350mA | 450mA peak | 800mA | ✅ Works |
| Power bank | varies | 350mA | 450mA peak | 800mA | ❌ Often sags |

Power banks are unreliable for this because they have internal resistance + cable resistance + breadboard wire resistance. By the time current reaches your ESP32 VIN, the voltage is below 4.75V.

### Solution A: Two USB Sources (Use This Now for Prototyping)

```
USB Charger #1 (any) ──→ Pi GPIO Pin 2 (5V) + Pin 6 (GND) via rail
USB Charger #2 (any) ──→ ESP32 USB port directly

Bridge wire: Pi GND ────→ ESP32 GND (common ground)
Signal wires: all connected normally (UART, I2C, etc.)
```

This is **perfectly valid** — separate power sources with shared ground is standard practice.

### Solution B: Single Source (When You Get a 2A+ Charger)

If you want one cable powering everything:

1. **Use a 5V 2A (or higher) phone charger** — not a computer USB port
2. **Add a 470µF or 1000µF electrolytic capacitor** across 5V rail and GND
   - Long leg (+) → 5V rail
   - Short leg (−) → GND rail  
   - Place it **right next to the ESP32 VIN pin**
3. **Use thick/short wires** from USB to rail (thinner = more resistance = more sag)
4. **Power the Pi from GPIO pins 2+4 (both 5V pins)** — doubles the current path

The 100µF you tried earlier wasn't enough — you need 470µF+ for the ESP32 startup surge.

### Solution C: Proper Regulator (Best — For Your Final PCB)

Your PCB design guide already specifies:
- LM2596 buck converter (3A capacity)
- 1000µF bulk capacitor (C9)
- Proper copper traces (low resistance)

This will solve it permanently when you make the real PCB.

---

## PHASE 3: Component-by-Component Wiring Verification

After flashing the updated firmware, the serial monitor will tell you exactly what's connected and what's not. Fix any `[ERROR]` lines using this reference:

### ESP32 Pin Connections (Verify Each One)

| Function | ESP32 Pin | Goes To | Check |
|----------|-----------|---------|-------|
| Left OLED SDA | GPIO 21 | Left OLED SDA pin | [ ] |
| Left OLED SCL | GPIO 22 | Left OLED SCL pin | [ ] |
| Right OLED SDA | GPIO 32 | Right OLED SDA pin | [ ] |
| Right OLED SCL | GPIO 33 | Right OLED SCL pin | [ ] |
| MPU6050 SDA | GPIO 21 | MPU6050 SDA (shared with Left OLED) | [ ] |
| MPU6050 SCL | GPIO 22 | MPU6050 SCL (shared with Left OLED) | [ ] |
| Haptic motor | GPIO 25 | 100Ω → 2N2222 Base | [ ] |
| UART TX to Pi | GPIO 17 | Pi Pin 10 (GPIO15 RX) | [ ] |
| UART RX from Pi | GPIO 16 | Pi Pin 8 (GPIO14 TX) | [ ] |

### Raspberry Pi Pin Connections (Verify Each One)

| Function | Pi Pin | Goes To | Check |
|----------|--------|---------|-------|
| 5V Power | Pin 2 | 5V rail (or USB) | [ ] |
| GND | Pin 6 | GND rail | [ ] |
| UART TX | Pin 8 (GPIO14) | ESP32 GPIO 16 (RX) | [ ] |
| UART RX | Pin 10 (GPIO15) | ESP32 GPIO 17 (TX) | [ ] |
| I2S BCK | Pin 12 (GPIO18) | INMP441 SCK + MAX98357A BCLK | [ ] |
| I2S LRCK | Pin 35 (GPIO19) | INMP441 WS + MAX98357A LRC | [ ] |
| I2S DIN (mic) | Pin 38 (GPIO20) | INMP441 SD | [ ] |
| I2S DOUT (spk) | Pin 40 (GPIO21) | MAX98357A DIN | [ ] |

### OLED Power (Both OLEDs)

| Pin | Goes To | Check |
|-----|---------|-------|
| VCC | 3.3V rail | [ ] |
| GND | GND rail | [ ] |

### MPU6050 Power

| Pin | Goes To | Check |
|-----|---------|-------|
| VCC | 3.3V rail | [ ] |
| GND | GND rail | [ ] |

### INMP441 Microphone

| Pin | Goes To | Check |
|-----|---------|-------|
| VDD | 3.3V | [ ] |
| GND | GND | [ ] |
| L/R | GND (mono left) | [ ] |
| SCK | Pi Pin 12 (GPIO18) | [ ] |
| WS | Pi Pin 35 (GPIO19) | [ ] |
| SD | Pi Pin 38 (GPIO20) | [ ] |

### MAX98357A Amplifier

| Pin | Goes To | Check |
|-----|---------|-------|
| VIN | 5V rail | [ ] |
| GND | GND | [ ] |
| BCLK | Pi Pin 12 (GPIO18) | [ ] |
| LRC | Pi Pin 35 (GPIO19) | [ ] |
| DIN | Pi Pin 40 (GPIO21) | [ ] |

### Haptic Motor Circuit

| Component | From → To | Check |
|-----------|-----------|-------|
| 100Ω resistor | ESP32 GPIO 25 → 2N2222 Base | [ ] |
| 2N2222 Emitter | GND rail | [ ] |
| 2N2222 Collector | Motor (+) | [ ] |
| Motor (−) | GND rail | [ ] |
| 1N4148 Cathode (band) | Motor (+) / Collector | [ ] |
| 1N4148 Anode | GND rail | [ ] |

---

## PHASE 4: Common Soldering Issues on Perfboard

When moving from breadboard to perfboard, these are the most common failure modes:

### 1. Cold Solder Joints
- **Symptom:** Component works sometimes, fails other times
- **Check:** Every solder joint should be shiny and cone-shaped
- **Fix:** Reheat the joint, add a tiny bit more solder, hold still until it solidifies

### 2. Solder Bridges (Shorts Between Adjacent Pins)
- **Symptom:** Component gets hot, or power LED goes dark
- **Check:** Look at every IC/header pin under bright light — any silver connecting two adjacent pins?
- **Fix:** Use solder wick or a solder sucker to remove the bridge

### 3. Cracked Traces / Lifted Pads
- **Symptom:** Component doesn't work even though solder looks OK
- **Check:** Gently wiggle the wire — if the solder joint moves, the pad is lifted
- **Fix:** Solder a jumper wire directly from the component leg to its destination

### 4. Wrong Row (Off-by-One)
- **Symptom:** Component doesn't work at all
- **Check:** Count the perfboard holes carefully — one row off means completely wrong connection
- **Fix:** Desolder and move to correct hole

---

## PHASE 5: Verify Raspberry Pi Software

### Step 1: SSH into the Pi
```bash
ssh zero@192.168.1.181
# Password: 1234567890
```

### Step 2: Check the zoark-pi service
```bash
sudo systemctl status zoark-pi
```

**Expected:** `active (running)` in green

**If stopped/failed:**
```bash
sudo systemctl restart zoark-pi
sudo journalctl -u zoark-pi -n 30 --no-pager
```

### Step 3: Check UART communication
```bash
# On Pi, check if serial port exists:
ls -la /dev/serial0

# Should show: /dev/serial0 -> ttyS0
```

### Step 4: Check I2S audio
```bash
# List sound cards:
aplay -l
arecord -l

# Test speaker (should hear white noise):
speaker-test -t sine -f 440 -l 1 -D hw:0,0

# Test mic recording:
arecord -D hw:0,0 -f S16_LE -r 16000 -c 2 -d 3 test.wav
aplay test.wav
```

### Step 5: Check WebSocket connection to server
```bash
sudo journalctl -u zoark-pi -n 50 --no-pager | grep -i "websocket\|connect\|error"
```

**Expected:** `WebSocket connected` message  
**If failing:** Check that the VPS server at 157.173.210.131:8765 is running

---

## PHASE 6: End-to-End Test Sequence

Once all components pass individual checks, run through this sequence:

### Test 1: ESP32 Eyes
1. Power on ESP32 (via USB)
2. Serial monitor should show all `[OK]`
3. Both OLEDs should show animated blinking eyes
4. Shake the board → eyes go dizzy + motor vibrates

### Test 2: UART Communication
1. Power on both ESP32 and Pi
2. On Pi: `sudo journalctl -u zoark-pi -f`
3. Look for: `UART port opened` and `ESP32 state:` messages
4. You should see `{"motion":"stable","orientation":"up"}` streaming

### Test 3: Audio
1. On Pi: `speaker-test -t sine -f 440 -l 1`
2. Should hear tone from speaker through MAX98357A
3. On Pi: `arecord -D hw:0,0 -f S16_LE -r 16000 -c 2 -d 3 /tmp/test.wav && aplay /tmp/test.wav`
4. Speak into INMP441, should hear playback

### Test 4: Full System
1. Both devices powered and running
2. Pi service connected to VPS WebSocket
3. Speak to the robot → mic captures → sends to server
4. Server responds → audio plays through speaker → eyes animate "speak_anim"

---

## Quick Troubleshooting Reference

| Symptom | Most Likely Cause | Fix |
|---------|-------------------|-----|
| ESP32 LED completely dark on shared rail | Voltage sag — not enough current | Use separate USB sources |
| ESP32 crash-looping (IMU blinks) | I2C hang — missing/bad OLED connection | Flash updated firmware (v3 with timeouts) |
| Serial shows `[ERROR] Left OLED failed` | SDA/SCL swapped or loose solder joint | Recheck GPIO 21 (SDA) and GPIO 22 (SCL) |
| Serial shows `[ERROR] Right OLED failed` | SDA/SCL swapped or loose solder joint | Recheck GPIO 32 (SDA) and GPIO 33 (SCL) |
| Serial shows `[ERROR] MPU6050 not found` | Bad solder joint or wrong I2C address | Reheat SDA/SCL joints on MPU6050 |
| Only right OLED works | Left OLED shares bus with MPU — bus contention | Check left OLED + MPU wiring on Bus 0 |
| Pi UART shows nothing from ESP32 | TX/RX crossed wrong | ESP32 TX (GPIO17) → Pi RX (Pin10), ESP32 RX (GPIO16) → Pi TX (Pin8) |
| No sound from speaker | MAX98357A DIN wrong pin | Must be Pi Pin 40 (GPIO21), not Pin 38 |
| Mic doesn't capture | INMP441 L/R not grounded | Tie L/R pin to GND |
| Pi service keeps restarting | VPS WebSocket unreachable | Check `journalctl -u zoark-pi` for error |
| Haptic motor doesn't vibrate | Transistor wrong orientation | Flat side facing you: E-B-C left to right |

---

*Document Version: 1.0 | ZoarkBot Perfboard Bring-Up Guide | Mar 27, 2026*
