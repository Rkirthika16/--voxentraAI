import re
from typing import Tuple, Optional

# Pure Tanglish keywords & particles (Tamil words written phonetically in Latin/Roman script)
TANGLISH_KEYWORDS = {
    "thanni", "thani", "thanneer", "thanniye", "thanneere", "neer", "kudineer", "kudika", "kudikka", "kudikira",
    "varala", "varla", "vara", "varadhu", "varudhu", "varave", "varudhunga", "varangala", "varalaam", "vandhuchu",
    "aagala", "aagadhu", "aagudhu", "aaguthu", "aachu", "aayiduchu", "aana", "aaganum", "aayittu", "aagikittu",
    "matingithu", "maatenguthu", "maatingudhu", "maatenghuthu", "maatikuthu", "maatendhu", "mudiyala", "mudiyadhu",
    "odanju", "odanjiduchu", "odanjuruchu", "udanjiduchu", "udanjuruchu", "valiyuthu", "valiyudhu", "valiyithu",
    "thengi", "thengudhu", "theengudhu", "nikkuthu", "odudhu", "adaichu", "adaichuruchu", "adaichikichu", "adaippu",
    "salai", "pallam", "gundu", "kuliyum", "periya", "chinna", "romba", "mosam", "theru", "theruvil", "therula", "theruvula",
    "kuppai", "naaththam", "vaadai", "alli", "podala", "allala", "clean", "suththam", "allamaatenguranga",
    "sakkadai", "sakkada", "saakadai", "naatram", "kallu",
    "vilakku", "eriyala", "eriyave", "eriyudhu", "eriyadhu", "velicham", "iruttu", "illa", "illai", "illaye", "illanga", "arunthu", "pala",
    "aabathu", "aapathu", "avasaram", "thee", "vizhunthuduchu", "naai", "thollai", "kadi", "paambu", "kambam",
    "pakkam", "pakathula", "kitta", "udane", "seiyunga", "pannunga", "pannikonga", "pannalaam", "panren", "pannren", "panrom",
    "irukku", "iruku", "irukkunga", "irukka", "aaguthu", "aagudhu", "vandhuchu", "nadakuthu", "nadakkudhu",
    "endha", "enga", "inga", "unga", "enaku", "enakku", "ungalukku", "veedu", "veetla", "veetula", "sonna", "maatha", "maathanum",
    "seri", "sari", "seringa", "saringa", "aama", "aamam", "ama", "amam", "aamaa", "kandippa", "podunga", "vendaam", "paravala",
    "sollunga", "solren", "solreenga", "puriyala", "purinjukitten", "theriyala", "theriyadhu", "kettan",
    "naala", "naal", "naatkal", "mani", "kaalai", "maalai", "iravu", "inniku", "netru", "naalaiku", "nethu", "rendu", "moonu", "naalu", "anju",
    "la", "le", "ley", "nu", "dhaan", "thaan", "dhaane", "kooda", "moththa", "mothama", "mattum", "mattuma", "fulla", "fullah",
    "sandhai", "kovil", "pallikoodam", "maram"
}

TANGLISH_ROOT_PATTERNS = [
    r'\b(?:thann|kudin|kudik|thanneer)',
    r'\b(?:varal|varave|vara\b|varla|varudh|varang|vandh)',
    r'\b(?:aagal|aagad|aagud|aaguth|aachu|aayid|aagan)',
    r'\b(?:matin|maaten|maatin|maatik|maatend|mudiyal)',
    r'\b(?:odanj|udanj|valiy|theng|adaich|eriyal|ananj)',
    r'\b(?:theru|salai|kupp|sakkad|vilakk|pallam|gundu)',
    r'\b(?:iruk|illai|illa\b|illay|pochu|poidu|nadakk)',
    r'\b(?:enga|inga|unga|namma|veetl|veetu|enaku|unak)',
    r'\b(?:pannu|seiyu|sollu|solr|kitta|pakkam|pakath)',
    r'\b(?:naala|rendu|moonu|naalu|aama|seri\b|vendaam|theriy)',
    r'\b[a-zA-Z]+(?:-la|-le|-kitta|-pakkam|-ah|-aa|-ye|-lendhu|-nu|-dhaan|-thaan)\b',
    r'\b(?:full-ah|fulla|fullah|area-la|street-la|veetla)\b'
]

