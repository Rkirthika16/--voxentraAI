import re
from typing import Tuple

# Pure Tanglish keywords & particles (Tamil words written phonetically in Latin/Roman script)
TANGLISH_KEYWORDS = {
    "thanni", "thani", "thanneer", "thanniye", "thanneere", "neer", "kudineer", "kudika", "kudikka", "kudikira",
    "varala", "varla", "vara", "varadhu", "varudhu", "varave", "varudhunga", "varangala", "varalaam",
    "matingithu", "maatenguthu", "maatingudhu", "maatenghuthu", "maatikuthu", "maatendhu", "mudiyala", "mudiyadhu",
    "odanju", "odanjiduchu", "odanjuruchu", "udanjiduchu", "udanjuruchu", "valiyuthu", "valiyudhu", "valiyithu",
    "thengi", "thengudhu", "theengudhu", "nikkuthu", "odudhu", "adaichu", "adaichuruchu", "adaippu",
    "salai", "pallam", "gundu", "kuliyum", "periya", "chinna", "romba", "mosam", "theru", "theruvil", "therula", "theruvula",
    "kuppai", "naaththam", "vaadai", "alli", "podala", "allala", "clean", "suththam", "allamaatenguranga",
    "sakkadai", "sakkada", "saakadai", "naatram", "kallu",
    "vilakku", "eriyala", "eriyave", "velicham", "iruttu", "illa", "illai", "illaye", "illanga", "arunthu", "pala",
    "aabathu", "aapathu", "avasaram", "thee", "vizhunthuduchu", "naai", "thollai", "kadi", "paambu", "kambam",
    "pakkam", "pakathula", "kitta", "udane", "seiyunga", "pannunga", "pannikonga", "pannalaam", "panren", "pannren",
    "irukku", "iruku", "irukkunga", "aachu", "pochu", "poiduchu", "aaguthu", "aagudhu", "vandhuchu", "nadakuthu", "nadakkudhu",
    "endha", "enga", "inga", "unga", "enaku", "enakku", "ungalukku", "veedu", "veetla", "veetula", "sonna", "maatha", "maathanum",
    "seri", "aama", "aamam", "kandippa", "podunga", "vendaam", "paravala", "sollunga", "solren", "solreenga",
    "naala", "naal", "mani", "kaalai", "maalai", "iravu", "inniku", "netru", "naalaiku", "rendu", "moonu", "naalu", "anju",
    "la", "le", "ley", "nu", "dhaan", "thaan", "dhaane", "kooda", "moththa", "mothama", "mattum", "mattuma", "fulla", "fullah",
    "sandhai", "kovil", "pallikoodam", "maram", "annur", "gandhipuram", "peelamedu", "singanallur", "kinathukadavu"
}

TANGLISH_ROOT_PATTERNS = [
    r'\b(?:thann|kudin|kudik|thanneer)',
    r'\b(?:varal|varave|vara\b|varla|varudh|varang)',
    r'\b(?:matin|maaten|maatin|maatik|maatend|mudiyal)',
    r'\b(?:odanj|udanj|valiy|theng|adaich|eriyal|ananj)',
    r'\b(?:theru|salai|kupp|sakkad|vilakk|pallam|gundu)',
    r'\b(?:iruk|illai|illa\b|illay|aachu|pochu|poidu|aagud|vandhu)',
    r'\b(?:enga|inga|unga|namma|veetl|veetu|enaku|unak)',
    r'\b(?:pannu|seiyu|sollu|solr|kitta|pakkam|pakath)',
    r'\b(?:naala|rendu|moonu|naalu|aama|seri\b|vendaam)',
    r'\b[a-zA-Z]+(?:-la|la|le|-kitta|kitta|-pakkam|pakkam|-ah|ah|-ye|ye)\b'
]

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

    # Match exact Tanglish dictionary keywords or roots
    tanglish_matches = 0
    for w in words:
        if w in TANGLISH_KEYWORDS or any(re.search(pat, w) for pat in TANGLISH_ROOT_PATTERNS):
            tanglish_matches += 1

    english_matches = sum(1 for w in words if w in ENGLISH_INDICATORS)

    # Check for strong Tanglish grammatical particle phrases like '... la ...', '... kitta ...', '-ah', '-ye'
    has_tanglish_particles = bool(re.search(r'\b(?:la|le|kitta|pakkam|nu|dhaan|thaan|aama|seri|illa|matingithu|varala|thanni|thanniye)\b', cleaned.lower()))

    # If sentence has Tanglish markers or matches
    if tanglish_matches > 0 or has_tanglish_particles:
        if tanglish_matches >= english_matches or has_tanglish_particles:
            return "Tanglish", min(0.98, 0.75 + (tanglish_matches * 0.1))

    # If sentence is predominantly standard English words
    if english_matches > tanglish_matches and english_matches > 0:
        return "English", 0.95

    return "English", 0.85


class LanguageService:
    @staticmethod
    def detect_language(text: str) -> Tuple[str, float]:
        return detect_language(text)

    @staticmethod
    def is_tamil_script(text: str) -> bool:
        return is_tamil_script(text)


language_service = LanguageService()

