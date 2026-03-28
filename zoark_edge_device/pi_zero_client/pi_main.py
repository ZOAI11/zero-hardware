"""
============================================================
 ZoarkBot Edge Device — Raspberry Pi Zero W Client
 Bridge: ESP32 ↔ Audio ↔ WebSocket ↔ Server
============================================================

Hardware
--------
  UART to ESP32  : /dev/serial0  (115200 baud)
  I2S Mic        : INMP441 on GPIO 18/19/20 (BCM)
  I2S Speaker    : MAX98357A on GPIO 18/19/21 (BCM)
  Note: I2S mic and speaker share BCLK/LRCLK; use ALSA device 'hw:1,0'

Architecture
------------
  Thread 1 : uart_reader   — reads ESP32 JSON → current_context
  Thread 2 : ws_client     — WebSocket loop (send/receive)
  Thread 3 : audio_capture — VAD + record → triggers send
  Main      : glue / signal handling

WebSocket protocol
------------------
  Send   : {"type":"user_input","audio_b64":"<b64>","context":{...}}
  Receive: {"type":"agent_reply","audio_b64":"<b64>","ui":"speak_anim"}

============================================================
"""

import asyncio
import base64
import io
import json
import logging
import queue
import signal
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import serial           # type: ignore[import-untyped]  # pyserial
try:
    import sounddevice as sd  # type: ignore[import]        # Pi-only
    AUDIO_AVAILABLE = True
except Exception as _sd_err:
    sd = None  # type: ignore[assignment]
    AUDIO_AVAILABLE = False
    import logging as _log_tmp; _log_tmp.getLogger("zoark-pi").warning(
        "sounddevice unavailable (%s) — audio capture disabled", _sd_err
    )
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

# ─────────────────────────────────────────────────────────────
#  CONFIG — edit these before deploying
# ─────────────────────────────────────────────────────────────

SERVER_WS_URL     = "ws://157.173.210.131:8765/ws"   # ZoarkBot VPS
# WSS_URL (requires DNS record in Cloudflare for robot.zoarkai.org):
# SERVER_WS_URL = "wss://robot.zoarkai.org/ws"
UART_PORT         = "/dev/serial0"
UART_BAUD         = 115_200

# Audio settings
SAMPLE_RATE       = 16_000    # Hz — Whisper-compatible
CHANNELS          = 2         # INMP441 is stereo I2S (signal on Ch1/left)
CHUNK_FRAMES      = 512       # frames per sounddevice callback
AUDIO_DEVICE      = None      # use default ALSA (plug → hw:0,0 via asound.conf)

# VAD settings
MIC_GAIN          = 10.0      # software gain (10x = +20 dB boost; compensates for quiet mic)
VAD_THRESHOLD_DB  = -30.0     # dB after gain — louder than this = voice
VAD_HOLD_SEC      = 1.2       # seconds of silence before ending utterance
VAD_MIN_SEC       = 0.3       # minimum utterance length to bother sending
VAD_MAX_SEC       = 12.0      # hard cap — auto-flush at 12 seconds

# #15 Local LLM fallback (Pi Zero 2W offline mode)
# SmolLM2-135M-Q4: ~110MB file, ~150MB runtime RAM — fits Pi Zero 2W 512MB
# Install model:
#   mkdir -p ~/models
#   wget -O ~/models/smollm2-135m-q4.gguf \
#     "https://huggingface.co/bartowski/SmolLM2-135M-Instruct-GGUF/resolve/main/SmolLM2-135M-Instruct-Q4_K_M.gguf"
# Install llama-cpp-python (ARM, no GPU):
#   pip install llama-cpp-python
LOCAL_LLM_ENABLED   = True
LOCAL_LLM_MODEL     = str(Path.home() / "models" / "smollm2-135m-q4.gguf")
LOCAL_LLM_CTX       = 512          # context window (keep small for speed)
LOCAL_LLM_THREADS   = 2            # use only 2 threads to avoid OOM on 512MB
LOCAL_LLM_MAX_TOK   = 60           # max tokens per reply (shorter = faster)
# How many consecutive WS failures before switching to offline mode:
OFFLINE_FAIL_THRESH = 3

