import re
from typing import Tuple

# Pure Tanglish keywords (Tamil words written phonetically in Latin/Roman script)
# Strictly excludes pure English words like 'pipe', 'drainage', 'near', 'side', 'current'
TANGLISH_KEYWORDS = {
    "thanni", "thani", "neer", "kudineer", "odanju", "varala", "valiyuthu", "valiyithu",
    "salai", "pallam", "gundu", "kuliyum", "periya", "chinna", "romba", "mosam",
    "kuppai", "naaththam", "vaadai", "alli", "podala", "theru", "theruvil",
    "sakkadai", "adaippu", "thengi", "nikkuthu",
    "vilakku", "eriyala", "velicham", "iruttu", "illa", "illai", "arunthu",
    "aabathu", "aapathu", "avasaram", "thee", "vizhunthuduchu", "naai", "thollai",
    "pakkam", "pakathula", "kitta", "udane", "seiyunga",
    "irukku", "pannunga", "mudiyala", "aachu", "pochu", "aaguthu",
    "endha", "enga", "inga", "unga", "enaku", "veedu", "sonna", "maatha",
    "seri", "aama", "aamam", "kandippa", "podunga", "vendaam"
}

ENGLISH_INDICATORS = {
    "the", "is", "was", "are", "were", "there", "this", "that", "in", "on", "at", "to",
    "for", "of", "with", "from", "by", "about", "and", "or", "not", "have", "has", "had",
    "pipe", "water", "drainage", "garbage", "leak", "leaking", "broken", "road", "street",
    "light", "lamp", "electric", "pole", "current", "power", "cut", "problem", "issue",
    "complaint", "hospital", "school", "near", "opposite", "behind", "morning", "evening",
    "today", "yesterday", "daily", "frequent", "active", "status", "still", "hazard",
    "overflow", "overflowing", "dustbin", "avenue", "lane", "cross", "colony", "ward",
    "speaking", "english", "hello", "good", "please", "help", "register", "confirm"
}


def is_tamil_script(text: str) -> bool:
    """Check if text contains Tamil Unicode characters (\u0B80-\u0BFF)."""
    tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', text))
    return tamil_chars > 0


def detect_language(text: str) -> Tuple[str, float]:
    """
    Accurately detects whether text is Tamil (script), Tanglish (Tamil in Latin script),
    or English.
    Returns: (language_name, confidence)
    """
    if not text or not text.strip():
        return "English", 0.0

    cleaned = text.strip()
    total_len = len(cleaned)
    tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', cleaned))

    # 1. Tamil Script Detection
    if tamil_chars > 0:
        ratio = tamil_chars / total_len
        if ratio > 0.3:
            return "Tamil", 0.98
        return "Mixed (Tamil/English)", 0.85

    # 2. Latin Script: Differentiate English vs Tanglish
    words = [w.lower() for w in re.findall(r'[a-zA-Z]+', cleaned)]
    if not words:
        return "English", 0.5

    tanglish_matches = sum(1 for w in words if w in TANGLISH_KEYWORDS)
    english_matches = sum(1 for w in words if w in ENGLISH_INDICATORS)

    # If sentence is predominantly standard English words
    if english_matches >= tanglish_matches and english_matches > 0:
        if tanglish_matches == 0 or (english_matches / len(words)) >= 0.3:
            return "English", 0.95

    # If clear Tanglish markers exist
    if tanglish_matches >= 2 or (tanglish_matches / len(words)) >= 0.2:
        return "Tanglish", min(0.95, 0.65 + (tanglish_matches * 0.1))

    # Check for Tanglish suffix patterns: e.g. -la, -kitta, -pakkam
    if re.search(r'\b[a-zA-Z]+(?:-la|la|le|-kitta|kitta|-pakkam|pakkam)\b', cleaned.lower()):
        return "Tanglish", 0.85

    return "English", 0.92
