import os
import re
import urllib.parse
from typing import Optional
import httpx

# In-memory LRU cache for TTS audio bytes (up to 500 items)
TTS_CACHE: dict[str, bytes] = {}
MAX_CACHE_ITEMS = 500


def clean_text_for_tts(text: str) -> str:
    """Strips markdown links, emojis, and symbols that shouldn't be spoken."""
    if not text:
        return ""
    cleaned = re.sub(r'[*#_`~>]', '', text)
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
    cleaned = re.sub(r'VOX-\d{4}-\d+', lambda m: m.group(0).replace('-', ' '), cleaned, flags=re.IGNORECASE)
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


def _split_into_chunks(text: str, max_chars: int = 150) -> list[str]:
    """Splits long sentences by punctuation to stay within TTS character limit."""
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
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text]


def synthesize_speech(text: str, lang: Optional[str] = None) -> bytes:
    """
    Synthesizes crystal clear native Tamil, Hindi, or English MP3 audio.
    Caches results to deliver sub-millisecond playback.
    """
    cleaned = clean_text_for_tts(text)
    if not cleaned:
        return b""

    lang_code = detect_tts_lang_code(cleaned, lang)
    cache_key = f"{lang_code}:{cleaned}"

    if cache_key in TTS_CACHE:
        return TTS_CACHE[cache_key]

    chunks = _split_into_chunks(cleaned, max_chars=180)
    audio_bytes = bytearray()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    with httpx.Client(timeout=10.0) as client:
        for chunk in chunks:
            if not chunk.strip():
                continue
            encoded_query = urllib.parse.quote(chunk)
            url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_query}&tl={lang_code}&client=tw-ob"
            try:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200 and len(resp.content) > 0:
                    audio_bytes.extend(resp.content)
            except Exception as e:
                print(f"[TTS Synthesis Warning] Error fetching chunk: {e}")
                continue

    result = bytes(audio_bytes)
    if result:
        if len(TTS_CACHE) >= MAX_CACHE_ITEMS:
            first_key = next(iter(TTS_CACHE))
            del TTS_CACHE[first_key]
        TTS_CACHE[cache_key] = result

    return result
