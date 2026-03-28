# ZoarkBot Edge Device

A talking robot with animated OLED eyes, IMU-driven reactions, and real-time AI conversation.
Say **"hey zoark"** → it listens → responds with neural speech and matching facial expressions.

## Hardware

| Component | Part | Notes |
|-----------|------|-------|
| Brain | ESP32 DevKit v1 | Handles eyes, IMU, haptic, UART |
| Compute | Raspberry Pi Zero 2W | Audio bridge, wake word, WebSocket |
| Left Eye | SSD1306 128×64 OLED | I2C Bus 0 (SDA=21, SCL=22) |
| Right Eye | SSD1306 128×64 OLED | I2C Bus 1 (SDA=32, SCL=33) |
| IMU | MPU-6050 | I2C Bus 0 — shake & orientation |
| Microphone | INMP441 | I2S: BCLK=18, LRCLK=19, DATA=20 |
| Speaker | MAX98357A | I2S: BCLK=18, LRCLK=19, DATA=21 |
| Haptic | Coin vibration motor | GPIO 25 |
| UART link | Pi TX→ESP RX / Pi RX→ESP TX | GPIO 16/17 on ESP, /dev/serial0 on Pi |

## Repository Structure

```
zoark_edge_device/
├── esp32_firmware/          # PlatformIO project (C++ / Arduino)
│   ├── src/main.cpp         # Eye animations, IMU, haptic, UART
│   └── platformio.ini       # Board: esp32dev, libs: SSD1306, MPU6050, ArduinoJson
│
├── pi_zero_client/          # Python service on Raspberry Pi
│   └── pi_main.py           # Wake word → VAD → WebSocket → playback
│
└── server_backend/          # FastAPI service on VPS
    └── server.py            # Whisper STT → NVIDIA LLM → edge-tts
```

## Quick Start

### 1. Flash ESP32
```bash
cd zoark_edge_device/esp32_firmware
python -m platformio run --target upload --upload-port COM3
```

### 2. Pi Zero — install dependencies
```bash
sudo apt install python3-pip python3-venv portaudio19-dev
python3 -m venv ~/zoark-env
source ~/zoark-env/bin/activate
pip install sounddevice numpy pyserial websockets openwakeword
```

Configure ALSA (`/etc/asound.conf`):
```
pcm.!default {
    type asym
    playback.pcm { type plug; slave.pcm "dmix:0,0" }
    capture.pcm  { type plug; slave.pcm "dsnoop:0,0" }
}
ctl.!default { type hw; card 0 }
```

Add to `/boot/firmware/config.txt`:
```
dtoverlay=googlevoicehat-soundcard
dtparam=i2s=on
enable_uart=1
dtoverlay=disable-bt
```

### 3. VPS — run server
```bash
pip install fastapi uvicorn faster-whisper openai edge-tts pydub numpy
uvicorn server:app --host 0.0.0.0 --port 8765
```

Or use the systemd service:
```bash
systemctl start zoark-edge-server
```

### 4. Systemd service on Pi
```ini
# /etc/systemd/system/zoark-pi.service
[Service]
ExecStart=/home/zero/zoark-env/bin/python /home/zero/pi_zero_client/pi_main.py
Restart=always
User=zero
```

## How It Works

```
Say "hey zoark"
    → openWakeWord (hey_jarvis model) detects keyword
    → Adaptive VAD records utterance (stops after 1.2s silence)
    → WAV + ESP32 context sent via WebSocket to VPS
    → faster-whisper transcribes to text
    → NVIDIA llama-3.1-8b-instruct generates reply
    → Emotion detected from reply text → ESP32 expression
    → edge-tts synthesizes neural speech WAV
    → WAV returned to Pi → aplay plays through speaker
    → ESP32 shows speak_anim / happy / sad / angry eyes
```

## Conversation Flow

The bot maintains per-connection conversation history (last 10 exchanges) on the VPS.
The ESP32 streams IMU state (motion/orientation) at 10 Hz via UART to Pi, which forwards
it as context with each audio payload. If the bot is being shaken, it feels it and reacts.

## VPS Config

- Server: `ws://157.173.210.131:8765/ws` (direct) or `wss://robot.zoarkai.org/ws` (TLS via Caddy + Cloudflare)
- Health check: `GET /health`
- Systemd service: `zoark-edge-server`

## Enhancements

See [ENHANCEMENTS_ROADMAP.md](ENHANCEMENTS_ROADMAP.md) for the full backlog of 18+ planned improvements.
