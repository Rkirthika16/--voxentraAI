import re
import unicodedata
from typing import Optional, List, Dict, Tuple
from rapidfuzz import fuzz

# Comprehensive list of Tamil Nadu locations, districts and landmarks with GPS coordinates
KNOWN_LOCATIONS = [
    # Thiruvarur
    {
        "name": "Thiruvarur Central, Tamil Nadu",
        "latitude": "10.772500",
        "longitude": "79.636500",
        "keywords": ["thiruvarur", "tiruvarur", "திருவாரூர்", "திருவாரூர்ல"]
    },
    # Coimbatore & Landmarks
    {
        "name": "Gandhipuram Central Bus Stand, Coimbatore",
        "latitude": "11.014092",
        "longitude": "76.966940",
        "keywords": ["gandhipuram", "காந்திபுரம்", "gandhipuram bus stand"]
    },
    {
        "name": "RS Puram, Coimbatore",
        "latitude": "11.008321",
        "longitude": "76.949056",
        "keywords": ["rs puram", "r s puram", "rspuram", "ஆர் எஸ் புரம்", "ஆர்.எஸ்.புரம்"]
    },
    {
        "name": "Ukkadam Bus Stand, Coimbatore",
        "latitude": "10.988220",
        "longitude": "76.960240",
        "keywords": ["ukkadam", "உக்கடம்", "ukkadam bus stand"]
    },
    {
        "name": "Peelamedu, Coimbatore",
        "latitude": "11.026110",
        "longitude": "77.008240",
        "keywords": ["peelamedu", "பீளமேடு"]
    },
    {
        "name": "Mettupalayam, Coimbatore",
        "latitude": "11.300000",
        "longitude": "76.950000",
        "keywords": ["mettupalayam", "மேட்டுப்பாளையம்", "மேட்டுப்பாளையம் ஊராட்சி"]
    },
    {
        "name": "Perur, Coimbatore",
        "latitude": "10.970000",
        "longitude": "76.910000",
        "keywords": ["perur", "பேரூர்"]
    },
    {
        "name": "Pollachi, Coimbatore",
        "latitude": "10.660000",
        "longitude": "77.010000",
        "keywords": ["pollachi", "பொள்ளாச்சி"]
    },

    # Chennai & Major Areas
    {
        "name": "T Nagar, Chennai",
        "latitude": "13.041800",
        "longitude": "80.234100",
        "keywords": ["t nagar", "t.nagar", "தி நகர்", "தி.நகர்"]
    },
    {
        "name": "Anna Nagar, Chennai",
        "latitude": "13.085000",
        "longitude": "80.210100",
        "keywords": ["anna nagar", "அண்ணா நகர்"]
    },
    {
        "name": "Guindy, Chennai",
        "latitude": "13.006700",
        "longitude": "80.202500",
        "keywords": ["guindy", "கிண்டி"]
    },
    {
        "name": "Velachery, Chennai",
        "latitude": "12.981500",
        "longitude": "80.218000",
        "keywords": ["velachery", "வேளச்சேரி"]
    },
    {
        "name": "Tambaram, Chennai",
        "latitude": "12.924900",
        "longitude": "80.100000",
        "keywords": ["tambaram", "தாம்பரம்"]
    },
    {
        "name": "Mylapore, Chennai",
        "latitude": "13.036800",
        "longitude": "80.267600",
        "keywords": ["mylapore", "மயிலாப்பூர்"]
    },

    # Madurai
    {
        "name": "Madurai Central, Tamil Nadu",
        "latitude": "9.925200",
        "longitude": "78.119800",
        "keywords": ["madurai", "மதுரை", "மாட்டுத்தாவணி", "mattuthavani", "கோரிப்பாளையம்", "goripalayam"]
    },

    # Tiruchirappalli (Trichy)
    {
        "name": "Tiruchirappalli (Trichy) Central",
        "latitude": "10.790500",
        "longitude": "78.704700",
        "keywords": ["trichy", "tiruchirappalli", "திருச்சி", "திருச்சிராப்பள்ளி", "srirangam", "ஸ்ரீரங்கம்"]
    },

    # Salem
    {
        "name": "Salem Central, Tamil Nadu",
        "latitude": "11.664300",
        "longitude": "78.146000",
        "keywords": ["salem", "சேலம்", "salem junction", "ஆத்தூர்", "athoor", "attur"]
    },

    # Tirunelveli
    {
        "name": "Tirunelveli Central, Tamil Nadu",
        "latitude": "8.713900",
        "longitude": "77.756700",
        "keywords": ["tirunelveli", "நெல்லை", "திருநெல்வேலி", "palayamkottai", "பாளை"]
    },

    # Erode & Tiruppur
    {
        "name": "Erode Central, Tamil Nadu",
        "latitude": "11.341000",
        "longitude": "77.717200",
        "keywords": ["erode", "ஈரோடு"]
    },
    {
        "name": "Tiruppur Central, Tamil Nadu",
        "latitude": "11.108500",
        "longitude": "77.341100",
        "keywords": ["tiruppur", "tirupur", "திருப்பூர்"]
    },

    # Thanjavur & Delta Districts
    {
        "name": "Thanjavur Central, Tamil Nadu",
        "latitude": "10.787000",
        "longitude": "79.137800",
        "keywords": ["thanjavur", "tanjore", "தஞ்சாவூர்", "தஞ்சை"]
    },
    {
        "name": "Nagapattinam, Tamil Nadu",
        "latitude": "10.767200",
        "longitude": "79.844900",
        "keywords": ["nagapattinam", "நாகப்பட்டினம்"]
    },
    {
        "name": "Mayiladuthurai, Tamil Nadu",
        "latitude": "11.107500",
        "longitude": "79.652400",
        "keywords": ["mayiladuthurai", "மயிலாடுதுறை"]
    },

    # Vellore & Northern Districts
    {
        "name": "Vellore Central, Tamil Nadu",
        "latitude": "12.916500",
        "longitude": "79.132500",
        "keywords": ["vellore", "வேலூர்", "katpadi", "காட்பாடி"]
    },
    {
        "name": "Kanchipuram, Tamil Nadu",
        "latitude": "12.834200",
        "longitude": "79.703600",
        "keywords": ["kanchipuram", "காஞ்சிபுரம்"]
    },
    {
        "name": "Tiruvannamalai, Tamil Nadu",
        "latitude": "12.225300",
        "longitude": "79.074700",
        "keywords": ["tiruvannamalai", "திருவண்ணாமலை"]
    },
    {
        "name": "Dindigul, Tamil Nadu",
        "latitude": "10.367300",
        "longitude": "77.980300",
        "keywords": ["dindigul", "திண்டுக்கல்"]
    },
    {
        "name": "Kanyakumari / Nagercoil",
        "latitude": "8.183300",
        "longitude": "77.411900",
        "keywords": ["kanyakumari", "nagercoil", "கன்னியாகுமரி", "நாகர்கோவில்"]
    }
]


