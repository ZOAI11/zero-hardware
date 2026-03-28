"""
============================================================
 Zero Edge Device — Server Backend v6
 FastAPI + WebSocket + Whisper STT + NVIDIA LLM + edge-tts
 Features:
   - Streaming TTS (sentence-by-sentence, ~half latency)
   - Persistent memory (facts + history per device)
   - Whisper tiny (fast, free)
   - DuckDuckGo web search for unknown questions
   - Voice toggle (say "stop" / "wake up")
   - GET /toggle, GET /status
   - #13 Voice emotion detection (pitch + energy + ZCR)
   - #20 Live web dashboard with SSE event stream
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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from openai import AsyncOpenAI

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
)
log = logging.getLogger("zero-server")

# ── FastAPI ──────────────────────────────────────────────────
app = FastAPI(title="Zero Edge Server v6")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ── Global toggle ─────────────────────────────────────────────
_MUTE_STATE_FILE = Path("/opt/zoark-edge-server/mute_state.json")

def _load_mute_state() -> bool:
    try:
        if _MUTE_STATE_FILE.exists():
            return json.loads(_MUTE_STATE_FILE.read_text()).get("muted", False)
    except Exception:
        pass
    return False

def _save_mute_state(muted: bool) -> None:
    try:
        _MUTE_STATE_FILE.write_text(json.dumps({"muted": muted}))
    except Exception:
        pass

response_enabled: bool = not _load_mute_state()

# ── NVIDIA async client ───────────────────────────────────────
NVIDIA_API_KEY  = "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"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL    = "meta/llama-3.1-8b-instruct"

_llm = AsyncOpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)
log.info("LLM: NVIDIA API (%s)", NVIDIA_MODEL)

# ── Whisper STT ───────────────────────────────────────────────
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
  - If the user sounds happy (voice_emotion=happy), be extra cheerful
  - If the user sounds sad (voice_emotion=sad), be warm and comforting
  - If the user sounds angry (voice_emotion=angry), be calm and understanding
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
# Mute trigger: explicit always fires; short ambiguous on <=4 word utterances
_VOICE_OFF_RE = re.compile(
    r"(?:be quiet|shut up|go quiet|go to sleep|sleep mode|stop talking|"
    r"stop (?:responding|listening)|take a break|shush|shh+|"
    r"zero[\s,]+(?:stop|be quiet|shut up|go quiet|go to sleep|sleep|mute|silence|quiet))",
    re.IGNORECASE,
)
_VOICE_OFF_SHORT_RE = re.compile(
    r"(?:stop|pause|quiet|mute|silence|sleep)",
    re.IGNORECASE,
)
# Unmute trigger
_VOICE_ON_RE = re.compile(
    r"(?:wake up|wakeup|start talking|start listening|come back|"
    r"unmute|talk (?:again|to me)|respond again|"
    r"i need you|hey zero|"
    r"zero[\s,]+(?:respond|listen|wake up|wakeup|start|come back)|"
    r"you can (?:talk|speak|respond) (?:now|again)|turn on)",
    re.IGNORECASE,
)

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
    t = text.strip()
    if _VOICE_OFF_RE.search(t):
        return "off"
    if len(t.split()) <= 4 and _VOICE_OFF_SHORT_RE.search(t):
        return "off"
    if _VOICE_ON_RE.search(t):
        return "on"
    return None

# ── #13 Voice Emotion Detection ───────────────────────────────
def detect_voice_emotion(wav_bytes: bytes) -> str:
    """
    Analyze audio signal to detect user's emotional state.
    Uses pitch (autocorrelation), RMS energy, and zero-crossing rate.
    Returns: 'happy', 'angry', 'sad', or 'neutral'
    """
    try:
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            sr        = wf.getframerate()
            n_frames  = wf.getnframes()
            n_ch      = wf.getnchannels()
            sampw     = wf.getsampwidth()
            raw       = wf.readframes(n_frames)

        # Decode samples
        if sampw == 2:
            pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampw == 4:
            pcm = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            return "neutral"

        # Take mono (left channel if stereo)
        if n_ch > 1:
            pcm = pcm[::n_ch]

        if len(pcm) < sr // 10:  # < 100ms — too short to analyze
            return "neutral"

        # ── Energy (RMS) ─────────────────────────────────────
        rms       = float(np.sqrt(np.mean(pcm ** 2)) + 1e-9)
        energy_db = 20.0 * np.log10(rms)

        # ── Zero-crossing rate ────────────────────────────────
        zcr = float(np.mean(np.abs(np.diff(np.sign(pcm)))) / 2.0)

        # ── Pitch (autocorrelation on first second max) ───────
        analysis_samples = min(len(pcm), sr)
        seg    = pcm[:analysis_samples]
        min_lag = max(1, sr // 400)  # 400 Hz upper bound
        max_lag = sr // 80           # 80 Hz lower bound
        corr   = np.correlate(seg, seg, mode="full")
        corr   = corr[len(corr) // 2:]
        pitch_hz = 0.0
        if max_lag < len(corr) and max_lag > min_lag:
            peak_offset = int(np.argmax(corr[min_lag:max_lag]))
            peak_lag    = peak_offset + min_lag
            if peak_lag > 0:
                pitch_hz = float(sr) / peak_lag

        log.debug(
            "VoiceEmotion: energy=%.1f dB  pitch=%.0f Hz  zcr=%.3f",
            energy_db, pitch_hz, zcr,
        )

        # ── Mapping heuristics ────────────────────────────────
        # High energy + high pitch → excited / happy
        if energy_db > -22.0 and pitch_hz > 210:
            return "happy"
        # High energy + low-mid pitch + low ZCR → angry / assertive
        if energy_db > -20.0 and pitch_hz < 185 and zcr < 0.12:
            return "angry"
        # Low energy, low pitch, or both → sad / quiet
        if energy_db < -34.0 or (pitch_hz < 145 and energy_db < -28.0):
            return "sad"
        return "neutral"

    except Exception as exc:
        log.debug("detect_voice_emotion error: %s", exc)
        return "neutral"

# ── #20 SSE Event Bus ─────────────────────────────────────────
# Each subscriber is an asyncio.Queue fed by _broadcast_event().
_sse_subscribers: list[asyncio.Queue] = []

async def _broadcast_event(event: dict) -> None:
    """Push an event to all active SSE subscribers (non-blocking)."""
    dead: list[asyncio.Queue] = []
    for q in _sse_subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _sse_subscribers.remove(q)
        except ValueError:
            pass

# ── #20 Dashboard HTML ────────────────────────────────────────
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zero · Live Dashboard</title>
<style>
  :root {
    --bg: #0d0d1a; --card: #13132a; --border: #252545;
    --accent: #7c6af5; --accent2: #4de8c2; --text: #e8e8f5;
    --muted: #6a6a8a; --user: #2a4a8a; --zero: #1a3a2a;
    --angry: #c0392b; --happy: #f39c12; --sad: #2980b9; --neutral: #7c6af5;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif;
         height: 100vh; display: flex; flex-direction: column; }
  header { background: var(--card); border-bottom: 1px solid var(--border);
           padding: 14px 24px; display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
  .logo { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.5px;
          background: linear-gradient(135deg, var(--accent), var(--accent2));
          -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .status-dot { width: 10px; height: 10px; border-radius: 50%; background: #555;
                transition: background 0.4s; flex-shrink: 0; }
  .status-dot.live { background: #2ecc71; box-shadow: 0 0 8px #2ecc71; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
  .status-label { font-size: 0.8rem; color: var(--muted); }
  .mute-badge { margin-left: auto; font-size: 0.75rem; padding: 4px 10px; border-radius: 12px;
                background: #333; color: var(--muted); transition: all 0.3s; }
  .mute-badge.muted { background: #4a1a1a; color: #e74c3c; }
  .main { display: flex; flex: 1; overflow: hidden; gap: 0; }
  .chat-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; border-right: 1px solid var(--border); }
  .chat-header { padding: 12px 20px; border-bottom: 1px solid var(--border);
                 font-size: 0.8rem; color: var(--muted); letter-spacing: 0.5px; text-transform: uppercase; flex-shrink: 0; }
  .chat-feed { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  .chat-feed::-webkit-scrollbar { width: 4px; }
  .chat-feed::-webkit-scrollbar-track { background: transparent; }
  .chat-feed::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
  .msg { max-width: 80%; padding: 10px 14px; border-radius: 14px; font-size: 0.9rem;
         line-height: 1.45; animation: fadeIn 0.25s ease; }
  @keyframes fadeIn { from { opacity:0; transform: translateY(6px); } to { opacity:1; transform:none; } }
  .msg.user { background: var(--user); border-bottom-right-radius: 4px; align-self: flex-end;
              border: 1px solid rgba(124,106,245,0.2); }
  .msg.zero { background: var(--zero); border-bottom-left-radius: 4px; align-self: flex-start;
              border: 1px solid rgba(77,232,194,0.15); }
  .msg .sender { font-size: 0.7rem; color: var(--muted); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.4px; }
  .msg .emo-tag { display: inline-block; margin-left: 6px; font-size: 0.7rem;
                  padding: 1px 6px; border-radius: 8px; vertical-align: middle; }
  .side-panel { width: 280px; display: flex; flex-direction: column; gap: 0; flex-shrink: 0; }
  .side-section { border-bottom: 1px solid var(--border); padding: 16px; }
  .side-title { font-size: 0.7rem; color: var(--muted); text-transform: uppercase;
                letter-spacing: 0.5px; margin-bottom: 12px; }
  .emotion-display { text-align: center; padding: 8px 0; }
  .emotion-icon { font-size: 3rem; display: block; line-height: 1; margin-bottom: 8px;
                  transition: all 0.4s; filter: drop-shadow(0 0 12px currentColor); }
  .emotion-name { font-size: 1rem; font-weight: 600; transition: color 0.4s; }
  .emotion-name.happy { color: var(--happy); }
  .emotion-name.angry { color: var(--angry); }
  .emotion-name.sad   { color: var(--sad); }
  .emotion-name.neutral { color: var(--neutral); }
  .emotion-bars { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
  .emo-bar-row { display: flex; align-items: center; gap: 8px; font-size: 0.75rem; color: var(--muted); }
  .emo-bar-label { width: 50px; text-align: right; }
  .emo-bar-track { flex: 1; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden; }
  .emo-bar-fill { height: 100%; border-radius: 3px; transition: width 0.6s ease; width: 0%; }
  .emo-bar-fill.happy  { background: var(--happy); }
  .emo-bar-fill.angry  { background: var(--angry); }
  .emo-bar-fill.sad    { background: var(--sad); }
  .emo-bar-fill.neutral { background: var(--neutral); }
  .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .stat-card { background: rgba(255,255,255,0.03); border: 1px solid var(--border);
               border-radius: 8px; padding: 10px; text-align: center; }
  .stat-val { font-size: 1.2rem; font-weight: 700; color: var(--accent2); }
  .stat-key { font-size: 0.65rem; color: var(--muted); margin-top: 2px; text-transform: uppercase; }
  .waveform { display: flex; align-items: flex-end; justify-content: center;
              gap: 3px; height: 40px; margin-top: 4px; }
  .wave-bar { width: 4px; background: var(--accent); border-radius: 2px; min-height: 3px;
              transition: height 0.1s; opacity: 0.7; }
  .conn-log { font-size: 0.72rem; color: var(--muted); font-family: 'Courier New', monospace;
              max-height: 80px; overflow-y: auto; line-height: 1.6; }
  .conn-log .log-line { color: #5a9; }
  .conn-log .log-line.warn { color: #e67; }
</style>
</head>
<body>
<header>
  <span class="logo">&#9675; Zero</span>
  <span class="status-dot" id="dot"></span>
  <span class="status-label" id="status-label">Connecting…</span>
  <span class="mute-badge" id="mute-badge">ACTIVE</span>
</header>
<div class="main">
  <div class="chat-panel">
    <div class="chat-header">Live Conversation</div>
    <div class="chat-feed" id="feed">
      <div style="color:var(--muted);font-size:0.82rem;text-align:center;margin-top:20px">
        Waiting for Zero to speak…
      </div>
    </div>
  </div>
  <div class="side-panel">
    <div class="side-section">
      <div class="side-title">Emotion</div>
      <div class="emotion-display">
        <span class="emotion-icon" id="emo-icon">😐</span>
        <div class="emotion-name neutral" id="emo-name">neutral</div>
      </div>
      <div class="emotion-bars">
        <div class="emo-bar-row"><span class="emo-bar-label">happy</span>
          <div class="emo-bar-track"><div class="emo-bar-fill happy" id="bar-happy"></div></div></div>
        <div class="emo-bar-row"><span class="emo-bar-label">angry</span>
          <div class="emo-bar-track"><div class="emo-bar-fill angry" id="bar-angry"></div></div></div>
        <div class="emo-bar-row"><span class="emo-bar-label">sad</span>
          <div class="emo-bar-track"><div class="emo-bar-fill sad" id="bar-sad"></div></div></div>
        <div class="emo-bar-row"><span class="emo-bar-label">neutral</span>
          <div class="emo-bar-track"><div class="emo-bar-fill neutral" id="bar-neutral"></div></div></div>
      </div>
    </div>
    <div class="side-section">
      <div class="side-title">Audio Activity</div>
      <div class="waveform" id="wave">
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
        <div class="wave-bar" style="height:3px"></div>
      </div>
    </div>
    <div class="side-section">
      <div class="side-title">Session Stats</div>
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-val" id="stat-turns">0</div><div class="stat-key">Turns</div></div>
        <div class="stat-card"><div class="stat-val" id="stat-clients">0</div><div class="stat-key">Clients</div></div>
        <div class="stat-card"><div class="stat-val" id="stat-emo">😐</div><div class="stat-key">Mood</div></div>
        <div class="stat-card"><div class="stat-val" id="stat-muted">🔊</div><div class="stat-key">State</div></div>
      </div>
    </div>
    <div class="side-section" style="flex:1">
      <div class="side-title">Log</div>
      <div class="conn-log" id="conn-log"></div>
    </div>
  </div>
</div>
<script>
const EMO_ICONS = {happy:'😄', angry:'😠', sad:'😢', neutral:'😐', speak_anim:'🗣️'};
const EMO_COLORS = {happy:'#f39c12', angry:'#c0392b', sad:'#2980b9', neutral:'#7c6af5'};
let turns = 0, currentEmo = 'neutral', waveTimer = null;

function addLog(msg, warn=false) {
  const el = document.getElementById('conn-log');
  const line = document.createElement('div');
  line.className = 'log-line' + (warn ? ' warn' : '');
  line.textContent = new Date().toLocaleTimeString() + '  ' + msg;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
  while (el.children.length > 30) el.removeChild(el.firstChild);
}

function setEmotion(emo) {
  const raw = emo === 'speak_anim' ? 'neutral' : emo;
  currentEmo = raw;
  document.getElementById('emo-icon').textContent = EMO_ICONS[raw] || '😐';
  const nameEl = document.getElementById('emo-name');
  nameEl.textContent = raw;
  nameEl.className = 'emotion-name ' + raw;
  document.getElementById('stat-emo').textContent = EMO_ICONS[raw] || '😐';
  const bars = {happy:0, angry:0, sad:0, neutral:0};
  bars[raw] = 100;
  // add secondary bar for context
  if (raw === 'happy')   bars.neutral = 20;
  if (raw === 'angry')   bars.neutral = 15;
  if (raw === 'sad')     bars.neutral = 25;
  if (raw === 'neutral') { bars.happy = 15; bars.sad = 10; }
  ['happy','angry','sad','neutral'].forEach(e => {
    const b = document.getElementById('bar-' + e);
    if (b) b.style.width = bars[e] + '%';
  });
}

function animateWave(active) {
  clearInterval(waveTimer);
  const bars = document.querySelectorAll('.wave-bar');
  if (!active) {
    bars.forEach(b => b.style.height = '3px');
    return;
  }
  waveTimer = setInterval(() => {
    bars.forEach(b => {
      const h = active ? (3 + Math.random() * 34) : 3;
      b.style.height = h + 'px';
    });
  }, 80);
}

function addMessage(role, text, emo) {
  const feed = document.getElementById('feed');
  // Remove placeholder
  const ph = feed.querySelector('div[style]');
  if (ph) ph.remove();

  const wrap = document.createElement('div');
  wrap.className = 'msg ' + role;
  const sender = document.createElement('div');
  sender.className = 'sender';
  sender.textContent = role === 'user' ? 'You' : 'Zero';
  if (emo && emo !== 'speak_anim') {
    const tag = document.createElement('span');
    tag.className = 'emo-tag';
    tag.style.background = EMO_COLORS[emo] + '33';
    tag.style.color = EMO_COLORS[emo];
    tag.textContent = EMO_ICONS[emo] + ' ' + emo;
    sender.appendChild(tag);
  }
  const body = document.createElement('div');
  body.textContent = text;
  wrap.appendChild(sender);
  wrap.appendChild(body);
  feed.appendChild(wrap);
  feed.scrollTop = feed.scrollHeight;
}

function connect() {
  const es = new EventSource('/events');
  document.getElementById('dot').className = 'status-dot';
  document.getElementById('status-label').textContent = 'Connecting…';

  es.onopen = () => {
    document.getElementById('dot').className = 'status-dot live';
    document.getElementById('status-label').textContent = 'Live';
    addLog('Connected to Zero server');
  };

  es.onerror = () => {
    document.getElementById('dot').className = 'status-dot';
    document.getElementById('status-label').textContent = 'Reconnecting…';
    addLog('Connection lost — retrying…', true);
    setTimeout(connect, 3000);
    es.close();
  };

  es.onmessage = (e) => {
    let ev;
    try { ev = JSON.parse(e.data); } catch { return; }
    if (ev.type === 'ping') return;

    if (ev.type === 'user_heard') {
      turns++;
      document.getElementById('stat-turns').textContent = turns;
      if (ev.voice_emotion) setEmotion(ev.voice_emotion);
      addMessage('user', ev.text, ev.voice_emotion);
      animateWave(true);
      addLog('User: ' + ev.text.substring(0, 60));
    }

    if (ev.type === 'zero_chunk') {
      if (ev.text) addMessage('zero', ev.text, ev.ui);
      if (ev.ui) setEmotion(ev.ui);
      animateWave(false);
      if (ev.text) addLog('Zero: ' + ev.text.substring(0, 60));
    }

    if (ev.type === 'mute_change') {
      const muted = ev.muted;
      const badge = document.getElementById('mute-badge');
      badge.textContent = muted ? 'MUTED' : 'ACTIVE';
      badge.className = 'mute-badge' + (muted ? ' muted' : '');
      document.getElementById('stat-muted').textContent = muted ? '🔇' : '🔊';
      addLog(muted ? 'Zero muted' : 'Zero unmuted');
    }

    if (ev.type === 'client_count') {
      document.getElementById('stat-clients').textContent = ev.count;
    }
  };
}

connect();
</script>
</body>
</html>"""

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
    voice_emotion: str = "neutral",
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
    # Inject voice emotion so LLM can tailor its response tone
    if voice_emotion and voice_emotion != "neutral":
        ctx_note += f" [voice_emotion={voice_emotion}]"

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
                    ui  = detect_emotion(sentence) if first_chunk else "speak_anim"
                    first_chunk = False
                    payload = {
                        "type":        "audio_chunk",
                        "audio_b64":   base64.b64encode(wav).decode(),
                        "ui":          ui,
                        "text":        sentence,
                        "chunk_index": chunk_index,
                        "is_last":     False,
                    }
                    await websocket.send_json(payload)
                    # Broadcast to dashboard
                    await _broadcast_event({
                        "type": "zero_chunk",
                        "text": sentence,
                        "ui":   ui,
                        "chunk_index": chunk_index,
                    })
                    chunk_index += 1
                    log.info("Chunk %d sent: %r", chunk_index, sentence[:50])

        # Flush remaining buffer
        remaining = token_buf.strip()
        if remaining:
            wav = await tts_sentence(remaining)
            ui = detect_emotion(remaining)
            await websocket.send_json({
                "type":        "audio_chunk",
                "audio_b64":   base64.b64encode(wav).decode(),
                "ui":          ui,
                "text":        remaining,
                "chunk_index": chunk_index,
                "is_last":     True,
            })
            await _broadcast_event({"type": "zero_chunk", "text": remaining, "ui": ui})
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
        await _broadcast_event({"type": "zero_chunk", "text": fallback, "ui": "speak_anim"})
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
                    await _broadcast_event({"type": "zero_chunk", "text": followup, "ui": "happy"})
                    full_reply += " " + followup
            except Exception as e:
                log.error("Search follow-up error: %s", e)

    return full_reply.strip()

