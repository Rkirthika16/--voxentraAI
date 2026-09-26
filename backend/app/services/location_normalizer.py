"""Location Normalizer for Coimbatore Location Intelligence System.
Handles Tamil, English, and Tanglish text normalization and Whisper speech-to-text corrections.
"""
import re
import unicodedata
from typing import List, Tuple

# Common Tamil locative case affixes and speech noise
TAMIL_LOCATIVE_SUFFIXES = [
    r"த்தில்$", r"தில்$", r"இல்$", r"ல்$", r"க்கு$", r"உக்கு$", r"ல$"
]

# Common Tanglish locative suffixes and prepositions
TANGLISH_LOCATIVE_SUFFIXES = [
    "-la", "-le", "-kku", "-ku", "-il", "-ula", " la", " le", " kku", " ku", " il", " ula",
    " pakkam", " pakkathula", " pakka", " kitta", " andae", " side", " opposite", " near"
]

# Whisper speech recognition phonetic mistakes & joined/separated tokens
WHISPER_SPEECH_CORRECTIONS = {
    "gandhi puram": "Gandhipuram",
    "gandhipuram la": "Gandhipuram",
    "gandhipuram-la": "Gandhipuram",
    "gandhipuramla": "Gandhipuram",
    "kaandhipuram": "Gandhipuram",
    "ganthipuram": "Gandhipuram",
    "rs puram": "R.S. Puram",
    "r s puram": "R.S. Puram",
    "rspuram": "R.S. Puram",
    "db road": "D.B. Road",
    "d b road": "D.B. Road",
    "dbroad": "D.B. Road",
    "saravanampatti": "Saravanampatti",
    "saravana patti": "Saravanampatti",
    "saravanampatty": "Saravanampatti",
    "saravanampatti bus stand": "Saravanampatti Bus Stand",
    "race course": "Race Course",
    "racecourse": "Race Course",
    "saibaba colony": "Saibaba Colony",
    "sai baba colony": "Saibaba Colony",
    "saibabacolony": "Saibaba Colony",
    "peelamedu": "Peelamedu",
    "peela medu": "Peelamedu",
    "singanallur": "Singanallur",
    "singa nallur": "Singanallur",
    "marudhamalai": "Marudamalai",
    "maruthamalai": "Marudamalai",
    "marudamalai road": "Marudamalai Road",
    "maruthamalai road": "Marudamalai Road",
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
    "100 ft road": "100 Feet Road",
    "avinashi road": "Avinashi Road",
    "avinasi road": "Avinashi Road",
    "trichy road": "Trichy Road",
    "mettupalayam road": "Mettupalayam Road",
    "mtp road": "Mettupalayam Road",
    "pollachi road": "Pollachi Road",
    "sathy road": "Sathy Road",
    "sathyamangalam road": "Sathy Road",
    "sivanandha colony": "Sivananda Colony",
    "sivananda colony": "Sivananda Colony",
    "sivanandhacolony": "Sivananda Colony",
    "ukkadam": "Ukkadam",
    "ukkkadam": "Ukkadam",
    "ukkadam bus stand": "Ukkadam Bus Stand",
    "town hall": "Town Hall",
    "townhall": "Town Hall",
    "kavundampalayam": "Kavundampalayam",
    "goundampalayam": "Kavundampalayam",
    "koundampalayam": "Kavundampalayam",
    "kuniyamuthur": "Kuniyamuthur",
    "kuniamuthur": "Kuniyamuthur",
    "kuniya muthur": "Kuniyamuthur",
    "vadavalli": "Vadavalli",
    "vada valli": "Vadavalli",
    "sowripalayam": "Sowripalayam",
    "sowri palayam": "Sowripalayam",
    "ganapathy": "Ganapathy",
    "ganapathi": "Ganapathy",
    "ganapathi pudur": "Ganapathy Pudur",
    "kovaipudur": "Kovaipudur",
    "kovai pudur": "Kovaipudur",
    "podanur": "Podanur",
    "pothanur": "Podanur",
    "sungam": "Sungam",
    "lakshmi mills": "Lakshmi Mills",
    "lakshmimills": "Lakshmi Mills",
    "brookefields": "Brookefields",
    "brooke fields": "Brookefields",
    "fun republic": "Fun Republic Mall",
    "prozone": "Prozone Mall",
    "tidel park": "TIDEL Park",
    "codissia": "Codissia"
}

# Number words to ordinal conversion for street names
STREET_NUMBER_WORDS = {
    "1st": "1st", "first": "1st", "mudhal": "1st", "onnaavathu": "1st", "1": "1st",
    "2nd": "2nd", "second": "2nd", "irandaavathu": "2nd", "rendavathu": "2nd", "2": "2nd",
    "3rd": "3rd", "third": "3rd", "moondraavathu": "3rd", "moonavathu": "3rd", "3": "3rd",
    "4th": "4th", "fourth": "4th", "naangaavathu": "4th", "naalavathu": "4th", "4": "4th",
    "5th": "5th", "fifth": "5th", "aindhaavathu": "5th", "anjavathu": "5th", "5": "5th",
    "6th": "6th", "sixth": "6th", "aaraavathu": "6th", "6": "6th",
    "7th": "7th", "seventh": "7th", "eezhaavathu": "7th", "elavathu": "7th", "7": "7th",
    "8th": "8th", "eighth": "8th", "ettaavathu": "8th", "8": "8th",
    "9th": "9th", "ninth": "9th", "onpathaavathu": "9th", "9": "9th",
    "10th": "10th", "tenth": "10th", "pathaavathu": "10th", "10": "10th"
}

