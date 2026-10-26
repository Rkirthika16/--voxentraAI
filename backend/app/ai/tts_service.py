import os
import re
import asyncio
import urllib.parse
import struct
from typing import Optional
import httpx
import logging

logger = logging.getLogger("voxentra.tts")

# In-memory LRU cache for TTS audio bytes (up to 500 items)
TTS_CACHE: dict[str, bytes] = {}
MAX_CACHE_ITEMS = 500

VOICE_MAP = {
    "ta": "ta-IN-ValluvarNeural",
    "en": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural"
}


def clean_text_for_tts(text: str) -> str:
    """Strips markdown links, emojis, and symbols that shouldn't be spoken."""
    if not text:
        return ""
    cleaned = re.sub(r'[*#_`~>]', '', text)
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
    cleaned = re.sub(r'VOX-\d{4}-\d+|VX-\d{4}-\d+', lambda m: m.group(0).replace('-', ' '), cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def detect_tts_lang_code(text: str, explicit_lang: Optional[str] = None) -> str:
    """Returns ISO 639-1 language code for TTS engine."""
    if explicit_lang:
        l = explicit_lang.lower()
        if 'ta' in l or 'tamil' in l:
            return 'ta'
        if 'hi' in l or 'hindi' in l:
            return 'hi'
        if 'tanglish' in l:
            return 'ta' if any('\u0B80' <= c <= '\u0BFF' for c in text) else 'en'
        if 'en' in l or 'english' in l:
            return 'en'

    # Detect by unicode script
    if any('\u0B80' <= c <= '\u0BFF' for c in text):
        return 'ta'
    if any('\u0900' <= c <= '\u097F' for c in text):
        return 'hi'

    return 'en'


def _split_into_chunks(text: str, max_chars: int = 180) -> list[str]:
    """Splits long sentences by punctuation to stay within TTS limits."""
    sentences = re.split(r'([.!?,;\n।])', text)
    chunks = []
    current = ""
    for piece in sentences:
        if len(current) + len(piece) <= max_chars:
            current += piece
        else:
            if current.strip():
                chunks.append(current.strip())
            current = piece
        if len(current) >= max_chars:
            chunks.append(current.strip())
            current = ""
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c.strip()] or [text]


async def _synthesize_edge_tts(text: str, lang_code: str) -> Optional[bytes]:
    """Generates crystal clear neural voice using edge-tts."""
    try:
        import edge_tts
        voice = VOICE_MAP.get(lang_code, "en-IN-NeerjaNeural")
        communicate = edge_tts.Communicate(text, voice)
        audio_stream = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.extend(chunk["data"])
        if len(audio_stream) > 0:
            return bytes(audio_stream)
    except Exception as e:
        logger.debug(f"Edge-TTS synthesis error: {e}")
    return None


def _synthesize_google_tts(text: str, lang_code: str) -> Optional[bytes]:
    """Fallback Google Translate TTS for low-latency chunks."""
    chunks = _split_into_chunks(text, max_chars=180)
    audio_bytes = bytearray()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        with httpx.Client(timeout=6.0) as client:
            for chunk in chunks:
                if not chunk.strip():
                    continue
                encoded_query = urllib.parse.quote(chunk)
                url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_query}&tl={lang_code}&client=tw-ob"
                resp = client.get(url, headers=headers)
                if resp.status_code == 200 and len(resp.content) > 0:
                    audio_bytes.extend(resp.content)
        if len(audio_bytes) > 0:
            return bytes(audio_bytes)
    except Exception as e:
        logger.debug(f"Google TTS fallback error: {e}")
    return None


def _generate_fallback_wav() -> bytes:
    """Generates valid fallback PCM WAV audio when network is unavailable."""
    sample_rate = 8000
    num_samples = 4000  # 500ms
    data_size = num_samples * 2
    chunk_size = 36 + data_size
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', chunk_size, b'WAVE', b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16, b'data', data_size
    )
    return header + (b'\x00' * data_size)


def synthesize_speech(text: str, lang: Optional[str] = None) -> bytes:
    """
    Synthesizes crystal clear native Tamil, English, or Tanglish audio.
    Caches results to deliver sub-millisecond repeated playback.
    """
    cleaned = clean_text_for_tts(text)
    if not cleaned:
        return b""

    lang_code = detect_tts_lang_code(cleaned, lang)
    cache_key = f"{lang_code}:{cleaned}"

    if cache_key in TTS_CACHE:
        return TTS_CACHE[cache_key]

    result = None

    # 1. Primary: Edge-TTS Neural Synthesis
    try:
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                result = executor.submit(lambda: asyncio.run(_synthesize_edge_tts(cleaned, lang_code))).result(timeout=6.0)
        except RuntimeError:
            result = asyncio.run(_synthesize_edge_tts(cleaned, lang_code))
    except Exception as e:
        logger.debug(f"Edge TTS attempt failed: {e}")

    # 2. Secondary Fallback: Google TTS
    if not result:
        result = _synthesize_google_tts(cleaned, lang_code)

    # 3. Tertiary Fallback: Silent PCM WAV
    if not result:
        result = _generate_fallback_wav()

    if result:
        if len(TTS_CACHE) >= MAX_CACHE_ITEMS:
            first_key = next(iter(TTS_CACHE))
            del TTS_CACHE[first_key]
        TTS_CACHE[cache_key] = result

    return result