def extract_location(text: str) -> Tuple[Optional[str], Optional[str], Optional[str], float]:
    """
    Extracts location and coordinates from complaint text with support for Tamil/Tanglish suffixes (-la, -il).
    Returns: (location_name, latitude, longitude, confidence)
    """
    if not text:
        return None, None, None, 0.0

    raw = text.strip()
    lowered = raw.lower()
    norm_text = unicodedata.normalize("NFC", lowered)

    # 1. Exact & Substring Keyword Matching
    best_loc = None
    highest_score = 0.0

    for loc in KNOWN_LOCATIONS:
        for kw in loc["keywords"]:
            kw_norm = unicodedata.normalize("NFC", kw.lower())
            
            # Direct match
            if kw_norm in norm_text:
                score = 0.98 if kw_norm == norm_text else 0.95
                if score > highest_score:
                    highest_score = score
                    best_loc = loc
            
            # Suffix stripped matching (e.g. திருவாரூர்ல -> திருவாரூர்)
            # Strip common Tamil & Tanglish locative suffixes (-la, -il, -le, -la)
            tamil_base = re.sub(r'(?:ல|இல்|இடம்|பக்கம்|அருகே)$', '', kw_norm)
            if len(tamil_base) >= 4 and tamil_base in norm_text:
                score = 0.92
                if score > highest_score:
                    highest_score = score
                    best_loc = loc

    if best_loc:
        return best_loc["name"], best_loc["latitude"], best_loc["longitude"], highest_score

    # 2. Fuzzy Token Matching
    for loc in KNOWN_LOCATIONS:
        for kw in loc["keywords"]:
            kw_norm = unicodedata.normalize("NFC", kw.lower())
            ratio = fuzz.token_set_ratio(kw_norm, norm_text)
            if ratio >= 80 and (ratio / 100.0) > highest_score:
                highest_score = ratio / 100.0
                best_loc = loc

    if best_loc and highest_score >= 0.80:
        return best_loc["name"], best_loc["latitude"], best_loc["longitude"], round(highest_score, 2)

    # 3. Fallback regex for "near <Word>", "<Word>-la", "at <Word>", "<Word> pakkam"
    location_patterns = [
        r'(?:near|at|opposite|in|around)\s+([A-Za-z0-9\s]{3,20})(?:\s+street|\s+road|\s+area|\s+nagar|\s+colony|\b)',
        r'([A-Za-z0-9]+)\s*-\s*la\b',
        r'([A-Za-z0-9]+)\s+pakkam\b',
        r'([A-Za-z0-9]+)\s+kitta\b',
        r'([\u0B80-\u0BFF]{3,15})ல\b'
    ]

    for pattern in location_patterns:
        match = re.search(pattern, norm_text)
        if match:
            candidate = match.group(1).strip()
            if candidate and len(candidate) > 2 and candidate.lower() not in ["romba", "periya", "chinna", "the", "that", "this"]:
                return candidate.title() if candidate.isascii() else candidate, None, None, 0.70

    return None, None, None, 0.0