class LocationNormalizer:
    """Normalizes natural speech transcripts in Tamil, Tanglish, and English."""

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
        t = unicodedata.normalize("NFKD", text)
        t = re.sub(r"[^\w\s\u0B80-\u0BFF\.\-\/]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @classmethod
    def normalize_tamil(cls, text: str) -> str:
        """Removes locative case endings and punctuation from Tamil script per word."""
        if not text:
            return ""
        t = cls.clean(text)
        words = t.split()
        norm_words = []
        for w in words:
            # Strip Tamil locative case markers: e.g. காந்திபுரத்தில் -> காந்திபுரம்
            w_norm = re.sub(r"த்தில்$", "ம்", w)
            w_norm = re.sub(r"தில்$", "", w_norm)
            w_norm = re.sub(r"இல்$", "", w_norm)
            w_norm = re.sub(r"ல்$", "", w_norm)
            w_norm = re.sub(r"க்கு$", "", w_norm)
            w_norm = re.sub(r"உக்கு$", "", w_norm)
            norm_words.append(w_norm)
        return " ".join(norm_words).strip()

    @classmethod
    def normalize_tanglish(cls, text: str) -> str:
        """Strips Tanglish case suffixes, normalizes phonetic tokens and Whisper errors."""
        if not text:
            return ""
        t = cls.clean(text).lower()

        # Whisper error corrections first
        for mistake, corr in WHISPER_SPEECH_CORRECTIONS.items():
            pattern = r"\b" + re.escape(mistake) + r"\b"
            t = re.sub(pattern, corr.lower(), t)

        # Strip suffixes
        for suffix in TANGLISH_LOCATIVE_SUFFIXES:
            if t.endswith(suffix):
                t = t[:-len(suffix)].strip()

        # Word-level hyphenated suffix removal
        t = re.sub(r"-(?:la|le|kku|ku|il|ula)\b", "", t)

        # Normalize street ordinal numbers: e.g., "5 th street" -> "5th street", "fifth street" -> "5th street"
        for word, ord_val in STREET_NUMBER_WORDS.items():
            pattern = r"\b" + re.escape(word) + r"\s+(street|theru|cross|road|lane|salai|main\s+road)\b"
            replacement = rf"{ord_val} \1"
            t = re.sub(pattern, replacement, t)

        return t.strip()

    @classmethod
    def extract_numbered_street(cls, text: str) -> str:
        """Detects patterns like '5th street', '3rd cross', 'cross cut road', '5th theru'."""
        pattern = r"\b(\d+(?:st|nd|rd|th)?|[a-zA-Z]+)\s+(street|theru|cross\s+street|cross|road|salai|lane|main\s+road|nagar)\b"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            num = match.group(1).lower()
            unit_raw = match.group(2).lower()
            
            # Convert number words or check if valid number
            ord_val = None
            for w, o in STREET_NUMBER_WORDS.items():
                if num == w:
                    ord_val = o
                    break
            if not ord_val:
                if num.isdigit():
                    if num == "1": ord_val = "1st"
                    elif num == "2": ord_val = "2nd"
                    elif num == "3": ord_val = "3rd"
                    else: ord_val = f"{num}th"
                elif re.match(r"^\d+(?:st|nd|rd|th)$", num):
                    ord_val = num
            
            if ord_val:
                if unit_raw in ("street", "theru"):
                    unit = "Street"
                elif unit_raw in ("road", "salai"):
                    unit = "Road"
                elif "cross" in unit_raw:
                    unit = "Cross"
                else:
                    unit = match.group(2).capitalize()
                return f"{ord_val} {unit}"
        return ""

    @classmethod
    def get_candidate_tokens(cls, text: str) -> List[str]:
        """Generates list of search candidates from transcript sorted by length descending."""
        cleaned = cls.clean(text)
        tamil_norm = cls.normalize_tamil(cleaned)
        tanglish_norm = cls.normalize_tanglish(cleaned)
        
        candidates = set()
        if cleaned: candidates.add(cleaned)
        if tamil_norm: candidates.add(tamil_norm)
        if tanglish_norm: candidates.add(tanglish_norm)
        
        # Sub-token n-grams from tanglish_norm, tamil_norm and cleaned
        for norm_str in [tanglish_norm, tamil_norm, cleaned]:
            words = norm_str.split()
            for n in range(1, min(5, len(words) + 1)):
                for i in range(len(words) - n + 1):
                    ngram = " ".join(words[i:i+n]).strip()
                    if len(ngram) >= 3:
                        candidates.add(ngram)
                        # Also add normalized Tamil words
                        if any('\u0B80' <= c <= '\u0BFF' for c in ngram):
                            cand_norm = cls.normalize_tamil(ngram)
                            if cand_norm:
                                candidates.add(cand_norm)

        # Return sorted by length descending (longest match first)
        return sorted(list(candidates), key=len, reverse=True)
