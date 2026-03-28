# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ZoarkBot Edge Device — a talking robot with animated OLED eyes, IMU-driven reactions, and real-time AI conversation. Three-layer split-brain architecture:

```
Cloud VPS (FastAPI + WebSocket + Whisper STT + LLM + edge-tts)
    ↕ WiFi/WebSocket
Raspberry Pi Zero 2W (audio I/O, VAD, WebSocket client, UART bridge)
    ↕ UART 115200 baud
ESP32-WROOM-32 (dual OLED eyes, MPU-6050 IMU, haptic motor)
```

VPS address: `157.173.210.131` | Server WebSocket: `ws://157.173.210.131:8765/ws`

## Source Files

```
zoark_edge_device/
├── esp32_firmware/
│   ├── platformio.ini          # Board: esp32dev, upload port: COM3
│   └── src/main.cpp            # 558-line C++ Arduino firmware
├── pi_zero_client/
│   ├── pi_main.py              # 600+ line Python multi-threaded client
│   ├── requirements.txt
│   └── zoark-pi.service        # systemd unit
└── server_backend/
    ├── server.py               # 344-line FastAPI WebSocket server
    ├── requirements.txt
    └── zoark-edge-server.service
```

## Commands

### ESP32 Firmware (PlatformIO)
```bash
cd zoark_edge_device/esp32_firmware
pio run                                          # build
pio run --target upload --upload-port COM3       # flash
pio device monitor --baud 115200                 # serial monitor
```

### Raspberry Pi Client
```bash
cd zoark_edge_device/pi_zero_client
python3 -m venv ~/zoark-env && source ~/zoark-env/bin/activate
pip install -r requirements.txt
python pi_main.py                                # run directly
# systemd: sudo systemctl start zoark-pi
# logs:    journalctl -u zoark-pi -f
```

### VPS Server
```bash
cd zoark_edge_device/server_backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8765   # dev run
curl http://157.173.210.131:8765/health          # health check
# systemd: sudo systemctl start zoark-edge-server
```

## Architecture Details

### ESP32 (`main.cpp`)
- **I2C Bus 0** (SDA=GPIO19, SCL=GPIO18): Left OLED (0x3C) + MPU-6050 (0x68)
- **I2C Bus 1** (SDA=GPIO32, SCL=GPIO33): Right OLED (0x3C)
- **UART2** (RX=GPIO16, TX=GPIO17): Pi crossover at 115200
- **GPIO25**: Haptic motor via NPN transistor
- IMU polls at ~80Hz; broadcasts JSON state every 100ms: `{"motion":"stable|shaking","orientation":"up|down"}`
- Receives JSON commands from Pi: `{"command":"speak_anim|angry|happy|sad|blink"}`
- Eye states: `EYE_OPEN`, `EYE_BLINKING`, `EYE_DIZZY`, `EYE_SPEAK`, `EYE_ANGRY`, `EYE_HAPPY`, `EYE_SAD`, `EYE_BOOT`

### Pi Client (`pi_main.py`)
Three threads running concurrently:
1. **UART reader** — reads ESP32 IMU JSON, drains `uart_write_q` for outbound commands
2. **WebSocket client** — sends `{type:"user_input", audio_b64, context}`, receives `{type:"agent_reply", audio_b64, ui, text}`
3. **Audio capture** — INMP441 at 16kHz, adaptive VAD (−30dB threshold, 1.2s hold), suppresses capture during playback

Key config constants at top of `pi_main.py`: `SERVER_WS_URL`, `UART_PORT`, `SAMPLE_RATE`, `VAD_THRESHOLD_DB`, `WAKE_WORD_ENABLED`

### Server (`server.py`)
Pipeline per utterance: WAV → faster-whisper (tiny, CPU) → NVIDIA llama-3.1-8b-instruct → emotion regex → edge-tts (AriaNeural) → base64 WAV back to Pi. Target latency: <3s.

ESP32 context injected into LLM system prompt (shaking/orientation affects responses). Per-connection conversation history capped at 20 messages.

## Pi OS Configuration (Required)
`/boot/config.txt` must include:
```
enable_uart=1
dtparam=i2s=on
dtoverlay=disable-bt
```
ALSA config: `zoark_edge_device/pi_zero_client/alsa/`

## Known Issues
- NVIDIA API key is hardcoded in `server.py` — move to env var before any public deployment
- WebSocket CORS is `allow_origins=["*"]` — restrict for production
