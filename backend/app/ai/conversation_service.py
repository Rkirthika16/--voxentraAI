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

        street_match = re.search(r'\b([A-Za-z0-9\.\s]+(?:street|road|salai|theru|cross|avenue|lane|nagar\s+main\s+road))\b', text, re.IGNORECASE)
        if street_match:
            cand = street_match.group(1).strip()
            if cand.lower() not in ["our street", "my street", "the street", "enga theru", "street", "road"]:
                street = cand
        else:
            ta_street = re.search(r'([\u0B80-\u0BFF\s0-9]+(?:தெரு|சாலை|வீதி|நகர்\s*மெயின்\s*ரோடு))', text)
            if ta_street:
                cand = ta_street.group(1).strip()
                if cand not in ["எங்கள் தெரு", "என் தெரு", "தெரு", "சாலை"]:
                    street = cand

        landmark_match = re.search(r'\b(?:near|opposite|behind|beside|next to|close to|opp|kitta|pakkam|pakathula)\s+([A-Za-z0-9\s\.\,\-]+?)(?:\.|\,|$|\band\b)', text, re.IGNORECASE)
        if landmark_match:
            landmark = landmark_match.group(1).strip()
        else:
            ta_landmark = re.search(r'([\u0B80-\u0BFF\s]+)\s+(?:அருகில்|எதிரில்|பின்னால்|பக்கத்தில்)', text)
            if ta_landmark:
                landmark = ta_landmark.group(1).strip()

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
        mumbles = {"umm", "uhh", "uhhh", "aaa", "hmm", "huh", "enna", "mm", "ah", "err", "uh", "um", "er", "ha", "zzz", "ummuhhh", "ummuh"}
        if cleaned in mumbles or len(cleaned) <= 1:
            return True
        words = re.findall(r'[a-zA-Z\u0B80-\u0BFF]+', raw.lower())
        if words and all(w in mumbles or re.match(r'^[uamhze]+$', w) for w in words):
            return True
        if re.search(r'(.)\1{3,}', cleaned):
            return True
        return False

    def get_unclear_response(self, lang: str) -> Tuple[str, str]:
        """Provides polite clarification when speech is unclear."""
        if lang == "Tamil":
            return (
                "மன்னிக்கவும், உங்கள் குரல் தெளிவாக புரியவில்லை. தயவுசெய்து மீண்டும் ஒருமுறை கூறவும்.",
                "மன்னிக்கவும், உங்கள் குரல் தெளிவாக புரியவில்லை. தயவுசெய்து மீண்டும் கூறவும்."
            )
        elif lang == "Tanglish":
            return (
                "Sorry, unga voice-la konjam clear-ah puriyala. Please repeat pannunga.",
                "Sorry, unga voice clear-ah puriyala. Please repeat pannunga."
            )
        else:
            return (
                "I'm sorry, I couldn't hear that clearly. Could you please repeat your complaint?",
                "I'm sorry, I couldn't hear that clearly. Could you please repeat?"
            )

    def generate_confirmation_summary(self, ctx: ConversationContext) -> Tuple[str, str]:
        """Generates structured pre-registration summary in detected language."""
        dept = ctx.department or "Municipal Administration"
        prob = ctx.problem or "Civic Grievance"
        loc = ctx.location or "Not specified"
        duration_str = ctx.duration or "Recently"
        scope_str = ctx.affected_scope or "Not specified"
        priority_str = ctx.priority or "MEDIUM"

        if ctx.language == "Tamil":
            text = (
                "உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன்:\n\n"
                f"📋 பிரச்சினை: {prob}\n"
                f"🏢 துறை: {dept}\n"
                f"📍 இடம்: {loc}\n"
                f"⏱️ காலம்: {duration_str}\n"
                f"👥 பாதிக்கப்பட்ட அளவு: {scope_str}\n"
                f"⚡ முன்னுரிமை: {priority_str}\n\n"
                "இந்த தகவல்கள் சரியாக இருக்கிறதா? புகாரை பதிவு செய்யலாமா?"
            )
            spoken = (
                f"உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன். "
                f"பிரச்சினை: {prob}. இடம்: {loc}. காலம்: {duration_str}. துறை: {dept}. "
                "இந்த தகவல்கள் சரியாக இருக்கிறதா? புகாரை பதிவு செய்யலாமா?"
            )
        elif ctx.language == "Tanglish":
            text = (
                "Ungaloda complaint summary:\n\n"
                f"📋 Problem: {prob}\n"
                f"🏢 Department: {dept}\n"
                f"📍 Location: {loc}\n"
                f"⏱️ Duration: {duration_str}\n"
                f"👥 Affected scope: {scope_str}\n"
                f"⚡ Priority: {priority_str}\n\n"
                "Idha complaint-ah register pannalama?"
            )
            spoken = (
                f"Ungaloda complaint summary: "
                f"{prob}. Location: {loc}. Duration: {duration_str}. Department: {dept}. "
                "Idha confirm pannalama?"
            )
        else:
            text = (
                "Here is your complaint summary:\n\n"
                f"📋 Issue: {prob}\n"
                f"🏢 Department: {dept}\n"
                f"📍 Location: {loc}\n"
                f"⏱️ Duration: {duration_str}\n"
                f"👥 Affected Area: {scope_str}\n"
                f"⚡ Priority: {priority_str}\n\n"
                "Are these details correct? Shall I register the complaint?"
            )
            spoken = (
                f"Here is your complaint summary: "
                f"{prob} at {loc}. Duration: {duration_str}. Department: {dept}. "
                "Are these details correct? Shall I register this complaint now?"
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
        - Priority indicators (sparks/wires -> immediate urgent handling)
        """
        cat = ctx.category or "Other"
        lang = ctx.language
        disp_loc = self.get_display_location(ctx.location)

        # 1. Location missing
        if not ctx.location:
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
            if lang == "Tamil":
                return (
                    f"சரி, {disp_loc} பகுதியில் இந்தப் பிரச்சினை எத்தனை நாட்களாக அல்லது எப்போது இருந்து உள்ளது?",
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

        # 3. Category-Specific Depth Questions
        if cat == "Water" and not ctx.affected_scope:
            if lang == "Tamil":
                return (
                    "இது உங்கள் பகுதியில் உள்ள அனைவருக்கும் உள்ள பிரச்சனையா அல்லது உங்கள் வீட்டில் மட்டுமா?",
                    "இது பகுதி முழுவதும் உள்ள பிரச்சனையா அல்லது உங்கள் வீட்டில் மட்டுமா?"
                )
            elif lang == "Tanglish":
                return (
                    "Idhu area full-ah water problem-aa, illa unga veetla mattum-aa?",
                    "Idhu area full-ah water problem-aa, illa unga veetla mattum-aa?"
                )
            else:
                return (
                    "Is this a water interruption affecting the entire area or only your individual house?",
                    "Is this affecting the entire area or only your house?"
                )

        if cat == "Electricity":
            if not ctx.affected_scope:
                if lang == "Tamil":
                    return (
                        "இது மொத்த பகுதியில் ஏற்பட்டுள்ள மின்வெட்டா அல்லது உங்கள் வீட்டில் மட்டுமா? தீப்பொறி அல்லது அறுந்த கம்பி ஏதேனும் உள்ளதா?",
                        "இது பகுதி முழுவதும் உள்ள மின்வெட்டா அல்லது உங்கள் வீட்டில் மட்டுமா?"
                    )
                elif lang == "Tanglish":
                    return (
                        "Idhu area full-ah power cut-aa, illa unga veetla mattum-aa? Any live wire or spark risk irukka?",
                        "Idhu area full-ah power cut-aa, illa unga veetla mattum-aa?"
                    )
                else:
                    return (
                        "Is this power failure affecting the entire area or only your house? Are there any exposed wires or sparks?",
                        "Is this power failure area-wide or for your house only?"
                    )

        if cat == "Roads" and not ctx.severity:
            if lang == "Tamil":
                return (
                    "இந்த சாலை சேதத்தால் போக்குவரத்து பாதிப்பு அல்லது விபத்து அபாயம் ஏதேனும் உள்ளதா?",
                    "சாலை சேதத்தால் போக்குவரத்து பாதிப்பு ஏதேனும் உள்ளதா?"
                )
            elif lang == "Tanglish":
                return (
                    "Indha road damage-naala traffic block or accident risk ethavathu irukka?",
                    "Indha road damage-naala traffic block ethavathu irukka?"
                )
            else:
                return (
                    "Is this road damage causing traffic congestion or accident hazard?",
                    "Is this road damage affecting traffic or safety?"
                )

        if cat == "Drainage" and not ctx.affected_scope:
            if lang == "Tamil":
                return (
                    "சாக்கடை நீர் சாலையில் வழிகிறதா அல்லது அடைப்பு மட்டுமா?",
                    "சாக்கடை நீர் சாலையில் வழிகிறதா?"
                )
            elif lang == "Tanglish":
                return (
                    "Drainage water road-la overflow aagudha, illa adaippu mattum-aa?",
                    "Drainage water road-la overflow aagudha?"
                )
            else:
                return (
                    "Is the sewage overflowing onto the public road or is it a localized blockage?",
                    "Is the sewage overflowing onto the road?"
                )

        if cat == "Sanitation" and not ctx.affected_scope:
            if lang == "Tamil":
                return (
                    "குப்பைகள் பொது இடத்தில் அதிகளவில் தேங்கியுள்ளதா? துர்நாற்றம் அல்லது சுகாதார சீர்கேடு உள்ளதா?",
                    "குப்பைகள் பொது இடத்தில் அதிகளவில் தேங்கியுள்ளதா?"
                )
            elif lang == "Tanglish":
                return (
                    "Kuppai public area-la romba thengi irukka? Bad smell or health hazard irukka?",
                    "Kuppai public area-la romba thengi irukka?"
                )
            else:
                return (
                    "Is the uncollected garbage overflowing into public areas or causing foul odor?",
                    "Is the garbage overflowing into public areas?"
                )

        # Everything critical is collected! Transition to confirmation
        ctx.confirmation_required = True
        return self.generate_confirmation_summary(ctx)

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
            return {
                "session_id": ctx.session_id,
                "state": "WAITING_FOR_USER",
                "ai_text": unclear_txt,
                "ai_spoken": unclear_spk,
                "detected_language": ctx.language,
                "context": ctx.to_dict(),
                "confirmation_required": ctx.confirmation_required,
                "conversation_complete": ctx.conversation_complete
            }

        # Dynamically detect language from this turn and adapt
        turn_lang, conf = detect_language(ctx.original_transcription)
        ctx.language = turn_lang

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
                            f"இது {ctx.department} துறைக்கு அனுப்பப்பட்டுள்ளது. இந்த எண்ணை பயன்படுத்தி தங்கள் புகாரை கண்காணிக்கலாம்."
                        )
                        ai_spoken = (
                            f"உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது. உங்கள் புகார் எண் {created_comp.complaint_number}. "
                            "இந்த எண்ணை பயன்படுத்தி உங்கள் புகாரை கண்காணிக்கலாம்."
                        )
                    elif ctx.language == "Tanglish":
                        ai_text = (
                            f"Thank you! Unga complaint #{created_comp.complaint_number} successfully register aaiduchu. "
                            f"{ctx.department} ku assign panniyaachu. Tracking ID: {created_comp.complaint_number}."
                        )
                        ai_spoken = (
                            f"Unga complaint successfully register aaiduchu. Unga complaint number {created_comp.complaint_number}. "
                            "Indha number use panni track pannalaam."
                        )
                    else:
                        ai_text = (
                            f"Thank you! Your complaint #{created_comp.complaint_number} has been successfully registered "
                            f"and routed to {ctx.department}. You can track your grievance using ID {created_comp.complaint_number}."
                        )
                        ai_spoken = (
                            f"Your complaint has been successfully registered under ID {created_comp.complaint_number}. "
                            "You can use this number to track your complaint."
                        )

                    return {
                        "session_id": ctx.session_id,
                        "state": "COMPLETED",
                        "ai_text": ai_text,
                        "ai_spoken": ai_spoken,
                        "detected_language": ctx.language,
                        "complaint_number": created_comp.complaint_number,
                        "complaint_id": created_comp.id,
                        "context": ctx.to_dict(),
                        "confirmation_required": False,
                        "conversation_complete": True
                    }
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

                    return {
                        "session_id": ctx.session_id,
                        "state": "WAITING_FOR_USER",
                        "ai_text": ai_text,
                        "ai_spoken": ai_spoken,
                        "detected_language": ctx.language,
                        "context": ctx.to_dict(),
                        "confirmation_required": False,
                        "conversation_complete": False
                    }

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
        loc_name, lat, lon, lconf = extract_location(ctx.normalized_transcription)
        if loc_name and loc_name != "Tamil Nadu":
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
        # (Has problem + location + (duration or scope or max turns reached))
        is_sufficient = bool(
            ctx.problem and ctx.location and (ctx.duration or ctx.affected_scope or ctx.clarification_turn_count >= ctx.max_clarification_questions)
        )

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

        return {
            "session_id": ctx.session_id,
            "state": state,
            "ai_text": ai_text,
            "ai_spoken": ai_spoken,
            "detected_language": ctx.language,
            "context": ctx.to_dict(),
            "confirmation_required": ctx.confirmation_required,
            "conversation_complete": ctx.conversation_complete
        }

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
