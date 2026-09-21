import re
import unicodedata
from typing import Dict, Tuple, List

# Comprehensive Multilingual Root Lexicon for Tamil Nadu Civic Classification
CATEGORY_ROOTS: Dict[str, Dict[str, List[str]]] = {
    "Water": {
        "tamil_roots": [
            "தண்ணீர்", "தண்ணி", "குடிநீர்", "குடிநீ", "குழாய்", "குழா", "பைப்", "லீக்",
            "வாட்டர்", "கைப்பம்பு", "கை பம்பு", "பம்பு", "மோட்டார்", "மோட்டா", "கிணறு",
            "ஆழ்துளை", "கசிவு", "நீர் கசிவு", "குடிநீர் தொட்டி", "நீர் விநியோகம்", "குடிநீர்",
            "நீர் வரவில்லை", "நீர் தட்டுப்பாடு", "குழாய் உடை", "நீர்", "தண்ணி வரல", "உடைஞ்சு",
            "பைப் லீக்", "வாட்டர் டேங்க்", "குழாயில் தண்ணீர்", "தண்ணீர் பிரச்சனை", "தண்ணி பிரச்சனை",
            "குடிநீர் குழாய்", "பைப் உடைப்பு", "மோட்டார் பழுது", "தண்ணீர் வரல"
        ],
        "tanglish_roots": [
            "thann", "thani", "thanni", "kudineer", "pipe", "leak", "leakage", "valiyuthu", "odanju", "varala",
            "water", "tap", "borewell", "handpump", "motor", "kinaru", "sump", "tank",
            "kudikka thanni", "twad", "pipeline", "pressure", "water supply", "pipe odanju",
            "water problem", "water issue", "water leak", "thanni varala", "no water", "drinking water"
        ],
        "english_roots": [
            "water", "pipe", "pipes", "leak", "leaks", "leakage", "drinking water", "tap", "taps",
            "water supply", "contamination", "pipeline", "water pressure", "valves", "broken pipe",
            "burst pipe", "borewell", "handpump", "hand pump", "twad", "water tank", "sump",
            "motor repair", "well", "submersible", "no water", "water shortage", "water crisis",
            "water problem", "water issue", "dirty water"
        ]
    },
    "Electricity": {
        "tamil_roots": [
            "மின்", "மின்சாரம்", "மின்வெட்டு", "மின்வெ", "கரண்ட்", "கரண்டு", "கரண்",
            "டிரான்ஸ்பார்மர்", "டிரான்ஸ்பார்", "மின்மாற்றி", "தீப்பொறி", "ஸ்பார்க்",
            "மின் கம்பி", "மின் கம்பம்", "அறுந்த கம்பி", "மின்னழுத்தம்", "மின்னழுத்த",
            "மின்சார வாரியம்", "மின் இணைப்பு", "வயல் மின்", "விவசாய மின்", "ஈபி",
            "பவர் கட்", "ஒயர்", "கரண்ட் கட்", "கரண்ட் போச்சு", "கரண்ட் இல்ல",
            "மின் தடை", "மின் பிரச்சனை", "கரண்ட் பிரச்சனை", "பவர் போச்சு", "டிஎன்பி"
        ],
        "tanglish_roots": [
            "current", "curr", "power", "eb", "tangedco", "tneb", "wire", "spark", "transformer", "transfarmer",
            "fuse", "voltage", "current cut", "current poiduchu", "current varala", "current illa",
            "shock", "kambam", "power cut", "blackout", "live wire", "dangling wire", "electric",
            "electricity", "power problem", "current problem", "current issue", "power outage", "low voltage"
        ],
        "english_roots": [
            "electricity", "electric", "power", "power cut", "current", "wire", "wires", "spark",
            "transformer", "voltage", "power outage", "blackout", "live wire", "electric shock",
            "meter", "short circuit", "dangling wire", "fuse", "low voltage", "eb", "tangedco",
            "tneb", "electric pole", "agricultural power", "current cut", "current problem", "power issue",
            "electricity problem", "high voltage", "power failure"
        ]
    },
    "Roads": {
        "tamil_roots": [
            "சாலை", "சாலைகள்", "ரோடு", "ரோட்டு", "பள்ளம்", "பள்ள", "குழி", "குழிகள்", "தார் சாலை", "மண் சாலை",
            "கிராம சாலை", "பாலம்", "சிறு பாலம்", "நடைபாதை", "சாலை விபத்து", "குண்டும்",
            "குழியும்", "சேதமடைந்த சாலை", "வேகத்தடை", "ரோடு டேமேஜ்", "ரோடு உடைஞ்சு",
            "ஸ்பீடு பிரேக்கர்", "தார் ரோடு", "பேருந்து", "பஸ் வசதி", "சாலை வசதி", "ரோடு சரியில்ல"
        ],
        "tanglish_roots": [
            "road", "roads", "pallam", "salai", "gundu", "kuli", "kuzhi", "thar road", "tar road",
            "speed breaker", "pothole", "potholes", "mann road", "grama salai", "panchayat road",
            "paalam", "bridge", "vandi poda mudiyala", "asphalt", "road damage", "road problem",
            "road repair", "road issue", "bad road", "broken road"
        ],
        "english_roots": [
            "road", "roads", "pothole", "potholes", "asphalt", "crater", "craters", "broken road",
            "damaged road", "speed breaker", "sidewalk", "pavement", "tar road", "highway",
            "accident spot", "culvert", "mud road", "village road", "panchayat road", "road problem",
            "road issue", "road condition", "road work"
        ]
    },
    "Sanitation/Garbage": {
        "tamil_roots": [
            "குப்பை", "குப்பைகள்", "குப்ப", "கழிவு", "துர்நாற்றம்", "துர்நாற்ற", "நாற்றம்", "நாற்ற",
            "குப்பைத்தொட்டி", "தூய்மை", "தூய்ம", "திடக்கழிவு", "சுத்தம்", "சாக்கடை குப்பை",
            "கிராம தூய்மை", "கொசு", "கொசு தொல்லை", "கழிவு கொட்டு", "அள்ளவில்லை",
            "வேஸ்ட்", "டஸ்ட்பின்", "கழிவு மேலாண்மை", "துப்புரவு", "துப்புரவு பணியாளர்", "கொசு மருந்து"
        ],
        "tanglish_roots": [
            "kuppa", "kuppai", "waste", "dustbin", "garbage", "trash", "naaththam", "smell", "dump",
            "clean pannala", "kosu", "mosquito", "cleanliness", "sweep", "kuppai thotti",
            "garbage problem", "garbage issue", "waste problem", "cleaning", "thuppuravu"
        ],
        "english_roots": [
            "garbage", "waste", "trash", "cleanliness", "stench", "litter",
            "dump yard", "dumping", "plastic waste", "dead animal", "dustbin", "sweep",
            "solid waste", "smell", "bad smell", "sanitation", "mosquito menace", "mosquitoes",
            "garbage problem", "garbage issue", "garbage collection", "cleaning", "unhygienic"
        ]
    },
    "Drainage": {
        "tamil_roots": [
            "சாக்கடை", "சாக்கட", "வடிகால்", "வடிகா", "கழிவுநீர்", "கழிவுநீ", "சாக்கடை அடைப்பு",
            "வடிகால் அடைப்பு", "கழிவுநீர் வழிதல்", "தேங்கிய நீர்", "வாய்க்கால்", "வாய்க்கா",
            "பாசன வாய்க்கால்", "ஓடை", "கால்வாய்", "கால்வா", "கால்வாய் அடைப்பு",
            "சாக்கடை நீர்", "ட்ரைனேஜ்", "ட்ரைனேஜ் அடைப்பு", "கட்டர்", "வடிகால் தூர்வார",
            "சாக்கடை நாற்றம்", "கழிவு நீர் தேக்கம்"
        ],
        "tanglish_roots": [
            "sakkada", "sakkadai", "drain", "drainage", "gutter", "sewage", "sewer", "adaippu", "thengi",
            "valiyuthu", "sewage leak", "vaykal", "odai", "kaalvai", "waterlogging",
            "drainage overflow", "drainage adaippu", "drainage problem", "drain blocked", "gutter leak"
        ],
        "english_roots": [
            "drain", "drainage", "gutter", "sewage", "overflow", "stormwater",
            "blocked drain", "sewer", "stagnant water", "choked", "drainage water",
            "waterlogging", "canal", "irrigation canal", "culvert blockage", "drainage problem",
            "drainage overflow", "drainage issue", "choked drain", "sewerage"
        ]
    },
    "Streetlights": {
        "tamil_roots": [
            "தெருவிளக்கு", "தெரு விளக்கு", "தெருவிள", "விளக்கு", "விளக்", "ஸ்ட்ரீட் லைட்", "ஸ்ட்ரீட்லைட்",
            "ஸ்ட்ரீட்", "லைட்", "லைட்டு", "லைட்ஸ்", "விளக்கு எரியவில்லை", "எரியல", "எரியவில்லை",
            "இருட்டாக", "இருட்டு", "இருள்", "விளக்கு பழுது", "மின் விளக்கு", "வெளிச்சமில்லை",
            "ஊராட்சி தெருவிளக்கு", "விளக்கு கம்பம்", "சோலார் விளக்கு", "பல்பு", "பல்ப்",
            "தெரு விளக்குகள்", "லைட் எரியல", "ஸ்ட்ரீட் லைட் எரியல", "விளக்குகள்"
        ],
        "tanglish_roots": [
            "street light", "streetlight", "street lights", "streetlights", "vilakku", "theru vilakku",
            "eriyala", "dark", "iruttu", "bulb", "post light", "pole light", "light vela seiyala",
            "light eriyala", "lamp", "light poiduchu", "street light prachana", "light problem",
            "light issue", "lights", "light", "theru light"
        ],
        "english_roots": [
            "streetlight", "street light", "streetlights", "street lights", "lamp post", "dark street",
            "street lamp", "light not working", "bulb broken", "flickering light", "lighting",
            "darkness", "solar light", "panchayat light", "light problem", "light issue",
            "street lighting", "pole light", "light", "lights", "lamp", "streetlamp", "no light"
        ]
    },
    "Public Safety": {
        "tamil_roots": [
            "தீ", "தீ விபத்து", "விபத்து", "ஆபத்து", "அவசரம்", "மரம் விழு", "மரம் விழுந்தது",
            "வெறிநாய்", "நாய் தொல்லை", "நாய் கடி", "தெரு நாய்", "பாம்பு", "பாம்பு கடி",
            "108 ஆம்புலன்ஸ்", "ஆரம்ப சுகாதார", "மருத்துவமனை", "அவசர சிகிச்சை",
            "உயிருக்கு ஆபத்து", "ரேஷன்", "ரேஷன் கடை", "அரிசி", "பருப்பு", "நியாய விலைக்கடை",
            "சர்க்கரை", "காவல்துறை", "போலீஸ்"
        ],
        "tanglish_roots": [
            "thee", "fire", "accident", "aabathu", "aapathu", "avasaram", "danger", "dog",
            "naai", "dog bite", "paambu", "snake", "ambulance", "hospital", "phc", "aaspattiri",
            "ration", "ration shop", "arisi", "paruppu", "fair price", "police", "theft"
        ],
        "english_roots": [
            "fire", "accident", "emergency", "danger", "hazard", "collapsed",
            "fallen tree", "dog menace", "stray dogs", "unsafe", "threat", "life danger",
            "snake", "hospital", "ambulance", "primary health centre", "phc", "ration", "ration shop",
            "rice", "sugar", "pds", "police", "emergency safety"
        ]
    }
}

