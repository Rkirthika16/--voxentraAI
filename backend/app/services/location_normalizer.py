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
# Whisper speech recognition phonetic mistakes & joined/separated tokens
WHISPER_SPEECH_CORRECTIONS = {
    # Vadavalli variants & common village mispronunciations
    "vadaveli": "Vadavalli",
    "vada valli": "Vadavalli",
    "vadavelli": "Vadavalli",
    "vadavali": "Vadavalli",
    "vaadavalli": "Vadavalli",
    "vadavellii": "Vadavalli",
    "wadavalli": "Vadavalli",
    "vadavalli la": "Vadavalli",
    "vadaveli la": "Vadavalli",
    "vada valli la": "Vadavalli",
    "vadavallila": "Vadavalli",
    "vadavallile": "Vadavalli",
    "vadavelila": "Vadavalli",
    "coimbatore vadaveli": "Coimbatore Vadavalli",
    "coimbatore vadavalli": "Coimbatore Vadavalli",
    "vada valli water problem": "Vadavalli water problem",
    "vadaveli water problem": "Vadavalli water problem",

    # Anna Nagar Street variants in Tanglish & Tamil
    "anna nagar second street": "Anna Nagar 2nd Street",
    "anna nagar rendu street": "Anna Nagar 2nd Street",
    "anna nagar 2 street": "Anna Nagar 2nd Street",
    "anna nagar 2nd street": "Anna Nagar 2nd Street",
    "anna nagar rendavathu theru": "Anna Nagar 2nd Street",
    "anna nagar rendaavathu theru": "Anna Nagar 2nd Street",
    "anna nagar irandavathu theru": "Anna Nagar 2nd Street",
    "anna nagar first street": "Anna Nagar 1st Street",
    "anna nagar onnu street": "Anna Nagar 1st Street",
    "anna nagar mudhal theru": "Anna Nagar 1st Street",
    "anna nagar third street": "Anna Nagar 3rd Street",
    "anna nagar moonu street": "Anna Nagar 3rd Street",
    "அண்ணா நகர் இரண்டாவது தெரு": "Anna Nagar 2nd Street",
    "அண்ணா நகர் 2வது தெரு": "Anna Nagar 2nd Street",
    "அண்ணா நகர் ரெண்டாவது தெரு": "Anna Nagar 2nd Street",

    # Landmark speech clues
    "government school pakkathula": "Government School pakkathula",
    "government school pakkam": "Government School pakkam",
    "government school kitta": "Government School kitta",
    "govt school pakkathula": "Government School pakkathula",
    "govt school kitta": "Government School kitta",
    "govt school pakkam": "Government School pakkam",
    "அரசு பள்ளி பக்கத்துல": "Government School pakkathula",
    "அரசு பள்ளி அருகில்": "Government School arugil",

    # Gandhipuram & common Whisper STT errors
    "gandhi puram la tani vara la": "Gandhipuram thanni varala",
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
    "டி பி ரோட்டில்": "DB Road",
    "டி பி ரோடு": "DB Road",
    "டி.பி. ரோட்டில்": "DB Road",
    "டி.பி. ரோடு": "DB Road",
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
    "kavundam palayam": "Kavundampalayam",
    "kuniyamuthur": "Kuniyamuthur",
    "kuniamuthur": "Kuniyamuthur",
    "kuniya muthur": "Kuniyamuthur",
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
    "codissia": "Codissia",

    # Phonetic Tamil water / civic terms
    "tani vara la": "thanni varala",
    "tani varala": "thanni varala",
    "tani varla": "thanni varala",
    "thani vara la": "thanni varala",
    "thani varala": "thanni varala",
    "thani": "thanni",
    "vara la": "varala",
    "vara le": "varala",
    "varla": "varala"
}