# Wake word settings
# WAKE_WORD_ENABLED = True requires a model trained on the exact phrase.
# No pre-built "hey zero" model exists in openwakeword 0.4.0.
# Set False → always-on VAD (just speak, bot always listens).
# Set True + WAKE_WORD_MODEL = alexa path → say "alexa" to wake.
WAKE_WORD_ENABLED = False
WAKE_WORD_MODEL   = "/home/zero/zoark-env/lib/python3.13/site-packages/openwakeword/resources/models/alexa_v0.1.onnx"
WAKE_WORD_THRESHOLD = 0.35    # confidence score 0-1 to trigger wake
WAKE_CHUNK_FRAMES = 1280      # 80ms at 16kHz — required by openWakeWord

# WebSocket reconnect
WS_RECONNECT_SEC  = 3.0

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(levelname)s  %(message)s",
)
log = logging.getLogger("zoark-pi")

# ─────────────────────────────────────────────────────────────
#  SHARED STATE
# ─────────────────────────────────────────────────────────────

current_context: dict = {"motion": "stable", "orientation": "up"}
context_lock = threading.Lock()

# audio_send_q carries raw PCM bytes (mono 16-bit) ready to transmit
audio_send_q: queue.Queue = queue.Queue(maxsize=4)

# ws_send_q carries arbitrary JSON dicts to send over WebSocket
ws_send_q: asyncio.Queue  # initialised in main

# UART write queue (thread-safe, non-async)
uart_write_q: queue.Queue = queue.Queue(maxsize=8)

# Sequential audio playback queue — all chunks go here, one thread drains it
# This prevents multiple aplay processes racing and playback_active getting stuck
audio_play_q: queue.Queue = queue.Queue(maxsize=32)

# Suppresses VAD while speaker is playing (prevents feedback loop)
playback_active = threading.Event()

# Watchdog: timestamp of when playback_active was last set
_playback_started_at: float = 0.0
_PLAYBACK_WATCHDOG_SEC = 45.0  # force-clear if stuck longer than this

# Shutdown event
shutdown_event = threading.Event()

# ── #15 Local LLM (llama-cpp-python) ─────────────────────────
# Loaded lazily on first offline fallback to avoid startup delay.
_local_llm = None
_local_llm_lock = threading.Lock()
_ws_fail_count = 0   # consecutive WS connection failures
_offline_mode  = False

_LOCAL_SYSTEM = (
    "You are Zero, a small friendly robot. Answer warmly and very briefly "
    "(1-2 sentences max). No markdown, no lists, just natural speech."
)

# Simple canned responses used when llama.cpp is unavailable or model missing
_OFFLINE_CANNED = [
    "I'm offline right now, but I'm still here with you!",
    "No internet at the moment, but I heard you! Try again in a bit.",
    "My connection is down, but don't worry — I'll be back soon!",
    "I'm in offline mode right now. Give me a moment to reconnect!",
]
_canned_idx = 0


def _try_load_local_llm() -> bool:
    """Try to load llama-cpp-python with the SmolLM2 model. Returns True on success."""
    global _local_llm
    if _local_llm is not None:
        return True
    if not LOCAL_LLM_ENABLED:
        return False
    model_path = LOCAL_LLM_MODEL
    if not Path(model_path).exists():
        log.warning("Local LLM: model not found at %s", model_path)
        return False
    try:
        from llama_cpp import Llama  # type: ignore[import]
        with _local_llm_lock:
            if _local_llm is None:
                log.info("Local LLM: loading %s …", model_path)
                _local_llm = Llama(
                    model_path=model_path,
                    n_ctx=LOCAL_LLM_CTX,
                    n_threads=LOCAL_LLM_THREADS,
                    use_mmap=True,   # page weights from disk, saves peak RAM
                    verbose=False,
                )
                log.info("Local LLM: SmolLM2-135M loaded OK")
        return True
    except ImportError:
        log.warning("Local LLM: llama-cpp-python not installed (pip install llama-cpp-python)")
        return False
    except Exception as e:
        log.error("Local LLM: load error: %s", e)
        return False


