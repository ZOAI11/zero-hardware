"""
============================================================
 ZoarkBot Edge Device — Agentic Server Backend v3
 FastAPI + WebSocket + Whisper STT + NVIDIA LLM + edge-tts
============================================================

Pipeline (per utterance, ~2-3s total)
--------------------------------------
  1. Receive WAV bytes + ESP32 context from Pi Zero
  2. Transcribe with faster-whisper (tiny model, ~0.5s)
  3. Call NVIDIA API (llama-3.1-8b) with conversation history
  4. Detect emotion in reply → ui command (happy/sad/angry/speak_anim)
  5. Convert reply text → WAV via edge-tts (neural, async, free)
  6. Send WAV + ui command back to Pi

============================================================
"""

import asyncio
import base64
import io
import json
import logging
import os
import re
import tempfile
import wave
from typing import Any

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
)
log = logging.getLogger("zoark-server")

# ── FastAPI ──────────────────────────────────────────────────
app = FastAPI(title="ZoarkBot Edge Server v3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── NVIDIA / OpenAI-compatible client ────────────────────────
NVIDIA_API_KEY  = "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"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL    = "meta/llama-3.1-8b-instruct"

try:
    from openai import OpenAI
    _llm_client = OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)
    log.info("LLM: NVIDIA API (%s)", NVIDIA_MODEL)
except ImportError:
    _llm_client = None
    log.warning("openai package not found — LLM will use stub")

# ── Whisper STT ───────────────────────────────────────────────
_whisper_model = None
try:
    from faster_whisper import WhisperModel
    _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    log.info("STT: faster-whisper tiny loaded")
except Exception as e:
    log.warning("faster-whisper not available (%s) — STT disabled", e)

# ── edge-tts (neural TTS, async, free) ───────────────────────
_edge_tts_available = False
try:
    import edge_tts  # noqa: F401
    _edge_tts_available = True
    log.info("TTS: edge-tts (Microsoft neural)")
except ImportError:
    log.warning("edge-tts not available — falling back to gTTS")

# ── gTTS fallback ─────────────────────────────────────────────
_gtts_cls = None
if not _edge_tts_available:
    try:
        from gtts import gTTS as _imported_gtts
        _gtts_cls = _imported_gtts
        log.info("TTS: gTTS (fallback)")
    except ImportError:
        log.warning("gTTS not available either — TTS silent")

# ── edge-tts voice ────────────────────────────────────────────
EDGE_TTS_VOICE = "en-US-AriaNeural"   # warm, natural female voice

# ── System prompt ────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are ZoarkBot, a friendly AI assistant living inside a small robot body. "
    "You can sense motion and orientation via your built-in IMU. "
    "Keep every reply SHORT — 1 to 2 sentences maximum. "
    "Be warm, witty, and natural. Never use bullet points or lists when speaking."
)

# ── Emotion keyword maps ───────────────────────────────────────
_ANGRY_WORDS = re.compile(
    r"\b(angry|furious|mad|outraged|annoyed|frustrated|no way|stop|"
    r"ridiculous|nonsense|ugh|unbelievable)\b",
    re.IGNORECASE,
)
_HAPPY_WORDS = re.compile(
    r"\b(happy|great|awesome|wonderful|love|excited|yay|fantastic|"
    r"brilliant|joy|amazing|hooray|perfect|delighted)\b",
    re.IGNORECASE,
)
_SAD_WORDS = re.compile(
    r"\b(sad|sorry|unfortunately|miss|lonely|hurt|sigh|wish|"
    r"regret|afraid|scared|worried|upset|poor)\b",
    re.IGNORECASE,
)


def detect_emotion(text: str) -> str:
    """Return 'angry', 'happy', 'sad', or 'speak_anim' based on reply text."""
    if _ANGRY_WORDS.search(text):
        return "angry"
    if _HAPPY_WORDS.search(text):
        return "happy"
    if _SAD_WORDS.search(text):
        return "sad"
    return "speak_anim"


# ─────────────────────────────────────────────────────────────
#  STT — Whisper transcription
# ─────────────────────────────────────────────────────────────

def transcribe_audio(wav_bytes: bytes) -> str:
    """Convert WAV bytes → text using faster-whisper."""
    if _whisper_model is None:
        return ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp_path = f.name
        segments, info = _whisper_model.transcribe(tmp_path, language="en", beam_size=1)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        os.unlink(tmp_path)
        log.info("STT: %r (%.2fs audio, lang=%s)", text[:80], info.duration, info.language)
        return text
    except Exception as e:
        log.error("STT error: %s", e)
        return ""


# ─────────────────────────────────────────────────────────────
#  LLM — NVIDIA API
# ─────────────────────────────────────────────────────────────