ENGLISH_INDICATORS = {
    "the", "is", "was", "are", "were", "there", "this", "that", "in", "on", "at", "to",
    "for", "of", "with", "from", "by", "about", "and", "or", "not", "have", "has", "had",
    "pipe", "water", "drainage", "garbage", "leak", "leaking", "broken", "road", "street",
    "light", "lamp", "electric", "pole", "current", "power", "cut", "problem", "issue",
    "complaint", "hospital", "school", "near", "opposite", "behind", "morning", "evening",
    "today", "yesterday", "daily", "frequent", "active", "status", "still", "hazard",
    "overflow", "overflowing", "dustbin", "avenue", "lane", "cross", "colony", "ward",
    "speaking", "english", "hello", "good", "please", "help", "register", "confirm",
    "entire", "whole", "accident", "danger", "since", "happening"
}


def is_tamil_script(text: str) -> bool:
    """Check if text contains Tamil Unicode characters (\u0B80-\u0BFF)."""
    tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', text))
    return tamil_chars > 0


def detect_language(text: str, current_session_lang: Optional[str] = None) -> Tuple[str, float]:
    """
    Accurately detects whether text is Tamil (script), Tanglish (Tamil in Latin script),
    or English.

    - Dynamically adapts across turns
    - Detects Tanglish markers, root verbs, and particles (-ah, -la, varala, work aagala)
    - Preserves established conversational language for short slot replies (e.g. 'Two days', 'RS Puram')
    Returns: (language_name, confidence)
    """
    if not text or not text.strip():
        return current_session_lang or "English", 0.0

    cleaned = text.strip()
    total_len = len(cleaned)
    tamil_chars = len(re.findall(r'[\u0B80-\u0BFF]', cleaned))

    # 1. Tamil Script Detection
    if tamil_chars > 0:
        return "Tamil", 0.98

    lowered = cleaned.lower()

    # 2. Strong Tanglish Particles & Suffix Patterns
    has_tanglish_particles = bool(re.search(
        r'(?:-\s*ah\b|-\s*aa\b|-\s*la\b|-\s*le\b|-\s*kitta\b|-\s*pakkam\b|-\s*nu\b|-\s*dhaan\b|-\s*thaan\b|-\s*lendhu\b|\b(?:full-ah|fulla|fullah|varala|varla|thanni|thani|aagala|aagudhu|aachu|aayiduchu|eriyala|adaichu|seri|aama|ama|aamam|illai|illa|rendu|moonu|naalu|naala|enga|unga|veetla|pannunga|seiyunga|solren|sollunga|theriyala|paravala|kitta|pakkam|lendhu)\b)',
        lowered
    ))

    # 3. Match word-level Tanglish keywords
    words = [w for w in re.findall(r'[a-zA-Z0-9\-]+', lowered)]
    tanglish_matches = 0
    for w in words:
        clean_w = w.replace("-", "")
        if clean_w in TANGLISH_KEYWORDS or any(re.search(pat, clean_w) for pat in TANGLISH_ROOT_PATTERNS):
            tanglish_matches += 1

    if has_tanglish_particles or tanglish_matches > 0:
        return "Tanglish", 0.98

    # 4. Contextual Session Stickiness for Short Responses
    # If the user replies with a short phrase like "Two days", "RS Puram", "Yes", "No", "100 Feet Road"
    # in an ongoing Tanglish or Tamil conversation, preserve the established conversational language!
    if current_session_lang and current_session_lang in ["Tanglish", "Tamil"]:
        if len(words) <= 4:
            # Short slot reply: keep conversation in citizen's chosen language
            return current_session_lang, 0.90

    # 5. English Grammar & Indicators
    english_matches = sum(1 for w in words if w in ENGLISH_INDICATORS)
    if english_matches > 0 or len(words) >= 3:
        return "English", 0.95

    # Default fallback
    if current_session_lang:
        return current_session_lang, 0.85

    return "English", 0.85


class LanguageService:
    @staticmethod
    def detect_language(text: str, current_session_lang: Optional[str] = None) -> Tuple[str, float]:
        return detect_language(text, current_session_lang)

    @staticmethod
    def is_tamil_script(text: str) -> bool:
        return is_tamil_script(text)


language_service = LanguageService()