def local_llm_reply(user_text: str) -> str:
    """Generate a response using the on-device SmolLM2 model."""
    global _canned_idx
    if not _try_load_local_llm() or _local_llm is None:
        # Fallback to canned responses
        reply = _OFFLINE_CANNED[_canned_idx % len(_OFFLINE_CANNED)]
        _canned_idx += 1
        return reply
    try:
        prompt = (
            f"<|system|>\n{_LOCAL_SYSTEM}\n"
            f"<|user|>\n{user_text}\n"
            "<|assistant|>\n"
        )
        with _local_llm_lock:
            out = _local_llm(
                prompt,
                max_tokens=LOCAL_LLM_MAX_TOK,
                temperature=0.7,
                stop=["<|user|>", "<|system|>", "\n\n"],
            )
        text = out["choices"][0]["text"].strip()
        log.info("Local LLM reply: %r", text[:80])
        return text or _OFFLINE_CANNED[0]
    except Exception as e:
        log.error("Local LLM inference error: %s", e)
        return _OFFLINE_CANNED[0]

# ─────────────────────────────────────────────────────────────
#  THREAD 1 — UART READER
# ─────────────────────────────────────────────────────────────

def uart_reader_thread() -> None:
    """
    Continuously reads newline-terminated JSON from ESP32 via UART.
    Updates global current_context.
    Also drains uart_write_q to send commands back to ESP32.
    """
    log.info("UART reader starting on %s @ %d", UART_PORT, UART_BAUD)

    ser: Optional[serial.Serial] = None

    while not shutdown_event.is_set():
        # (Re-)open serial port
        try:
            ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)
            log.info("UART port opened")
        except serial.SerialException as e:
            log.error("UART open failed: %s — retry in 2s", e)
            time.sleep(2)
            continue

        rx_buf = ""
        try:
            while not shutdown_event.is_set():
                # Write any pending commands to ESP32
                while not uart_write_q.empty():
                    try:
                        cmd = uart_write_q.get_nowait()
                        line = json.dumps(cmd) + "\n"
                        ser.write(line.encode())
                        log.debug("UART TX: %s", line.strip())
                    except queue.Empty:
                        break

                # Read incoming bytes
                if ser.in_waiting:
                    raw = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    rx_buf += raw
                    while "\n" in rx_buf:
                        line, rx_buf = rx_buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            _handle_uart_line(line)
                else:
                    time.sleep(0.01)

        except serial.SerialException as e:
            log.warning("UART read error: %s — reconnecting", e)
        finally:
            try:
                if ser and ser.is_open:
                    ser.close()
            except Exception:
                pass

    log.info("UART reader stopped")


def _handle_uart_line(line: str) -> None:
    """Parse a JSON line from the ESP32 and update current_context."""
    global current_context
    try:
        data = json.loads(line)
        with context_lock:
            current_context.update(data)
        log.debug("ESP32 state: %s", data)
    except json.JSONDecodeError:
        log.debug("UART non-JSON line: %r", line)


# ─────────────────────────────────────────────────────────────
#  THREAD 2 — WEBSOCKET CLIENT (async event loop in thread)
# ─────────────────────────────────────────────────────────────

def ws_client_thread(loop: asyncio.AbstractEventLoop) -> None:
    """
    Runs an asyncio event loop in a dedicated thread.
    Handles WebSocket connect / send / receive / reconnect.
    """
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_ws_client_loop())


