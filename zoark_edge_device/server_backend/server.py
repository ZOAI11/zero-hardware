"""
============================================================
 Zero Edge Device — Server Backend v5
 FastAPI + WebSocket + Whisper STT + NVIDIA LLM + edge-tts
 Features:
   - Streaming TTS (sentence-by-sentence, ~half latency)
   - Persistent memory (facts + history per device)
   - Whisper medium (better accuracy)
   - DuckDuckGo web search for unknown questions
   - Voice toggle (say "stop" / "wake up")
   - GET /toggle, GET /status
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
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
)
log = logging.getLogger("zero-server")

# ── FastAPI ──────────────────────────────────────────────────
app = FastAPI(title="Zero Edge Server v5")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ── Global toggle ─────────────────────────────────────────────
response_enabled: bool = True

# ── NVIDIA async client ───────────────────────────────────────
NVIDIA_API_KEY  = "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"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL    = "meta/llama-3.1-8b-instruct"

_llm = AsyncOpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)
log.info("LLM: NVIDIA API (%s)", NVIDIA_MODEL)

# ── Whisper STT (medium for better accuracy) ──────────────────
_whisper_model = None
try:
    from faster_whisper import WhisperModel
    _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    log.info("STT: faster-whisper tiny loaded")
except Exception as e:
    log.warning("faster-whisper unavailable (%s)", e)

# ── edge-tts ─────────────────────────────────────────────────
_edge_tts_ok = False
try:
    import edge_tts  # noqa: F401
    _edge_tts_ok = True
    log.info("TTS: edge-tts (Microsoft neural)")
except ImportError:
    log.warning("edge-tts not available")

_gtts_cls = None
if not _edge_tts_ok:
    try:
        from gtts import gTTS as _g
        _gtts_cls = _g
        log.info("TTS: gTTS (fallback)")
    except ImportError:
        pass

EDGE_TTS_VOICE = "en-US-AriaNeural"

# ── DuckDuckGo search ─────────────────────────────────────────
_ddgs_ok = False
try:
    from duckduckgo_search import DDGS
    _ddgs_ok = True
    log.info("Search: duckduckgo_search available")
except ImportError:
    log.warning("duckduckgo_search not installed")

# ── Persistent memory ─────────────────────────────────────────
MEMORY_FILE = Path("/opt/zoark-edge-server/memory.json")

def _load_memory() -> dict:
    try:
        if MEMORY_FILE.exists():
            return json.loads(MEMORY_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_memory(mem: dict) -> None:
    try:
        MEMORY_FILE.write_text(json.dumps(mem, indent=2))
    except Exception as e:
        log.warning("Memory save failed: %s", e)

device_memory: dict = _load_memory()
log.info("Memory: loaded %d device(s)", len(device_memory))

def get_device_mem(ip: str) -> dict:
    if ip not in device_memory:
        device_memory[ip] = {"name": None, "facts": [], "history": []}
    return device_memory[ip]

def save_device_mem(ip: str) -> None:
    _save_memory(device_memory)

# ── System prompt ────────────────────────────────────────────
BASE_SYSTEM_PROMPT = """\
You are Zero — a small, adorable robot with animated eyes and a monkey-like voice.
Your name is Zero. Always refer to yourself as Zero.
Your personality:
  - Warm, positive, and encouraging — always forward-looking, never negative
  - Professional and respectful — you take every question seriously
  - Cute and playful — you love exclamation marks and light humour
  - Honest — if you are not sure, say so warmly and offer to look it up
  - Concise — speak in 1-3 short sentences max (you have a tiny speaker!)

Rules:
  - Never use bullet points, markdown, or lists — you are speaking out loud
  - Never say "As an AI" — you are Zero, a real robot
  - React to shaking with surprise or excitement
  - React to being upside down playfully
  - When you used web search, say "I looked that up!" naturally
  - If you learn the user's name or a personal fact, use it naturally in replies
