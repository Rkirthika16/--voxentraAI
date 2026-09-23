import re
import uuid
import logging
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session

from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text
from app.ai.classification_service import classify_complaint
from app.ai.location_service import extract_location
from app.ai.priority_service import assess_priority
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintSource
from app.models.user import User
from app.schemas.complaint import ComplaintCreate
from app.services.complaint_service import complaint_service

logger = logging.getLogger("voxentra.complaint_collector")

# Ordered definition of the 10 required complaint details (hierarchical location intake)
FIELD_KEYS = [
    "problem_description",
    "district_area",
    "street_road_name",
    "landmark",
    "exact_location",
    "date_and_time",
    "frequency",
    "current_status",
    "additional_details",
    "citizen_details"
]

FIELD_METADATA = {
    "problem_description": {
        "label_en": "Problem Description",
        "label_ta": "பிரச்சனை விவரம்",
        "label_tanglish": "Problem Description",
        "question_en": "Could you please describe the civic problem in detail? (e.g. water leakage, power outage, uncollected garbage, broken road)",
        "question_ta": "நீங்கள் சந்திக்கும் பொதுப் பிரச்சனை என்ன என்பதை விளக்கமாகக் கூற முடியுமா? (எ.கா: குடிநீர் கசிவு, மின்வெட்டு, குப்பை தேக்கம், சாலை சேதம்)",
        "question_tanglish": "Ungalukku enna civic problem irukku nu konjam describe pannunga? (e.g. Water leak, Current cut, Kuppai, Road damage)",
        "spoken_en": "Please describe the civic problem you would like to report.",
        "spoken_ta": "உங்களுக்கு ஏற்பட்டுள்ள பொது பிரச்சனை என்ன என்று கூறவும்.",
        "spoken_tanglish": "Ungaloda problem enna nu sollunga."
    },
    "district_area": {
        "label_en": "District / Area",
        "label_ta": "மாவட்டம் / பகுதி",
        "label_tanglish": "District / Area",
        "question_en": "In which District and Area or Locality did this occur? (e.g. Coimbatore - Gandhipuram, Chennai - Anna Nagar, Madurai - Melur)",
        "question_ta": "இது எந்த மாவட்டம் மற்றும் பகுதி அல்லது வட்டாரத்தில் நிகழ்ந்துள்ளது? (எ.கா: கோயம்புத்தூர் - காந்திபுரம், சென்னை - அண்ணா நகர், மதுரை - மேலூர்)",
        "question_tanglish": "Idhu endha District and Area or Locality-la nadanthuchu? (e.g. Coimbatore - Gandhipuram, Chennai - Anna Nagar)",
        "spoken_en": "In which district and area did this problem occur?",
        "spoken_ta": "இது எந்த மாவட்டம் மற்றும் பகுதியில் நிகழ்ந்துள்ளது?",
        "spoken_tanglish": "Idhu endha District and Area-la nadanthuchu?"
    },
    "street_road_name": {
        "label_en": "Street / Road Name",
        "label_ta": "தெரு / சாலை பெயர்",
        "label_tanglish": "Street / Road Name",
        "question_en": "Which street or road is affected? (e.g. Cross Cut Road, 5th Street, Gandhi Road, Main Bazaar)",
        "question_ta": "பாதிக்கப்பட்ட தெரு அல்லது சாலையின் பெயர் என்ன? (எ.கா: காந்தி தெரு, மெயின் ரோடு, கிராஸ் கட் ரோடு, 5-வது தெரு)",
        "question_tanglish": "Endha street or road affected aagi irukku? (e.g. Cross Cut Road, Gandhi Street, Main Road)",
        "spoken_en": "Which street or road is affected by this issue?",
        "spoken_ta": "பாதிக்கப்பட்ட தெரு அல்லது சாலையின் பெயர் என்ன?",
        "spoken_tanglish": "Endha street or road affected aagi irukku?"
    },
    "landmark": {
        "label_en": "Nearby Landmark",
        "label_ta": "அடையாளம் / Landmark",
        "label_tanglish": "Nearby Landmark",
        "question_en": "What nearby landmark can help our inspection team identify the spot? (e.g. Near Murugan Temple, Opposite Indian Bank ATM, Behind High School)",
        "question_ta": "எங்கள் ஆய்வு குழுவினர் இடத்தை அடையாளம் காண அருகிலுள்ள முக்கிய அடையாளம் (Landmark) என்ன? (எ.கா: முருகன் கோவில் அருகில், இந்தியன் வங்கி எதிரில், பள்ளி அருகில்)",
        "question_tanglish": "Spot ah identify panna nearby landmark enna? (e.g. Temple kitta, Bank ATM opposite, School pakkam)",
        "spoken_en": "What nearby landmark can help identify the location?",
        "spoken_ta": "அருகிலுள்ள முக்கிய அடையாளம் என்ன?",
        "spoken_tanglish": "Pakkathula irukura landmark enna?"
    },
    "exact_location": {
        "label_en": "Exact / Specific Location",
        "label_ta": "குறிப்பிட்ட இடம் / கதவு எண்",
        "label_tanglish": "Exact Location Details",
        "question_en": "What is the exact or approximate spot details? (e.g. Near Electric Pole #12, Opposite Door No. 45, Near Junction / Water Tank)",
        "question_ta": "அந்த இடத்தின் சரியான அல்லது தோராயமான குறிப்பிட்ட இடம் என்ன? (எ.கா: மின் கம்பம் #12 அருகில், கதவு எண் 45 எதிரில், சந்திப்பு அருகில்)",
        "question_tanglish": "Exact or specific spot details enna? (e.g. Electric Pole #12 kitta, Door No 45 opposite, Junction kitta)",
        "spoken_en": "What is the exact or specific location detail or door number?",
        "spoken_ta": "அந்த இடத்தின் குறிப்பிட்ட விவரம் அல்லது கதவு எண் என்ன?",
        "spoken_tanglish": "Specific spot details or door number enna?"
    },
    "date_and_time": {
        "label_en": "Date & Time",
        "label_ta": "நடந்த தேதி & நேரம்",
        "label_tanglish": "Date & Time",
        "question_en": "When did this problem start or occur? (e.g. Today morning at 8 AM, Yesterday evening, Since last 3 days)",
        "question_ta": "இந்தப் பிரச்சனை எப்போது தொடங்கியது அல்லது நிகழ்ந்தது? (எ.கா: இன்று காலை 8 மணிக்கு, நேற்று மாலை, கடந்த 3 நாட்களாக)",
        "question_tanglish": "Indha problem eppo start aachu? (e.g. Today morning, Yesterday evening, Last 3 days-ah)",
        "spoken_en": "When did this problem occur or start?",
        "spoken_ta": "இந்தப் பிரச்சனை எப்போது தொடங்கியது?",
        "spoken_tanglish": "Indha problem eppo start aachu?"
    },
    "frequency": {
        "label_en": "Frequency",
        "label_ta": "நிகழ்வு வீதம் / எத்தனை முறை",
        "label_tanglish": "Frequency",
        "question_en": "How often does this problem occur? (e.g. Happening for the first time, Recurring daily, Happens every rainy day, Frequent)",
        "question_ta": "இந்தப் பிரச்சனை எத்தனை முறை அல்லது எவ்வளவு அடிக்கடி நிகழ்கிறது? (எ.கா: முதல் முறையாக, தினமும் தொடர்ந்து, அடிக்கடி)",
        "question_tanglish": "Indha problem evalo frequency-la varudhu? (e.g. First time, Daily recurring, Adikkadi nadakudhu)",
        "spoken_en": "How many times or how often has this problem occurred?",
        "spoken_ta": "இந்தப் பிரச்சனை எவ்வளவு அடிக்கடி நிகழ்கிறது?",
        "spoken_tanglish": "Indha problem evalo adikkadi nadakudhu?"
    },
    "current_status": {
        "label_en": "Current Status",
        "label_ta": "தற்போதைய நிலை",
        "label_tanglish": "Current Status",
        "question_en": "Is the problem still happening right now, or has it been temporarily resolved? (e.g. Still active and severe, Still leaking, Temporarily blocked)",
        "question_ta": "தற்போது அந்த இடத்தின் நிலை என்ன? பிரச்சனை இன்னமும் நீடிக்கிறதா? (எ.கா: இன்னும் தீவிரமாக உள்ளது, தொடர்ந்து கசிகிறது, சரிசெய்யப்படவில்லை)",
        "question_tanglish": "Ippo current status enna? Still problem continue aagudha? (e.g. Still active, Still leaking, Temporarily stopped)",
        "spoken_en": "Is the problem still happening right now or resolved?",
        "spoken_ta": "பிரச்சனை இன்னமும் நீடிக்கிறதா? தற்போதைய நிலை என்ன?",
        "spoken_tanglish": "Ippo problem still continue aagudha?"
    },
    "additional_details": {
        "label_en": "Additional Details / Hazards",
        "label_ta": "கூடுதல் விவரங்கள் / ஆபத்துகள்",
        "label_tanglish": "Additional Details / Hazards",
        "question_en": "Are there any additional details, hazards, or safety warnings? (e.g. Causes traffic jam, Electric shock risk, Foul odor, or reply 'None')",
        "question_ta": "வேறு ஏதேனும் கூடுதல் தகவல்கள் அல்லது பாதுகாப்பு எச்சரிக்கைகள் உள்ளதா? (எ.கா: போக்குவரத்து பாதிப்பு, துர்நாற்றம், ஆபத்தான கம்பி, அல்லது 'இல்லை')",
        "question_tanglish": "Vera edhavadhu additional details or safety risks irukka? (e.g. Traffic block, Bad smell, or just say 'None')",
        "spoken_en": "Are there any additional details or safety hazards to note?",
        "spoken_ta": "வேறு ஏதேனும் கூடுதல் விவரங்கள் அல்லது எச்சரிக்கைகள் உள்ளதா?",
        "spoken_tanglish": "Vera edhavadhu additional information irukka?"
    },
    "citizen_details": {
        "label_en": "Citizen Contact Details",
        "label_ta": "பொதுமக்கள் தொடர்பு விவரம்",
        "label_tanglish": "Citizen Contact Details",
        "question_en": "Please provide your Name and Contact Phone Number for complaint registration and SMS status updates. (e.g. Ramesh Kumar, 9876543210)",
        "question_ta": "புகார் பதிவு மற்றும் எஸ்.எம்.எஸ் நிலை அறிவிப்புகளுக்கு உங்கள் பெயர் மற்றும் கைபேசி எண்ணை (Phone Number) தெரிவிக்கவும். (எ.கா: ரமேஷ் குமார், 9876543210)",
        "question_tanglish": "Complaint register panni SMS updates vara ungaloda Name and Mobile Number sollunga. (e.g. Ramesh Kumar, 9876543210)",
        "spoken_en": "Please provide your name and contact phone number.",
        "spoken_ta": "உங்கள் பெயர் மற்றும் தொடர்பு எண்ணைத் தெரிவிக்கவும்.",
        "spoken_tanglish": "Ungaloda Name and Phone Number sollunga."
    }
}