# ─────────────────────────────────────────────────────────────
#  ACTIVE CLIENT TRACKING
# ─────────────────────────────────────────────────────────────
_active_clients: set[str] = set()

# ─────────────────────────────────────────────────────────────
#  TOGGLE ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/toggle")
async def toggle_response() -> JSONResponse:
    global response_enabled
    response_enabled = not response_enabled
    _save_mute_state(not response_enabled)
    state = "ON" if response_enabled else "OFF"
    log.info("Response toggled: %s", state)
    await _broadcast_event({"type": "mute_change", "muted": not response_enabled})
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


@app.get("/memory/{ip}")
async def get_memory(ip: str) -> JSONResponse:
    mem = get_device_mem(ip.replace("-", "."))
    return JSONResponse({"ip": ip, "name": mem["name"], "facts": mem["facts"]})

# ─────────────────────────────────────────────────────────────
#  #20 DASHBOARD + SSE ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_HTML)


@app.get("/events")
async def sse_events(request: Request) -> StreamingResponse:
    """Server-Sent Events stream for the live dashboard."""
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _sse_subscribers.append(q)

    async def generator():
        try:
            # Send current state immediately on connect
            yield f"data: {json.dumps({'type': 'mute_change', 'muted': not response_enabled})}\n\n"
            yield f"data: {json.dumps({'type': 'client_count', 'count': len(_active_clients)})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive ping so the connection doesn't drop
                    yield "data: {\"type\":\"ping\"}\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            try:
                _sse_subscribers.remove(q)
            except ValueError:
                pass

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )

