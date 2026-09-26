import re
import unicodedata

# Common phonetic mapping for Tanglish variations and speech recognition artifacts
PHONETIC_NORMALIZATION = {
    # Water supply terms
    r"\bthani\b": "thanni",
    r"\bthanneer\b": "thanni",
    r"\bkudineeru?\b": "kudineer",
    r"\bthannila\b": "thanni",
    r"\bthanniye\b": "thanni",
    # Negation & Action verbs
    r"\bvarla\b": "varala",
    r"\bvaralaye\b": "varala",
    r"\bvarave\s*illa\b": "varala",
    r"\bvaramatenguthu\b": "varala",
    r"\bvaramaatingudhu\b": "varala",
    r"\bvaramatenguranga\b": "varala",
    r"\bvara\s*maatinguthu\b": "varala",
    r"\bvarudhilla\b": "varala",
    r"\bmatingithu\b": "mudiyala",
    r"\bmaatikuthu\b": "adaichuruchu",
    # Road, Potholes & Infrastructure
    r"\bpalame\b": "pallam",
    r"\bgundhum\b": "gundu",
    r"\bgundu\s*kuliyuma?\b": "gundu kuliyum",
    r"\bsala\b": "salai",
    r"\btheruvula\b": "theru",
    r"\btherula\b": "theru",
    # Sanitation, Garbage & Drainage
    r"\bkuppe\b": "kuppai",
    r"\bsakadai\b": "sakkadai",
    r"\bsaakadai\b": "sakkadai",
    r"\bsakkada\b": "sakkadai",
    r"\badaippu\b": "adaichuruchu",
    r"\badaichikichu\b": "adaichuruchu",
    # Electricity & Streetlights
    r"\bvelaku\b": "vilakku",
    r"\bvilaku\b": "vilakku",
    r"\beriyalaye\b": "eriyala",
    r"\beriyave\s*illa\b": "eriyala",
    r"\bcurrant\b": "current",
    r"\bcurant\b": "current",
    r"\bcurrent\s*illa\b": "power cut",
    r"\bcurrent\s*varala\b": "power cut",
    r"\bpower\s*cut-ah\b": "power cut",
    # Urgency & Danger
    r"\bavasharam\b": "avasaram",
    r"\baabaththu\b": "aabathu",
    r"\baapathu\b": "aabathu",
    r"\bnaaye\b": "naai",
    r"\burgent-ah\b": "urgent",
    r"\burgenta\b": "urgent",
    r"\budaney\b": "udane",
    r"\bseekiram\b": "seekiram",
    # Street & Area STT speech artifacts
    r"\bcross\s*cutting\b": "cross cut road",
    r"\bcross\s*cut\b": "cross cut road",
    r"\bcrosscut\b": "cross cut road",
    r"\b100\s*feet\b": "100 feet road",
    r"\bhundred\s*feet\b": "100 feet road",
    r"\b100\s*ft\b": "100 feet road",
    r"\b100ft\b": "100 feet road",
    r"\bseventh\s*street\b": "7th street",
}

# Filler particles and prefixes that STT might erroneously attach before place names
LOCATION_PREFIX_STRIPPERS = [
    r'^(?:in\s+the|in\s+this|on\s+the|at\s+the|at|in|near\s+the)\s+',
    r'^(?:இந்த|அந்த|எங்கள்|என்|எங்க|நம்ம|இங்க)\s+',
    r'^(?:inda|indha|andha|enga|unga|namma|inga)\s+',
]