async def _ws_client_loop() -> None:
    """
    Connect to server WebSocket, relay messages both ways.
    Auto-reconnects on any error.
    After OFFLINE_FAIL_THRESH consecutive failures, switches to offline mode
    (local LLM on Pi). Switches back as soon as the server is reachable.
    """
    global _ws_fail_count, _offline_mode
    while not shutdown_event.is_set():
        try:
            log.info("WebSocket connecting to %s", SERVER_WS_URL)
            async with websockets.connect(
                SERVER_WS_URL,
                ping_interval=20,
                ping_timeout=10,
            ) as ws:
                if _offline_mode:
                    _offline_mode = False
                    _ws_fail_count = 0
                    log.info("Back online — disabling offline mode")
                    uart_write_q.put({"command": "happy"})
                log.info("WebSocket connected")
                _ws_fail_count = 0
                await asyncio.gather(
                    _ws_sender(ws),
                    _ws_receiver(ws),
                )
        except (ConnectionClosedError, ConnectionClosedOK):
            log.warning("WebSocket closed — reconnecting in %.1fs", WS_RECONNECT_SEC)
            _ws_fail_count += 1
        except OSError as e:
            log.error("WebSocket connection error: %s — retry in %.1fs", e, WS_RECONNECT_SEC)
            _ws_fail_count += 1
        except asyncio.CancelledError:
            break

        # Switch to offline mode after repeated failures
        if _ws_fail_count >= OFFLINE_FAIL_THRESH and not _offline_mode:
            _offline_mode = True
            log.warning("Offline mode ENABLED after %d failures — using local LLM", _ws_fail_count)
            uart_write_q.put({"command": "sad"})
            # Pre-load local model in background
            threading.Thread(
                target=_try_load_local_llm, name="LocalLLMLoad", daemon=True
            ).start()

        if not shutdown_event.is_set():
            await asyncio.sleep(WS_RECONNECT_SEC)


async def _ws_sender(ws) -> None:
    """Drains ws_send_q and sends JSON messages over the WebSocket."""
    while True:
        try:
            payload = await asyncio.wait_for(ws_send_q.get(), timeout=1.0)
            await ws.send(json.dumps(payload))
            log.debug("WS TX: type=%s", payload.get("type"))
        except asyncio.TimeoutError:
            continue   # keep looping; check ws_send_q again


async def _ws_receiver(ws) -> None:
    """Receives JSON messages from server and dispatches them."""
    async for raw_msg in ws:
        try:
            msg = json.loads(raw_msg)
        except json.JSONDecodeError:
            log.warning("Non-JSON from server: %r", raw_msg[:80])
            continue

        msg_type = msg.get("type")
        log.info("WS RX: type=%s", msg_type)

        if msg_type == "agent_reply":
            _handle_agent_reply(msg)
        elif msg_type == "audio_chunk":
            _handle_audio_chunk(msg)
        else:
            log.debug("Unhandled server message type: %s", msg_type)


def _handle_agent_reply(msg: dict) -> None:
    """
    Process an agent_reply message.
    Enqueues audio + UART command onto audio_play_q (sequential playback thread).
    """
    ui_cmd    = msg.get("ui")
    audio_b64 = msg.get("audio_b64", "")
    text      = msg.get("text", "")

    uart_cmd: Optional[dict] = None
    if ui_cmd:
        uart_cmd = {"command": ui_cmd}
        if text:
            uart_cmd["text"] = text[:60]

    if audio_b64:
        try:
            audio_bytes = base64.b64decode(audio_b64)
            audio_play_q.put({"audio": audio_bytes, "uart": uart_cmd}, block=False)
        except queue.Full:
            log.warning("audio_play_q full — dropping chunk")
        except Exception as e:
            log.error("Audio decode failed: %s", e)
    elif uart_cmd:
        audio_play_q.put({"audio": None, "uart": uart_cmd}, block=False)


def _handle_audio_chunk(msg: dict) -> None:
    """
    Process a streaming audio_chunk message (sentence-by-sentence TTS).
    Enqueues onto audio_play_q for sequential playback.
    """
    audio_b64 = msg.get("audio_b64", "")
    text      = msg.get("text", "")
    is_last   = msg.get("is_last", False)

    uart_cmd: Optional[dict] = {"command": "speak_anim"}
    if text:
        uart_cmd["text"] = text[:60]
        log.info("Chunk UART text: %r", text[:40])

    if audio_b64:
        try:
            audio_bytes = base64.b64decode(audio_b64)
            audio_play_q.put({"audio": audio_bytes, "uart": uart_cmd, "is_last": is_last}, block=False)
        except queue.Full:
            log.warning("audio_play_q full — dropping chunk")
        except Exception as e:
            log.error("Chunk audio decode failed: %s", e)
    elif is_last:
        # Final marker with no audio — still clear the playback flag via queue
        audio_play_q.put({"audio": None, "uart": None, "is_last": True}, block=False)


