import re
from typing import Tuple

# Common Tanglish words (Tamil words written in Latin script)
TANGLISH_KEYWORDS = {
    "thanni", "thani", "neer", "kudineer", "pipe", "odanju", "varala", "valiyuthu",
    "salai", "pallam", "gundu", "kuliyum", "periya", "chinna", "romba", "mosam",
    "kuppai", "dustbin", "naaththam", "vaadai", "alli", "podala", "theru",
    "sakkadai", "drainage", "adaippu", "thengi", "nikkuthu", "valiyithu",
    "vilakku", "eriyala", "velicham", "iruttu", "current", "illa", "arunthu",
    "aabathu", "aapathu", "avasaram", "thee", "vizhunthuduchu", "naai", "thollai",
    "pakkam", "la", "kitta", "near", "side", "romba", "udane", "seiyunga",
    "irukku", "illai", "pannunga", "mudiyala", "aachu", "pochu", "aaguthu"
}


def is_tamil_script(text: str) -> bool:
    """Check if text contains Tamil Unicode characters (\u0B80-\u0BFF)."""
    tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', text))
    return tamil_chars > 0


def detect_language(text: str) -> Tuple[str, float]:
    """
    Detects whether the text is Tamil (script), Tanglish (Tamil in Latin script),
    English, or Mixed.
    Returns: (language_name, confidence)
    """
    if not text or not text.strip():
        return "English", 0.0

    cleaned = text.strip()
    total_len = len(cleaned)
    tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', cleaned))

    # If significant Tamil script characters exist
    if tamil_chars > 0:
        ratio = tamil_chars / total_len
        if ratio > 0.4:
            return "Tamil", 0.95
        return "Mixed (Tamil/English)", 0.85

    # Check for Tanglish keywords in Latin script
    words = [w.lower() for w in re.findall(r'[a-zA-Z]+', cleaned)]
    if not words:
        return "English", 0.5

    tanglish_matches = sum(1 for w in words if w in TANGLISH_KEYWORDS)
    tanglish_ratio = tanglish_matches / len(words)

    if tanglish_matches >= 2 or tanglish_ratio >= 0.2:
        return "Tanglish", min(0.9, 0.6 + (tanglish_matches * 0.1))

    return "English", 0.9