def clean_transcription(text: str) -> str:
    """
    Intelligently cleans, normalizes, and corrects speech-to-text transcriptions
    (similar to how LLMs like ChatGPT and Gemini polish raw speech transcripts):
    1. Normalizes Unicode representations (NFC)
    2. Corrects common speech-to-text acoustic mishearings (e.g., 'cross cutting' -> 'Cross Cut Road')
    3. Normalizes Tanglish phonetic variations (e.g., 'thanni varla' -> 'thanni varala')
    4. Cleans out speech fillers ('umm', 'uhh', 'like', 'er')
    5. Cleans erroneous locative prefixes attached to place names
    """
    if not text:
        return ""

    # Normalize Unicode (NFC)
    cleaned = unicodedata.normalize("NFC", text.strip())

    # Remove acoustic speech fillers
    cleaned = re.sub(r'\b(?:umm+|uhh+|ah+|err+|hmm+)\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^(?:like\s*,?|you\s*know\s*,?|basically\s*,?)\s*', '', cleaned, flags=re.IGNORECASE)

    # Correct STT common acoustic misrecognitions in Tamil, Tanglish and English
    stt_corrections = [
        # Tamil STT phonetic mishearings
        (r'காந்தி\s*தம்பியின்\s*வரவில்லை', 'காந்திபுரத்தில் தண்ணீர் வரவில்லை'),
        (r'காந்தி\s*தம்பியின்\s*வரல', 'காந்திபுரத்தில் தண்ணீர் வரவில்லை'),
        (r'காந்தி\s*தம்பியின்\s*பிரச்சனை', 'காந்திபுரத்தில் தண்ணீர் பிரச்சினை'),
        (r'காந்தி\s*தம்பியின்', 'காந்திபுரம் தண்ணீர்'),
        (r'காந்தி\s*தம்பி\s*தண்ணீர்', 'காந்திபுரம் தண்ணீர்'),
        (r'காந்தி\s*தம்பி', 'காந்திபுரம்'),
        (r'காந்திபுரம்\s*தம்பியின்', 'காந்திபுரத்தில் தண்ணீர்'),
        (r'காந்திபுரம்\s*தம்பி', 'காந்திபுரம் தண்ணீர்'),
        (r'காந்திபுரத்தில\s*தம்பி', 'காந்திபுரத்தில் தண்ணீர்'),
        (r'காந்திபுரத்தில்\s*தம்பி', 'காந்திபுரத்தில் தண்ணீர்'),
        (r'காந்தி\s*புரத்தில', 'காந்திபுரத்தில்'),
        (r'காந்தி\s*புரத்துல', 'காந்திபுரத்தில்'),
        (r'காந்தி\s*புரம்', 'காந்திபுரம்'),
        (r'காந்திபுரத்துல', 'காந்திபுரம்'),
        (r'தம்பியின்\s*வரவில்லை', 'தண்ணீர் வரவில்லை'),
        (r'தம்பியின்\s*வரல', 'தண்ணீர் வரவில்லை'),
        (r'தம்பியின்\s*பிரச்சனை', 'தண்ணீர் பிரச்சினை'),
        (r'தம்பி\s*வரல', 'தண்ணீர் வரவில்லை'),
        (r'\bதண்ணி\s*வரல\b', 'தண்ணீர் வரவில்லை'),
        (r'\bதண்ணி\s*வரவில்லை\b', 'தண்ணீர் வரவில்லை'),
        (r'\bதண்ணி\s*பிரச்சனை\b', 'தண்ணீர் பிரச்சினை'),
        (r'\bகரண்ட்\s*போச்சு\b', 'மின்சாரம் தடை'),
        (r'\bகரண்ட்\s*இல்ல\b', 'மின்சாரம் தடை'),
        (r'\bகுப்ப\s*அள்ளல\b', 'குப்பை அள்ளப்படவில்லை'),
        (r'\bரோடு\s*டேமேஜ்\b', 'சாலை சேதம்'),
        (r'\bரோட்ல\s*பள்ளம்\b', 'சாலையில் பள்ளம்'),
        # Tanglish & English STT corrections
        (r'\bgandhi\s*thambiyin\b', 'Gandhipuram thanni'),
        (r'\bgandhi\s*thambi\b', 'Gandhipuram thanni'),
        (r'\bgandhi\s*puram\b', 'Gandhipuram'),
        (r'\bgandipuram\b', 'Gandhipuram'),
        (r'\bcross\s*cutting\b', 'Cross Cut Road'),
        (r'\bcross\s*cut\b', 'Cross Cut Road'),
        (r'\bcrosscut\b', 'Cross Cut Road'),
        (r'\b100\s*feet\s*road\b', '100 Feet Road'),
        (r'\b100\s*feet\b', '100 Feet Road'),
        (r'\bhundred\s*feet\b', '100 Feet Road'),
        (r'\b100\s*ft\s*road\b', '100 Feet Road'),
        (r'\bgandhipuram\s*stand\b', 'Gandhipuram Bus Stand'),
        (r'\bgandhipuram\s*bus\s*stand\b', 'Gandhipuram Bus Stand'),
        (r'\bpeelamedu\s*airport\b', 'Coimbatore Airport, Peelamedu'),
    ]
    for pattern, replacement in stt_corrections:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

    # Collapse multiple whitespaces and punctuation artifacts
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\s+([,\.\?!])', r'\1', cleaned)

    return cleaned.strip()


def normalize_text(text: str) -> str:
    """
    Cleans and normalizes text for semantic classification and entity extraction:
    - Normalizes Unicode forms
    - Preserves Tamil characters
    - Normalizes whitespace and common Tanglish phonetic variations
    """
    if not text:
        return ""

    # First clean speech artifacts
    cleaned = clean_transcription(text)

    # Lowercase Latin text while preserving Tamil intact
    lowered = cleaned.lower()

    # Apply phonetic Tanglish normalization
    for pattern, replacement in PHONETIC_NORMALIZATION.items():
        lowered = re.sub(pattern, replacement, lowered, flags=re.IGNORECASE)

    return lowered.strip()


class NormalizationService:
    @staticmethod
    def clean_transcription(text: str) -> str:
        return clean_transcription(text)

    @staticmethod
    def normalize_text(text: str) -> str:
        return normalize_text(text)


normalization_service = NormalizationService()