def audio_playback_thread() -> None:
    """
    Single dedicated thread that drains audio_play_q sequentially.
    Guarantees only one aplay process runs at a time and that
    playback_active is always cleared even if aplay crashes or hangs.
    Also runs a watchdog to force-clear playback_active if stuck.
    """
    global _playback_started_at
    log.info("Audio playback thread started")
    _aplay_proc: Optional[subprocess.Popen] = None

    while not shutdown_event.is_set():
        # ── Watchdog: force-clear if stuck too long ───────────
        if playback_active.is_set():
            stuck_secs = time.monotonic() - _playback_started_at
            if stuck_secs > _PLAYBACK_WATCHDOG_SEC:
                log.warning("Watchdog: playback_active stuck %.0fs — force clearing", stuck_secs)
                if _aplay_proc and _aplay_proc.poll() is None:
                    try:
                        _aplay_proc.kill()
                    except Exception:
                        pass
                playback_active.clear()

        try:
            item = audio_play_q.get(timeout=0.5)
        except queue.Empty:
            continue

        audio_bytes: Optional[bytes] = item.get("audio")
        uart_cmd: Optional[dict]     = item.get("uart")

        # Send UART command to ESP32
        if uart_cmd:
            try:
                uart_write_q.put_nowait(uart_cmd)
            except queue.Full:
                pass

        if not audio_bytes:
            # is_last marker or uart-only item — clear flag if all chunks done
            if audio_play_q.empty():
                time.sleep(0.3)
                if audio_play_q.empty():
                    playback_active.clear()
                    log.debug("Playback flag cleared (empty queue)")
            continue

        # ── Play audio via aplay ──────────────────────────────
        playback_active.set()
        _playback_started_at = time.monotonic()
        try:
            _aplay_proc = subprocess.Popen(
                ["aplay", "-q"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            try:
                _, stderr = _aplay_proc.communicate(input=audio_bytes, timeout=30)
                if _aplay_proc.returncode != 0:
                    err = stderr.decode(errors="replace")[:200]
                    log.error("aplay error (code %d): %s", _aplay_proc.returncode, err)
                else:
                    log.info("Chunk played (%d bytes)", len(audio_bytes))
            except subprocess.TimeoutExpired:
                log.error("aplay timed out — killing")
                _aplay_proc.kill()
                _aplay_proc.communicate()
        except FileNotFoundError:
            log.error("aplay not found — is alsa-utils installed?")
        except Exception as e:
            log.error("Playback error: %s", e)
        finally:
            _aplay_proc = None
            # Only clear flag if nothing else is queued
            if audio_play_q.empty():
                time.sleep(0.4)  # brief tail silence so mic doesn't catch speaker
                if audio_play_q.empty():
                    playback_active.clear()
                    log.debug("Playback flag cleared — mic re-enabled")

    log.info("Audio playback thread stopped")


# ─────────────────────────────────────────────────────────────
#  THREAD 3 — AUDIO CAPTURE + VAD
# ─────────────────────────────────────────────────────────────

def audio_capture_thread(loop: asyncio.AbstractEventLoop) -> None:
    """
    Audio capture with:
      1. openWakeWord — waits for "hey zoark" (hey_jarvis model) before recording
         Inference runs in a separate thread so the audio callback is never blocked.
      2. Adaptive VAD calibration — measures ambient floor at startup
      3. Energy VAD — records utterance, flushes to WebSocket
    """
    if not AUDIO_AVAILABLE or sd is None:
        log.warning("Audio capture disabled — sounddevice not available. Check PortAudio / mic hardware.")
        while not shutdown_event.is_set():
            time.sleep(5)
        return

    log.info("Audio capture starting (SR=%d, chunk=%d)", SAMPLE_RATE, CHUNK_FRAMES)

    # ── Load wake word model ──────────────────────────────────
    oww_model = None
    ww_label  = None
    if WAKE_WORD_ENABLED:
        try:
            from openwakeword.model import Model as OWWModel
            oww_model = OWWModel(wakeword_model_paths=[WAKE_WORD_MODEL])
            ww_label = list(oww_model.models.keys())[0]
            log.info("Wake word: model loaded, label=%r (threshold=%.2f)", ww_label, WAKE_WORD_THRESHOLD)
        except Exception as e:
            log.warning("Wake word model failed to load (%s) — disabled, always listening", e)
            oww_model = None

    # ── Adaptive VAD calibration ──────────────────────────────
    vad_threshold_db = VAD_THRESHOLD_DB
    try:
        cal_seconds = 3.0
        cal_frames  = int(cal_seconds * SAMPLE_RATE)
        log.info("VAD calibration: measuring ambient noise for %.0fs...", cal_seconds)
        cal_data = sd.rec(
            cal_frames,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            device=AUDIO_DEVICE,
            blocking=True,
        )
        cal_gained = np.clip(cal_data * MIC_GAIN, -1.0, 1.0)
        if cal_gained.ndim == 2:
            cal_gained = cal_gained[:, 0]
        cal_chunks: list[float] = []
        for i in range(0, len(cal_gained) - CHUNK_FRAMES, CHUNK_FRAMES):
            chunk = cal_gained[i:i + CHUNK_FRAMES]
            rms = float(np.sqrt(np.mean(chunk ** 2)) + 1e-9)
            cal_chunks.append(20 * np.log10(rms))
        if cal_chunks:
            floor_db = float(np.percentile(cal_chunks, 75))
            vad_threshold_db = floor_db + 20.0
            log.info("VAD calibration done: floor=%.1f dB → threshold=%.1f dB",
                     floor_db, vad_threshold_db)
        else:
            log.warning("VAD calibration got no chunks — using default %.1f dB", vad_threshold_db)
    except Exception as e:
        log.warning("VAD calibration failed (%s) — using default %.1f dB", e, vad_threshold_db)

    # ── Wake word inference thread ────────────────────────────
    # The audio callback puts int16 chunks on ww_infer_q.
    # A separate thread drains the queue and runs ONNX inference,
    # so the audio callback is never blocked by slow ML inference.
    ww_infer_q: queue.Queue = queue.Queue(maxsize=64)
    ww_active_flag = threading.Event()   # set = wake word fired, record now
    if oww_model is None:
        ww_active_flag.set()             # no model → always active

    def _ww_inference_worker():
        """Drain ww_infer_q and run openWakeWord inference off the audio thread."""
        ww_accum: list[np.ndarray] = []
        log_counter = 0
        while not shutdown_event.is_set():
            try:
                chunk = ww_infer_q.get(timeout=0.5)
            except queue.Empty:
                continue
            if chunk is None:  # poison pill
                break
            if ww_active_flag.is_set():
                # Already triggered — drain queue but don't infer
                ww_accum.clear()
                continue
            ww_accum.append(chunk)
            total = sum(len(c) for c in ww_accum)
            if total >= WAKE_CHUNK_FRAMES:
                window = np.concatenate(ww_accum)[:WAKE_CHUNK_FRAMES]
                ww_accum = [np.concatenate(ww_accum)[WAKE_CHUNK_FRAMES:]] if total > WAKE_CHUNK_FRAMES else []
                try:
                    pred  = oww_model.predict(window)
                    score = float(pred.get(ww_label, 0.0))
                    log_counter += 1
                    if log_counter % 20 == 0:  # log score every ~2s
                        log.debug("WW score: %.3f", score)
                    if score >= WAKE_WORD_THRESHOLD:
                        ww_active_flag.set()
                        oww_model.reset()
                        ww_accum.clear()
                        log.info("Wake word detected! (score=%.2f) — listening...", score)
                        uart_write_q.put({"command": "blink"})
                except Exception as exc:
                    log.debug("WW infer error: %s", exc)

    if oww_model is not None:
        ww_thread = threading.Thread(target=_ww_inference_worker,
                                     name="WakeWordInfer", daemon=True)
        ww_thread.start()
        log.info("Waiting for wake word ('hey zoark' / hey_jarvis)...")
    else:
        log.info("Wake word disabled — always listening")

    # ── VAD state ─────────────────────────────────────────────
    pcm_buffer:  list[np.ndarray] = []
    recording    = False
    silence_secs = 0.0
    total_secs   = 0.0
    chunk_sec    = CHUNK_FRAMES / SAMPLE_RATE

    def audio_callback(indata: np.ndarray, _frames: int, _time_info, status):
        """Called by sounddevice on each audio chunk — kept as lightweight as possible."""
        nonlocal recording, silence_secs, total_secs

        if status:
            log.debug("Audio status: %s", status)

        # Don't process while speaker is playing
        if playback_active.is_set():
            if recording:
                recording = False
                pcm_buffer.clear()
            return

        # Apply gain, extract left channel mono
        gained = np.clip(indata * MIC_GAIN, -1.0, 1.0)
        mono   = gained[:, 0] if gained.ndim == 2 else gained

        # ── Feed wake word inference queue (non-blocking) ─────
        if oww_model is not None and not ww_active_flag.is_set():
            int16_chunk = (mono * 32767).astype(np.int16)
            try:
                ww_infer_q.put_nowait(int16_chunk)
            except queue.Full:
                pass  # inference can't keep up — drop oldest
            return  # don't do VAD yet

        # ── VAD + recording ───────────────────────────────────
        rms    = float(np.sqrt(np.mean(mono ** 2)) + 1e-9)
        rms_db = 20 * np.log10(rms)

        if not recording:
            if rms_db > vad_threshold_db:
                recording    = True
                silence_secs = 0.0
                total_secs   = 0.0
                pcm_buffer.clear()
                log.info("VAD: utterance started (%.1f dB, threshold=%.1f dB)",
                         rms_db, vad_threshold_db)
                pcm_buffer.append(mono.copy())
        else:
            pcm_buffer.append(mono.copy())
            total_secs += chunk_sec

            if rms_db < vad_threshold_db:
                silence_secs += chunk_sec
            else:
                silence_secs = 0.0

            if silence_secs >= VAD_HOLD_SEC or total_secs >= VAD_MAX_SEC:
                if total_secs >= VAD_MIN_SEC:
                    _flush_audio(pcm_buffer.copy(), loop)
                else:
                    log.debug("VAD: utterance too short (%.2fs) — discarded", total_secs)
                recording    = False
                pcm_buffer.clear()
                silence_secs = 0.0
                total_secs   = 0.0
                # Return to wake word listening mode
                if oww_model is not None:
                    ww_active_flag.clear()
                    log.info("Utterance done — waiting for wake word again...")

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=CHUNK_FRAMES,
            device=AUDIO_DEVICE,
            callback=audio_callback,
        ):
            log.info("Audio stream open — listening...")
            while not shutdown_event.is_set():
                time.sleep(0.1)
    except Exception as e:
        log.error("Audio capture fatal error: %s", e)
    finally:
        if oww_model is not None:
            try:
                ww_infer_q.put_nowait(None)  # stop inference thread
            except Exception:
                pass


def _flush_audio(pcm_chunks: list[np.ndarray], loop: asyncio.AbstractEventLoop) -> None:
    """
    Convert captured PCM float32 → 16-bit WAV → base64.
    If online: package and enqueue for WebSocket send.
    If offline (#15): run local LLM inference and play TTS via espeak/piper.
    """
    log.info("VAD: flushing utterance (%d chunks)", len(pcm_chunks))
    try:
        # Stack and convert float32 → int16
        pcm = np.concatenate(pcm_chunks, axis=0)
        # INMP441 outputs on Ch1 (left) only — extract mono from stereo capture
        if pcm.ndim == 2 and pcm.shape[1] == 2:
            pcm = pcm[:, 0]
        pcm_int16 = (pcm * 32767).astype(np.int16)

        # Encode as WAV in memory (always mono to server)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm_int16.tobytes())
        wav_bytes = buf.getvalue()

        # ── #15 Offline mode: use local STT + LLM + TTS ──────
        if _offline_mode:
            threading.Thread(
                target=_offline_respond,
                args=(wav_bytes,),
                name="OfflineRespond",
                daemon=True,
            ).start()
            return

        audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
        with context_lock:
            ctx_snapshot = dict(current_context)

        payload = {
            "type":       "user_input",
            "audio_b64":  audio_b64,
            "context":    ctx_snapshot,
        }

        asyncio.run_coroutine_threadsafe(ws_send_q.put(payload), loop)
        log.info("Audio payload enqueued (%d bytes WAV)", len(wav_bytes))

    except Exception as e:
        log.error("Audio flush error: %s", e)


def _offline_respond(wav_bytes: bytes) -> None:
    """
    #15 Offline fallback pipeline:
      WAV → Whisper tiny (local) → SmolLM2 → espeak TTS → speaker
    Runs entirely on the Pi with no network.
    """
    import io as _io, wave as _wave, tempfile as _tmp, os as _os

    log.info("Offline pipeline: transcribing…")
    # ── STT: try faster-whisper if available ─────────────────
    user_text = ""
    try:
        from faster_whisper import WhisperModel
        with _tmp.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp = f.name
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(tmp, language="en", beam_size=1)
        user_text = " ".join(s.text.strip() for s in segments).strip()
        _os.unlink(tmp)
        log.info("Offline STT: %r", user_text[:60])
    except Exception as e:
        log.warning("Offline STT failed: %s — using canned response", e)

    if not user_text:
        user_text = "hey"

    # ── LLM: SmolLM2 local ───────────────────────────────────
    reply = local_llm_reply(user_text)
    log.info("Offline reply: %r", reply)

    uart_write_q.put({"command": "speak_anim", "text": reply[:60]})

    # ── TTS: espeak → WAV → audio_play_q ─────────────────────
    try:
        import tempfile as _tmp2, os as _os2
        with _tmp2.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        result = subprocess.run(
            ["espeak", "-v", "en", "-s", "150", "-p", "60", reply,
             "--stdout"],
            capture_output=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            audio_play_q.put({"audio": result.stdout, "uart": None}, block=False)
        else:
            log.warning("espeak failed or produced no audio")
        try:
            _os2.unlink(wav_path)
        except Exception:
            pass
    except FileNotFoundError:
        log.warning("espeak not found — no audio for offline reply")
    except Exception as e:
        log.error("Offline TTS error: %s", e)


# ─────────────────────────────────────────────────────────────
#  MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────

def main() -> None:
    global ws_send_q

    log.info("=== ZoarkBot Pi Zero client starting ===")
    log.info("Server: %s", SERVER_WS_URL)

    # Create a dedicated asyncio loop for WebSocket
    ws_loop = asyncio.new_event_loop()
    ws_send_q = asyncio.Queue(loop=ws_loop) if sys.version_info < (3, 10) else asyncio.Queue()

    # Wire the queue to the loop for Python 3.10+
    # We'll pass `ws_loop` to thread functions that need to enqueue
    ws_send_q_loop = ws_loop

    # Graceful shutdown on SIGINT / SIGTERM
    def _shutdown(sig, _frame):
        log.info("Shutdown signal received (%s)", sig)
        shutdown_event.set()

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Start threads
    threads = [
        threading.Thread(target=uart_reader_thread,    name="UartReader",    daemon=True),
        threading.Thread(target=ws_client_thread,      args=(ws_loop,),      name="WsClient",     daemon=True),
        threading.Thread(target=audio_capture_thread,  args=(ws_send_q_loop,), name="AudioCapture", daemon=True),
        threading.Thread(target=audio_playback_thread, name="AudioPlayback", daemon=True),
    ]

    for t in threads:
        t.start()

    log.info("All threads started — running until shutdown signal")

    # Block main thread
    try:
        while not shutdown_event.is_set():
            time.sleep(0.5)
    finally:
        shutdown_event.set()
        log.info("Shutting down...")

        # Stop asyncio loop
        ws_loop.call_soon_threadsafe(ws_loop.stop)

        for t in threads:
            t.join(timeout=3)

        log.info("ZoarkBot Pi Zero client stopped cleanly")


if __name__ == "__main__":
    main()
