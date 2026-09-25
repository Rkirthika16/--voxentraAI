import re
import uuid
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from sqlalchemy.orm import Session

from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text
from app.ai.classification_service import classify_complaint, DEPARTMENT_MAPPING
from app.ai.location_service import extract_location
from app.ai.priority_service import assess_priority
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintSource
from app.models.department import Department
from app.models.user import User
from app.services.complaint_service import complaint_service

logger = logging.getLogger("voxentra.conversation")


@dataclass
class ConversationContext:
    session_id: str
    language: str = "Tamil"  # "Tamil" | "English" | "Tanglish" | "Mixed (Tamil/English)"
    category: Optional[str] = None
    problem: Optional[str] = None
    location: Optional[str] = None
    district: Optional[str] = None
    area: Optional[str] = None
    street: Optional[str] = None
    landmark: Optional[str] = None
    duration: Optional[str] = None
    severity: Optional[str] = None
    affected_scope: Optional[str] = None  # "area_wide" | "individual_house" | None
    priority: Optional[str] = None
    department: Optional[str] = None
    summary: Optional[str] = None
    missing_fields: List[str] = field(default_factory=list)
    confirmation_required: bool = False
    conversation_complete: bool = False
    pending_slot_confirmation: Optional[Dict[str, Any]] = None
    original_transcription: str = ""
    normalized_transcription: str = ""
    analysis_method: str = "offline_rule_based"
    clarification_turn_count: int = 0
    max_clarification_questions: int = 3
    turns: List[Dict[str, Any]] = field(default_factory=list)
    caller_phone: Optional[str] = None
    citizen_name: Optional[str] = None
    complaint_id: Optional[int] = None
    complaint_number: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# In-memory session store
CONVERSATION_STORE: Dict[str, ConversationContext] = {}