# Number words and ordinals across Tamil, English, and Tanglish
STREET_NUMBER_WORDS = {
    # 1
    "1st": "1st", "first": "1st", "one": "1st", "onnu": "1st", "onnaavathu": "1st", "onnavathu": "1st",
    "mudhal": "1st", "1": "1st", "முதல்": "1st", "முதலாவது": "1st", "ஒன்று": "1st", "1வது": "1st",
    # 2
    "2nd": "2nd", "second": "2nd", "two": "2nd", "rendu": "2nd", "irandu": "2nd", "irandavathu": "2nd",
    "irandaavathu": "2nd", "rendavathu": "2nd", "rendaavathu": "2nd", "2": "2nd",
    "இரண்டாவது": "2nd", "இரண்டு": "2nd", "ரெண்டாவது": "2nd", "ரெண்டு": "2nd", "2வது": "2nd",
    # 3
    "3rd": "3rd", "third": "3rd", "three": "3rd", "moonu": "3rd", "moondru": "3rd", "moondraavathu": "3rd",
    "moonavathu": "3rd", "3": "3rd", "மூன்றாவது": "3rd", "மூன்று": "3rd", "3வது": "3rd",
    # 4
    "4th": "4th", "fourth": "4th", "four": "4th", "naalu": "4th", "naanku": "4th", "naangaavathu": "4th",
    "naalavathu": "4th", "4": "4th", "நான்காவது": "4th", "நான்கு": "4th", "4வது": "4th",
    # 5
    "5th": "5th", "fifth": "5th", "five": "5th", "ainthu": "5th", "aindhu": "5th", "anju": "5th",
    "aindhaavathu": "5th", "anjavathu": "5th", "5": "5th", "ஐந்தாவது": "5th", "ஐந்து": "5th", "5வது": "5th",
    # 6
    "6th": "6th", "sixth": "6th", "six": "6th", "aaru": "6th", "aaraavathu": "6th", "6": "6th",
    "ஆறாவது": "6th", "ஆறு": "6th", "6வது": "6th",
    # 7
    "7th": "7th", "seventh": "7th", "seven": "7th", "ezhu": "7th", "eezhaavathu": "7th", "elavathu": "7th",
    "7": "7th", "ஏழாவது": "7th", "ஏழு": "7th", "7வது": "7th",
    # 8
    "8th": "8th", "eighth": "8th", "eight": "8th", "ettu": "8th", "ettaavathu": "8th", "8": "8th",
    "எட்டாவது": "8th", "எட்டு": "8th", "8வது": "8th",
    # 9
    "9th": "9th", "ninth": "9th", "nine": "9th", "onpathu": "9th", "onbadhu": "9th", "onpathaavathu": "9th",
    "9": "9th", "ஒன்பதாவது": "9th", "ஒன்பது": "9th", "9வது": "9th",
    # 10
    "10th": "10th", "tenth": "10th", "ten": "10th", "pathu": "10th", "pathaavathu": "10th", "10": "10th",
    "பத்தாவது": "10th", "பத்து": "10th", "10வது": "10th"
}