# ─────────────────────────────────────────────────────────────
#  WEBSOCKET
# ─────────────────────────────────────────────────────────────

MAX_HISTORY = 20

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    global response_enabled
    client_ip = websocket.client.host if websocket.client else "unknown"
    await websocket.accept()
    _active_clients.add(client_ip)
    await _broadcast_event({"type": "client_count", "count": len(_active_clients)})
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

            # ── #13 Voice emotion analysis (non-blocking) ─────
            voice_emotion = await loop.run_in_executor(
                None, detect_voice_emotion, audio_bytes
            )
            log.info("Voice emotion: %s", voice_emotion)

            # ── STT ──────────────────────────────────────────
            user_text = await loop.run_in_executor(None, transcribe_audio, audio_bytes)
            if not user_text:
                log.info("STT empty — skipping")
                continue
            # Whisper sometimes transcribes "zero" as digit "0" — normalise it
            user_text = re.sub(r"\b0\b", "zero", user_text)
            log.info("User said: %r", user_text)

            # Broadcast user utterance to dashboard
            await _broadcast_event({
                "type":         "user_heard",
                "text":         user_text,
                "voice_emotion": voice_emotion,
            })

            # ── Voice toggle ──────────────────────────────────
            voice_cmd = check_voice_toggle(user_text)
            log.info("Toggle: cmd=%r enabled=%r", voice_cmd, response_enabled)
            if voice_cmd == "off" and response_enabled:
                response_enabled = False
                _save_mute_state(True)
                log.info("MUTED: Zero going quiet")
                await _broadcast_event({"type": "mute_change", "muted": True})
                reply = "Okay, going quiet! Just say wake up whenever you need me!"
                wav   = await tts_sentence(reply)
                await websocket.send_json({
                    "type": "audio_chunk",
                    "audio_b64": base64.b64encode(wav).decode(),
                    "ui": "sad", "text": reply,
                    "chunk_index": 0, "is_last": True,
                })
                await _broadcast_event({"type": "zero_chunk", "text": reply, "ui": "sad"})
                continue
            elif voice_cmd == "on" and not response_enabled:
                response_enabled = True
                _save_mute_state(False)
                log.info("UNMUTED: Zero waking up")
                await _broadcast_event({"type": "mute_change", "muted": False})
                reply = "Zero is back! So happy to talk to you again!"
                wav   = await tts_sentence(reply)
                await websocket.send_json({
                    "type": "audio_chunk",
                    "audio_b64": base64.b64encode(wav).decode(),
                    "ui": "happy", "text": reply,
                    "chunk_index": 0, "is_last": True,
                })
                await _broadcast_event({"type": "zero_chunk", "text": reply, "ui": "happy"})
                continue

            if not response_enabled:
                log.info("SILENT (muted) — ignoring: %r", user_text[:50])
                continue

            # ── Extract and store personal facts (async, non-blocking) ─
            asyncio.create_task(_update_memory(client_ip, user_text))

            # ── Stream LLM + TTS ─────────────────────────────
            history    = mem.get("history", [])
            full_reply = await stream_reply(
                websocket, history, user_text, context, client_ip,
                voice_emotion=voice_emotion,
            )

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
        _active_clients.discard(client_ip)
        await _broadcast_event({"type": "client_count", "count": len(_active_clients)})
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
