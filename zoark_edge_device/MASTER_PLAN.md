# ZoarkBot Edge Device — Complete Master Plan
### Hardware Body for Zero & Zorro AI Agents
**Version:** 1.0 | **Date:** 2026-03-23 | **Author:** Zoark AI

---

## Table of Contents
1. [Vision & Architecture](#1-vision--architecture)
2. [Bill of Materials (BOM)](#2-bill-of-materials-bom)
3. [Phase 1 — Hardware Assembly & Wiring](#3-phase-1--hardware-assembly--wiring)
4. [Phase 2 — ESP32 Firmware Flash & Verification](#4-phase-2--esp32-firmware-flash--verification)
5. [Phase 3 — Raspberry Pi Zero W OS Setup](#5-phase-3--raspberry-pi-zero-w-os-setup)
6. [Phase 4 — Server Deployment on VPS](#6-phase-4--server-deployment-on-vps)
7. [Phase 5 — Integration Testing](#7-phase-5--integration-testing)
8. [Phase 6 — Future Roadmap](#8-phase-6--future-roadmap)
9. [Troubleshooting Guide](#9-troubleshooting-guide)

---

## 1. Vision & Architecture

```
╔══════════════════════════════════════════════════════════════════╗
║          ZOARKBOT EDGE DEVICE — SPLIT-BRAIN ARCHITECTURE         ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ┌─────────────────────┐        ┌──────────────────────────┐    ║
║  │   REFLEX BRAIN      │  UART  │   EXECUTIVE BRAIN        │    ║
║  │   (ESP32-WROOM-32)  │◄──────►│   (Raspberry Pi Zero W)  │    ║
║  │                     │        │                          │    ║
║  │  • 2× OLED eyes     │        │  • Mic (INMP441)         │    ║
║  │  • MPU-6050 IMU     │        │  • Speaker (MAX98357A)   │    ║
║  │  • Haptic motor     │        │  • WebSocket client      │    ║
║  │  • 10Hz state JSON  │        │  • Audio VAD + encode    │    ║
║  └─────────────────────┘        └──────────┬───────────────┘    ║
║                                            │  WiFi (WebSocket)  ║
║                                            ▼                    ║
║                              ┌─────────────────────────┐        ║
║                              │   CLOUD BRAIN (VPS)     │        ║
║                              │   FastAPI + WebSocket   │        ║
║                              │                         │        ║
║                              │  • Zero agent (CTO)     │        ║
║                              │  • Zorro agent (Resch)  │        ║
║                              │  • Whisper STT          │        ║
║                              │  • gTTS / ElevenLabs    │        ║
║                              └─────────────────────────┘        ║
╚══════════════════════════════════════════════════════════════════╝
```

### Design Principles
- **Reflex System** (ESP32): Reacts in <10ms — blinks, shakes, speaks, without needing the cloud.
- **Executive Brain** (Pi Zero): Audio I/O + WiFi gateway. Does not process AI; it delegates.
- **Cloud Brain** (VPS): Full Zero & Zorro CrewAI pipeline; stateful, powerful, upgradeable.
- **Graceful degradation**: If WiFi drops, ESP32 still animates. If ESP32 loses power, Pi still works.

---

## 2. Bill of Materials (BOM)

| # | Component | Part / Model | Qty | Est. Price | Where to Buy |
|---|-----------|-------------|-----|------------|-------------|
| 1 | Main controller | **ESP32-WROOM-32 DevKit v1** | 1 | $5–8 | AliExpress / Amazon |
| 2 | Left eye display | **SSD1306 0.96" OLED 128×64 I2C** (blue or white) | 1 | $2–4 | AliExpress |
| 3 | Right eye display | **SSD1306 0.96" OLED 128×64 I2C** (same model) | 1 | $2–4 | AliExpress |
| 4 | IMU | **MPU-6050 GY-521 breakout** | 1 | $1–2 | AliExpress |
| 5 | Haptic motor | **ERM coin vibration motor 10mm** + 100Ω resistor + NPN transistor (2N2222) | 1 | $1–2 | AliExpress |
| 6 | I2S microphone | **INMP441 breakout** | 1 | $3–5 | AliExpress |
| 7 | I2S amplifier/speaker | **MAX98357A breakout** + 1W 8Ω mini speaker | 1 | $4–6 | Adafruit / AliExpress |
| 8 | Main SBC | **Raspberry Pi Zero 2 W** (preferred) or Pi Zero W | 1 | $15 | Raspberry Pi official |
| 9 | SD card | **microSD 16GB Class 10** | 1 | $5 | Any |
| 10 | Power (portable) | **Li-Ion 3.7V 2000mAh LiPo** + TP4056 charger module + MT3608 boost to 5V | 1 set | $5–8 | AliExpress |
| 11 | Logic level | **5V → 3.3V level shifter** (if OLED modules not already 3.3V tolerant) | 1 | $1 | AliExpress |
| 12 | Enclosure | **3D-printed shell** (PETG recommended) — STL in `/enclosure/` (TBD) | 1 | $5–10 filament | Your printer |
| 13 | Wires | Jumper wires (female-female, 20cm) | 20 | $2 | Any |
| 14 | Proto board | **Small perfboard 5×7cm** | 1 | $1 | AliExpress |
| 15 | USB-C breakout | For power + Pi Zero programming | 1 | $2 | AliExpress |

**Total estimated BOM cost: ~$55–75 USD**

---

## 3. Phase 1 — Hardware Assembly & Wiring

### 3.1 Wiring Reference

```
════════════════════════════════════════════════════
 ESP32 DevKit v1 Wiring
════════════════════════════════════════════════════

 ┌──────────────────────────────────────────────┐
 │               ESP32 DevKit                   │
 │                                              │
 │  GND ────────────────── GND (all components) │
 │  3.3V ───────────────── VCC (OLED 1, 2, MPU) │
 │  5V ─────────────────── VCC (only if needed) │
 │                                              │
 │  ── LEFT EYE OLED (I2C Bus 0) ──             │
 │  GPIO 21 (SDA0) ───── OLED-L SDA             │
 │  GPIO 22 (SCL0) ───── OLED-L SCL             │
 │                                              │
 │  ── RIGHT EYE OLED (I2C Bus 1) ──            │
 │  GPIO 32 (SDA1) ───── OLED-R SDA             │
 │  GPIO 33 (SCL1) ───── OLED-R SCL             │
 │                                              │
 │  ── MPU-6050 (shares I2C Bus 0) ──           │
 │  GPIO 21 (SDA0) ───── MPU SDA                │
 │  GPIO 22 (SCL0) ───── MPU SCL                │
 │  NOTE: both OLEDs have addr 0x3C;            │
 │        MPU6050 has addr 0x68 — no conflict!  │
 │                                              │
 │  ── HAPTIC MOTOR (via transistor) ──         │
 │  GPIO 25 ─── 100Ω ─── 2N2222 Base           │
 │  2N2222 Collector ─── Motor (+)              │
 │  2N2222 Emitter  ─── GND                    │
 │  Motor (−)       ─── GND                    │
 │  1N4148 diode across motor (flyback!)        │
 │                                              │
 │  ── Pi Zero UART (crossover) ──              │
 │  GPIO 17 (TX2) ───── Pi GPIO15 (RX/TXD0)    │
 │  GPIO 16 (RX2) ───── Pi GPIO14 (TX/TXD0)    │
 │  GND ──────────────── Pi GND                 │
 └──────────────────────────────────────────────┘

════════════════════════════════════════════════════
 Raspberry Pi Zero W Wiring
════════════════════════════════════════════════════

 ┌──────────────────────────────────────────────┐
 │           Raspberry Pi Zero W                │
 │                                              │
 │  ── UART to ESP32 ──                         │
 │  GPIO14 (TXD0/Pin 8)  ──── ESP32 GPIO16 (RX) │
 │  GPIO15 (RXD0/Pin 10) ──── ESP32 GPIO17 (TX) │
 │  GND (Pin 6)          ──── ESP32 GND         │
 │                                              │
 │  ── INMP441 I2S Microphone ──                │
 │  GPIO18 (PCM_CLK/Pin 12) ── INMP441 SCK     │
 │  GPIO19 (PCM_FS/Pin 35)  ── INMP441 WS      │
 │  GPIO20 (PCM_DIN/Pin 38) ── INMP441 SD      │
 │  3.3V (Pin 1) ────────────── INMP441 VDD    │
 │  GND   (Pin 6) ───────────── INMP441 GND    │
 │  GND   (Pin 6) ───────────── INMP441 L/R    │
 │  NOTE: L/R pin = GND → left channel mono    │
 │                                              │
 │  ── MAX98357A I2S Speaker Amplifier ──       │
 │  GPIO18 (PCM_CLK/Pin 12) ── MAX98357A BCLK  │
 │  GPIO19 (PCM_FS/Pin 35)  ── MAX98357A LRC   │
 │  GPIO21 (PCM_DOUT/Pin 40)── MAX98357A DIN   │
 │  5V  (Pin 2) ─────────────── MAX98357A VIN  │
 │  GND (Pin 6) ─────────────── MAX98357A GND  │
 │  MAX98357A OUT+ ──── Speaker (+)            │
 │  MAX98357A OUT- ──── Speaker (−)            │
 └──────────────────────────────────────────────┘
```

### 3.2 Assembly Order
1. Solder header pins to INMP441, MAX98357A, MPU-6050 breakouts.
2. Mount ESP32 DevKit on proto board.
3. Wire OLED-Left to I2C0 (21/22) and OLED-Right to I2C1 (32/33).
4. Wire MPU-6050 to I2C0 (21/22) — same bus, different address (0x68).
5. Wire haptic motor transistor circuit to GPIO 25.
6. Wire UART crossover (ESP32 TX17→Pi RX, ESP32 RX16→Pi TX).
7. Wire Pi I2S mic (INMP441) and speaker amp (MAX98357A) per diagram.
8. Power ESP32 from Pi Zero's 5V pin — or from shared LiPo boost module.

### 3.3 Power Design
```
LiPo 3.7V ─── TP4056 (charging) ─── MT3608 boost ─── 5V rail
                                                        │
                                              ┌─────────┴────────┐
                                            ESP32 (5V)     Pi Zero (5V)
```
- Total current draw: ESP32 ~250mA peak, Pi Zero ~400mA → need ≥1A boost converter.
- Use a USB-C breakout to allow cable charging while powered on.

---

## 4. Phase 2 — ESP32 Firmware Flash & Verification

### 4.1 Prerequisites
```bash
# Install PlatformIO Core (CLI)
pip install platformio

# Or use VS Code + PlatformIO IDE extension
```

### 4.2 Build & Flash
```bash
cd zoark_edge_device/esp32_firmware

# Build (download libs on first run — takes ~2 min)
pio run

# Flash to ESP32 (ensure USB is connected, port auto-detected)
pio run --target upload

# Monitor serial output (Ctrl+C to exit)
pio device monitor --baud 115200
```

### 4.3 Expected Serial Output
```
[ZoarkBot] ESP32 booting...
[OK] Left OLED ready
[OK] Right OLED ready
[OK] MPU6050 calibrated
[ZoarkBot] Boot complete — entering main loop
```

### 4.4 OLED Verification
- Left eye should show a white rounded rectangle with black pupil.
- Right eye mirrors the left.
- Every ~3 seconds, eyes blink (close and open smoothly).

### 4.5 Shake Test
1. Pick up the device and shake it vigorously.
2. Both OLEDs should switch to concentric-square "dizzy" pattern.
3. GPIO 25 should pulse HIGH for 200ms (haptic motor vibrates).
4. When still, eyes return to normal.

### 4.6 UART Test (without Pi)
```bash
# Use a USB-UART adapter on GPIO16/17
# Open two terminal windows:

# Window 1 — send commands
echo '{"command":"speak_anim"}' > /dev/ttyUSB1

# Window 2 — read state stream
cat /dev/ttyUSB1
# Expected output every 100ms:
# {"motion":"stable","orientation":"up"}
```

---

## 5. Phase 3 — Raspberry Pi Zero W OS Setup

### 5.1 Flash OS
1. Download **Raspberry Pi OS Lite (64-bit)** from raspberrypi.com.
2. Flash to microSD using **Raspberry Pi Imager**.
3. In Imager advanced options, pre-configure:
   - WiFi SSID + password
   - SSH enabled
   - Hostname: `zoarkbot`
   - Username: `pi`

### 5.2 Boot & Connect
```bash
# Find Pi's IP (check router, or use mDNS)
ssh pi@zoarkbot.local

# Update packages
sudo apt-get update && sudo apt-get upgrade -y
```

### 5.3 Enable UART (for ESP32 communication)
```bash
# Edit /boot/config.txt
sudo nano /boot/config.txt
```
Add at the end:
```ini
# Disable Bluetooth (frees up hardware UART)
dtoverlay=disable-bt
# Keep UART enabled
enable_uart=1
```

```bash
# Edit /boot/cmdline.txt — REMOVE "console=serial0,115200"
# (so the Pi doesn't use UART for a login shell)
sudo nano /boot/cmdline.txt
# Before: console=serial0,115200 console=tty1 ...
# After:  console=tty1 ...

# Disable serial getty service
sudo systemctl disable serial-getty@ttyS0.service

sudo reboot
```

### 5.4 Enable I2S Audio
```bash
sudo nano /boot/config.txt
```
Add:
```ini
# I2S audio — INMP441 mic + MAX98357A speaker
dtparam=i2s=on
dtoverlay=i2s-mmap

# MAX98357A DAC
dtoverlay=hifiberry-dac
```

```bash
# Install ALSA tools
sudo apt-get install -y alsa-utils

# Test speaker (after reboot)
speaker-test -c2 -t wav

# Test mic
arecord -D hw:1,0 -f S16_LE -r 16000 -c 1 test.wav -d 3
aplay test.wav
```

### 5.5 Install Python Dependencies
```bash
# Install system deps
sudo apt-get install -y python3-pip python3-venv portaudio19-dev \
    libportaudio2 libportaudiocpp0 libsndfile1 ffmpeg

# Create venv
python3 -m venv ~/zoark-env
source ~/zoark-env/bin/activate

# Install Pi client deps
cd ~/zoark_edge_device/pi_zero_client
pip install -r requirements.txt
```

### 5.6 ALSA Config for I2S
Create `/etc/asound.conf`:
```
pcm.!default {
    type asym
    playback.pcm "plughw:0,0"
    capture.pcm  "plughw:1,0"
}

ctl.!default {
    type hw
    card 0
}
```

### 5.7 Configure Server IP
```bash
# Edit pi_main.py — set your server IP
nano ~/zoark_edge_device/pi_zero_client/pi_main.py
# Change SERVER_WS_URL to your VPS address:
# SERVER_WS_URL = "ws://157.173.210.131:8000/ws"
```

### 5.8 Create systemd Service (auto-start on boot)
```bash
sudo nano /etc/systemd/system/zoark-pi.service
```
```ini
[Unit]
Description=ZoarkBot Pi Zero Edge Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/zoark_edge_device/pi_zero_client
ExecStart=/home/pi/zoark-env/bin/python pi_main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable zoark-pi
sudo systemctl start zoark-pi

# Check logs
journalctl -u zoark-pi -f
```

---

## 6. Phase 4 — Server Deployment on VPS

**Target:** VPS `157.173.210.131` running Ubuntu (inside or alongside existing ZoarkBot containers)

### 6.1 Upload Code to VPS
```bash
# From your dev machine (Windows):
scp -r zoark_edge_device/server_backend/ root@157.173.210.131:/opt/zoark-edge-server/

# Or use rsync:
rsync -avz zoark_edge_device/server_backend/ root@157.173.210.131:/opt/zoark-edge-server/
```

### 6.2 Install Dependencies on VPS
```bash
ssh root@157.173.210.131

cd /opt/zoark-edge-server

# System deps
apt-get install -y python3-pip python3-venv ffmpeg espeak

# Python venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 6.3 Test Run
```bash
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8000 --log-level info

# Check health endpoint from another terminal:
curl http://157.173.210.131:8000/health
# Expected: {"status":"ok","tts_engine":"gtts","service":"zoark-edge-server"}
```

### 6.4 Create systemd Service
```bash
nano /etc/systemd/system/zoark-edge-server.service
```
```ini
[Unit]
Description=ZoarkBot Edge Device Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/zoark-edge-server
ExecStart=/opt/zoark-edge-server/venv/bin/uvicorn server:app \
    --host 0.0.0.0 --port 8000 --workers 1 --log-level info
Restart=always
RestartSec=5
Environment=ZOARK_TTS_ENGINE=gtts

[Install]
WantedBy=multi-user.target
```
```bash
systemctl daemon-reload
systemctl enable zoark-edge-server
systemctl start zoark-edge-server
systemctl status zoark-edge-server
```

### 6.5 Caddy Reverse Proxy (HTTPS, optional but recommended)
Add to your existing Caddyfile:
```caddy
edge.zoarkai.org {
    reverse_proxy 127.0.0.1:8000
}
```
Then update Pi's `SERVER_WS_URL` to `wss://edge.zoarkai.org/ws`.

### 6.6 Firewall
```bash
ufw allow 8000/tcp   # direct WebSocket (dev)
# OR keep 8000 blocked and only expose via Caddy on 443
```

---

## 7. Phase 5 — Integration Testing

### 7.1 End-to-End Test Sequence

```
Step 1: Verify ESP32 is streaming
─────────────────────────────────
On Pi:  cat /dev/serial0
Output: {"motion":"stable","orientation":"up"}  (repeating at 10Hz)

Step 2: Verify Pi connects to server
─────────────────────────────────────
On Pi:  journalctl -u zoark-pi -f
Output: WebSocket connected to ws://157.173.210.131:8000/ws

Step 3: Speak into mic
──────────────────────
Say anything into INMP441 microphone.
On Pi log:    VAD: utterance started
              Audio payload enqueued
On Server log: Agent pipeline invoked | motion=stable
               Sent reply | text="Hello! I'm Zero..."

Step 4: Verify speaker playback
────────────────────────────────
Audio should play through MAX98357A speaker.
ESP32 eyes should animate (speak_anim).

Step 5: Shake test
───────────────────
Shake device.
ESP32 serial: [Motion] SHAKING detected
Server log:   motion=shaking → "Whoa, I felt that shake!"
Speaker plays the response.
Eyes show dizzy animation + haptic vibrates.
```

### 7.2 Manual WebSocket Test (curl/wscat)
```bash
# Install wscat
npm install -g wscat

# Connect to server
wscat -c ws://157.173.210.131:8000/ws

# Send test payload (paste in wscat):
{"type":"user_input","audio_b64":"UklGR...","context":{"motion":"stable","orientation":"up"}}
```

### 7.3 Latency Budget

| Stage | Target | Typical |
|-------|--------|---------|
| VAD detection → encode | <100ms | ~50ms |
| Pi → Server (WiFi+network) | <200ms | ~80ms |
| Agent processing (stub) | <100ms | ~10ms |
| TTS generation (gTTS) | <2s | ~1.2s |
| Server → Pi audio | <200ms | ~80ms |
| Audio decode + play | <50ms | ~20ms |
| **Total end-to-end** | **<3s** | **~1.5s** |

*Real agent pipeline (Whisper + CrewAI) will add 2–5s — acceptable for a conversational device.*

---

## 8. Phase 6 — Future Roadmap

### 6.1 Pi Camera Module (Vision)
```
Hardware add: Pi Camera v2 or HQ Camera Module
              Ribbon cable into Pi Zero's CSI port

Software:
  - Add picamera2 library to pi_zero_client
  - Capture a frame when user speaks (or on motion trigger)
  - Encode as JPEG base64, include in WebSocket payload:
    {"type":"user_input","audio_b64":"...","image_b64":"...","context":{...}}
  - Server: use GPT-4o / Claude Vision to describe what it sees
  - Zero agent gains "eyes" — can read documents, recognize faces, describe scenes
```

### 6.2 Wake Word Detection (Always-On)
```
Library: openWakeWord (runs on Pi Zero 2 W at ~30% CPU)
Trigger word: "Hey Zero" or "Hey Zoark"

Implementation:
  - Run openWakeWord in audio_capture_thread
  - Only begin VAD recording AFTER wake word confirmed
  - Power-efficient: skip cloud round-trip until triggered
```

### 6.3 On-Device Whisper STT
```
Pi Zero 2 W is too slow for Whisper, but options:
  Option A: Run whisper.cpp (tiny model) on server — already planned
  Option B: Stream audio directly to Deepgram / AssemblyAI (faster + cheaper)
  Option C: Upgrade to Pi 4 / Pi 5 if size allows — runs whisper-small

Recommended: Deepgram streaming WS in the server pipeline
  - Sub-500ms transcription latency
  - Partial results for faster UX
```

### 6.4 Zero / Zorro Agent Integration (Full Pipeline)
```python
# In server.py process_with_agents() — replace stub with:

async def process_with_agents(audio_bytes: bytes, context: dict) -> str:
    # 1. Transcribe
    transcript = await whisper_transcribe(audio_bytes)

    # 2. Build message with hardware context
    user_msg = f"""
    User said: "{transcript}"
    Device state: motion={context['motion']}, orientation={context['orientation']}
    """

    # 3. Send to ZoarkBot Zero via gateway RPC (reuse existing WebSocket)
    response = await zero_gateway_call("agent_chat", {
        "message": user_msg,
        "session_id": "hardware_device",
    })

    return response["text"]
```

### 6.5 Emotional Expression System
```
Map agent sentiment → OLED animation:
  "happy"    → eyes widen + subtle shimmer
  "thinking" → eyes look up-left (lookup animation)
  "confused" → eyes rotate inward (cross-eyed)
  "excited"  → rapid blink + eyes grow

Implementation: add "emotion" field to agent_reply payload
  {"type":"agent_reply","audio_b64":"...","ui":"speak_anim","emotion":"happy"}

ESP32: map emotion → animation enum, update drawEmotionEyes()
```

### 6.6 Enclosure Design
```
Requirements:
  - 2 circular cutouts for OLED displays (~26mm diameter)
  - Mic hole (1–2mm, pointed at user)
  - Speaker grille (perforated face)
  - USB-C port opening for charging
  - Access button (GPIO input on Pi — TODO)
  - Magnetic clip for pocket / desk stand

Suggested dimensions: 85mm × 45mm × 22mm
Materials: PETG (flexible, durable) or PLA+
```

### 6.7 Local Fallback Mode (No Internet)
```
When server WS is unreachable:
  - Pi client detects disconnect → enters offline mode
  - Load small local model (GGUF via llama.cpp on Pi Zero 2 W)
  - Offline model handles simple commands: "tell me a joke", "set a timer"
  - ESP32 animates with "thinking" eyes
  - When connection restored, seamlessly switch back to Zero+Zorro
```

---

## 9. Troubleshooting Guide

### OLED Not Displaying

| Symptom | Cause | Fix |
|---------|-------|-----|
| Both OLEDs blank | Wrong I2C address | Check `OLED_ADDR 0x3C` vs `0x3D` with i2cscanner |
| Left works, right blank | Wire1 not initialized | Verify GPIO 32/33, check `Wire1.begin(32,33)` |
| Garbled display | SDA/SCL swapped | Swap SDA↔SCL connections |
| Serial says "init failed" | No 3.3V on OLED VCC | Check power rail |

### MPU-6050 Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Always shows "shaking" | Address conflict | MPU6050 default is 0x68; if AD0=HIGH it's 0x69 |
| Calibration loops forever | MPU not powered | Check 3.3V on VCC, GND continuity |
| Values drift | Calibration done while moving | Hold still during the ~2s auto-calibration on boot |

### UART Not Working

| Symptom | Cause | Fix |
|---------|-------|-----|
| Pi sees no data | `/dev/serial0` not enabled | Check `/boot/config.txt` for `enable_uart=1` |
| Garbled data | Baud mismatch | Both sides must be `115200` |
| ESP32 can't receive | TX/RX not crossed | ESP TX→Pi RX, Pi TX→ESP RX |
| Pi UART busy | Login shell on UART | Remove `console=serial0` from `/boot/cmdline.txt` |

### Audio Issues (Pi)

| Symptom | Cause | Fix |
|---------|-------|-----|
| No mic input | I2S not enabled | Check `/boot/config.txt` for `dtparam=i2s=on` |
| Mic picks up noise only | L/R pin floating | Tie L/R to GND for mono left channel |
| Speaker no sound | Wrong ALSA device | Check `/etc/asound.conf`, try `aplay -D hw:0,0` |
| Audio distorted | Sample rate mismatch | Set `SAMPLE_RATE=16000` consistently |
| VAD never triggers | Threshold too low | Lower `VAD_THRESHOLD_DB` (e.g., from -30 to -45) |

### WebSocket Connection

| Symptom | Cause | Fix |
|---------|-------|-----|
| Can't connect to server | Firewall | `ufw allow 8000/tcp` on VPS |
| Reconnecting in loop | Wrong IP/port | Verify `SERVER_WS_URL` in pi_main.py |
| 403 Forbidden | CORS issue | Server has `allow_origins=["*"]` — check uvicorn is running |
| Large audio timeout | Audio too long | Reduce `VAD_MAX_SEC` (default 12s) |

### ESP32 Flash Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Failed to connect` | Boot mode wrong | Hold BOOT button while clicking Upload |
| `esptool: Port not found` | Driver not installed | Install CP2102 or CH340 USB driver |
| OTA flash hung | Build cache corrupt | `pio run -t clean` then rebuild |

---

## Quick-Start Checklist

```
Hardware
 ☐ All components wired per diagram
 ☐ Power rail verified with multimeter (3.3V at OLEDs, MPU)
 ☐ UART crossover: ESP TX17 → Pi GPIO15, ESP RX16 → Pi GPIO14
 ☐ I2S pins connected: BCLK=GPIO18, LRCLK=GPIO19, DOUT=GPIO21, DIN=GPIO20

ESP32 Firmware
 ☐ PlatformIO installed
 ☐ pio run — 0 errors
 ☐ pio run --target upload — success
 ☐ Serial monitor shows eyes + IMU data
 ☐ Shake test: dizzy eyes + haptic

Pi Zero W
 ☐ OS flashed with WiFi + SSH pre-configured
 ☐ UART enabled (/boot/config.txt + cmdline.txt)
 ☐ I2S enabled + speaker test passes
 ☐ Python deps installed in venv
 ☐ SERVER_WS_URL set correctly in pi_main.py
 ☐ zoark-pi.service enabled and running

VPS Server
 ☐ server.py uploaded to /opt/zoark-edge-server/
 ☐ requirements.txt installed
 ☐ uvicorn running on port 8000
 ☐ /health returns {"status":"ok"}
 ☐ zoark-edge-server.service enabled

Integration
 ☐ ESP32 UART stream visible on Pi (cat /dev/serial0)
 ☐ Pi connects to server (WebSocket connected log)
 ☐ Speak into mic → audio received on server log
 ☐ TTS reply plays through speaker
 ☐ ESP32 eyes animate during speech
 ☐ Shake → correct agent response + haptic + dizzy eyes
```

---

*Built by Zoark AI — Zero & Zorro hardware extension. Questions → check logs first.*
