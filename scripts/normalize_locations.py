"""Normalization script for Coimbatore Location Intelligence data."""
import re
import unicodedata

TAMIL_STOPWORDS = {
    "la", "le", "ula", "kku", "ku", "il", "le", "pakkam", "pakkathula",
    "opposite", "near", "side", "theru", "road", "street", "nagar", "oor", "oorula"
}

ENGLISH_SUFFIXES = {
    "-la", "-le", "-kku", "-ku", "-il", "-ula"
}

WHISPER_SPEECH_CORRECTIONS = {
    "gandhi puram": "Gandhipuram",
    "gandhipuram la": "Gandhipuram",
    "gandhipuram-la": "Gandhipuram",
    "rs puram": "R.S. Puram",
    "r s puram": "R.S. Puram",
    "db road": "D.B. Road",
    "d b road": "D.B. Road",
    "saravanampatti": "Saravanampatti",
    "saravana patti": "Saravanampatti",
    "saravanampatty": "Saravanampatti",
    "race course": "Race Course",
    "saibaba colony": "Saibaba Colony",
    "sai baba colony": "Saibaba Colony",
    "peelamedu": "Peelamedu",
    "peela medu": "Peelamedu",
    "singanallur": "Singanallur",
    "singa nallur": "Singanallur",
    "marudhamalai": "Marudamalai",
    "marudamalai road": "Marudamalai Road",
    "thudiyalur": "Thudiyalur",
    "thudiya lur": "Thudiyalur",
    "ramanathapuram": "Ramanathapuram",
    "ramana thapuram": "Ramanathapuram",
    "selvapuram": "Selvapuram",
    "selva puram": "Selvapuram",
    "cross cut": "Cross Cut",
    "crosscut": "Cross Cut",
    "cross cut road": "Cross Cut Road",
    "100 feet road": "100 Feet Road",
    "hundred feet road": "100 Feet Road",
    "avinashi road": "Avinashi Road",
    "avinasi road": "Avinashi Road",
    "trichy road": "Trichy Road",
    "mettupalayam road": "Mettupalayam Road",
    "pollachi road": "Pollachi Road",
    "sathy road": "Sathy Road",
    "sathyamangalam road": "Sathy Road",
    "sivanandha colony": "Sivananda Colony",
    "sivananda colony": "Sivananda Colony",
    "sivanandhacolony": "Sivananda Colony",
    "ukkkadam": "Ukkadam",
    "ukkadam bus stand": "Ukkadam Bus Stand",
    "town hall": "Town Hall",
    "townhall": "Town Hall",
    "kavundampalayam": "Kavundampalayam",
    "goundampalayam": "Kavundampalayam",
    "kuniyamuthur": "Kuniyamuthur",
    "kuniyamuthur": "Kuniamuthur",
    "vadavalli": "Vadavalli",
    "vada valli": "Vadavalli",
    "sowripalayam": "Sowripalayam",
    "ganapathy": "Ganapathy",
    "ganapathi": "Ganapathy",
    "koundampalayam": "Kavundampalayam"
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s\u0B80-\u0BFF\.\-\/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def normalize_tanglish(text: str) -> str:
    """Standardizes Tanglish tokens and strips common speech affixes."""
    if not text:
        return ""
    t = text.lower().strip()
    
    # Strip common Tanglish location suffixes
    for suffix in ["-la", "-le", "-kku", "-ku", "-il", "-ula", " la", " le", " kku", " ku", " il"]:
        if t.endswith(suffix):
            t = t[:-len(suffix)].strip()
            
    # Normalize common phonetics
    t = re.sub(r"\bkaandhi\b", "gandhi", t)
    t = re.sub(r"\bganthi\b", "gandhi", t)
    t = re.sub(r"\bpuram\b", "puram", t)
    t = re.sub(r"\btheru\b", "street", t)
    t = re.sub(r"\bsalai\b", "road", t)
    t = re.sub(r"\bpaathai\b", "street", t)
    t = re.sub(r"\bkoil\b", "temple", t)
    t = re.sub(r"\bkovil\b", "temple", t)
    t = re.sub(r"\bmaruthuvamanai\b", "hospital", t)
    t = re.sub(r"\bpalli\b", "school", t)
    t = re.sub(r"\bkalloori\b", "college", t)
    t = re.sub(r"\bmaruthuvar\b", "hospital", t)
    
    # Handle Whisper multi-word spacing errors
    for mistake, correction in WHISPER_SPEECH_CORRECTIONS.items():
        pattern = r"\b" + re.escape(mistake) + r"\b"
        t = re.sub(pattern, correction.lower(), t, flags=re.IGNORECASE)
        
    return clean_text(t)

def normalize_tamil(text: str) -> str:
    """Normalizes Tamil Unicode text and removes locative case markers."""
    if not text:
        return ""
    t = clean_text(text)
    # Tamil locative markers: -இல் (il), -ல் (l), -க்கு (kku), -உக்கு (ukku)
    t = re.sub(r"([^\s]+)இல்$", r"\1", t)
    t = re.sub(r"([^\s]+)ல்$", r"\1", t)
    t = re.sub(r"([^\s]+)க்கு$", r"\1", t)
    t = re.sub(r"([^\s]+)உக்கு$", r"\1", t)
    t = re.sub(r"([^\s]+)த்தில்$", r"\1ம்", t) # e.g., காந்திபுரத்தில் -> காந்திபுரம்
    t = re.sub(r"([^\s]+)தில்$", r"\1", t)
    return t.strip()

if __name__ == "__main__":
    test_cases = [
        "Gandhipuram-la",
        "Gandhi puram la",
        "காந்திபுரத்தில்",
        "RS puram DB road la",
        "Saravanampatti bus stand pakkathula",
        "kaandhipuram 5th theru"
    ]
    print("Testing Location Normalizer:")
    for tc in test_cases:
        print(f"Original: '{tc}' -> Tanglish/Normalized: '{normalize_tanglish(tc)}' / Tamil: '{normalize_tamil(tc)}'")