class LocationNormalizer:
    """Normalizes natural speech transcripts in Tamil, Tanglish, and English."""

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
        t = unicodedata.normalize("NFKD", text)
        # Collapse repeated letters (3 or more, e.g. vaaaaadavalli -> vadavalli)
        t = re.sub(r'([A-Za-z])\1{2,}', r'\1', t)
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
            # Strip Tamil locative case markers: e.g. காந்திபுரத்தில் -> காந்திபுரம், வடவள்ளில -> வடவள்ளி
            w_norm = re.sub(r"த்தில்$", "ம்", w)
            w_norm = re.sub(r"தில்$", "", w_norm)
            w_norm = re.sub(r"இல்$", "", w_norm)
            w_norm = re.sub(r"ல்$", "", w_norm)
            w_norm = re.sub(r"க்கு$", "", w_norm)
            w_norm = re.sub(r"உக்கு$", "", w_norm)
            w_norm = re.sub(r"ல$", "", w_norm)
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

        # Normalize street ordinal numbers: e.g., "5 th street" -> "5th street", "second street" -> "2nd street"
        for word, ord_val in STREET_NUMBER_WORDS.items():
            pattern = r"\b" + re.escape(word) + r"\s+(street|theru|cross|road|lane|salai|main\s+road)\b"
            replacement = rf"{ord_val} \1"
            t = re.sub(pattern, replacement, t)

        return t.strip()

    @classmethod
    def extract_numbered_street(cls, text: str) -> str:
        """
        Detects patterns like:
        'Anna nagar second street' -> 'Anna Nagar 2nd Street'
        'Anna nagar rendu street' -> 'Anna Nagar 2nd Street'
        '5th street' -> '5th Street'
        '3rd cross' -> '3rd Cross'
        'ரெண்டாவது தெரு' -> '2nd Street'
        'அண்ணா நகர் 2வது தெரு' -> 'Anna Nagar 2nd Street'
        """
        # 1. Pattern with prefix (e.g., 'Anna nagar second street', 'காந்திபுரம் 5வது தெரு')
        pattern_with_prefix = r"\b([a-zA-Z\u0B80-\u0BFF\s]+?)\s+(\d+(?:st|nd|rd|th|வது)?|[a-zA-Z\u0B80-\u0BFF]+)\s+(street|theru|cross\s+street|cross|road|salai|lane|main\s+road|தெரு|சாலை|வீதி)\b"
        match_p = re.search(pattern_with_prefix, text, re.IGNORECASE)
        if match_p:
            prefix = match_p.group(1).strip()
            num = match_p.group(2).lower()
            unit_raw = match_p.group(3).lower()

            ord_val = STREET_NUMBER_WORDS.get(num)
            if not ord_val:
                if num.isdigit():
                    if num == "1": ord_val = "1st"
                    elif num == "2": ord_val = "2nd"
                    elif num == "3": ord_val = "3rd"
                    else: ord_val = f"{num}th"
                elif re.match(r"^\d+(?:st|nd|rd|th)$", num):
                    ord_val = num

            if ord_val:
                if unit_raw in ("street", "theru", "தெரு", "வீதி"):
                    unit = "Street"
                elif unit_raw in ("road", "salai", "சாலை"):
                    unit = "Road"
                elif "cross" in unit_raw:
                    unit = "Cross"
                else:
                    unit = "Street"
                
                # Check prefix is meaningful and not noise
                prefix = re.sub(r'^(?:in|at|near|the|enga|anga|inda|indha|இந்த|அந்த|எங்கள்)\s+', '', prefix, flags=re.IGNORECASE)
                prefix = re.sub(r'^[a-zA-Z\u0B80-\u0BFF]+(?:-(?:la|le|kku|ku|il|ula)|\s+(?:la|le|kku|ku|il|ula))\s+', '', prefix, flags=re.IGNORECASE)
                parts = prefix.split()
                if len(parts) > 1:
                    try:
                        from app.services.location_alias_service import location_alias_service
                        first_exact = location_alias_service.lookup_exact(parts[0])
                        if any(e.get("entity_type") in ("area", "taluk", "revenue_village") for e in first_exact):
                            prefix = " ".join(parts[1:]).strip()
                    except Exception:
                        pass

                prefix_clean = prefix.title()
                if prefix.lower() in ("this", "that", "the", "inga", "enga", "enga oor", "inda", "indha", "இந்த", "அந்த", "எங்கள்", ""):
                    return f"{ord_val} {unit}"
                return f"{prefix_clean} {ord_val} {unit}"

        # 2. Pattern without prefix (e.g., 'second street', '5th street', '2nd cross')
        pattern_simple = r"\b(\d+(?:st|nd|rd|th|வது)?|[a-zA-Z\u0B80-\u0BFF]+)\s+(street|theru|cross\s+street|cross|road|salai|lane|main\s+road|தெரு|சாலை|வீதி)\b"
        match = re.search(pattern_simple, text, re.IGNORECASE)
        if match:
            num = match.group(1).lower()
            unit_raw = match.group(2).lower()

            ord_val = STREET_NUMBER_WORDS.get(num)
            if not ord_val:
                if num.isdigit():
                    if num == "1": ord_val = "1st"
                    elif num == "2": ord_val = "2nd"
                    elif num == "3": ord_val = "3rd"
                    else: ord_val = f"{num}th"
                elif re.match(r"^\d+(?:st|nd|rd|th)$", num):
                    ord_val = num

            if ord_val:
                if unit_raw in ("street", "theru", "தெரு", "வீதி"):
                    unit = "Street"
                elif unit_raw in ("road", "salai", "சாலை"):
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