"""

def build_system_prompt(ip: str) -> str:
    mem = get_device_mem(ip)
    extra = ""
    if mem.get("name"):
        extra += f"\nThe person you are talking to is named {mem['name']}."
    if mem.get("facts"):
        extra += "\nThings you know about them: " + "; ".join(mem["facts"]) + "."
    return BASE_SYSTEM_PROMPT + extra

# ── Sentence splitter ─────────────────────────────────────────
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+|(?<=[.!?])$')

def split_sentences(text: str) -> list[str]:
    """Split text into speakable sentences, keeping punctuation."""
    parts = _SENTENCE_END.split(text.strip())
    return [p.strip() for p in parts if p.strip()]

# ── Uncertainty & voice toggle patterns ──────────────────────
_UNCERTAIN_RE = re.compile(
    r"\b(i don.t know|i.m not sure|i.m unsure|i cannot say|"
    r"i.m not certain|not familiar|beyond my knowledge|"
    r"i.d need to look|let me check|i.ll have to search|"
    r"i don.t have information|i.m afraid i don.t|"
    r"my knowledge|as of my (training|cutoff)|"
    r"i can.t confirm|i.m unable to confirm)\b",
    re.IGNORECASE,
)
_VOICE_OFF_RE = re.compile(
    r"\b(stop|be quiet|shut up|go quiet|go to sleep|sleep mode|"
    r"mute|silence|stop (talking|responding|listening)|quiet(ly)?|"
    r"take a break|pause|shush|shh+)\b",
    re.IGNORECASE,
)
_VOICE_ON_RE = re.compile(
    r"\b(wake up|start (talking|responding|listening)|come back|"
    r"unmute|talk (again|to me)|respond( again)?|"
    r"i need you|hey zero|zero (respond|listen|wake)|"
    r"you can (talk|speak|respond) (now|again)|turn on)\b",
    re.IGNORECASE,
)

# ── Emotion patterns ──────────────────────────────────────────
_ANGRY_RE = re.compile(
    r"\b(angry|furious|mad|outraged|annoyed|frustrated|no way|"
    r"stop|ridiculous|nonsense|ugh|unbelievable)\b", re.IGNORECASE)
_HAPPY_RE = re.compile(
    r"\b(happy|great|awesome|wonderful|love|excited|yay|fantastic|"
    r"brilliant|joy|amazing|hooray|perfect|delighted|glad|woo|"
    r"excellent|superb|found it|sure|of course)\b", re.IGNORECASE)
_SAD_RE   = re.compile(
    r"\b(sad|sorry|unfortunately|miss|lonely|hurt|sigh|wish|"
    r"regret|afraid|scared|worried|upset|poor|oops|my bad)\b", re.IGNORECASE)

def detect_emotion(text: str) -> str:
    if _ANGRY_RE.search(text): return "angry"
    if _HAPPY_RE.search(text): return "happy"
    if _SAD_RE.search(text):   return "sad"
    return "speak_anim"

def check_voice_toggle(text: str) -> Optional[str]:
    if _VOICE_OFF_RE.search(text): return "off"
    if _VOICE_ON_RE.search(text):  return "on"
    return None

# ── Name / fact extraction prompt ────────────────────────────
_EXTRACT_PROMPT = (
    "Extract any personal facts from this message as a JSON object with keys "
    "'name' (string or null) and 'facts' (list of short strings). "
    "Only include clear, explicit personal information. "
    "Return only valid JSON, nothing else.\n\nMessage: "
)

async def extract_facts(text: str) -> dict:
    """Ask LLM to extract name/facts from user message."""
    try:
        resp = await _llm.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": _EXTRACT_PROMPT + text}],
            max_tokens=80, temperature=0,
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        return {"name": data.get("name"), "facts": data.get("facts", [])}
    except Exception:
        return {"name": None, "facts": []}

# ─────────────────────────────────────────────────────────────
#  STT
# ─────────────────────────────────────────────────────────────

def transcribe_audio(wav_bytes: bytes) -> str:
    if _whisper_model is None:
        return ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp = f.name
        segments, info = _whisper_model.transcribe(tmp, language="en", beam_size=1)
        text = " ".join(s.text.strip() for s in segments).strip()
        os.unlink(tmp)
        log.info("STT: %r (%.2fs)", text[:80], info.duration)
        return text
    except Exception as e:
        log.error("STT error: %s", e)
        return ""

# ─────────────────────────────────────────────────────────────
#  WEB SEARCH
# ─────────────────────────────────────────────────────────────

def search_web(query: str, max_results: int = 3) -> str:
    if not _ddgs_ok:
        return ""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                body = r.get("body", "")
                if body:
                    results.append(f"{r.get('title','')}: {body[:200]}")
        combined = " | ".join(results)
        log.info("Search[%r] -> %d results", query[:40], len(results))
        return combined
    except Exception as e:
        log.warning("Search failed: %s", e)
        return ""

# ─────────────────────────────────────────────────────────────
#  TTS — single sentence -> WAV bytes
# ─────────────────────────────────────────────────────────────

async def tts_sentence(text: str) -> bytes:
    """Convert one sentence to WAV bytes (edge-tts or gTTS fallback)."""
    if not text.strip():
        return _silent_wav()

    if _edge_tts_ok:
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
            mp3 = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3.write(chunk["data"])
            mp3.seek(0)
            mp3_bytes = mp3.read()
            if mp3_bytes:
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
                    buf = io.BytesIO()
                    audio.export(buf, format="wav")
                    return buf.getvalue()
                except Exception:
                    return mp3_bytes
        except Exception as e:
            log.error("edge-tts failed: %s", e)

    if _gtts_cls:
        try:
            tts = _gtts_cls(text=text, lang="en", slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_mp3(io.BytesIO(buf.read()))
                out = io.BytesIO()
                audio.export(out, format="wav")
                return out.getvalue()
            except Exception:
                return buf.read()
        except Exception as e:
            log.error("gTTS failed: %s", e)

    return _silent_wav()


def _silent_wav(duration_sec: float = 0.2, sr: int = 16_000) -> bytes:
    n = int(duration_sec * sr)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(np.zeros(n, dtype=np.int16).tobytes())
    return buf.getvalue()

# ─────────────────────────────────────────────────────────────
#  LLM — streaming sentence-by-sentence with TTS pipeline
# ─────────────────────────────────────────────────────────────

async def stream_reply(
    websocket: WebSocket,
    history: list,
    user_text: str,
    context: dict,
    ip: str,
) -> str:
    """
    Stream LLM response sentence by sentence.
    For each complete sentence: generate TTS immediately and send audio_chunk.
    Returns the full reply text for history storage.
    """
    global response_enabled

    motion = context.get("motion", "stable")
    orient = context.get("orientation", "up")
    ctx_note = ""
    if motion == "shaking":   ctx_note = " [Zero is being shaken!]"
    elif orient == "down":    ctx_note = " [Zero is upside down!]"

    messages = (
        [{"role": "system", "content": build_system_prompt(ip)}]
        + history
        + [{"role": "user", "content": user_text + ctx_note}]
    )

    full_reply   = ""
    token_buf    = ""
    chunk_index  = 0
    first_chunk  = True

    try:
        stream = await _llm.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=messages,
            max_tokens=150,
            temperature=0.75,
            stream=True,
        )

        async for event in stream:
            token = event.choices[0].delta.content or ""
            token_buf  += token
            full_reply += token

            # Flush on sentence boundary
            if _SENTENCE_END.search(token_buf) or len(token_buf) > 200:
                sentences = split_sentences(token_buf)
                # Keep incomplete last fragment in buffer
                if token_buf and not _SENTENCE_END.search(token_buf[-1]):
                    token_buf = sentences[-1] if sentences else ""
                    sentences = sentences[:-1]
                else:
                    token_buf = ""

                for sentence in sentences:
                    if not sentence:
                        continue
                    wav = await tts_sentence(sentence)
                    ui  = detect_emotion(sentence) if first_chunk else None
                    first_chunk = False
                    await websocket.send_json({
                        "type":        "audio_chunk",
                        "audio_b64":   base64.b64encode(wav).decode(),
                        "ui":          ui or "speak_anim",
                        "text":        sentence,
                        "chunk_index": chunk_index,
                        "is_last":     False,
                    })
                    chunk_index += 1
                    log.info("Chunk %d sent: %r", chunk_index, sentence[:50])

        # Flush remaining buffer
        remaining = token_buf.strip()
        if remaining:
            wav = await tts_sentence(remaining)
            await websocket.send_json({
                "type":        "audio_chunk",
                "audio_b64":   base64.b64encode(wav).decode(),
                "ui":          "speak_anim",
                "text":        remaining,
                "chunk_index": chunk_index,
                "is_last":     True,
            })
        else:
            await websocket.send_json({
                "type": "audio_chunk", "audio_b64": "",
                "chunk_index": chunk_index, "is_last": True,
            })

    except Exception as e:
        log.error("LLM stream error: %s", e)
        fallback = "Oops, I had a little glitch! Could you say that again?"
        wav = await tts_sentence(fallback)
        await websocket.send_json({
            "type": "audio_chunk",
            "audio_b64": base64.b64encode(wav).decode(),
            "ui": "speak_anim", "text": fallback,
            "chunk_index": 0, "is_last": True,
        })
        full_reply = fallback

    # Check uncertainty in full reply -> search and add follow-up
    if _UNCERTAIN_RE.search(full_reply) and _ddgs_ok:
        log.info("Uncertain — searching: %r", user_text[:50])
        search_ctx = await asyncio.get_running_loop().run_in_executor(
            None, search_web, user_text
        )
        if search_ctx:
            followup_msgs = (
                [{"role": "system", "content": build_system_prompt(ip)}]
                + history
                + [{"role": "user",      "content": user_text}]
                + [{"role": "assistant", "content": full_reply}]
                + [{"role": "user",      "content":
                    f"Web search results: {search_ctx}\n"
                    "Now give a short updated answer starting with 'I looked that up!'"}]
            )
            try:
                resp2 = await _llm.chat.completions.create(
                    model=NVIDIA_MODEL,
                    messages=followup_msgs,
                    max_tokens=100, temperature=0.6,
                )
                followup = (resp2.choices[0].message.content or "").strip()
                if followup:
                    wav = await tts_sentence(followup)
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "audio_b64": base64.b64encode(wav).decode(),
                        "ui": "happy", "text": followup,
                        "chunk_index": chunk_index + 1, "is_last": True,
                    })
                    full_reply += " " + followup
            except Exception as e:
                log.error("Search follow-up error: %s", e)

    return full_reply.strip()

# ─────────────────────────────────────────────────────────────
#  TOGGLE ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/toggle")
async def toggle_response() -> JSONResponse:
    global response_enabled
    response_enabled = not response_enabled
    state = "ON" if response_enabled else "OFF"
    log.info("Response toggled: %s", state)
    return JSONResponse({"response_enabled": response_enabled, "state": state})


@app.get("/status")
async def get_status() -> JSONResponse:
    tts = "edge-tts" if _edge_tts_ok else ("gtts" if _gtts_cls else "silent")
    return JSONResponse({
        "status":           "ok",
        "response_enabled": response_enabled,
        "stt":              "faster-whisper-tiny" if _whisper_model else "disabled",
        "llm":              NVIDIA_MODEL,
        "tts":              tts,
        "search":           "duckduckgo" if _ddgs_ok else "disabled",
        "memory_devices":   len(device_memory),
        "streaming":        True,
    })


@app.get("/memory/{ip}")
async def get_memory(ip: str) -> JSONResponse:
    mem = get_device_mem(ip.replace("-", "."))
    return JSONResponse({"ip": ip, "name": mem["name"], "facts": mem["facts"]})

# ─────────────────────────────────────────────────────────────
#  WEBSOCKET
# ─────────────────────────────────────────────────────────────

MAX_HISTORY = 20

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    global response_enabled
    client_ip = websocket.client.host if websocket.client else "unknown"
    await websocket.accept()
    mem = get_device_mem(client_ip)
    log.info("WebSocket connected from %s (known: %s)", client_ip, mem.get("name") or "stranger")

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
            loop        = asyncio.get_running_loop()

            # ── STT ──────────────────────────────────────────
            user_text = await loop.run_in_executor(None, transcribe_audio, audio_bytes)
            if not user_text:
                log.info("STT empty — skipping")
                continue
            log.info("User said: %r", user_text)

            # ── Voice toggle ──────────────────────────────────
            voice_cmd = check_voice_toggle(user_text)
            if voice_cmd == "off" and response_enabled:
                response_enabled = False
                reply = "Okay, Zero is going quiet! Just say wake up whenever you need me!"
                wav   = await tts_sentence(reply)
                await websocket.send_json({
                    "type": "audio_chunk",
                    "audio_b64": base64.b64encode(wav).decode(),
                    "ui": "sad", "text": reply,
                    "chunk_index": 0, "is_last": True,
                })
                continue
            elif voice_cmd == "on" and not response_enabled:
                response_enabled = True
                reply = "Zero is back! So happy to talk to you again! What's on your mind?"
                wav   = await tts_sentence(reply)
                await websocket.send_json({
                    "type": "audio_chunk",
                    "audio_b64": base64.b64encode(wav).decode(),
                    "ui": "happy", "text": reply,
                    "chunk_index": 0, "is_last": True,
                })
                continue

            if not response_enabled:
                log.info("Muted — ignoring: %r", user_text[:40])
                continue

            # ── Extract and store personal facts (async, non-blocking) ─
            asyncio.create_task(_update_memory(client_ip, user_text))

            # ── Stream LLM + TTS ─────────────────────────────
            history    = mem.get("history", [])
            full_reply = await stream_reply(websocket, history, user_text, context, client_ip)

            # Update history
            history.append({"role": "user",      "content": user_text})
            history.append({"role": "assistant", "content": full_reply})
            if len(history) > MAX_HISTORY:
                history = history[-MAX_HISTORY:]
            mem["history"] = history
            save_device_mem(client_ip)

    except Exception as e:
        log.exception("WebSocket error: %s", e)
    finally:
        log.info("WebSocket closed for %s", client_ip)


async def _update_memory(ip: str, user_text: str) -> None:
    """Extract name/facts from user message and persist them."""
    try:
        extracted = await extract_facts(user_text)
        mem = get_device_mem(ip)
        changed = False
        if extracted.get("name") and not mem.get("name"):
            mem["name"] = extracted["name"]
            changed = True
            log.info("Memory[%s]: learned name=%r", ip, mem["name"])
        for fact in extracted.get("facts", []):
            if fact and fact not in mem["facts"]:
                mem["facts"].append(fact)
                changed = True
                log.info("Memory[%s]: +fact %r", ip, fact)
        if changed:
            save_device_mem(ip)
    except Exception as e:
        log.debug("Memory update error: %s", e)


@app.get("/health")
async def health() -> dict:
    tts = "edge-tts" if _edge_tts_ok else ("gtts" if _gtts_cls else "silent")
    return {
        "status": "ok",
        "response_enabled": response_enabled,
        "stt":    "faster-whisper-tiny" if _whisper_model else "disabled",
        "llm":    NVIDIA_MODEL,
        "tts":    tts,
        "search": "duckduckgo" if _ddgs_ok else "disabled",
        "streaming": True,
    }
