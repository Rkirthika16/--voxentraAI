import re
import unicodedata

# Common phonetic mapping for Tanglish variations
PHONETIC_NORMALIZATION = {
    r"\bthani\b": "thanni",
    r"\bthanneer\b": "thanni",
    r"\bpalame\b": "pallam",
    r"\bgundhum\b": "gundu",
    r"\bkuppe\b": "kuppai",
    r"\bsakadai\b": "sakkadai",
    r"\bvelaku\b": "vilakku",
    r"\beriyalaye\b": "eriyala",
    r"\bcurrant\b": "current",
    r"\bcurant\b": "current",
    r"\bavasharam\b": "avasaram",
    r"\baabaththu\b": "aabathu",
    r"\bnaaye\b": "naai",
}


def normalize_text(text: str) -> str:
    """
    Cleans and normalizes text for analysis:
    - Normalizes Unicode forms
    - Preserves Tamil characters
    - Normalizes whitespace and common Tanglish phonetic variations
    """
    if not text:
        return ""

    # Normalize Unicode (NFC)
    normalized = unicodedata.normalize("NFC", text.strip())

    # Lowercase Latin text while preserving Tamil intact
    lowered = normalized.lower()

    # Apply phonetic Tanglish normalization
    for pattern, replacement in PHONETIC_NORMALIZATION.items():
        lowered = re.sub(pattern, replacement, lowered, flags=re.IGNORECASE)

    # Collapse multiple whitespaces
    lowered = re.sub(r"\s+", " ", lowered)

    return lowered.strip()