def call_llm(history: list[dict], user_text: str, context: dict) -> str:
    """Call NVIDIA LLM and return the reply text."""
    if _llm_client is None:
        return "I'm thinking... my language model isn't connected yet."

    motion = context.get("motion", "stable")
    orient = context.get("orientation", "up")
    ctx_note = ""
    if motion == "shaking":
        ctx_note = " [Note: I can feel shaking right now!]"
    elif orient == "down":
        ctx_note = " [Note: I'm upside down!]"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": user_text + ctx_note}
    ]

    try:
        resp = _llm_client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=messages,
            max_tokens=80,
            temperature=0.7,
        )
        content = resp.choices[0].message.content
        if not content:
            log.warning("LLM returned empty content, finish_reason=%s", resp.choices[0].finish_reason)
            return "I didn't quite catch that. Could you say that again?"
        reply = content.strip()
        log.info("LLM reply: %r", reply[:80])
        return reply
    except Exception as e:
        log.error("LLM error: %s", e)
        return "Sorry, I had trouble thinking of a response."


# ─────────────────────────────────────────────────────────────
#  TTS — edge-tts (neural) → WAV, fallback gTTS
# ─────────────────────────────────────────────────────────────

async def generate_tts_async(text: str) -> bytes:
    """Convert text → WAV using edge-tts (neural) or gTTS fallback."""
    if not text.strip():
        return _silent_wav()

    # ── edge-tts path ─────────────────────────────────────────
    if _edge_tts_available:
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
            mp3_buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_buf.write(chunk["data"])
            mp3_buf.seek(0)
            mp3_bytes = mp3_buf.read()
            if mp3_bytes:
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
                    wav_buf = io.BytesIO()
                    audio.export(wav_buf, format="wav")
                    log.info("TTS: edge-tts generated %d bytes", len(wav_buf.getvalue()))
                    return wav_buf.getvalue()
                except Exception:
                    log.info("TTS: edge-tts mp3 (%d bytes, pydub unavail)", len(mp3_bytes))
                    return mp3_bytes
        except Exception as e:
            log.error("edge-tts failed: %s — falling back", e)

    # ── gTTS fallback ─────────────────────────────────────────
    if _gtts_cls is not None:
        try:
            tts = _gtts_cls(text=text, lang="en", slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            mp3_bytes = buf.read()
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
                wav_buf = io.BytesIO()
                audio.export(wav_buf, format="wav")
                return wav_buf.getvalue()
            except Exception:
                return mp3_bytes
        except Exception as e:
            log.error("gTTS failed: %s", e)

    return _silent_wav()


def _silent_wav(duration_sec: float = 0.3, sample_rate: int = 16_000) -> bytes:
    n = int(duration_sec * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate)
        wf.writeframes(np.zeros(n, dtype=np.int16).tobytes())
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
#  WEBSOCKET — per-connection conversation memory
# ─────────────────────────────────────────────────────────────

conversation_history: dict[int, list[dict]] = {}
MAX_HISTORY = 10


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    client_host = websocket.client.host if websocket.client else "unknown"
    await websocket.accept()
    conn_id = id(websocket)
    conversation_history[conn_id] = []
    log.info("WebSocket connected from %s", client_host)

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") != "user_input":
                continue

            audio_b64 = msg.get("audio_b64", "")
            context   = msg.get("context", {})
            if not audio_b64:
                continue

            audio_bytes = base64.b64decode(audio_b64)

            # ── STT ──────────────────────────────────────────
            loop = asyncio.get_running_loop()
            user_text = await loop.run_in_executor(None, transcribe_audio, audio_bytes)

            if not user_text:
                log.info("STT returned empty — skipping reply")
                continue

            log.info("User said: %r", user_text)

            # ── LLM ──────────────────────────────────────────
            history = conversation_history[conn_id]
            reply_text = await loop.run_in_executor(None, call_llm, history, user_text, context)

            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply_text})
            if len(history) > MAX_HISTORY * 2:
                conversation_history[conn_id] = history[-(MAX_HISTORY * 2):]

            # ── Emotion detection ─────────────────────────────
            ui_cmd = detect_emotion(reply_text)
            log.info("Emotion: %s", ui_cmd)

            # ── TTS ───────────────────────────────────────────
            wav_bytes = await generate_tts_async(reply_text)

            # ── Reply ─────────────────────────────────────────
            await websocket.send_json({
                "type":      "agent_reply",
                "audio_b64": base64.b64encode(wav_bytes).decode("ascii"),
                "ui":        ui_cmd,
                "text":      reply_text,
                "user_text": user_text,
            })
            log.info("Replied: %r (%d byte WAV, ui=%s)", reply_text[:60], len(wav_bytes), ui_cmd)

    except Exception as e:
        log.exception("WebSocket error from %s: %s", client_host, e)
    finally:
        conversation_history.pop(conn_id, None)
        log.info("WebSocket session ended for %s", client_host)


@app.get("/health")
async def health() -> dict:
    tts_engine = "edge-tts" if _edge_tts_available else ("gtts" if _gtts_cls else "silent")
    return {
        "status":    "ok",
        "stt":       "faster-whisper-tiny" if _whisper_model else "disabled",
        "llm":       NVIDIA_MODEL if _llm_client else "stub",
        "tts":       tts_engine,
        "service":   "zoark-edge-server",
    }
