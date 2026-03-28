# ZoarkBot Edge Device — Enhancements Roadmap

Current state: fully working voice bot (wake word → STT → LLM → neural TTS → speaker)
with animated OLED eyes, IMU shake detection, and emotion-driven facial expressions.
Robot name: **Zero**

---

## Implemented (v1.0 baseline)

| # | Enhancement | Status |
|---|-------------|--------|
| 1 | Angry / happy / sad OLED expressions on ESP32 | ✅ Done |
| 2 | Adaptive VAD (ambient noise calibration at startup) | ✅ Done |
| 3 | Neural TTS via edge-tts (Microsoft neural voices) | ✅ Done |
| 4 | WSS/TLS — wss://robot.zoarkai.org/ws via Caddy + Cloudflare | ✅ Done |
| 5 | Wake word detection — "hey zoark" (hey_jarvis model) | ✅ Done |

## Implemented (v2.0 — high-impact sprint)

| # | Enhancement | Status |
|---|-------------|--------|
| A | **Robot renamed to Zero** — system prompt, boot announcement, all responses | ✅ Done |
| B | **Monkey voice TTS** — piper neural + sox (pitch 680, tempo 1.05, bass/treble/overdrive) | ✅ Done |
| C | **arecord-based capture** — replaces PortAudio; full-duplex with googlevoicehat-soundcard | ✅ Done |
| D | **DuckDuckGo search** — unknown questions trigger web search + follow-up LLM pass | ✅ Done |
| E | **Voice toggle** — say "stop" / "be quiet" to mute; "wake up" / "hey zero" to unmute | ✅ Done |
| F | **Capacitive touch** — ESP32 GPIO 4 (T0); Zero says "that tickles!" + happy eyes + haptic | ✅ Done (needs USB flash) |
| G | **Streaming TTS** — sentence-by-sentence `audio_chunk` messages; ~halves first-word latency | ✅ Done |
| H | **Whisper medium** — upgraded from tiny to medium for better accuracy | ✅ Done |
| I | **Persistent memory** — JSON per device-IP; stores name + personal facts across sessions | ✅ Done |
| J | **Custom personality** — Zero: warm, cute, positive, professional, concise (≤3 sentences) | ✅ Done |

## Implemented (v3.0 — AI + dashboard sprint)

| # | Enhancement | Status |
|---|-------------|--------|
| K | **Ultra-realistic OLED eyes v6** — anatomical eyelids (per-column droop), eyebrow hair texture, pupil dilation animation, micro-saccades, emotion flash labels, scrolling text ticker | ✅ Done |
| 13 | **Emotion from voice** — WAV pitch/energy/ZCR analysis; Zero mirrors user mood in LLM tone + OLED expression | ✅ Done |
| 15 | **Local LLM fallback** — SmolLM2-360M-Instruct Q4 via llama-cpp-python; auto-activates after 3 WS failures; espeak TTS offline | ✅ Done |
| 20 | **Live web dashboard** — `GET /dashboard` — real-time SSE feed: conversation bubbles, animated emotion bars, waveform, session stats | ✅ Done |

---

## Priority Backlog (Next Wave)

### Hardware / ESP32
| # | Enhancement | Impact | Effort |
|---|-------------|--------|--------|
| 6 | **Colour OLED upgrade** — Replace SSD1306 mono OLEDs with SSD1351 128×128 colour OLEDs for full colour eyes with gradients | High | Medium |
| 7 | **LED ring** — NeoPixel ring around each eye; pulse colour to emotion (blue=listening, green=speaking, red=angry) | High | Low |
| 8 | **Servo neck** — 2-DOF servo bracket, ESP32 moves head toward sound source (use mic amplitude on two ears) | High | High |
| 9 | **Battery + BMS** — 18650 Li-ion + TP4056 charger + IP5306 boost; full wireless operation | Medium | Medium |

### Raspberry Pi / Edge AI
| # | Enhancement | Impact | Effort |
|---|-------------|--------|--------|
| 11 | **Custom wake word** — Train a "hey zero" model using openWakeWord training pipeline; replace hey_jarvis placeholder | High | High |
| 12 | **On-device STT** — Run Whisper tiny fully on Pi Zero 2W (no VPS round-trip for STT) — ~1.5s latency savings | High | High |
| 13 | **Emotion from voice** — ✅ Done (server v6) |  |  |
| 14 | **Face tracking** — Add Pi Camera + MediaPipe; eyes follow the human face in view | High | High |
| 15 | **Local LLM fallback** — ✅ Done (SmolLM2-360M Q4, pi_main.py v2) |  |  |

### Server / VPS
| # | Enhancement | Impact | Effort |
|---|-------------|--------|--------|
| 19 | **Multi-language** — Detect language from audio and respond in same language (Spanish, Hindi, etc.) | Medium | Medium |
| 20 | **Web dashboard** — ✅ Done (`/dashboard` + SSE `/events` endpoint, server v6) |  |  |

---

## Recommended Next Sprint (3 items)

1. **Custom wake word** (#11) — "hey zero" trained on your own voice; biggest UX win
2. **LED ring** (#7) — Instant visual feedback, cheapest hardware upgrade (~$3 NeoPixel rings)
3. **Face tracking** (#14) — Pi Camera Module 3 + MediaPipe; eyes follow you

---

## Architecture Overview

```
┌──────────────┐   UART/JSON    ┌──────────────────┐
│   ESP32      │◄──────────────►│  Pi Zero 2W      │
│  Dual OLEDs  │                │  INMP441 mic     │
│  MPU-6050    │                │  MAX98357A spkr  │
│  Haptic      │                │  openWakeWord    │
│  Touch (T0)  │                │  VAD + record    │
│  Expressions │                │  piper monkey TTS│
└──────────────┘                └────────┬─────────┘
                                         │ WebSocket ws://
                                         ▼
                                ┌──────────────────┐
                                │  VPS (Ubuntu)    │
                                │  faster-whisper  │
                                │    medium        │
                                │  llama-3.3-70b   │
                                │  edge-tts neural │
                                │  DuckDuckGo srch │
                                │  Persistent mem  │
                                │  Streaming TTS   │
                                └──────────────────┘
```

## Server v6 Capabilities
- `GET /health` — status + feature flags
- `GET /status` — same
- `GET /toggle` — toggle response on/off
- `GET /memory/{ip}` — inspect remembered facts for a device
- `GET /dashboard` — **live web dashboard** (conversation + emotion + waveform)
- `GET /events` — SSE stream for dashboard (conversation, emotion, mute, client-count events)
- `WS  /ws` — main pipeline: `user_input` → `audio_chunk` stream + voice emotion detection