CATEGORY_KEYWORDS = CATEGORY_ROOTS

DEPARTMENT_MAPPING = {
    "Water": "Water Supply & Sewage Department",
    "Electricity": "Electricity & Power Department",
    "Roads": "Roads & Transport Department",
    "Sanitation/Garbage": "Sanitation & Solid Waste Department",
    "Drainage": "Drainage & Stormwater Department",
    "Streetlights": "Street Lighting Department",
    "Public Safety": "Public Safety & Emergency Department",
    "Other": "General Administration Department"
}


def classify_complaint(text: str) -> Tuple[str, str, float]:
    """
    Classifies civic complaint text into precise categories using multilingual morphological root matching.
    Returns: (category, department_name, confidence)
    """
    if not text or not text.strip():
        return "Other", DEPARTMENT_MAPPING["Other"], 0.0

    raw = text.strip()
    lowered = raw.lower()
    normalized_nfc = unicodedata.normalize("NFC", lowered)

    scores: Dict[str, float] = {cat: 0.0 for cat in CATEGORY_ROOTS}

    for category, lang_dict in CATEGORY_ROOTS.items():
        # 1. Tamil Morphological Roots (Substring Matching for Agglutinative suffixes & Transliterations)
        for root in lang_dict["tamil_roots"]:
            norm_root = unicodedata.normalize("NFC", root.lower())
            if norm_root in normalized_nfc:
                # Longer root matches give higher confidence
                weight = 5.0 if len(norm_root) >= 4 else 3.5
                scores[category] += weight

        # 2. Tanglish Roots
        for root in lang_dict["tanglish_roots"]:
            r = root.lower()
            if " " in r:
                if r in lowered:
                    scores[category] += 4.5
            elif len(r) >= 4:
                if r in lowered:
                    scores[category] += 3.5
            else:
                # Short word boundary
                if re.search(r'\b' + re.escape(r), lowered):
                    scores[category] += 2.5

        # 3. English Roots
        for root in lang_dict["english_roots"]:
            r = root.lower()
            if " " in r:
                if r in lowered:
                    scores[category] += 4.5
            elif len(r) >= 4:
                if r in lowered:
                    scores[category] += 3.0
            else:
                if re.search(r'\b' + re.escape(r) + r'\b', lowered):
                    scores[category] += 2.0

    # Find highest scoring category
    best_category = "Other"
    max_score = 0.0

    for category, score in scores.items():
        if score > max_score:
            max_score = score
            best_category = category

    if max_score == 0.0:
        return "Other", DEPARTMENT_MAPPING["Other"], 0.35

    confidence = min(0.99, 0.70 + (max_score * 0.04))
    return best_category, DEPARTMENT_MAPPING[best_category], confidence