# In-memory session store for dialogue sessions
# Key: session_id -> Session state dict
SESSION_STORE: Dict[str, Dict[str, Any]] = {}


class ComplaintCollector:
    """
    Multilingual State-Machine Engine for 10-Point Grievance Intake.
    Extracts entities, maintains conversation continuity in Tamil, Tanglish, and English,
    prompts missing details one-by-one, generates confirmation summaries,
    and registers complaints to the database.
    """

    def get_or_create_session(
        self,
        session_id: Optional[str],
        current_user: Optional[User] = None,
        language_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        if sid not in SESSION_STORE:
            user_details = None
            if current_user:
                phone = getattr(current_user, "phone", "") or ""
                name = getattr(current_user, "full_name", "") or getattr(current_user, "username", "") or ""
                if name or phone:
                    user_details = f"{name} ({phone})".strip()

            SESSION_STORE[sid] = {
                "session_id": sid,
                "language": language_hint or "English",
                "state": "COLLECTING",  # GREETING, COLLECTING, CONFIRMATION_PENDING, REGISTERED
                "fields": {
                    "problem_description": None,
                    "exact_location": None,
                    "street_road_name": None,
                    "district_area": None,
                    "landmark": None,
                    "date_and_time": None,
                    "frequency": None,
                    "current_status": None,
                    "additional_details": None,
                    "citizen_details": user_details
                },
                "current_field_prompted": None,
                "history": [],
                "created_complaint_number": None,
                "created_complaint_id": None
            }
        return SESSION_STORE[sid]

    def reset_session(self, session_id: str) -> None:
        if session_id in SESSION_STORE:
            del SESSION_STORE[session_id]

    def _extract_phone_and_name(self, text: str) -> Optional[str]:
        """Extracts phone number and citizen name from input."""
        phone_match = re.search(r'\b[6-9]\d{9}\b', text)
        phone = phone_match.group(0) if phone_match else None

        name = None
        # Look for explicit name markers first (Tamil & English)
        name_match = re.search(r'(?:பெயர்|name|peyar|i am|naan|nan)\s*(?:is|:|-)?\s*([A-Za-z\u0B80-\u0BFF]+(?:\s+[A-Za-z\u0B80-\u0BFF]+)?)', text, re.IGNORECASE)
        if name_match:
            candidate = name_match.group(1).strip()
            # Exclude false positives
            if candidate.lower() not in ["enna", "irukku", "sollunga", "problem", "theru", "road", "number", "phone"]:
                name = candidate

        if not name and phone:
            cleaned = re.sub(r'\b[6-9]\d{9}\b', '', text)
            cleaned = re.sub(r'(\bname\b|\bnumber\b|\bphone\b|\bmobile\b|\bmy\b|\bis\b|\bpeyar\b|\ben\b|\bபெயர்\b|\bஎண்\b|:|-|,)', ' ', cleaned, flags=re.IGNORECASE)
            name_words = [w for w in cleaned.split() if len(w) > 1 and not w.isdigit()]
            if name_words:
                name = " ".join(name_words[:2]).strip()

        if name and phone:
            return f"{name} ({phone})"
        elif name:
            return name
        elif phone:
            return phone
        return None

    def _extract_date_time(self, text: str) -> Optional[str]:
        lowered = text.lower()
        patterns = [
            r'\b(\d{1,2}[:.]\d{2}\s*(?:am|pm|a\.m\.|p\.m\.)?)\b',
            r'\b(today\s*(?:morning|afternoon|evening|night)?)\b',
            r'\b(yesterday\s*(?:morning|afternoon|evening|night)?)\b',
            r'\b(since\s*\d+\s*days?)\b',
            r'\b(last\s*\d+\s*(?:days?|hours?|weeks?))\b',
            r'\b(\d+\s*days?(?:-ah)?)\b',
            r'\b(இன்று\s*(?:காலை|மாலை|இரவு)?)\b',
            r'\b(நேற்று\s*(?:காலை|மாலை|இரவு)?)\b',
            r'\b(\d+\s*நாட்களாக|\d+\s*நாளாக|\d+\s*நாளா)\b',
            r'\b((?:மூன்று|மூணு|இரண்டு|ரெண்டு|நான்கு|நாலு|ஐந்து|அஞ்சு|\d+)\s*(?:நாட்களாக|நாளாக|நாளா|வாரமாக|வாரமா|மாசமாக|மாசமா))\b',
            r'\b(netru|indru|inniku|kaalai|maalai|iravu|today|yesterday|morning|evening|night)\b'
        ]
        for pat in patterns:
            m = re.search(pat, lowered)
            if m:
                return m.group(0).strip()
        return None

    def _extract_frequency(self, text: str) -> Optional[str]:
        lowered = text.lower()
        freq_keywords = {
            "first time": ["first time", "mudhal murai", "முதல் முறை", "first time only", "just now"],
            "daily recurring": ["daily", "every day", "dinamum", "thinamum", "தினமும்", "ஒவ்வொரு நாளும்", "daily-ah", "everyday"],
            "frequent / multiple times": ["frequent", "often", "adikkadi", "அடிக்கடி", "multiple times", "palavattai", "always", "continuous", "continuously", "eppovum"],
            "occasional / rain time": ["rain", "rainy day", "mazhai", "மழை நேரம்", "sometimes", "sela neram"]
        }
        for label, kw_list in freq_keywords.items():
            if any(kw in lowered for kw in kw_list):
                return label
        return None

    def _extract_current_status(self, text: str) -> Optional[str]:
        lowered = text.lower()
        status_keywords = {
            "Active / Still Happening": ["still", "happening", "ongoing", "not resolved", "not fixed", "innum", "ippovum", "irukku", "valiyuthu", "leak", "இன்னும்", "நீடிக்கிறது", "முடியவில்லை", "sariyaagala", "continue", "severe"],
            "Resolved / Stopped": ["resolved", "fixed", "stopped", "mudinjathu", "seri aaiduchu", "முடிந்தது", "சரிசெய்யப்பட்டது", "closed"],
            "Partially / Temporarily Handled": ["temporary", "partially", "temporary fix", "konjam", "தற்காலிகமாக"]
        }
        for label, kw_list in status_keywords.items():
            if any(kw in lowered for kw in kw_list):
                return label
        return None

    def _extract_street_and_landmark(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        street = None
        landmark = None

        # Street detection
        street_match = re.search(r'\b([A-Za-z0-9\.\s]+(?:street|road|salai|theru|cross|avenue|lane|nagar|nagar\s+main\s+road|highway|boulevard))\b', text, re.IGNORECASE)
        if street_match:
            street = street_match.group(1).strip()
        else:
            # Tamil street words
            ta_street = re.search(r'([\u0B80-\u0BFF\s]+(?:தெரு|சாலை|நகர்|மெயின்\s*ரோடு|வீதி))', text)
            if ta_street:
                street = ta_street.group(1).strip()

        if street:
            low_st = street.strip().lower()
            if any(low_st == v or low_st.startswith(v) for v in ["எங்க தெரு", "எங்கள் தெரு", "என் தெரு", "enga theru", "our street", "my street", "our road", "my road", "the street", "தெரு", "road", "street", "சாலை"]):
                street = None

        # Landmark detection
        landmark_match = re.search(r'\b(?:near|opposite|behind|beside|next to|close to|opp|kitta|pakkam|pakathula)\s+([A-Za-z0-9\s\.\,\-]+?)(?:\.|\,|$|\band\b)', text, re.IGNORECASE)
        if landmark_match:
            landmark = landmark_match.group(1).strip()
        else:
            ta_landmark = re.search(r'(?:அருகில்|எதிரில்|பின்னால்|பக்கத்தில்)\s+([\u0B80-\u0BFF\s]+)', text)
            if ta_landmark:
                landmark = ta_landmark.group(1).strip()
            else:
                ta_landmark2 = re.search(r'([\u0B80-\u0BFF\s]+)\s+(?:அருகில்|எதிரில்|பின்னால்|பக்கத்தில்)', text)
                if ta_landmark2:
                    landmark = ta_landmark2.group(1).strip()

        return street, landmark

    def extract_slots(
        self,
        text: str,
        current_field: Optional[str] = None,
        existing_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Multilingual slot extraction from raw citizen speech/text.
        Extracts up to 10 entities simultaneously or contextual to the current field.
        Safely respects existing fields to prevent overwriting already-gathered data.
        """
        extracted: Dict[str, Any] = {}
        existing = existing_fields or {}
        raw = text.strip()
        normalized = normalize_text(raw)
        lowered = normalized.lower()

        # If currently prompting for a specific single field, check direct assignment
        if current_field:
            if current_field == "citizen_details":
                contact = self._extract_phone_and_name(raw) or (raw if len(raw) >= 3 else None)
                if contact:
                    extracted["citizen_details"] = contact
            elif current_field == "date_and_time":
                dt = self._extract_date_time(raw) or raw
                extracted["date_and_time"] = dt
            elif current_field == "frequency":
                freq = self._extract_frequency(raw) or raw
                extracted["frequency"] = freq
            elif current_field == "current_status":
                status = self._extract_current_status(raw) or raw
                extracted["current_status"] = status
            elif current_field == "additional_details":
                if any(w in lowered for w in ["none", "no hazard", "no additional", "nil", "nothing else", "வேறு இல்லை", "கூடுதல் இல்லை", "இல்லை"]):
                    extracted["additional_details"] = "None (No additional hazards)"
                else:
                    extracted["additional_details"] = raw
            elif current_field == "landmark":
                extracted["landmark"] = raw
            elif current_field == "street_road_name":
                extracted["street_road_name"] = raw
            elif current_field == "district_area":
                extracted["district_area"] = raw
            elif current_field == "exact_location":
                extracted["exact_location"] = raw
            elif current_field == "problem_description":
                extracted["problem_description"] = raw

        # Also run global entity extraction to capture any extra details mentioned in the turn
        phone_contact = self._extract_phone_and_name(raw)
        if phone_contact and not existing.get("citizen_details") and not extracted.get("citizen_details"):
            extracted["citizen_details"] = phone_contact

        dt = self._extract_date_time(raw)
        if dt and not existing.get("date_and_time") and not extracted.get("date_and_time"):
            extracted["date_and_time"] = dt

        freq = self._extract_frequency(raw)
        if freq and not existing.get("frequency") and not extracted.get("frequency"):
            extracted["frequency"] = freq

        stat = self._extract_current_status(raw)
        if stat and not existing.get("current_status") and not extracted.get("current_status"):
            extracted["current_status"] = stat

        street, landmark = self._extract_street_and_landmark(raw)
        if street and not existing.get("street_road_name") and not extracted.get("street_road_name") and current_field != "landmark":
            extracted["street_road_name"] = street
        if landmark and not existing.get("landmark") and not extracted.get("landmark") and current_field != "street_road_name":
            extracted["landmark"] = landmark

        # Specific spot / exact location extraction
        spot_match = re.search(r'\b(?:door\s*no\.?|pole\s*no\.?|pillar\s*no\.?|ward\s*\d+|plot\s*no\.?)\s*([A-Za-z0-9\-]+)', raw, re.IGNORECASE)
        if spot_match and not existing.get("exact_location") and not extracted.get("exact_location"):
            extracted["exact_location"] = spot_match.group(0).strip()
        elif landmark and street and not existing.get("exact_location") and not extracted.get("exact_location"):
            extracted["exact_location"] = f"{landmark}, {street}"

        # Additional details extraction - strict matching
        if not existing.get("additional_details") and not extracted.get("additional_details"):
            if any(w in lowered for w in ["no other", "no hazard", "no additional", "nothing else", "no risk", "வேறு தகவல் இல்லை", "கூடுதல் தகவல் இல்லை", "ஆபத்து இல்லை"]):
                extracted["additional_details"] = "None (No additional hazards)"

        # Location extraction from location_service (DO NOT assume street or exact location)
        if not existing.get("district_area") and not extracted.get("district_area") and current_field not in ["landmark", "street_road_name", "exact_location"]:
            loc_name, lat, lon, conf = extract_location(raw)
            if loc_name and loc_name != "Tamil Nadu" and not any(loc_name.lower().startswith(v) for v in ["தெருவு", "தெரு", "street", "road"]):
                extracted["district_area"] = loc_name

        # Problem description check if classification detects civic grievance
        if not existing.get("problem_description") and not extracted.get("problem_description") and (current_field is None or current_field == "problem_description"):
            category, dept, cat_conf = classify_complaint(normalized)
            if category != "Other" or any(w in lowered for w in ["leak", "broken", "cut", "garbage", "drainage", "pothole", "light", "குடிநீர்", "மின்வெட்டு", "குப்பை", "சாலை", "சாக்கடை"]):
                extracted["problem_description"] = raw

        return extracted

    def is_vague_location(self, text: str) -> bool:
        """Detects if citizen entered a vague/unclear location that needs clarification."""
        lowered = text.strip().lower()
        vague_phrases = [
            "my street", "my area", "here", "near my house", "our street", "our area", "enga veedu kitta",
            "enga theru", "inga", "inga thanni varala", "வீட்டு பக்கம்", "எங்கள் தெரு", "இங்கு",
            "near me", "opp to my house", "nearby", "road side"
        ]
        return any(vp in lowered for vp in vague_phrases) or len(lowered.split()) <= 1 and lowered in ["street", "road", "area", "house"]

    def get_contextual_question(self, session: Dict[str, Any], next_field: str, lang: str) -> Tuple[str, str]:
        """
        Generates smart, dynamic follow-up questions tailored to previously collected details.
        Ensures AI asks specifically for street, landmark, and exact location without assumptions.
        """
        f = session["fields"]
        meta = FIELD_METADATA.get(next_field, {})

        area = f.get("district_area")
        street = f.get("street_road_name")
        prob = f.get("problem_description")

        if next_field == "district_area":
            if lang == "Tamil":
                q = meta["question_ta"]
                sp = meta["spoken_ta"]
            elif lang == "Tanglish":
                q = meta["question_tanglish"]
                sp = meta["spoken_tanglish"]
            else:
                q = meta["question_en"]
                sp = meta["spoken_en"]
            return q, sp

        if next_field == "street_road_name":
            if area:
                if lang == "Tamil":
                    q = f"📍 **{area}** பகுதியில் எந்த தெருவில் அல்லது எந்த landmark அருகில் இந்த பிரச்சினை உள்ளது?"
                    sp = f"{area} பகுதியில் எந்த தெருவில் அல்லது எந்த அடையாளம் அருகில் இந்த பிரச்சினை உள்ளது?"
                elif lang == "Tanglish":
                    q = f"📍 **{area}**-la endha street-la or endha landmark pakkathula indha problem irukku?"
                    sp = f"{area}-la endha street or landmark pakkathula indha problem irukku?"
                else:
                    q = f"📍 In **{area}**, on which street or near which landmark is this issue located?"
                    sp = f"In {area}, which street or nearby landmark is this problem located?"
                return q, sp
            else:
                return meta["question_" + ("ta" if lang == "Tamil" else ("tanglish" if lang == "Tanglish" else "en"))], meta["spoken_" + ("ta" if lang == "Tamil" else ("tanglish" if lang == "Tanglish" else "en"))]

        if next_field == "landmark":
            ref = street or area or "அந்த இடம்"
            if lang == "Tamil":
                q = f"🏛️ **{ref}** அருகில் உள்ள முக்கிய அடையாளம் (Landmark) அல்லது பேருந்து நிலையம் எங்குள்ளது?"
                sp = f"{ref} அருகில் ஏதேனும் முக்கிய அடையாளம் அல்லது பேருந்து நிலையம் உள்ளதா?"
            elif lang == "Tanglish":
                q = f"🏛️ **{ref}** pakkathula ethavathu landmark or bus stand irukka?"
                sp = f"{ref} pakkathula ethavathu landmark irukka?"
            else:
                q = f"🏛️ What nearby **landmark** near **{ref}** can help our team locate the spot?"
                sp = f"What nearby landmark near {ref} can help locate the spot?"
            return q, sp

        if next_field == "exact_location":
            ref = street or area or "the location"
            if lang == "Tamil":
                q = f"🎯 **{ref}** பகுதியில் உள்ள குறிப்பிட்ட இடம் அல்லது கதவு எண் தெரிந்தால் கூறவும்."
                sp = f"{ref} பகுதியில் குறிப்பிட்ட இடம் அல்லது கதவு எண் தெரிந்தால் கூறவும்."
            elif lang == "Tanglish":
                q = f"🎯 **{ref}**-la exact spot or door number sollunga."
                sp = f"{ref}-la exact spot or door number sollunga."
            else:
                q = f"🎯 Please provide any exact spot detail or door number on **{ref}** if available."
                sp = f"Please provide the exact spot detail or door number on {ref} if available."
            return q, sp

        # Default fallback to metadata questions
        lang_key = "ta" if lang == "Tamil" else ("tanglish" if lang == "Tanglish" else "en")
        return meta.get(f"question_{lang_key}", meta["question_en"]), meta.get(f"spoken_{lang_key}", meta["spoken_en"])

    def get_next_missing_field(self, session: Dict[str, Any]) -> Optional[str]:
        fields = session["fields"]
        
        # Check critical mandatory slots first
        critical_slots = ["problem_description", "district_area", "street_road_name", "landmark"]
        for key in critical_slots:
            val = fields.get(key)
            if not val or not str(val).strip():
                return key

        # If citizen details are missing and not pre-populated, ask citizen details
        if not fields.get("citizen_details") or not str(fields.get("citizen_details")).strip():
            return "citizen_details"

        # Once critical slots (problem, district/area, street, landmark, citizen) are gathered:
        # Fill sensible defaults for auxiliary fields if citizen didn't mention them
        if not fields.get("exact_location"):
            fields["exact_location"] = f"{fields.get('landmark', '')}, {fields.get('street_road_name', '')}".strip(", ") or "Specified Area"
        if not fields.get("date_and_time"):
            fields["date_and_time"] = "Recently / Active"
        if not fields.get("frequency"):
            fields["frequency"] = "Recurring"
        if not fields.get("current_status"):
            fields["current_status"] = "Active / Still Happening"
        if not fields.get("additional_details"):
            fields["additional_details"] = "None (No additional hazards)"

        return None

    def evaluate_location_accuracy(self, session: Dict[str, Any]) -> str:
        """
        Evaluates location completeness: 'Complete', 'Partially Complete', or 'Unclear'.
        District + Area + Street + Landmark is considered Complete.
        """
        f = session.get("fields", {})
        area = f.get("district_area")
        street = f.get("street_road_name")
        landmark = f.get("landmark")
        exact = f.get("exact_location")

        if area and (street or exact) and landmark:
            return "Complete"
        if area and (street or landmark or exact):
            return "Complete" if (street and landmark) else "Partially Complete"
        if area or street:
            return "Partially Complete"
        return "Unclear"

    def is_confirmation_response(self, text: str) -> Tuple[bool, bool]:
        """
        Determines if citizen confirmed ("yes") or rejected/wants edits ("no").
        Returns: (is_decision_made, is_confirmed)
        """
        lowered = text.strip().lower()

        positive_words = [
            "yes", "confirm", "confirmed", "submit", "register", "proceed", "okay", "ok",
            "correct", "right", "aama", "aamam", "seri", "kandippa", "pannunga", "register pannunga",
            "podunga", "submit pannunga", "ஆமாம்", "சரி", "உறுதி", "பதிவு செய்க", "பதிவு செய்",
            "சமர்ப்பி", "நிச்சயமாக", "ஆம்", "sure", "go ahead"
        ]

        negative_words = [
            "no", "cancel", "stop", "wait", "change", "edit", "wrong", "thappu", "illai", "illa",
            "vendaam", "maatha num", "வேண்டாம்", "இல்லை", "மாற்ற வேண்டும்", "தவறு", "modify"
        ]

        if any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in positive_words) or any(w in lowered for w in ["ஆமாம்", "சரி", "பதிவு", "ஆம்"]):
            return True, True

        if any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in negative_words) or any(w in lowered for w in ["வேண்டாம்", "இல்லை", "தவறு"]):
            return True, False

        return False, False

    def generate_summary(self, session: Dict[str, Any], lang: str) -> Tuple[str, str]:
        """
        Generates clean pre-registration confirmation summary in Tamil, Tanglish, or English.
        """
        f = session["fields"]
        problem = f.get("problem_description") or "Civic Grievance"
        category, dept, _ = classify_complaint(normalize_text(problem))
        priority, _ = assess_priority(normalize_text(problem), category)

        # Dissect district vs area
        dist_area_val = f.get("district_area") or "Tamil Nadu"
        if " - " in dist_area_val:
            district_part, area_part = [p.strip() for p in dist_area_val.split(" - ", 1)]
        elif ", " in dist_area_val:
            parts = [p.strip() for p in dist_area_val.split(", ")]
            district_part, area_part = parts[-1], parts[0]
        else:
            district_part = dist_area_val
            area_part = dist_area_val

        street_part = f.get("street_road_name") or f.get("exact_location") or "குறிப்பிடப்படவில்லை"
        street_part_en = f.get("street_road_name") or f.get("exact_location") or "Not Specified"
        landmark_part = f.get("landmark") or "அருகில்"
        landmark_part_en = f.get("landmark") or "Not Specified"
        
        # Extract name from citizen_details
        cit_det = f.get("citizen_details") or ""
        name_part = "குடிமகன்"
        name_part_en = "Citizen"
        if cit_det:
            name_match = re.match(r'^([^(]+)', cit_det)
            if name_match:
                extracted_name = name_match.group(1).strip()
                if extracted_name and not extracted_name.isdigit():
                    name_part = extracted_name
                    name_part_en = extracted_name

        if lang == "Tamil":
            reply = (
                "உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன்.\n\n"
                f"பிரச்சினை: {problem}\n"
                f"துறை: {dept}\n"
                f"மாவட்டம்: {district_part}\n"
                f"பகுதி: {area_part}\n"
                f"தெரு: {street_part}\n"
                f"அருகிலுள்ள இடம்: {landmark_part}\n"
                f"பெயர்: {name_part}\n\n"
                "இந்த புகாரை பதிவு செய்யலாமா?"
            )
            spoken = (
                f"உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன். "
                f"பிரச்சினை: {problem}. துறை: {dept}. இடம்: {area_part}, {street_part}. "
                "இந்த புகாரை பதிவு செய்யலாமா?"
            )
        elif lang == "Tanglish":
            reply = (
                "Unga complaint details ah confirm panren.\n\n"
                f"Problem: {problem}\n"
                f"Department: {dept}\n"
                f"District: {district_part}\n"
                f"Area: {area_part}\n"
                f"Street: {street_part_en}\n"
                f"Nearby Landmark: {landmark_part_en}\n"
                f"Name: {name_part_en}\n\n"
                "Indha complaint ah register pannalaama?"
            )
            spoken = (
                f"Unga complaint details confirm panren. "
                f"Problem: {problem}. Department: {dept}. Location: {area_part}, {street_part_en}. "
                "Indha complaint ah register pannalaama?"
            )
        else:
            reply = (
                "Let me confirm your complaint.\n\n"
                f"Issue: {problem}\n"
                f"Department: {dept}\n"
                f"District: {district_part}\n"
                f"Area: {area_part}\n"
                f"Street: {street_part_en}\n"
                f"Landmark: {landmark_part_en}\n"
                f"Name: {name_part_en}\n\n"
                "Shall I register this complaint?"
            )
            spoken = (
                f"Let me confirm your complaint details. "
                f"Issue: {problem}. Department: {dept}. Location: {area_part}, {street_part_en}. "
                "Shall I register this complaint now?"
            )

        return reply, spoken

    def register_complaint_record(
        self,
        session: Dict[str, Any],
        db: Session,
        current_user: Optional[User] = None,
        call_sid: Optional[str] = None,
        caller_phone: Optional[str] = None,
        sms_status: str = "PENDING",
        sms_sid: Optional[str] = None
    ) -> Complaint:
        """
        Creates official Complaint entry in the database with 10 collected parameters,
        routes to department, sets coordinates, and issues VX-YYYYMMDD-XXXXXX tracking number.
        Stores call_sid, caller_phone and SMS delivery status in ai_metadata.
        """
        f = session["fields"]
        problem = f.get("problem_description") or "Civic grievance reported via AI voice assistant"
        category, dept, _ = classify_complaint(normalize_text(problem))
        priority, _ = assess_priority(normalize_text(problem), category)

        location_parts = [
            f.get("exact_location"),
            f.get("street_road_name"),
            f.get("district_area"),
            f"Landmark: {f.get('landmark')}" if f.get('landmark') else None
        ]
        full_location = ", ".join([p for p in location_parts if p]) or "Tamil Nadu"

        # Try to obtain geocoordinates for location
        _, lat, lon, _ = extract_location(full_location)

        full_description = (
            f"**Problem:** {problem}\n\n"
            f"**Location Details:**\n"
            f"- Exact Location: {f.get('exact_location', 'N/A')}\n"
            f"- Street/Road: {f.get('street_road_name', 'N/A')}\n"
            f"- District/Area: {f.get('district_area', 'N/A')}\n"
            f"- Landmark: {f.get('landmark', 'N/A')}\n\n"
            f"**Timeline & Status:**\n"
            f"- Date & Time: {f.get('date_and_time', 'N/A')}\n"
            f"- Frequency: {f.get('frequency', 'N/A')}\n"
            f"- Current Status: {f.get('current_status', 'N/A')}\n\n"
            f"**Additional Details:** {f.get('additional_details', 'None')}\n"
            f"**Citizen Contact:** {f.get('citizen_details', 'N/A')}"
        )

        title = f"{category} issue at {f.get('district_area') or f.get('street_road_name') or 'Location'}"

        # Use TELEPHONY_IVR source when call_sid is provided (phone call), else WEB_VOICE
        complaint_source = ComplaintSource.TELEPHONY_IVR if call_sid else ComplaintSource.WEB_VOICE

        complaint_in = ComplaintCreate(
            title=title[:200],
            description=full_description,
            category=category,
            location=full_location[:255],
            latitude=lat,
            longitude=lon,
            priority=priority,
            language=session.get("language", "English"),
            source=complaint_source,
            citizen_confirmed=True,
            ai_metadata={
                "collected_fields": f,
                "intake_method": "multilingual_conversational_ai",
                "session_id": session.get("session_id"),
                "call_sid": call_sid,
                "caller_phone": caller_phone,
                "sms_status": sms_status,
                "sms_sid": sms_sid,
                "sms_sent_at": None
            }
        )

        citizen_id = current_user.id if current_user else None
        created = complaint_service.create_complaint(db=db, complaint_in=complaint_in, citizen_id=citizen_id)

        session["created_complaint_number"] = created.complaint_number
        session["created_complaint_id"] = created.id
        session["state"] = "REGISTERED"

        return created


complaint_collector = ComplaintCollector()