class ConversationService:
    """
    VoxentraAI Natural Live Conversational Voice Engine.
    Responsibilities:
    - Maintain structured ConversationContext
    - Process each user turn without pre-selecting languages or static questionnaires
    - Extract complaint information (Problem, Location, Duration, Scope, Severity)
    - Detect missing information dynamically
    - Category-specific question selection (Water, Electricity, Roads, Drainage, Sanitation, etc.)
    - Determine when sufficient information is gathered
    - Generate confirmation summaries and handle explicit confirmation / corrections
    """

    def get_or_create_context(self, session_id: Optional[str] = None, caller_phone: Optional[str] = None) -> ConversationContext:
        sid = session_id or f"conv_{uuid.uuid4().hex[:12]}"
        if sid not in CONVERSATION_STORE:
            ctx = ConversationContext(
                session_id=sid,
                caller_phone=caller_phone
            )
            CONVERSATION_STORE[sid] = ctx
        return CONVERSATION_STORE[sid]

    def reset_session(self, session_id: str):
        if session_id in CONVERSATION_STORE:
            del CONVERSATION_STORE[session_id]

    def _extract_duration(self, text: str) -> Optional[str]:
        """Extracts problem duration in Tamil, English, and Tanglish."""
        lowered = text.lower()
        patterns = [
            (r'\b(\d+\s*days?(?:-ah)?)\b', lambda m: m.group(1).replace("-ah", "").strip()),
            (r'\b(two\s*days?(?:-ah)?)\b', lambda m: "2 days"),
            (r'\b(three\s*days?(?:-ah)?)\b', lambda m: "3 days"),
            (r'\b(four\s*days?(?:-ah)?)\b', lambda m: "4 days"),
            (r'\b(five\s*days?(?:-ah)?)\b', lambda m: "5 days"),
            (r'\b(one\s*week(?:-ah)?)\b', lambda m: "1 week"),
            (r'\b(since\s*yesterday)\b', lambda m: "since yesterday"),
            (r'\b(today\s*(?:morning|afternoon|evening|night)?)\b', lambda m: m.group(0).strip()),
            (r'\b(yesterday\s*(?:morning|afternoon|evening|night)?)\b', lambda m: m.group(0).strip()),
            (r'\b(\d+\s*(?:நாட்களாக|நாளாக|நாளா))\b', lambda m: m.group(1).strip()),
            (r'\b((?:மூன்று|மூணு|இரண்டு|ரெண்டு|நான்கு|நாலு|ஐந்து|அஞ்சு)\s*(?:நாட்களாக|நாளாக|நாளா))\b', lambda m: m.group(1).strip()),
            (r'\b(இன்று\s*(?:காலை|மாலை|இரவு)?)\b', lambda m: m.group(0).strip()),
            (r'\b(நேற்று\s*(?:காலை|மாலை|இரவு)?)\b', lambda m: m.group(0).strip()),
            (r'\b(rendu\s*naala|moonu\s*naala|oru\s*varama)\b', lambda m: m.group(0).strip())
        ]
        for pat, formatter in patterns:
            match = re.search(pat, lowered)
            if match:
                return formatter(match)
        return None

    def _extract_affected_scope(self, text: str) -> Optional[str]:
        """Extracts whether the problem affects the whole area or only the individual house."""
        lowered = text.lower()
        area_keywords = [
            "area full-ah", "area full", "entire area", "whole area", "whole street", "all houses",
            "street full-ah", "full-ah", "எல்லா வீடுகளிலும்", "மொத்த பகுதி", "தெரு முழுவதும்",
            "area fulla", "area wide", "full area", "மொத்தமா", "எல்லாருக்கும்"
        ]
        house_keywords = [
            "my house only", "unga veetla mattum", "enga veetla mattum", "enga veedu mattum",
            "individual house", "only our house", "வீட்டில் மட்டும்", "என் வீட்டில் மட்டும்",
            "enga veetla", "my home only", "just my house"
        ]
        if any(k in lowered for k in area_keywords):
            return "Entire area"
        if any(k in lowered for k in house_keywords):
            return "Individual house only"
        return None

    def _extract_street_and_landmark(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts street name and nearby landmarks."""
        street = None
        landmark = None

        street_match = re.search(r'\b(\d+(?:st|nd|rd|th)?\s+(?:street|road|salai|theru|cross|avenue|lane)|(?:[A-Z][a-z0-9]+\s+){1,3}(?:Street|Road|Salai|Theru|Cross|Avenue|Lane|Main\s+Road)|[A-Za-z0-9]{3,20}\s+(?:street|road|salai|theru|cross|avenue|lane))\b', text, re.IGNORECASE)
        if street_match:
            cand = street_match.group(1).strip()
            cand = re.sub(r'^(?:in\s+the|in\s+this|on\s+the|the|this|that|inda|indha|இந்த|அந்த|எங்கள்|என்)\s+', '', cand, flags=re.IGNORECASE).strip()
            cand_low = cand.lower()
            generic_streets = [
                "our street", "my street", "the street", "in the street", "in our street", "enga theru",
                "street", "road", "this street", "that street", "in this street", "theru", "salai", "veethi"
            ]
            if len(cand) >= 3 and cand_low not in generic_streets and not any(cand_low.endswith(g) for g in ["in the street", "in our street"]):
                street = cand
        else:
            ta_street = re.search(r'([\u0B80-\u0BFF\s0-9]{3,25}(?:தெரு|சாலை|வீதி|நகர்\s*மெயின்\s*ரோடு))', text)
            if ta_street:
                cand = ta_street.group(1).strip()
                cand = re.sub(r'^(?:இந்த|அந்த|எங்கள்|என்|நமது)\s+', '', cand).strip()
                if len(cand) >= 3 and cand not in ["எங்கள் தெரு", "என் தெரு", "தெரு", "சாலை", "இந்த தெரு"]:
                    street = cand

        landmark_match = re.search(r'\b(?:near|opposite|behind|beside|next to|close to|opp|kitta|pakkam|pakathula)\s+([A-Za-z0-9\s\.\,\-]+?)(?:\.|\,|$|\band\b)', text, re.IGNORECASE)
        if landmark_match:
            cand_lm = landmark_match.group(1).strip()
            cand_lm = re.sub(r'^(?:the|this|that|a|an|in\s+the|near\s+the|இந்த|அந்த)\s+', '', cand_lm, flags=re.IGNORECASE).strip()
            if len(cand_lm) >= 3 and cand_lm.lower() not in ["area", "street", "road", "place", "house", "veedu", "theru"]:
                landmark = cand_lm
        else:
            ta_landmark = re.search(r'([\u0B80-\u0BFF\s]+)\s+(?:அருகில்|எதிரில்|பின்னால்|பக்கத்தில்)', text)
            if ta_landmark:
                cand_lm = ta_landmark.group(1).strip()
                cand_lm = re.sub(r'^(?:இந்த|அந்த)\s+', '', cand_lm).strip()
                if len(cand_lm) >= 3 and cand_lm not in ["பகுதி", "தெரு", "வீடு", "இடம்"]:
                    landmark = cand_lm

        return street, landmark

    def _is_confirmation(self, text: str) -> Tuple[bool, bool]:
        """Checks if speech is a confirmation (decision_made, is_confirmed)."""
        lowered = text.strip().lower()
        positives = [
            "yes", "confirm", "confirmed", "proceed", "okay", "ok", "correct", "right",
            "aama", "aamam", "seri", "kandippa", "pannunga", "podunga", "submit", "register",
            "ஆமாம்", "சரி", "உறுதி", "பதிவு செய்க", "பதிவு செய்", "ஆம்", "sure", "go ahead"
        ]
        negatives = [
            "no", "cancel", "stop", "wait", "change", "edit", "wrong", "thappu", "illai", "illa",
            "vendaam", "வேண்டாம்", "இல்லை", "மாற்ற வேண்டும்", "தவறு", "modify"
        ]
        if any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in positives) or any(w in lowered for w in ["ஆமாம்", "சரி", "பதிவு", "ஆம்"]):
            return True, True
        if any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in negatives) or any(w in lowered for w in ["வேண்டாம்", "இல்லை", "தவறு"]):
            return True, False
        return False, False

    def is_unclear_speech(self, text: str) -> bool:
        """Checks if input is garbled, unintelligible, or pure mumbling."""
        raw = text.strip()
        if not raw:
            return True
        cleaned = re.sub(r'[\.\?\!\,\-\_\s]+', '', raw.lower())
        if not cleaned:
            return True

        # Valid conversational and affirmative words must never be treated as mumbles
        valid_words = {
            "aama", "aamam", "ama", "amam", "aam", "seri", "ok", "yes", "no", "right", "correct", "sure",
            "confirm", "confirmed", "proceed", "cancel", "stop", "wait", "change", "edit", "wrong",
            "thappu", "illa", "illai", "vendaam", "kandippa", "pannunga", "podunga", "submit", "register",
            "ஆமாம்", "சரி", "உறுதி", "பதிவு", "ஆம்", "இல்லை", "வேண்டாம்", "தவறு"
        }
        if cleaned in valid_words or any(w in valid_words for w in re.split(r'[\s\.\,\-\_\?\!]+', raw.lower()) if w):
            return False

        mumbles = {"umm", "uhh", "uhhh", "aaa", "hmm", "huh", "enna", "mm", "ah", "err", "uh", "um", "er", "ha", "zzz", "ummuhhh", "ummuh"}
        if cleaned in mumbles or len(cleaned) <= 1:
            return True
        words = [w for w in re.split(r'[\s\.\,\-\_\?\!]+', raw.lower()) if w]
        if words and all(w in mumbles or re.match(r'^[umhz]+$', w) for w in words):
            return True
        if re.search(r'(.)\1{3,}', cleaned):
            return True
        return False

    def get_unclear_response(self, lang: str) -> Tuple[str, str]:
        """Provides polite clarification when speech is unclear or unrecognized."""
        if lang == "Tamil":
            return (
                "மன்னிக்கவும், நான் அதை சரியாக புரிந்து கொள்ளவில்லை என நினைக்கிறேன். தயவுசெய்து மீண்டும் கூற முடியுமா அல்லது சரியான எழுத்துக் கூட்டலை (spelling) கூற முடியுமா?",
                "மன்னிக்கவும், நான் அதை சரியாக புரிந்து கொள்ளவில்லை என நினைக்கிறேன். தயவுசெய்து மீண்டும் கூற முடியுமா அல்லது சரியான எழுத்துக் கூட்டலை கூற முடியுமா?"
            )
        elif lang == "Tanglish":
            return (
                "I’m sorry, naan adha sariya purinjikkala. Marubadiyum solreengala illa correct spelling solreengala?",
                "I'm sorry, naan adha sariya purinjikkala. Marubadiyum solreengala illa correct spelling solreengala?"
            )
        else:
            return (
                "I’m sorry, I may not have understood that correctly. Could you please say it again or provide the correct spelling?",
                "I'm sorry, I may not have understood that correctly. Could you please say it again or provide the correct spelling?"
            )

    def get_spelling_or_correction_prompt(self, candidate: str, lang: str) -> Tuple[str, str]:
        """Returns polite confirmation question when a possible spelling or recognition variation is detected."""
        if lang == "Tamil":
            text = f"நான் இதை '{candidate}' என்று புரிந்து கொண்டேன். இது சரியானதா, அல்லது சரியான எழுத்துக் கூட்டலை (spelling) கூற முடியுமா?"
            spoken = f"நான் இதை '{candidate}' என்று புரிந்து கொண்டேன். இது சரியானதா, அல்லது சரியான பெயரை கூற முடியுமா?"
        elif lang == "Tanglish":
            text = f"Naan idhai '{candidate}' nu purinjikiten. Idhu correct-ah, illa correct spelling solreengala?"
            spoken = f"Naan idhai '{candidate}' nu purinjikiten. Idhu correct-ah, illa correct spelling solreengala?"
        else:
            text = f"I understood it as {candidate}. Is that correct, or could you please provide the correct spelling?"
            spoken = f"I understood it as {candidate}. Is that correct, or could you please provide the correct spelling?"
        return text, spoken

    def clean_spelled_out_input(self, text: str) -> str:
        """Cleans and reconstructs spelled-out inputs like 'P E E L A M E D U'."""
        raw = text.strip()
        prefix_pattern = r'^(?:no\s*,?\s*(?:it\s*is|its|it\'s|actually|wait)?|correct\s*(?:is|spelling\s*is)?|correction\s*:?|illai\s*,?|illa\s*,?|thappu\s*,?|மாற்றி\s*,?|இல்லை\s*,?|தவறு\s*,?)\s*'
        cleaned = re.sub(prefix_pattern, '', raw, flags=re.IGNORECASE).strip()

        if re.match(r'^[A-Za-z\u0B80-\u0BFF](?:[\s\-\.][A-Za-z\u0B80-\u0BFF]){2,}$', cleaned):
            joined = re.sub(r'[\s\-\.]+', '', cleaned)
            return joined.title() if joined.isascii() else joined

        return cleaned or raw

    def detect_explicit_correction(
        self,
        ctx: ConversationContext,
        text: str,
        lang: str = "English"
    ) -> Optional[Tuple[str, str, str, str]]:
        """Detects explicit slot corrections like 'Change location to Madurai', 'No it is Peelamedu'."""
        raw = text.strip()
        if not raw:
            return None
        lowered = raw.lower()

        # Location explicit correction
        loc_match = re.search(
            r'(?:(?:change|update|modify|maathu|maathunga|மாற்று|மாற்றவும்)\s+(?:the\s*)?(?:district|area|location|place|city|town|மாவட்டம்|பகுதி|இடம்|ஊர்)|(?:district|location|area|place|மாவட்டம்|பகுதி|இடம்)\s+(?:name\s+is|is|to|:|endru|nu\s+maathunga)\s*)\s*([A-Za-z0-9\u0B80-\u0BFF\s\-\,]+)',
            raw,
            re.IGNORECASE
        )
        if not loc_match:
            loc_match = re.search(
                r'(?:மாவட்டம்|பகுதி|இடம்|ஊர்|district|area|location)\s+([A-Za-z0-9\u0B80-\u0BFF\s\-\,]+?)\s+(?:என\s+மாற்றவும்|என\s+மாற்று|ஆக\s+மாற்றவும்|endru\s+maathunga|nu\s+maathunga|nu\s+maathavum|maathunga|maathavum)',
                raw,
                re.IGNORECASE
            )
        if loc_match and any(w in lowered for w in ["change", "update", "modify", "district", "location", "area", "மாவட்டம்", "பகுதி", "இடம்", "maathu", "maathunga", "மாற்று", "மாற்றவும்"]):
            cand = loc_match.group(1).strip()
            cand = re.sub(r'^(?:to|is|name\s*is|as|என்)\s+', '', cand, flags=re.IGNORECASE).strip()
            cand = re.sub(r'\s+(?:nu|nu maathunga|endru|maathunga|maathavum|please|sollunga)$', '', cand, flags=re.IGNORECASE).strip()
            if len(cand) >= 2 and cand.lower() not in ["to", "is", "nu", "the", "change", "full-ah", "full", "fulla", "wide"]:
                cand_clean = self.clean_spelled_out_input(cand)
                ctx.location = cand_clean
                ctx.pending_slot_confirmation = None
                if lang == "Tamil":
                    ack_r = f"சரி, உங்கள் இடம் '{cand_clean}' என மாற்றப்பட்டது. 👍"
                    ack_s = f"சரி, உங்கள் இடம் {cand_clean} என மாற்றப்பட்டது."
                elif lang == "Tanglish":
                    ack_r = f"Sure, unga location '{cand_clean}' nu update panniyaachu. 👍"
                    ack_s = f"Sure, unga location {cand_clean} nu update panniyaachu."
                else:
                    ack_r = f"Understood! I have updated your location to '{cand_clean}'. 👍"
                    ack_s = f"Understood! I have updated your location to {cand_clean}."
                return "location", cand_clean, ack_r, ack_s

        # Spelled-out letters (e.g. "P E E L A M E D U", "P-E-E-L-A-M-E-D-U")
        prefix_pattern = r'^(?:no\s*,?\s*(?:it\s*is|its|it\'s|actually|wait)?|correct\s*(?:is|spelling\s*is)?|correction\s*:?|illai\s*,?|illa\s*,?|thappu\s*,?|மாற்றி\s*,?|இல்லை\s*,?|தவறு\s*,?)\s*'
        stripped_prefix = re.sub(prefix_pattern, '', raw, flags=re.IGNORECASE).strip()
        is_letter_by_letter = bool(re.match(r'^[A-Za-z\u0B80-\u0BFF](?:[\s\-\.][A-Za-z\u0B80-\u0BFF]){2,}$', stripped_prefix))

        if is_letter_by_letter:
            joined = re.sub(r'[\s\-\.]+', '', stripped_prefix)
            cleaned_spelled = joined.title() if joined.isascii() else joined
            ctx.location = cleaned_spelled
            ctx.pending_slot_confirmation = None
            if lang == "Tamil":
                ack_r = f"சரி, நீங்கள் கூறிய {cleaned_spelled} பதிவு செய்யப்பட்டது. 👍"
                ack_s = f"சரி, {cleaned_spelled} பதிவு செய்யப்பட்டது."
            elif lang == "Tanglish":
                ack_r = f"Sure, {cleaned_spelled} update panniyaachu. 👍"
                ack_s = f"Sure, {cleaned_spelled} update panniyaachu."
            else:
                ack_r = f"Understood! I have recorded {cleaned_spelled} as your location. 👍"
                ack_s = f"Understood! I have recorded {cleaned_spelled} as your location."
            return "location", cleaned_spelled, ack_r, ack_s

        return None

    def generate_confirmation_summary(self, ctx: ConversationContext) -> Tuple[str, str]:
        """Generates structured pre-registration summary in detected language."""
        dept = ctx.department or "Municipal Administration"
        prob = ctx.problem or "Civic Grievance"
        disp_loc = self.get_display_location(ctx.location)
        duration_str = ctx.duration or "Recently"
        scope_str = ctx.affected_scope or ""
        cat_lower = (ctx.category or "Civic issue").lower()

        if ctx.language == "Tamil":
            text = (
                f"உங்கள் புகார் {disp_loc} பகுதி {prob} பற்றியது. "
                f"{duration_str} நாட்களாக பிரச்சினை உள்ளது" + (f", {scope_str}" if scope_str else "") + ". "
                "புகாரை பதிவு செய்யலாமா?"
            )
            spoken = (
                f"உங்கள் புகார் {disp_loc} பகுதி {prob} பற்றியது. "
                f"காலம் {duration_str}. புகாரை பதிவு செய்யலாமா?"
            )
        elif ctx.language == "Tanglish":
            text = (
                f"Ungaloda complaint {disp_loc} area {cat_lower} pathi. "
                f"{duration_str} issue irukku" + (f", {scope_str}" if scope_str else "") + ". "
                "Complaint register pannava?"
            )
            spoken = (
                f"Ungaloda complaint {disp_loc} area {cat_lower} pathi. "
                f"{duration_str} issue irukku. Complaint register pannava?"
            )
        else:
            text = (
                f"Your complaint is regarding {cat_lower} in {disp_loc} area for {duration_str}"
                + (f" affecting {scope_str}" if scope_str else "") + ". "
                "Shall I register the complaint now?"
            )
            spoken = (
                f"Your complaint is regarding {cat_lower} in {disp_loc} area for {duration_str}. "
                "Shall I register this complaint now?"
            )

        return text, spoken

    def get_display_location(self, loc: Optional[str]) -> str:
        """Returns clean, primary place name for natural speech (e.g. 'Annur' from 'Annur & Pillayampalayam, Coimbatore District')."""
        if not loc or loc == "Tamil Nadu":
            return "Tamil Nadu"
        # Take first part before comma or ampersand
        clean = loc.split(",")[0].split("&")[0].strip()
        return clean or loc

    def get_category_followup_question(self, ctx: ConversationContext) -> Tuple[str, str]:
        """
        Dynamically chooses the next most relevant question based on:
        - Complaint category (Water, Electricity, Roads, Drainage, Sanitation, etc.)
        - Already collected vs missing fields
        - Does NOT re-ask details already provided
        """
        cat = ctx.category or "Other"
        lang = ctx.language
        disp_loc = self.get_display_location(ctx.location)

        # 1. Location missing
        if not ctx.location or ctx.location == "Tamil Nadu":
            if lang == "Tamil":
                return (
                    "சரி. இந்த பிரச்சினை எந்த பகுதியில் அல்லது தெருவில் உள்ளது?",
                    "சரி. இந்த பிரச்சினை எந்த பகுதியில் உள்ளது?"
                )
            elif lang == "Tanglish":
                return (
                    "Seri. Indha problem endha area or street-la irukku?",
                    "Seri. Indha problem endha area-la irukku?"
                )
            else:
                return (
                    "Okay. In which area or street did this problem occur?",
                    "In which area or street did this problem occur?"
                )

        # 2. Duration missing
        if not ctx.duration:
            if cat == "Water":
                if lang == "Tamil":
                    return (
                        f"சரி, {disp_loc} பகுதியில் தண்ணீர் விநியோகப் பிரச்சினை உள்ளதை புரிந்து கொண்டேன். இது எப்போது இருந்து உள்ளது?",
                        f"சரி, {disp_loc} பகுதியில் தண்ணீர் பிரச்சினை உள்ளதை புரிந்து கொண்டேன். இது எப்போது இருந்து உள்ளது?"
                    )
                elif lang == "Tanglish":
                    return (
                        f"Okay, {disp_loc}-la water supply problem irukku-nu purinjukitten. Idhu eppo lendhu irukku?",
                        f"Okay, {disp_loc}-la water supply problem irukku-nu purinjukitten. Idhu eppo lendhu irukku?"
                    )
                else:
                    return (
                        f"Understood, there is a water supply issue in {disp_loc}. How long has this problem existed?",
                        f"Understood, there is a water supply issue in {disp_loc}. How long has this problem existed?"
                    )
            elif cat == "Electricity":
                if lang == "Tamil":
                    return (
                        f"சரி, {disp_loc} பகுதியில் மின் தடை ஏற்பட்டுள்ளதை புரிந்து கொண்டேன். இது எப்போது இருந்து உள்ளது?",
                        f"சரி, {disp_loc} பகுதியில் மின் தடை ஏற்பட்டுள்ளதை புரிந்து கொண்டேன். இது எப்போது இருந்து உள்ளது?"
                    )
                elif lang == "Tanglish":
                    return (
                        f"Okay, {disp_loc}-la power supply issue irukku-nu purinjukitten. Idhu eppo lendhu irukku?",
                        f"Okay, {disp_loc}-la power supply issue irukku-nu purinjukitten. Idhu eppo lendhu irukku?"
                    )
                else:
                    return (
                        f"Understood, there is a power cut in {disp_loc}. How long has this power issue existed?",
                        f"Understood, there is a power cut in {disp_loc}. How long has this power issue existed?"
                    )
            elif cat == "Roads":
                if lang == "Tamil":
                    return (
                        f"சரி, {disp_loc} பகுதியில் சாலை சேதம் உள்ளதை புரிந்து கொண்டேன். இது எத்தனை நாட்களாக உள்ளது?",
                        f"சரி, {disp_loc} பகுதியில் சாலை சேதம் உள்ளதை புரிந்து கொண்டேன். இது எத்தனை நாட்களாக உள்ளது?"
                    )
                elif lang == "Tanglish":
                    return (
                        f"Okay, {disp_loc}-la road damage problem irukku-nu note pannitten. Idhu eppo lendhu irukku?",
                        f"Okay, {disp_loc}-la road damage problem irukku-nu note pannitten. Idhu eppo lendhu irukku?"
                    )
                else:
                    return (
                        f"Understood, there is road damage in {disp_loc}. How long has this issue existed?",
                        f"Understood, there is road damage in {disp_loc}. How long has this issue existed?"
                    )
            elif cat == "Drainage":
                if lang == "Tamil":
                    return (
                        f"சரி, {disp_loc} பகுதியில் சாக்கடை பிரச்சினை உள்ளதை புரிந்து கொண்டேன். இது எப்போது இருந்து உள்ளது?",
                        f"சரி, {disp_loc} பகுதியில் சாக்கடை பிரச்சினை உள்ளதை புரிந்து கொண்டேன். இது எப்போது இருந்து உள்ளது?"
                    )
                elif lang == "Tanglish":
                    return (
                        f"Okay, {disp_loc}-la drainage problem irukku-nu note pannitten. Idhu eppo lendhu irukku?",
                        f"Okay, {disp_loc}-la drainage problem irukku-nu note pannitten. Idhu eppo lendhu irukku?"
                    )
                else:
                    return (
                        f"Understood, there is a drainage problem in {disp_loc}. How long has this been happening?",
                        f"Understood, there is a drainage problem in {disp_loc}. How long has this been happening?"
                    )
            elif cat == "Sanitation":
                if lang == "Tamil":
                    return (
                        f"சரி, {disp_loc} பகுதியில் குப்பைகள் தேங்கியுள்ளதை புரிந்து கொண்டேன். இது எத்தனை நாட்களாக உள்ளது?",
                        f"சரி, {disp_loc} பகுதியில் குப்பைகள் தேங்கியுள்ளதை புரிந்து கொண்டேன். இது எத்தனை நாட்களாக உள்ளது?"
                    )
                elif lang == "Tanglish":
                    return (
                        f"Okay, {disp_loc}-la garbage problem irukku-nu note pannitten. Idhu eppo lendhu irukku?",
                        f"Okay, {disp_loc}-la garbage problem irukku-nu note pannitten. Idhu eppo lendhu irukku?"
                    )
                else:
                    return (
                        f"Understood, there is a sanitation issue in {disp_loc}. How long has this been uncollected?",
                        f"Understood, there is a sanitation issue in {disp_loc}. How long has this been uncollected?"
                    )
            else:
                if lang == "Tamil":
                    return (
                        f"சரி, {disp_loc} பகுதியில் இந்தப் பிரச்சினை எப்போது இருந்து உள்ளது?",
                        f"இந்தப் பிரச்சினை எப்போது இருந்து உள்ளது?"
                    )
                elif lang == "Tanglish":
                    return (
                        f"Okay, {disp_loc}-la indha issue eppo lendhu irukku?",
                        f"Idhu eppo lendhu irukku?"
                    )
                else:
                    return (
                        f"Okay, how long has this problem existed in {disp_loc}?",
                        "How long has this problem existed?"
                    )

        # 3. Category-Specific Depth Questions (Scope & Impact)
        if cat == "Water" and not ctx.affected_scope:
            if lang == "Tamil":
                return (
                    "சரி. இது பகுதி முழுவதும் உள்ள பிரச்சினையா அல்லது உங்கள் வீட்டில் மட்டுமா?",
                    "சரி. இது பகுதி முழுவதும் உள்ள பிரச்சினையா அல்லது உங்கள் வீட்டில் மட்டுமா?"
                )
            elif lang == "Tanglish":
                return (
                    "Seri. Area full-ah problem-aa, illa unga veetla mattum-aa?",
                    "Seri. Area full-ah problem-aa, illa unga veetla mattum-aa?"
                )
            else:
                return (
                    "Understood. Is this water supply problem affecting the entire area or only your house?",
                    "Is this water supply problem affecting the entire area or only your house?"
                )

        if cat == "Electricity" and not ctx.affected_scope:
            if lang == "Tamil":
                return (
                    "சரி. இது பகுதி முழுவதும் உள்ள மின்வெட்டா அல்லது உங்கள் வீட்டில் மட்டுமா?",
                    "சரி. இது பகுதி முழுவதும் உள்ள மின்வெட்டா அல்லது உங்கள் வீட்டில் மட்டுமா?"
                )
            elif lang == "Tanglish":
                return (
                    "Seri. Area full-ah power cut-aa, illa unga veetla mattum-aa?",
                    "Seri. Area full-ah power cut-aa, illa unga veetla mattum-aa?"
                )
            else:
                return (
                    "Understood. Is this power cut area-wide or for your house only?",
                    "Is this power cut area-wide or for your house only?"
                )

        if cat == "Roads" and not ctx.severity:
            if lang == "Tamil":
                return (
                    "சரி. சாலை சேதத்தால் போக்குவரத்து பாதிப்பு அல்லது விபத்து அபாயம் ஏதேனும் உள்ளதா?",
                    "சாலை சேதத்தால் போக்குவரத்து பாதிப்பு ஏதேனும் உள்ளதா?"
                )
            elif lang == "Tanglish":
                return (
                    "Seri. Indha road damage-naala traffic block or accident risk ethavathu irukka?",
                    "Indha road damage-naala traffic block ethavathu irukka?"
                )
            else:
                return (
                    "Understood. Is this road damage causing severe traffic obstruction or accident hazard?",
                    "Is this road damage causing traffic obstruction?"
                )

        if cat == "Drainage" and not ctx.affected_scope:
            if lang == "Tamil":
                return (
                    "சரி. சாக்கடை நீர் சாலையில் வழிகிறதா அல்லது அடைப்பு மட்டுமா?",
                    "சாக்கடை நீர் சாலையில் வழிகிறதா?"
                )
            elif lang == "Tanglish":
                return (
                    "Seri. Drainage water road-la overflow aagudha, illa adaippu mattum-aa?",
                    "Drainage water road-la overflow aagudha?"
                )
            else:
                return (
                    "Understood. Is the sewage overflowing onto the public road or is it a pipe blockage?",
                    "Is the sewage overflowing onto the road?"
                )

        if cat == "Sanitation" and not ctx.affected_scope:
            if lang == "Tamil":
                return (
                    "சரி. குப்பைகள் பொது இடத்தில் அதிகளவில் தேங்கியுள்ளதா?",
                    "குப்பைகள் பொது இடத்தில் அதிகளவில் தேங்கியுள்ளதா?"
                )
            elif lang == "Tanglish":
                return (
                    "Seri. Kuppai public area-la romba thengi irukka?",
                    "Kuppai public area-la romba thengi irukka?"
                )
            else:
                return (
                    "Understood. Is the uncollected garbage overflowing in the public area?",
                    "Is the garbage overflowing in the public area?"
                )

        # Everything critical is collected! Transition to confirmation
        ctx.confirmation_required = True
        return self.generate_confirmation_summary(ctx)

    def _build_turn_response(
        self,
        ctx: ConversationContext,
        state: str,
        ai_text: str,
        ai_spoken: str,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Constructs standardized conversation response matching backend and telephony transports."""
        if ctx.conversation_complete or state == "COMPLETED":
            conv_state = "CONFIRMED"
        elif state == "ERROR":
            conv_state = "ERROR"
        elif state == "CANCELLED":
            conv_state = "CANCELLED"
        else:
            conv_state = "WAITING_FOR_CITIZEN"

        lat = None
        lon = None
        osm_name = None
        if ctx.location:
            try:
                from app.ai.location_service import extract_location
                osm_name, lat, lon, _ = extract_location(ctx.location)
            except Exception:
                pass

        analysis_dict = {
            "category": ctx.category or "Other",
            "location": ctx.location or "",
            "problem": ctx.problem or "",
            "duration": ctx.duration or "",
            "affected_scope": ctx.affected_scope or "",
            "severity": ctx.severity or "normal",
            "priority": ctx.priority or "MEDIUM",
            "department": ctx.department or "Municipal Administration"
        }

        return {
            "session_id": ctx.session_id,
            "transcription": ctx.original_transcription,
            "original_transcription": ctx.original_transcription,
            "normalized_transcription": ctx.normalized_transcription,
            "language": ctx.language,
            "detected_language": ctx.language,
            "analysis": analysis_dict,
            "latitude": lat,
            "longitude": lon,
            "osm_location_name": osm_name or ctx.location,
            "response_text": ai_text,
            "ai_text": ai_text,
            "ai_spoken": ai_spoken,
            "audio_base64": None,
            "conversation_state": conv_state,
            "state": state,
            "should_continue": not ctx.conversation_complete,
            "complaint_id": ctx.complaint_id,
            "complaint_number": ctx.complaint_number,
            "context": ctx.to_dict(),
            "confirmation_required": ctx.confirmation_required,
            "conversation_complete": ctx.conversation_complete,
            "speech_recognition_available": True,
            "error": error
        }

    def process_turn(
        self,
        session_id: str,
        user_speech: str,
        db: Optional[Session] = None,
        caller_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main multi-turn conversation pipeline:
        1. Capture speech & maintain original vs normalized
        2. Detect language & dialect dynamically
        3. Extract slot entities without re-asking what was provided
        4. Decide next step (clarification question vs summary confirmation vs registration)
        5. Return structured JSON with state, spoken audio text, and metadata
        """
        ctx = self.get_or_create_context(session_id, caller_phone)
        ctx.original_transcription = (user_speech or "").strip()
        ctx.normalized_transcription = normalize_text(ctx.original_transcription)

        # Check for unclear input
        if self.is_unclear_speech(ctx.original_transcription):
            unclear_txt, unclear_spk = self.get_unclear_response(ctx.language)
            return self._build_turn_response(ctx, "WAITING_FOR_USER", unclear_txt, unclear_spk)

        # Dynamically detect language from this turn and adapt
        turn_lang, conf = detect_language(ctx.original_transcription)
        ctx.language = turn_lang

        # 0. Check if session has a pending slot confirmation (e.g. confirming misheard word or location candidate)
        if ctx.pending_slot_confirmation:
            pending = ctx.pending_slot_confirmation
            detected_word = pending.get("detected_word", "")
            is_dec, is_conf = self._is_confirmation(ctx.original_transcription)

            if is_dec and is_conf:
                # Citizen confirmed the detected word
                ctx.location = detected_word
                ctx.pending_slot_confirmation = None
                if ctx.language == "Tamil":
                    ack_reply = f"நன்றி, **{detected_word}** உறுதிப்படுத்தப்பட்டது. 👍"
                    ack_spoken = f"நன்றி, {detected_word} உறுதிப்படுத்தப்பட்டது."
                elif ctx.language == "Tanglish":
                    ack_reply = f"Thanks, **{detected_word}** confirm panniyaachu. 👍"
                    ack_spoken = f"Thanks, {detected_word} confirm panniyaachu."
                else:
                    ack_reply = f"Thank you, **{detected_word}** has been confirmed. 👍"
                    ack_spoken = f"Thank you, {detected_word} has been confirmed."

                # If enough info, generate confirmation summary, else next question
                is_sufficient = bool(ctx.problem and ctx.location and (ctx.duration or ctx.affected_scope or ctx.clarification_turn_count >= ctx.max_clarification_questions))
                if is_sufficient:
                    ctx.confirmation_required = True
                    sum_txt, sum_spk = self.generate_confirmation_summary(ctx)
                    return self._build_turn_response(ctx, "CONFIRMING", f"{ack_reply}\n\n{sum_txt}", f"{ack_spoken} {sum_spk}")
                else:
                    q_txt, q_spk = self.get_category_followup_question(ctx)
                    return self._build_turn_response(ctx, "WAITING_FOR_USER", f"{ack_reply} {q_txt}", f"{ack_spoken} {q_spk}")

            # Check if citizen provided a replacement / spelled out correction
            cleaned_correction = self.clean_spelled_out_input(ctx.original_transcription)
            rejection_words = ["no", "wrong", "thappu", "illa", "illai", "இல்லை", "தவறு", "வேண்டாம்"]
            if ctx.original_transcription.lower().strip() in rejection_words:
                if ctx.language == "Tamil":
                    r_txt = "சரி, தயவுசெய்து சரியான பெயர் அல்லது எழுத்துக் கூட்டலை (spelling) கூறவும்."
                    r_spk = "தயவுசெய்து சரியான பெயரை அல்லது எழுத்துக்களைக் கூறவும்."
                elif ctx.language == "Tanglish":
                    r_txt = "Sure, please correct place name or spelling sollunga."
                    r_spk = "Please correct place name or spelling sollunga."
                else:
                    r_txt = "Understood. Please provide the correct name or spelling."
                    r_spk = "Please provide the correct name or spelling."

                return self._build_turn_response(ctx, "WAITING_FOR_USER", r_txt, r_spk)

            if cleaned_correction and len(cleaned_correction) >= 2:
                ctx.location = cleaned_correction
                ctx.pending_slot_confirmation = None
                if ctx.language == "Tamil":
                    ack_reply = f"நன்றி, நீங்கள் கூறிய **{cleaned_correction}** பதிவு செய்யப்பட்டது. 👍"
                    ack_spoken = f"நன்றி, {cleaned_correction} பதிவு செய்யப்பட்டது."
                elif ctx.language == "Tanglish":
                    ack_reply = f"Thanks, **{cleaned_correction}** noted. 👍"
                    ack_spoken = f"Thanks, {cleaned_correction} noted."
                else:
                    ack_reply = f"Thank you, **{cleaned_correction}** has been noted. 👍"
                    ack_spoken = f"Thank you, {cleaned_correction} has been noted."

                is_sufficient = bool(ctx.problem and ctx.location and (ctx.duration or ctx.affected_scope or ctx.clarification_turn_count >= ctx.max_clarification_questions))
                if is_sufficient:
                    ctx.confirmation_required = True
                    sum_txt, sum_spk = self.generate_confirmation_summary(ctx)
                    return self._build_turn_response(ctx, "CONFIRMING", f"{ack_reply}\n\n{sum_txt}", f"{ack_spoken} {sum_spk}")
                else:
                    q_txt, q_spk = self.get_category_followup_question(ctx)
                    return self._build_turn_response(ctx, "WAITING_FOR_USER", f"{ack_reply} {q_txt}", f"{ack_spoken} {q_spk}")

        # 0b. Check for explicit slot correction
        explicit_corr = self.detect_explicit_correction(ctx, ctx.original_transcription, ctx.language)
        if explicit_corr:
            corr_field, new_val, ack_r, ack_s = explicit_corr
            is_sufficient = bool(ctx.problem and ctx.location and (ctx.duration or ctx.affected_scope or ctx.clarification_turn_count >= ctx.max_clarification_questions))
            if is_sufficient:
                ctx.confirmation_required = True
                sum_txt, sum_spk = self.generate_confirmation_summary(ctx)
                return self._build_turn_response(ctx, "CONFIRMING", f"{ack_r}\n\n{sum_txt}", f"{ack_s} {sum_spk}")
            else:
                q_txt, q_spk = self.get_category_followup_question(ctx)
                return self._build_turn_response(ctx, "WAITING_FOR_USER", f"{ack_r} {q_txt}", f"{ack_s} {q_spk}")

        # Category & Problem classification (ensure category/problem always captured early)
        cat, dept, conf = classify_complaint(ctx.normalized_transcription)
        if cat != "Other" or not ctx.category:
            ctx.category = cat
            ctx.department = dept

        if not ctx.problem:
            ctx.problem = ctx.original_transcription

        # 0c. Check for potential spelling or STT recognition variation in location without guessing
        from app.ai.location_service import find_fuzzy_location_candidate
        fuzzy_cand = find_fuzzy_location_candidate(ctx.original_transcription)
        if fuzzy_cand and (not ctx.location or ctx.location == "Tamil Nadu"):
            cand_name = fuzzy_cand[0].split(",")[0].split("&")[0].strip()
            if cand_name.lower() != ctx.original_transcription.strip().lower():
                ctx.pending_slot_confirmation = {
                    "field": "location",
                    "detected_word": cand_name,
                    "raw_input": ctx.original_transcription
                }
                conf_txt, conf_spk = self.get_spelling_or_correction_prompt(cand_name, ctx.language)
                return self._build_turn_response(ctx, "SLOT_CONFIRMATION_PENDING", conf_txt, conf_spk)

        # Check if citizen is in confirmation stage
        if ctx.confirmation_required and not ctx.conversation_complete:
            is_dec, is_conf = self._is_confirmation(ctx.original_transcription)
            if is_dec:
                if is_conf:
                    # Citizen confirmed! Create database record
                    ctx.conversation_complete = True
                    created_comp = self._create_database_complaint(ctx, db)
                    ctx.complaint_id = created_comp.id
                    ctx.complaint_number = created_comp.complaint_number

                    if ctx.language == "Tamil":
                        ai_text = (
                            f"நன்றி! உங்கள் புகார் எண் {created_comp.complaint_number} என வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது. "
                            f"இது {ctx.department} துறைக்கு அனுப்பப்பட்டுள்ளது."
                        )
                        ai_spoken = (
                            f"சரி. உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டது. புகார் எண் {created_comp.complaint_number}."
                        )
                    elif ctx.language == "Tanglish":
                        ai_text = (
                            f"Seri. Unga complaint successfully registered. Complaint ID {created_comp.complaint_number}. "
                            f"{ctx.department} ku forward panniyaachu."
                        )
                        ai_spoken = (
                            f"Seri. Unga complaint successfully registered. Complaint ID {created_comp.complaint_number}."
                        )
                    else:
                        ai_text = (
                            f"Thank you. Your complaint has been successfully registered under ID {created_comp.complaint_number} "
                            f"and routed to {ctx.department}."
                        )
                        ai_spoken = (
                            f"Your complaint has been successfully registered. Complaint ID {created_comp.complaint_number}."
                        )

                    return self._build_turn_response(ctx, "COMPLETED", ai_text, ai_spoken)
                else:
                    # Citizen wants to correct / change details
                    ctx.confirmation_required = False
                    if ctx.language == "Tamil":
                        ai_text = "சரி, எந்த விவரத்தை மாற்ற வேண்டும் என்று கூறவும்."
                        ai_spoken = "எந்த விவரத்தை மாற்ற வேண்டும் என்று கூறவும்."
                    elif ctx.language == "Tanglish":
                        ai_text = "Seri, endha detail ah change pannanum nu sollunga."
                        ai_spoken = "Endha detail ah change pannanum nu sollunga."
                    else:
                        ai_text = "Understood. Please let me know what detail you would like to correct."
                        ai_spoken = "Please let me know what detail you would like to correct."

                    return self._build_turn_response(ctx, "WAITING_FOR_USER", ai_text, ai_spoken)

        # -------------------------------------------------------------
        # Information Extraction from Current Speech
        # -------------------------------------------------------------
        # Category & Problem classification
        cat, dept, conf = classify_complaint(ctx.normalized_transcription)
        if cat != "Other" or not ctx.category:
            ctx.category = cat
            ctx.department = dept

        if not ctx.problem:
            ctx.problem = ctx.original_transcription

        # Location extraction
        from app.ai.location_service import extract_location, is_valid_tamil_nadu_location, find_fuzzy_location_candidate
        loc_name, lat, lon, lconf = extract_location(ctx.normalized_transcription)
        if loc_name and loc_name != "Tamil Nadu":
            if lconf >= 0.85:
                ctx.location = loc_name
            else:
                is_valid, loc_obj, vconf = is_valid_tamil_nadu_location(loc_name)
                if is_valid and loc_obj:
                    ctx.location = loc_obj["name"]
                else:
                    fuzzy = find_fuzzy_location_candidate(loc_name)
                    if fuzzy:
                        cand_name = fuzzy[0].split(",")[0].split("&")[0].strip()
                        ctx.pending_slot_confirmation = {
                            "field": "location",
                            "detected_word": cand_name,
                            "raw_input": ctx.original_transcription
                        }
                        conf_txt, conf_spk = self.get_spelling_or_correction_prompt(cand_name, ctx.language)
                        return self._build_turn_response(ctx, "SLOT_CONFIRMATION_PENDING", conf_txt, conf_spk)
                    else:
                        ctx.location = loc_name

        # Street and landmark
        st, lm = self._extract_street_and_landmark(ctx.original_transcription)
        if st and not ctx.street:
            ctx.street = st
            if not ctx.location or ctx.location == "Tamil Nadu":
                ctx.location = st
        if lm and not ctx.landmark:
            ctx.landmark = lm

        # Duration
        dur = self._extract_duration(ctx.original_transcription)
        if dur:
            ctx.duration = dur

        # Affected Scope
        scope = self._extract_affected_scope(ctx.original_transcription)
        if scope:
            ctx.affected_scope = scope

        # Priority calculation
        priority, reasons = assess_priority(ctx.normalized_transcription, ctx.category)
        ctx.priority = priority.value if hasattr(priority, 'value') else str(priority)

        # Check for immediate electrical / safety hazard
        if ctx.category == "Electricity" and any(w in ctx.normalized_transcription.lower() for w in ["spark", "தீப்பொறி", "shock", "live wire", "அறுந்த கம்பி"]):
            ctx.priority = "CRITICAL"
            ctx.severity = "critical"

        # -------------------------------------------------------------
        # Decision: Sufficient Information vs Next Question
        # -------------------------------------------------------------
        ctx.clarification_turn_count += 1

        # Check if enough information is collected:
        needs_scope = ctx.category in ["Water", "Electricity"] and not ctx.affected_scope and ctx.clarification_turn_count < 3
        is_sufficient = bool(
            ctx.problem and ctx.location and ctx.duration and not needs_scope
        ) or (ctx.problem and ctx.location and ctx.clarification_turn_count >= ctx.max_clarification_questions)

        if is_sufficient and not ctx.confirmation_required:
            ctx.confirmation_required = True
            ai_text, ai_spoken = self.generate_confirmation_summary(ctx)
            state = "CONFIRMING"
        else:
            ai_text, ai_spoken = self.get_category_followup_question(ctx)
            state = "CONFIRMING" if ctx.confirmation_required else "WAITING_FOR_USER"

        # Record turn history
        ctx.turns.append({
            "turn_index": len(ctx.turns) + 1,
            "user_speech": ctx.original_transcription,
            "normalized_speech": ctx.normalized_transcription,
            "detected_language": ctx.language,
            "ai_text": ai_text,
            "ai_spoken": ai_spoken,
            "state": state
        })

        return self._build_turn_response(ctx, state, ai_text, ai_spoken)

    def _create_database_complaint(self, ctx: ConversationContext, db: Optional[Session]) -> Complaint:
        """Saves confirmed grievance to database and triggers notifications."""
        from app.database.session import SessionLocal
        owns_session = False
        if db is None:
            db = SessionLocal()
            owns_session = True

        try:
            category = ctx.category or "Other"
            priority_val = ComplaintPriority[ctx.priority] if ctx.priority in ComplaintPriority.__members__ else ComplaintPriority.MEDIUM

            # Map department
            dept_obj = db.query(Department).filter(Department.name.ilike(f"%{ctx.department or category}%")).first()
            dept_id = dept_obj.id if dept_obj else 1

            location_parts = [ctx.landmark, ctx.street, ctx.location]
            full_loc = ", ".join([p for p in location_parts if p]) or "Tamil Nadu"

            from app.schemas.complaint import ComplaintCreate
            complaint_obj = ComplaintCreate(
                title=f"{category} grievance at {ctx.location or 'Tamil Nadu'}"[:200],
                description=ctx.problem or "Grievance reported via live voice assistant",
                category=category,
                priority=priority_val,
                location=full_loc[:255],
                source=ComplaintSource.WEB_VOICE,
                language=ctx.language or "English",
                ai_metadata={
                    "session_id": ctx.session_id,
                    "language": ctx.language,
                    "duration": ctx.duration,
                    "affected_scope": ctx.affected_scope,
                    "analysis_method": ctx.analysis_method,
                    "turns_count": len(ctx.turns)
                }
            )

            created_complaint = complaint_service.create_complaint(
                db=db,
                complaint_in=complaint_obj
            )
            if ctx.caller_phone:
                created_complaint.citizen_phone = ctx.caller_phone
                db.commit()

            # Send SMS confirmation via Twilio integration
            from app.integrations.telephony.twilio_adapter import twilio_adapter
            sms_body = twilio_adapter.build_complaint_sms(
                complaint_number=created_complaint.complaint_number,
                description=ctx.problem or "Civic Grievance",
                department=ctx.department or "Municipal Administration",
                location=full_loc,
                lang=ctx.language,
                created_at=created_complaint.created_at
            )
            twilio_adapter.send_sms(ctx.caller_phone or "+919843098765", sms_body)

            return created_complaint
        finally:
            if owns_session:
                db.close()


conversation_service = ConversationService()
