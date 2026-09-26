import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from app.models.tollfree import TollFreeCallSession, TollFreeMessage, TollFreeState
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintSource
from app.models.department import Department
from app.schemas.complaint import ComplaintCreate
from app.services.complaint_service import complaint_service
from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text, clean_transcription
from app.ai.classification_service import classify_complaint
from app.ai.location_service import extract_location, normalize_structured_location
from app.ai.priority_service import assess_priority
from app.integrations.telephony.provider_interface import generic_telephony_provider

logger = logging.getLogger("voxentra.tollfree_service")

# Configurable Department Master
DEPARTMENT_MASTER = {
    "Water Supply": "Water Supply Department",
    "Water": "Water Supply Department",
    "Electricity": "Electricity & Power Department",
    "Power": "Electricity & Power Department",
    "Roads": "Roads & Highways Department",
    "Roads & Infrastructure": "Roads & Highways Department",
    "Sanitation / Solid Waste Management": "Sanitation & Solid Waste Management Department",
    "Garbage": "Sanitation & Solid Waste Management Department",
    "Drainage": "Drainage & Sewerage Department",
    "Drainage / Sewerage": "Drainage & Sewerage Department",
    "Street Lighting": "Street Lighting & Electrical Department",
    "Streetlights": "Street Lighting & Electrical Department",
    "Public Transport": "Transport Department",
    "Public Health": "Public Health & Sanitation Department",
    "Public Safety": "Public Safety & Municipal Enforcement",
    "Animal Control": "Animal Control & Public Safety",
    "Revenue / Property Tax": "Revenue & Property Tax Department",
    "Civil Registration": "Civil Registration Department",
    "Other": "General Municipal Administration"
}

ORDERED_QUESTION_SLOTS = [
    "problem_description",
    "district_area",
    "duration",
    "affected_scope"
]


class TollFreeService:
    """
    Two-Way Conversational Engine for the VoxentraAI Toll-Free Grievance Helpline.
    Enforces strict turn-taking (Citizen speaks first, AI asks one question at a time),
    continuous conversation memory, language adaptation (Tamil, English, Tanglish),
    pre-registration confirmation, and real database complaint generation.
    """

    def create_call_session(
        self,
        db: Session,
        caller_phone: Optional[str] = "+919843098765",
        provider_call_id: Optional[str] = None,
        toll_free_number: str = "1800-425-8693"
    ) -> Tuple[TollFreeCallSession, str, str]:
        """
        Creates incoming toll-free call session and places call in silent LISTENING mode (Citizen speaks first).
        """
        session_id = f"tf_sess_{uuid.uuid4().hex[:12]}"

        initial_memory = {
            "problem_description": None,
            "problem": None,
            "category": None,
            "department": None,
            "district_area": None,
            "area": None,
            "street_road_name": None,
            "street": None,
            "exact_location": None,
            "landmark": None,
            "city": None,
            "district": None,
            "state": "Tamil Nadu",
            "start_time": None,
            "duration": None,
            "affected_scope": None,
            "affected_area": None,
            "frequency": None,
            "previous_complaint": None,
            "previous_complaint_number": None,
            "severity": None,
            "safety_hazard": None,
            "additional_details": None,
            "citizen_name": None,
            "citizen_phone": caller_phone or "+919843098765",
            "priority": "MEDIUM",
            "questions_asked_count": 0,
            "max_questions": 10,
            "raw_citizen_input": "",
            "corrected_transcription": ""
        }

        session = TollFreeCallSession(
            call_session_id=session_id,
            provider_call_id=provider_call_id,
            caller_phone=caller_phone or "+919843098765",
            toll_free_number=toll_free_number,
            language="Auto",
            state=TollFreeState.WAITING_FOR_CITIZEN.value,
            structured_memory=initial_memory,
            raw_transcript="",
            normalized_transcript="",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Silent mode on start: Citizen speaks first
        greeting_text = ""
        greeting_spoken = ""

        logger.info(f"[TollFree] Call connected: {session_id} from {caller_phone}. Waiting for citizen first utterance.")
        return session, greeting_text, greeting_spoken

    def get_session(self, db: Session, session_id: str) -> Optional[TollFreeCallSession]:
        return db.query(TollFreeCallSession).filter(
            (TollFreeCallSession.call_session_id == session_id) |
            (TollFreeCallSession.provider_call_id == session_id)
        ).first()

    def process_dialogue_turn(
        self,
        db: Session,
        session_id: str,
        speech_text: str,
        audio_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes one complete two-way conversational turn with speech correction,
        language detection & switching, dynamic questioning, confirmation, and DB saving.
        """
        session = self.get_session(db, session_id)
        if not session:
            return {
                "success": False,
                "error_code": "SESSION_NOT_FOUND",
                "message": f"Toll-free session '{session_id}' not found",
                "state": TollFreeState.ERROR.value
            }

        raw_text = speech_text.strip()
        if not raw_text:
            return self._handle_unclear_input(db, session, "EMPTY_INPUT")

        # 1. Clean & normalize speech while preserving raw text
        cleaned = clean_transcription(raw_text)
        normalized_str = normalize_text(raw_text)

        # 2. Dynamic Language Detection with Session Stickiness
        current_lang = session.language if session.language not in ["Auto", None] else None
        detected_lang, conf = detect_language(raw_text, current_session_lang=current_lang)
        session.language = detected_lang
        session.language_confidence = float(conf)

        # Record citizen message
        citizen_msg = TollFreeMessage(
            session_id=session.id,
            role="citizen",
            content=raw_text,
            normalized_content=cleaned,
            language=detected_lang,
            audio_url=audio_url,
            created_at=datetime.now(timezone.utc)
        )
        db.add(citizen_msg)

        # Append to full transcript records
        session.raw_transcript = (session.raw_transcript + f"\nCitizen: {raw_text}").strip()
        session.normalized_transcript = (session.normalized_transcript + f"\nCitizen: {cleaned}").strip()
        db.commit()

        # Update in-memory transcript
        memory = dict(session.structured_memory or {})
        memory["raw_citizen_input"] = (memory.get("raw_citizen_input", "") + f"\n{raw_text}").strip()
        memory["corrected_transcription"] = (memory.get("corrected_transcription", "") + f"\n{cleaned}").strip()

        # 3. Check for Mumbles / Unclear Audio
        if self._is_unclear_mumble(raw_text):
            return self._handle_unclear_input(db, session, "UNCLEAR_SPEECH")

        # 4. Check if currently in CONFIRMATION state
        if session.state == TollFreeState.CONFIRMATION.value:
            is_decision, is_confirmed = self._is_confirmation_response(raw_text)
            if is_decision:
                if is_confirmed:
                    return self._finalize_and_register_complaint(db, session)
                else:
                    session.state = TollFreeState.WAITING_FOR_CITIZEN.value
                    db.commit()
                    return self._generate_edit_prompt(db, session, detected_lang)

        # 5. Extract slots & update structured memory
        prompted_slot = session.current_field_prompted
        self._extract_and_update_memory(raw_text, cleaned, memory, prompted_slot=prompted_slot)

        # Synchronize columns with memory
        session.category = memory.get("category")
        session.problem = memory.get("problem_description") or memory.get("problem")
        session.location = memory.get("area") or memory.get("district_area") or memory.get("location")
        session.duration = memory.get("duration")
        session.affected_scope = memory.get("affected_scope") or memory.get("affected_area")
        session.frequency = memory.get("frequency")
        session.severity = memory.get("severity")
        session.priority = memory.get("priority", "MEDIUM")
        session.department = memory.get("department")
        session.citizen_name = memory.get("citizen_name")
        session.structured_memory = memory
        db.commit()

        # 6. Check missing slots & generate next relevant question (ONE AT A TIME)
        next_missing = self._get_next_missing_slot(memory)

        if next_missing is None:
            # Move to CONFIRMATION
            session.state = TollFreeState.CONFIRMATION.value
            session.current_field_prompted = None
            db.commit()

            summary_text, spoken_summary = self._build_confirmation_summary(memory, detected_lang)
            self._save_ai_message(db, session, summary_text, spoken_summary, detected_lang)

            confirmation_options = [
                {"label": "✅ ஆம், பதிவு செய்க (Confirm)", "text": "ஆம், புகாரை பதிவு செய்யுங்கள்"},
                {"label": "✏️ விவரங்களை மாற்று (Edit)", "text": "விவரங்களை மாற்ற வேண்டும்"}
            ] if detected_lang == "Tamil" else [
                {"label": "✅ Aama, Register Pannunga", "text": "Aama, complaint-a register pannunga"},
                {"label": "✏️ Details Maathanum", "text": "Details maathanum"}
            ] if detected_lang == "Tanglish" else [
                {"label": "✅ Yes, Register Complaint", "text": "Yes, please register the complaint"},
                {"label": "✏️ Modify Details", "text": "I want to change the details"}
            ]

            return {
                "success": True,
                "session_id": session.call_session_id,
                "state": TollFreeState.CONFIRMATION.value,
                "detected_language": detected_lang,
                "language_confidence": conf,
                "ai_reply": summary_text,
                "spoken_reply": spoken_summary,
                "memory": memory,
                "is_confirmation": True,
                "complaint_created": False,
                "options": confirmation_options
            }
        else:
            # Increment question count
            current_q_count = memory.get("questions_asked_count", 0) + 1
            memory["questions_asked_count"] = current_q_count
            session.structured_memory = memory

            session.state = TollFreeState.WAITING_FOR_CITIZEN.value
            session.current_field_prompted = next_missing
            db.commit()

            ai_reply, spoken_reply, options = self._generate_slot_question(next_missing, memory, detected_lang)
            self._save_ai_message(db, session, ai_reply, spoken_reply, detected_lang)

            return {
                "success": True,
                "session_id": session.call_session_id,
                "state": TollFreeState.WAITING_FOR_CITIZEN.value,
                "detected_language": detected_lang,
                "language_confidence": conf,
                "ai_reply": ai_reply,
                "spoken_reply": spoken_reply,
                "memory": memory,
                "next_field": next_missing,
                "is_confirmation": False,
                "complaint_created": False,
                "options": options
            }

    def _extract_and_update_memory(self, raw_text: str, cleaned: str, memory: Dict[str, Any], prompted_slot: Optional[str] = None) -> None:
        """Extracts civic entities across all 14 structured slots and updates memory."""
        lowered = cleaned.lower().strip()

        # Handle explicit corrections
        if any(w in lowered for w in ["change area", "location is", "area is", "peelamedu", "gandhipuram", "இடம்", "பகுதி மாற்று", "maathunga"]):
            loc_match = re.search(r'(?:area|location|place|actually|பகுதி|இடம்)\s+(?:is|to|:)?\s*([A-Za-z0-9\u0B80-\u0BFF\s]+)', raw_text, re.IGNORECASE)
            if loc_match:
                cand = loc_match.group(1).strip()
                if len(cand) >= 3 and cand.lower() not in ["is", "to", "the"]:
                    memory["district_area"] = cand
                    memory["area"] = cand
                    memory["location"] = cand

        if any(w in lowered for w in ["change street", "street is", "street name", "தெரு"]):
            st_match = re.search(r'(?:street|road|தெரு|சாலை)\s*(?:is|to|:)?\s*([A-Za-z0-9\u0B80-\u0BFF\s]+)', raw_text, re.IGNORECASE)
            if st_match:
                cand_st = st_match.group(1).strip()
                if len(cand_st) >= 2 and cand_st.lower() not in ["is", "to", "the"]:
                    memory["street_road_name"] = cand_st
                    memory["street"] = cand_st

        # 1. Problem & Category Detection
        if not memory.get("problem_description") or prompted_slot == "problem_description":
            cat, dept, cat_conf = classify_complaint(cleaned)
            if cat != "Other" or any(w in lowered for w in ["water", "thanni", "power", "current", "road", "garbage", "drainage", "light", "குடிநீர்", "மின்சாரம்", "குப்பை", "சாலை", "சாக்கடை"]) or prompted_slot == "problem_description":
                memory["problem_description"] = raw_text.strip()
                memory["problem"] = raw_text.strip()
                memory["category"] = cat if cat != "Other" else (memory.get("category") or "Water Supply")
                memory["department"] = DEPARTMENT_MASTER.get(memory["category"], dept)

        # 2. Location Normalization
        loc_struct = normalize_structured_location(
            cleaned,
            existing_area=memory.get("area") or memory.get("district_area"),
            existing_street=memory.get("street") or memory.get("street_road_name"),
            existing_landmark=memory.get("landmark"),
            existing_city=memory.get("city"),
            existing_district=memory.get("district")
        )

        if loc_struct.get("area"):
            memory["district_area"] = loc_struct["area"]
            memory["area"] = loc_struct["area"]
            memory["location"] = loc_struct["area"]
        if loc_struct.get("street"):
            memory["street_road_name"] = loc_struct["street"]
            memory["street"] = loc_struct["street"]
        if loc_struct.get("landmark") and not memory.get("landmark"):
            memory["landmark"] = loc_struct["landmark"]
        if loc_struct.get("city") and not memory.get("city"):
            memory["city"] = loc_struct["city"]
        if loc_struct.get("district") and not memory.get("district"):
            memory["district"] = loc_struct["district"]
        if loc_struct.get("exact_location") and not memory.get("exact_location"):
            memory["exact_location"] = loc_struct["exact_location"]

        if prompted_slot == "district_area" and not memory.get("district_area"):
            memory["district_area"] = raw_text.strip()
            memory["area"] = raw_text.strip()
            memory["location"] = raw_text.strip()
        if prompted_slot == "street_road_name" and not memory.get("street_road_name"):
            memory["street_road_name"] = raw_text.strip()
            memory["street"] = raw_text.strip()
        if prompted_slot == "exact_location" and not memory.get("exact_location"):
            memory["exact_location"] = raw_text.strip()

        # Ensure memory['location'] is always present if area is known
        if memory.get("area") and not memory.get("location"):
            memory["location"] = memory["area"]
            memory["exact_location"] = raw_text.strip()
        if prompted_slot == "landmark" and not memory.get("landmark"):
            memory["landmark"] = raw_text.strip()

        # 3. Duration & Start time
        dur_patterns = [
            r'\b(\d+\s*(?:days?|hours?|weeks?|months?)(?:-ah)?)\b',
            r'\b((?:two|three|four|five|six|seven|one|ten)\s*(?:days?|hours?|weeks?)(?:-ah)?)\b',
            r'\b(since\s*(?:yesterday|morning|last\s*week|\d+\s*days?))\b',
            r'\b(yesterday|today\s*morning|last\s*night|netru|inniku|kaalai|just\s*now|1\s*hour)\b',
            r'\b(\d+\s*(?:நாட்களாக|நாளாக|நாளா|வாரமாக|மணி நேரமாக|நாட்கள்|நாள்))\b',
            r'\b((?:ரெண்டு|மூணு|நாலு|அஞ்சு|பத்து|இரண்டு|மூன்று|ஒரு வாரம்)\s*(?:நாட்களாக|நாளாக|நாளா|நாள்|வாரம்))\b',
            r'\b(rendu\s*naal[a-z]*|moonu\s*naal[a-z]*|nethu\s*lendhu|nethula\s*irundhu|kaalaila\s*irundhu|morning\s*lendhu|romba\s*naal[a-z]*|palanaal[a-z]*|oru\s*varam[a-z]*|oru\s*masam[a-z]*|ippo\s*dhaan)\b'
        ]
        for pat in dur_patterns:
            m = re.search(pat, lowered)
            if m and not memory.get("duration"):
                memory["duration"] = m.group(0).strip()
                if not memory.get("start_time"):
                    memory["start_time"] = m.group(0).strip()
                break

        if prompted_slot == "duration" and not memory.get("duration"):
            memory["duration"] = raw_text.strip()
        if prompted_slot == "start_time" and not memory.get("start_time"):
            memory["start_time"] = raw_text.strip()

        # 4. Scope
        area_wide_indicators = [
            "full-ah", "fulla", "entire street", "whole street", "area full", "street full", "எல்லா வீடுகளும்", "முழுவதும்", "முழு தெரு",
            "ellarukum", "all houses", "colony full", "whole area", "entire area", "full street", "full-aa"
        ]
        individual_indicators = [
            "only my house", "veedu mattum", "single house", "எங்கள் வீடு மட்டும்", "enga veedu mattum",
            "en veedu", "my house", "only house", "individual"
        ]
        if any(w in lowered for w in area_wide_indicators):
            memory["affected_scope"] = "Entire street and area"
            memory["affected_area"] = "Entire street and area"
        elif any(w in lowered for w in individual_indicators):
            memory["affected_scope"] = "Single house only"
            memory["affected_area"] = "Single house only"
        elif prompted_slot == "affected_scope":
            if any(w in lowered for w in ["aama", "aamam", "ama", "aam", "yes", "seri", "sari", "ok", "okay", "correct", "right", "ஆமாம்", "சரி", "ஆம்", "sure", "kandippa", "full"]):
                memory["affected_scope"] = "Entire street and area"
                memory["affected_area"] = "Entire street and area"
            elif any(w in lowered for w in ["illa", "illai", "no", "vendaam", "இல்லை"]):
                memory["affected_scope"] = "Single house only"
                memory["affected_area"] = "Single house only"
            elif not memory.get("affected_scope"):
                memory["affected_scope"] = raw_text.strip()
                memory["affected_area"] = raw_text.strip()

        # 5. Frequency
        if any(w in lowered for w in ["daily", "every day", "dinamum", "thinamum", "தினமும்"]):
            memory["frequency"] = "Daily Recurring"
        elif any(w in lowered for w in ["first time", "mudhal murai", "முதல் முறை"]):
            memory["frequency"] = "First Time"
        elif prompted_slot == "frequency" and not memory.get("frequency"):
            memory["frequency"] = raw_text.strip()

        # 6. Previous Complaint
        if prompted_slot == "previous_complaint" and not memory.get("previous_complaint"):
            if any(w in lowered for w in ["yes", "aama", "already", "reported", "aamam", "ஆமாம்"]):
                memory["previous_complaint"] = "Yes (Previously reported)"
            elif any(w in lowered for w in ["no", "first time", "illa", "illai", "முதல் முறை", "இல்லை"]):
                memory["previous_complaint"] = "No (First time reporting)"
                memory["previous_complaint_number"] = "N/A"
            else:
                memory["previous_complaint"] = raw_text.strip()

        prev_no_match = re.search(r'\b(VX-[\w\-]+|[0-9]{4,12})\b', raw_text, re.IGNORECASE)
        if prev_no_match and not memory.get("previous_complaint_number"):
            memory["previous_complaint_number"] = prev_no_match.group(0)
            memory["previous_complaint"] = "Yes (Previously reported)"
        elif prompted_slot == "previous_complaint_number" and not memory.get("previous_complaint_number"):
            memory["previous_complaint_number"] = raw_text.strip()

        # 7. Severity & Safety Hazards
        hazard_keywords = ["danger", "hazard", "sparking", "live wire", "open wire", "pit", "hole", "fire", "smoke", "accident", "emergency", "flood", "stagnant", "smell", "mosquito", "கசிவு", "ஆபத்து", "விபத்து", "தீ", "துர்நாற்றம்", "கொசு", "aapathu"]
        if any(w in lowered for w in hazard_keywords):
            if not memory.get("safety_hazard"):
                memory["safety_hazard"] = "Immediate safety risk reported"
                memory["priority"] = "HIGH"
        if prompted_slot == "severity" and not memory.get("severity"):
            memory["severity"] = raw_text.strip()
        if prompted_slot == "safety_hazard" and not memory.get("safety_hazard"):
            if any(w in lowered for w in ["no", "illa", "illai", "nothing", "இல்லை", "ஆபத்து இல்லை"]):
                memory["safety_hazard"] = "None (No immediate safety hazard)"
            else:
                memory["safety_hazard"] = raw_text.strip()
                memory["priority"] = "HIGH"

        # 8. Additional details
        if prompted_slot == "additional_details" and not memory.get("additional_details"):
            if any(w in lowered for w in ["no", "nothing", "nothing else", "illa", "illai", "none", "வேறு இல்லை", "இல்லை"]):
                memory["additional_details"] = "None"
            else:
                memory["additional_details"] = raw_text.strip()

        # Priority Assessment
        if memory.get("problem_description"):
            prio, _ = assess_priority(memory["problem_description"], memory.get("category", "General"))
            if memory.get("safety_hazard") and "risk" in memory.get("safety_hazard", "").lower():
                memory["priority"] = "HIGH"
            else:
                memory["priority"] = prio.value if hasattr(prio, 'value') else str(prio)

    def _get_next_missing_slot(self, memory: Dict[str, Any]) -> Optional[str]:
        """Returns the next missing question slot from the prioritized checklist."""
        questions_count = memory.get("questions_asked_count", 0)
        max_q = memory.get("max_questions", 10)

        for slot in ORDERED_QUESTION_SLOTS:
            if slot == "previous_complaint_number":
                prev_rep = memory.get("previous_complaint", "")
                if not prev_rep or "no" in str(prev_rep).lower() or "first time" in str(prev_rep).lower():
                    continue

            val = memory.get(slot)
            if slot == "district_area":
                val = val or memory.get("area")
            elif slot == "street_road_name":
                val = val or memory.get("street")
            elif slot == "affected_scope":
                val = val or memory.get("affected_area")

            if not val or not str(val).strip():
                return slot

        return None

    def _generate_slot_question(self, slot: str, memory: Dict[str, Any], lang: str) -> Tuple[str, str, List[Dict[str, str]]]:
        """Generates dynamic, polite follow-up questions in Tamil, Tanglish, or English."""
        cat = memory.get("category", "General")
        area = memory.get("area") or memory.get("district_area") or "the area"
        street = memory.get("street") or memory.get("street_road_name") or area or "your street"
        dur = memory.get("duration") or ""

        options: List[Dict[str, str]] = []

        if slot == "problem_description":
            if lang == "Tamil":
                text = "வணக்கம்! நீங்கள் சந்திக்கும் பொதுப் பிரச்சினை என்ன என்று விளக்கமாகக் கூறுங்கள்."
                spoken = "நீங்கள் சந்திக்கும் பிரச்சினை என்ன என்று சொல்லுங்கள்."
                options = [
                    {"label": "💧 குடிநீர் விநியோகம் தடை", "text": "குடிநீர் விநியோகம் தடைப்பட்டுள்ளது"},
                    {"label": "⚡ மின் தடை / தீப்பொறி", "text": "மின்சாரம் தடை மற்றும் கம்பத்தில் தீப்பொறி"},
                    {"label": "🛣️ சாலை பள்ளங்கள்", "text": "சாலையில் பெரிய பள்ளங்கள் உள்ளன"},
                    {"label": "🗑️ குப்பை தேக்கம்", "text": "குப்பை அள்ளப்படாமல் தேங்கியுள்ளது"}
                ]
            elif lang == "Tanglish":
                text = "Vanakkam! Ungalukku enna civic problem irukku nu sollunga."
                spoken = "Ungalukku enna problem nu sollunga."
                options = [
                    {"label": "💧 Water supply issue", "text": "Water supply varala"},
                    {"label": "⚡ Power cut / Sparking", "text": "Power cut aaiduchu"},
                    {"label": "🛣️ Road potholes", "text": "Road-la periya gundu kuli irukku"},
                    {"label": "🗑️ Garbage accumulation", "text": "Garbage collect pannala"}
                ]
            else:
                text = "Welcome to VoxentraAI Grievance Helpline. What civic problem are you facing?"
                spoken = "What civic problem are you facing?"
                options = [
                    {"label": "💧 Water supply outage", "text": "Water supply is disrupted in our area"},
                    {"label": "⚡ Power outage", "text": "Power outage and sparking pole"},
                    {"label": "🛣️ Damaged road", "text": "Road damaged with dangerous potholes"},
                    {"label": "🗑️ Garbage uncollected", "text": "Garbage not collected"}
                ]
            return text, spoken, options

        if slot == "district_area":
            if lang == "Tamil":
                text = f"சரிங்க. இந்தப் பிரச்சினை எந்த பகுதியில் அல்லது மாவட்டத்தில் உள்ளது?"
                spoken = "இந்தப் பிரச்சினை எந்த பகுதியில் உள்ளது?"
                options = [
                    {"label": "📍 கோயம்புத்தூர் - காந்திபுரம்", "text": "கோயம்புத்தூர் காந்திபுரம் பகுதியில்"},
                    {"label": "📍 சென்னை - அண்ணா நகர்", "text": "சென்னை அண்ணா நகர் பகுதியில்"},
                    {"label": "📍 மதுரை - கே.கே.நகர்", "text": "மதுரை கே.கே.நகர் பகுதியில்"}
                ]
            elif lang == "Tanglish":
                text = f"Seri, indha problem endha area or district-la irukku?"
                spoken = "Indha problem endha area-la irukku?"
                options = [
                    {"label": "📍 Gandhipuram", "text": "Gandhipuram area"},
                    {"label": "📍 Peelamedu", "text": "Peelamedu area"},
                    {"label": "📍 Anna Nagar", "text": "Anna Nagar area"}
                ]
            else:
                text = "Which area or locality is affected?"
                spoken = "Which area or locality is affected?"
                options = [
                    {"label": "📍 Gandhipuram, Coimbatore", "text": "Gandhipuram, Coimbatore"},
                    {"label": "📍 Anna Nagar, Chennai", "text": "Anna Nagar, Chennai"}
                ]
            return text, spoken, options

        if slot == "street_road_name":
            if lang == "Tamil":
                text = f"📍 **{area}** பகுதியில் பாதிக்கப்பட்ட தெரு அல்லது சாலையின் பெயர் என்ன?"
                spoken = f"{area} பகுதியில் பாதிக்கப்பட்ட தெரு அல்லது சாலையின் பெயர் என்ன?"
                options = [
                    {"label": "📍 5வது தெரு", "text": "5வது தெரு"},
                    {"label": "📍 கிராஸ் கட் ரோடு", "text": "கிராஸ் கட் ரோடு"},
                    {"label": "📍 மெயின் ரோடு", "text": "மெயின் ரோடு"}
                ]
            elif lang == "Tanglish":
                text = f"📍 Unga street name enna? ({area}-la endha street?)"
                spoken = "Unga street name enna?"
                options = [
                    {"label": "📍 5th Street", "text": "5th street"},
                    {"label": "📍 Cross Cut Road", "text": "Cross Cut Road"},
                    {"label": "📍 Main Road", "text": "Main Road"}
                ]
            else:
                text = f"📍 What is the street name in {area}?"
                spoken = f"What is the street name in {area}?"
                options = [
                    {"label": "📍 5th Street", "text": "5th Street"},
                    {"label": "📍 Cross Cut Road", "text": "Cross Cut Road"}
                ]
            return text, spoken, options

        if slot == "exact_location":
            if lang == "Tamil":
                text = f"🎯 **{street}** பகுதியில் உள்ள குறிப்பிட்ட கதவு எண், மின் கம்ப எண் அல்லது இடம் எது?"
                spoken = "குறிப்பிட்ட கதவு எண் அல்லது மின் கம்ப எண் என்ன?"
                options = [
                    {"label": "🚪 கதவு எண் 45", "text": "கதவு எண் 45 எதிரில்"},
                    {"label": "⚡ மின் கம்பம் எண் 12", "text": "மின் கம்ப எண் 12 அருகில்"}
                ]
            elif lang == "Tanglish":
                text = f"🎯 Specific building, door number, or electric pole number theriyuma?"
                spoken = "Specific door number or spot details sollunga."
                options = [
                    {"label": "🚪 Door No. 45", "text": "Door No 45 opposite"},
                    {"label": "⚡ Pole No. 12", "text": "Near Electric Pole No 12"}
                ]
            else:
                text = f"🎯 What is the exact house, door number, or pole number on {street}?"
                spoken = "What is the exact door number or spot detail?"
                options = [
                    {"label": "🚪 Door No. 45", "text": "Opposite Door No 45"},
                    {"label": "⚡ Pole No. 12", "text": "Near Electric Pole No 12"}
                ]
            return text, spoken, options

        if slot == "landmark":
            if lang == "Tamil":
                text = f"🏛️ அதிகாரிகள் அந்த இடத்தை எளிதாகக் கண்டறிய **{street}** அருகில் உள்ள முக்கிய Landmark அடையாளம் என்ன?"
                spoken = "அருகிலுள்ள லேண்ட்மார்க் அடையாளம் என்ன?"
                options = [
                    {"label": "🚌 பேருந்து நிறுத்தம் அருகில்", "text": "பேருந்து நிறுத்தம் அருகில்"},
                    {"label": "🏛️ கோவில் அருகில்", "text": "விநாயகர் கோவில் அருகில்"}
                ]
            elif lang == "Tanglish":
                text = f"🏛️ Spot-a identify panna pakkathula irukkura nearby landmark enna?"
                spoken = "Pakkathula irukkura nearby landmark enna?"
                options = [
                    {"label": "🚌 Near Bus Stand", "text": "Near Bus Stand"},
                    {"label": "🏛️ Near Temple", "text": "Near Temple"}
                ]
            else:
                text = f"🏛️ Is there a nearby landmark near {street}?"
                spoken = "Is there a nearby landmark to locate the spot?"
                options = [
                    {"label": "🚌 Near Bus Stand", "text": "Near Bus Stand"},
                    {"label": "🏛️ Near Temple", "text": "Near Temple"}
                ]
            return text, spoken, options

        if slot == "start_time" or slot == "duration":
            if lang == "Tamil":
                text = f"⏱️ சரி. இந்தப் பிரச்சினை எப்போது முதல் நீடிக்கிறது? (எத்தனை நாட்களாக?)"
                spoken = "இந்தப் பிரச்சினை எப்போது தொடங்கியது? எத்தனை நாட்களாக நீடிக்கிறது?"
                options = [
                    {"label": "⏱️ 2 நாட்களாக", "text": "2 நாட்களாக"},
                    {"label": "⏱️ இன்று காலை முதல்", "text": "இன்று காலை முதல்"}
                ]
            elif lang == "Tanglish":
                text = f"⏱️ Seri. Indha problem eppo lendhu irukku? (Evalo naala?)"
                spoken = "Seri. Indha problem eppo lendhu irukku?"
                options = [
                    {"label": "⏱️ Rendu naala (2 days)", "text": "Rendu naala"},
                    {"label": "⏱️ Today morning", "text": "Today morning lendhu"}
                ]
            else:
                text = "⏱️ When did the problem start, and how long has it continued?"
                spoken = "How long has this problem continued?"
                options = [
                    {"label": "⏱️ For 2 days", "text": "For the past 2 days"},
                    {"label": "⏱️ Since today morning", "text": "Since today morning"}
                ]
            return text, spoken, options

        if slot == "affected_scope":
            if lang == "Tamil":
                text = f"🏘️ இந்தப் பிரச்சினை உங்கள் வீட்டிற்கு மட்டுமா, அல்லது **{street}** தெரு முழுவதும் பாதிக்கப்பட்டுள்ளதா?"
                spoken = "உங்கள் வீட்டிற்கு மட்டுமா அல்லது தெரு முழுவதும் பாதிக்கப்பட்டுள்ளதா?"
                options = [
                    {"label": "🏘️ தெரு முழுவதும்", "text": "தெருவில் உள்ள எல்லா வீடுகளுக்கும்"},
                    {"label": "🏠 எங்கள் வீடு மட்டும்", "text": "எங்கள் வீட்டிற்கு மட்டும்"}
                ]
            elif lang == "Tanglish":
                text = f"🏘️ {street} full-ah problem-aa illa unga veetukku mattum-aa?"
                spoken = f"{street} full-ah problem-aa illa unga veetukku mattum-aa?"
                options = [
                    {"label": "🏘️ Full street", "text": "Full street problem"},
                    {"label": "🏠 Enga veetukku mattum", "text": "Enga veetukku mattum dhaan"}
                ]
            else:
                text = f"🏘️ Is the problem affecting only one house or the whole street of {street}?"
                spoken = "Is this affecting one house or the entire street?"
                options = [
                    {"label": "🏘️ Entire street", "text": "Entire street is affected"},
                    {"label": "🏠 Only my house", "text": "Only my house is affected"}
                ]
            return text, spoken, options

        if slot == "frequency":
            if lang == "Tamil":
                text = f"🔄 இந்தப் பிரச்சினை எவ்வளவு அடிக்கடி நிகழ்கிறது? (முதல் முறையா அல்லது தினமும் ஏற்படுகிறதா?)"
                spoken = "இந்தப் பிரச்சினை எவ்வளவு அடிக்கடி நிகழ்கிறது?"
                options = [
                    {"label": "🆕 முதல் முறை", "text": "முதல் முறையாக இப்போது தான்"},
                    {"label": "🔄 தினமும் நிகழ்கிறது", "text": "தினமும் தொடர்ந்து நடக்கிறது"}
                ]
            elif lang == "Tanglish":
                text = f"🔄 Indha problem evalo frequency-la nadakudhu? First time-aa illa daily recurring-aa?"
                spoken = "Indha problem evalo frequency-la nadakudhu?"
                options = [
                    {"label": "🆕 First time", "text": "First time dhaan"},
                    {"label": "🔄 Daily recurring", "text": "Dinamum continuous-ah nadakudhu"}
                ]
            else:
                text = "🔄 How frequently is this problem occurring? (First time or recurring?)"
                spoken = "How frequently does this issue occur?"
                options = [
                    {"label": "🆕 First time", "text": "This is happening for the first time"},
                    {"label": "🔄 Daily recurring", "text": "Happening continuously every day"}
                ]
            return text, spoken, options

        if slot == "previous_complaint":
            if lang == "Tamil":
                text = f"📋 இந்தப் பிரச்சினை பற்றி ஏற்கனவே சம்பந்தப்பட்ட துறையில் புகார் செய்துள்ளீர்களா?"
                spoken = "இந்தப் பிரச்சினை பற்றி ஏற்கனவே புகார் செய்துள்ளீர்களா?"
                options = [
                    {"label": "🆕 முதல் முறை", "text": "இல்லை, இது முதல் முறை புகார்"},
                    {"label": "📋 ஏற்கனவே புகார் செய்தேன்", "text": "ஏற்கனவே புகார் அளித்துள்ளேன்"}
                ]
            elif lang == "Tanglish":
                text = f"📋 Indha issue pathi already municipality or helpline-la complaint pannirukeengala?"
                spoken = "Indha issue pathi already complaint pannirukeengala?"
                options = [
                    {"label": "🆕 First time report", "text": "Illa, first time report panren"},
                    {"label": "📋 Already reported", "text": "Aama, already complaint pannitom"}
                ]
            else:
                text = "📋 Have you already reported this problem previously?"
                spoken = "Have you already reported this problem previously?"
                options = [
                    {"label": "🆕 First time reporting", "text": "No, this is the first time I am reporting"},
                    {"label": "📋 Already reported", "text": "Yes, already reported earlier"}
                ]
            return text, spoken, options

        if slot == "previous_complaint_number":
            if lang == "Tamil":
                text = f"🔢 ஏற்கனவே அளித்த புகாரின் எண் (Complaint Number) தெரிந்தால் கூறவும்."
                spoken = "ஏற்கனவே அளித்த புகாரின் எண் உள்ளதா?"
                options = [
                    {"label": "ℹ️ எண் இல்லை", "text": "புகார் எண் நினைவில் இல்லை"}
                ]
            elif lang == "Tanglish":
                text = f"🔢 Previous complaint number edhavadhu irukka?"
                spoken = "Previous complaint number edhavadhu irukka?"
                options = [
                    {"label": "ℹ️ No complaint number", "text": "Complaint number illa"}
                ]
            else:
                text = "🔢 Was any previous complaint number provided?"
                spoken = "Was any previous complaint number provided?"
                options = [
                    {"label": "ℹ️ No reference number", "text": "I don't have the reference number"}
                ]
            return text, spoken, options

        if slot == "severity":
            if "water" in cat.lower():
                if lang == "Tamil":
                    text = f"💧 தண்ணீர் விநியோகம் முற்றிலும் நின்றுவிட்டதா அல்லது குறைந்த அழுத்தத்தில் வருகிறதா?"
                    spoken = "தண்ணீர் முற்றிலும் நின்றுவிட்டதா அல்லது குறைவாக வருகிறதா?"
                    options = [
                        {"label": "💧 முற்றிலும் வரவில்லை", "text": "தண்ணீர் முற்றிலும் வரவில்லை"},
                        {"label": "💧 குறைந்த பிரஷர்", "text": "குறைந்த அளவில் வருகிறது"}
                    ]
                elif lang == "Tanglish":
                    text = f"💧 Water completely stop aaiducha illa low pressure-la varudha?"
                    spoken = "Water completely stop aaiducha illa low pressure-aa?"
                    options = [
                        {"label": "💧 Completely stopped", "text": "Completely stopped"},
                        {"label": "💧 Low pressure", "text": "Low pressure-la varudhu"}
                    ]
                else:
                    text = "💧 Is the water supply completely stopped, or flowing with low pressure?"
                    spoken = "Is the water supply completely stopped or low pressure?"
                    options = [
                        {"label": "💧 Completely stopped", "text": "Water is completely stopped"},
                        {"label": "💧 Low pressure", "text": "Flowing with low pressure"}
                    ]
            elif "power" in cat.lower() or "electric" in cat.lower():
                if lang == "Tamil":
                    text = f"⚡ மின் தடை முழுமையாக உள்ளதா அல்லது குறைந்த வோல்டேஜ் பிரச்சினையா?"
                    spoken = "முழு மின் தடையா அல்லது குறைந்த வோல்டேஜா?"
                    options = [
                        {"label": "⚡ முழு மின் தடை", "text": "முழு மின் தடை ஏற்பட்டுள்ளது"},
                        {"label": "⚡ குறைந்த வோல்டேஜ்", "text": "வோல்டேஜ் மிகக் குறைவாக உள்ளது"}
                    ]
                elif lang == "Tanglish":
                    text = f"⚡ Total power cut-aa illa low voltage problem-aa?"
                    spoken = "Total power cut-aa illa low voltage-aa?"
                    options = [
                        {"label": "⚡ Total power cut", "text": "Total power cut"},
                        {"label": "⚡ Low voltage", "text": "Low voltage problem"}
                    ]
                else:
                    text = "⚡ Is it a total power outage or a low voltage issue?"
                    spoken = "Is it a total power outage or low voltage issue?"
                    options = [
                        {"label": "⚡ Total power outage", "text": "Total power cut"},
                        {"label": "⚡ Low voltage", "text": "Low voltage issue"}
                    ]
            else:
                if lang == "Tamil":
                    text = f"🚨 இந்தப் பிரச்சினை எவ்வளவு தீவிரமானது அல்லது அவசரமானது?"
                    spoken = "இந்தப் பிரச்சினை எவ்வளவு தீவிரமானது?"
                    options = [
                        {"label": "🚨 மிகவும் தீவிரமானது", "text": "மிகவும் தீவிரமான பிரச்சினை"},
                        {"label": "ℹ️ இயல்பான புகார்", "text": "இயல்பான பொதுப் பிரச்சினை தான்"}
                    ]
                elif lang == "Tanglish":
                    text = f"🚨 Indha problem evalo serious or urgent-ah irukku?"
                    spoken = "Indha problem evalo serious-ah irukku?"
                    options = [
                        {"label": "🚨 Very serious", "text": "Romba serious problem"},
                        {"label": "ℹ️ Normal issue", "text": "Normal issue dhaan"}
                    ]
                else:
                    text = "🚨 How serious or urgent is this problem?"
                    spoken = "How serious or urgent is this problem?"
                    options = [
                        {"label": "🚨 Very serious", "text": "Very serious issue"},
                        {"label": "ℹ️ Standard priority", "text": "Standard priority issue"}
                    ]
            return text, spoken, options

        if slot == "safety_hazard":
            if lang == "Tamil":
                text = f"⚠️ இந்தப் பிரச்சினையால் பொதுமக்கள் பாதுகாப்பு பாதிப்பு அல்லது உடனடி அவசர ஆபத்து ஏதேனும் உள்ளதா?"
                spoken = "உடனடி பாதுகாப்பு ஆபத்து ஏதேனும் உள்ளதா?"
                options = [
                    {"label": "🚨 ஆபத்து உள்ளது", "text": "பொதுமக்களுக்கு நேரடி ஆபத்து உள்ளது"},
                    {"label": "ℹ️ ஆபத்து இல்லை", "text": "ஆபத்து இல்லை"}
                ]
            elif lang == "Tanglish":
                text = f"⚠️ Indha issue nala public safety risk or immediate danger edhavadhu irukka?"
                spoken = "Public safety risk edhavadhu irukka?"
                options = [
                    {"label": "🚨 Safety hazard exists", "text": "Live danger and safety risk irukku"},
                    {"label": "ℹ️ No hazard", "text": "No hazard, danger illa"}
                ]
            else:
                text = "⚠️ Is there any public safety hazard or emergency issue?"
                spoken = "Is there any public safety hazard or emergency issue?"
                options = [
                    {"label": "🚨 Safety hazard", "text": "Direct public safety risk"},
                    {"label": "ℹ️ No hazard", "text": "No immediate safety hazard"}
                ]
            return text, spoken, options

        if slot == "additional_details":
            if lang == "Tamil":
                text = f"📝 வேறு ஏதேனும் கூடுதல் தகவல்கள் தெரிவிக்க விரும்புகிறீர்களா?"
                spoken = "வேறு ஏதேனும் கூடுதல் விவரங்கள் உள்ளதா?"
                options = [
                    {"label": "ℹ️ வேறு தகவல் இல்லை", "text": "வேறு கூடுதல் தகவல் இல்லை"}
                ]
            elif lang == "Tanglish":
                text = f"📝 Vera edhavadhu additional information or details solla virumbureengala?"
                spoken = "Vera edhavadhu additional details irukka?"
                options = [
                    {"label": "ℹ️ Nothing else", "text": "Nothing else, vera illa"}
                ]
            else:
                text = "📝 Is there any additional information you would like to provide?"
                spoken = "Is there any additional information you would like to provide?"
                options = [
                    {"label": "ℹ️ No additional details", "text": "No additional details"}
                ]
            return text, spoken, options

        return "Could you please provide more details?", "Please provide more details.", []

    def _build_confirmation_summary(self, memory: Dict[str, Any], lang: str) -> Tuple[str, str]:
        """Builds confirmation summary in Tamil, Tanglish, or English."""
        problem = memory.get("problem_description") or memory.get("problem") or "Civic grievance"
        category = memory.get("category", "General")
        dept = memory.get("department") or DEPARTMENT_MASTER.get(category, "Municipal Administration")
        area = memory.get("area") or memory.get("district_area") or "Location"
        street = memory.get("street") or memory.get("street_road_name") or "Main Street"
        duration = memory.get("duration") or "2 days"
        scope = memory.get("affected_scope") or memory.get("affected_area") or "Entire street"
        landmark = memory.get("landmark") or "Nearby spot"

        if lang == "Tamil":
            text = (
                f"சரி, உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன்:\n\n"
                f"📍 இடம்: {area}, {street}\n"
                f"🏛️ துறை: {dept}\n"
                f"⏱️ கால அளவு: {duration}\n"
                f"⚠️ பிரச்சினை: {problem}\n"
                f"🏘️ பரப்பளவு: {scope}\n"
                f"🏢 அடையாளம் (Landmark): {landmark}\n\n"
                f"இந்த புகாரை பதிவு செய்யலாமா?"
            )
            spoken = (
                f"சரி, நான் உறுதிப்படுத்துகிறேன். {area} {street} பகுதியில் {duration} {problem}. "
                f"இது {scope} பிரச்சினை. இந்த புகாரை பதிவு செய்யலாமா?"
            )
        elif lang == "Tanglish":
            text = (
                f"Seri, naan confirm panren.\n\n"
                f"📍 Location: {area}, {street}\n"
                f"🏛️ Department: {dept}\n"
                f"⏱️ Duration: {duration}\n"
                f"⚠️ Problem: {problem}\n"
                f"🏘️ Scope: {scope}\n"
                f"🏢 Landmark: {landmark}\n\n"
                f"Indha complaint-a register pannalama?"
            )
            spoken = (
                f"Seri, naan confirm panren. {area} {street}-la {duration} {problem}. "
                f"Idhu {scope} problem. Indha complaint-a register pannalama?"
            )
        else:
            text = (
                f"Let me confirm your complaint details:\n\n"
                f"📍 Location: {street}, {area}\n"
                f"🏛️ Department: {dept}\n"
                f"⏱️ Duration: {duration}\n"
                f"⚠️ Problem: {problem}\n"
                f"🏘️ Scope: {scope}\n"
                f"🏢 Landmark: {landmark}\n\n"
                f"Shall I register this complaint now?"
            )
            spoken = (
                f"Let me confirm your complaint: {problem} at {street}, {area} for {duration}. "
                f"This affects {scope}. Shall I register this complaint now?"
            )
        return text, spoken

    def _finalize_and_register_complaint(self, db: Session, session: TollFreeCallSession) -> Dict[str, Any]:
        """Creates complaint record in DB, generates unique Complaint ID, and saves all structured fields."""
        memory = dict(session.structured_memory or {})
        problem = memory.get("problem_description") or memory.get("problem") or "Civic grievance reported via Toll-Free Helpline"
        category = memory.get("category") or "Water Supply"
        area = memory.get("area") or memory.get("district_area") or "Tamil Nadu"
        street = memory.get("street") or memory.get("street_road_name") or ""
        landmark = memory.get("landmark") or ""
        city = memory.get("city") or memory.get("district") or ""
        district = memory.get("district") or ""
        state = memory.get("state") or "Tamil Nadu"

        full_loc_parts = [p for p in [street, area, landmark, city, district, state] if p]
        full_location = ", ".join(full_loc_parts) or "Tamil Nadu"

        priority_str = memory.get("priority", "MEDIUM")
        try:
            prio_enum = ComplaintPriority[priority_str]
        except Exception:
            prio_enum = ComplaintPriority.MEDIUM

        _, lat, lon, _ = extract_location(full_location)

        full_description = (
            f"**Citizen Toll-Free Helpline Grievance Intake:**\n\n"
            f"- Problem: {problem}\n"
            f"- Category: {category}\n"
            f"- Area: {area}\n"
            f"- Street: {street or 'N/A'}\n"
            f"- Landmark: {landmark or 'N/A'}\n"
            f"- City / District: {city or district or 'N/A'}\n"
            f"- State: {state}\n"
            f"- Start Time / Duration: {memory.get('duration', 'N/A')}\n"
            f"- Affected Scope: {memory.get('affected_scope', 'N/A')}\n"
            f"- Frequency: {memory.get('frequency', 'N/A')}\n"
            f"- Previous Complaint: {memory.get('previous_complaint', 'N/A')}\n"
            f"- Severity: {memory.get('severity', 'Standard')}\n"
            f"- Safety Hazard: {memory.get('safety_hazard', 'None')}\n"
            f"- Additional Details: {memory.get('additional_details', 'None')}\n"
            f"- Caller Phone: {session.caller_phone}\n"
            f"- Toll-Free Number: {session.toll_free_number}"
        )

        complaint_in = ComplaintCreate(
            title=f"{category} issue at {area} {street}"[:200].strip(),
            description=full_description,
            category=category,
            location=full_location[:255],
            latitude=lat,
            longitude=lon,
            priority=prio_enum,
            language=session.language or "English",
            source=ComplaintSource.TELEPHONY_IVR,
            citizen_confirmed=True,
            ai_metadata={
                "complaint_id": None,
                "citizen_input": memory.get("raw_citizen_input", ""),
                "corrected_transcription": memory.get("corrected_transcription", ""),
                "language": session.language,
                "category": category,
                "department": DEPARTMENT_MASTER.get(category, "Municipal Administration"),
                "area": area,
                "street": street,
                "landmark": landmark,
                "city": city,
                "district": district,
                "state": state,
                "problem_description": problem,
                "duration": memory.get("duration"),
                "affected_area": memory.get("affected_scope"),
                "frequency": memory.get("frequency"),
                "previous_complaint": memory.get("previous_complaint"),
                "previous_complaint_number": memory.get("previous_complaint_number"),
                "severity": memory.get("severity"),
                "safety_hazard": memory.get("safety_hazard"),
                "additional_information": memory.get("additional_details"),
                "priority": priority_str,
                "status": "PENDING",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "session_id": session.call_session_id
            }
        )

        created_complaint = complaint_service.create_complaint(db=db, complaint_in=complaint_in)
        c_num = created_complaint.complaint_number
        dept_name = created_complaint.department.name if created_complaint.department else "Municipal Administration"

        # Update TollFree Session
        session.complaint_id = created_complaint.id
        session.complaint_number = c_num
        session.state = TollFreeState.COMPLETED.value
        session.ended_at = datetime.now(timezone.utc)
        db.commit()

        # Spoken confirmation in detected language
        lang = session.language
        if lang == "Tamil":
            reply_text = f"நன்றி! உங்கள் புகார் எண் **{c_num}** வெற்றிகரமாக பதிவு செய்யப்பட்டது. இது **{dept_name}** துறைக்கு அனுப்பப்பட்டுள்ளது."
            spoken_text = f"நன்றி! உங்கள் புகார் எண் {c_num} வெற்றிகரமாக பதிவு செய்யப்பட்டது. உரிய நடவடிக்கை எடுக்கப்படும்."
        elif lang == "Tanglish":
            reply_text = f"Thank you! Unga complaint ID **{c_num}** register aaiduchu. Idhu **{dept_name}**-ku forward panniyaachu."
            spoken_text = f"Thank you! Unga complaint ID {c_num} register aaiduchu. Department udane action edupaanga."
        else:
            reply_text = f"Thank you! Your complaint has been registered under ID **{c_num}** and routed to **{dept_name}**."
            spoken_text = f"Thank you! Your complaint has been registered under ID {c_num}. Our team will take action shortly."

        self._save_ai_message(db, session, reply_text, spoken_text, lang)
        logger.info(f"[TollFree] Complaint registered: {c_num} for session {session.call_session_id}")

        return {
            "success": True,
            "session_id": session.call_session_id,
            "state": TollFreeState.COMPLETED.value,
            "detected_language": lang,
            "ai_reply": reply_text,
            "spoken_reply": spoken_text,
            "complaint_created": True,
            "complaint_id": created_complaint.id,
            "complaint_number": c_num,
            "department": dept_name,
            "memory": memory
        }

    def _generate_edit_prompt(self, db: Session, session: TollFreeCallSession, lang: str) -> Dict[str, Any]:
        if lang == "Tamil":
            reply = "சரி, எந்த விவரத்தை மாற்ற வேண்டும்? தயவுசெய்து கூறவும்."
            spoken = "எந்த விவரத்தை மாற்ற வேண்டும் என்று கூறவும்."
            options = [
                {"label": "📍 இடத்தை மாற்று", "text": "இடத்தை மாற்ற வேண்டும்"},
                {"label": "⏱️ கால அளவை மாற்று", "text": "கால அளவை மாற்ற வேண்டும்"}
            ]
        elif lang == "Tanglish":
            reply = "Seri, endha details ah maathanum nu sollunga."
            spoken = "Endha details maathanum nu sollunga."
            options = [
                {"label": "📍 Change Location", "text": "Location maathanum"},
                {"label": "⏱️ Change Duration", "text": "Duration maathanum"}
            ]
        else:
            reply = "Understood. Which detail would you like to correct or update?"
            spoken = "Which detail would you like to update?"
            options = [
                {"label": "📍 Update Location", "text": "I want to change the location"},
                {"label": "⏱️ Update Duration", "text": "I want to change the duration"}
            ]

        self._save_ai_message(db, session, reply, spoken, lang)
        return {
            "success": True,
            "session_id": session.call_session_id,
            "state": TollFreeState.WAITING_FOR_CITIZEN.value,
            "detected_language": lang,
            "ai_reply": reply,
            "spoken_reply": spoken,
            "memory": session.structured_memory,
            "is_confirmation": False,
            "complaint_created": False,
            "options": options
        }

    def _handle_unclear_input(self, db: Session, session: TollFreeCallSession, error_code: str) -> Dict[str, Any]:
        lang = session.language or "English"
        if lang == "Tamil":
            reply = "மன்னிக்கவும், உங்கள் குரல் சரியாக கேட்கவில்லை. தயவுசெய்து மீண்டும் ஒருமுறை கூற முடியுமா?"
            spoken = "மன்னிக்கவும், மீண்டும் ஒருமுறை கூற முடியுமா?"
            options = [
                {"label": "💧 குடிநீர் பிரச்சினை", "text": "குடிநீர் விநியோகம் வரவில்லை"},
                {"label": "⚡ மின்சாரம் தடை", "text": "மின்சாரம் தடைப்பட்டுள்ளது"}
            ]
        elif lang == "Tanglish":
            reply = "Sorry, unga voice clear-ah kekkala. Please once again sollunga."
            spoken = "Sorry, unga voice clear-ah kekkala. Please once again sollunga."
            options = [
                {"label": "💧 Water Issue", "text": "Water supply varala"},
                {"label": "⚡ Power Issue", "text": "Power cut aaiduchu"}
            ]
        else:
            reply = "Sorry, I couldn't understand that clearly. Could you please say it again?"
            spoken = "Sorry, I couldn't understand that clearly. Could you please say it again?"
            options = [
                {"label": "💧 Water Outage", "text": "Water supply outage"},
                {"label": "⚡ Power Outage", "text": "Power outage"}
            ]

        self._save_ai_message(db, session, reply, spoken, lang)
        return {
            "success": True,
            "session_id": session.call_session_id,
            "state": session.state,
            "detected_language": lang,
            "ai_reply": reply,
            "spoken_reply": spoken,
            "memory": session.structured_memory,
            "is_confirmation": session.state == TollFreeState.CONFIRMATION.value,
            "complaint_created": False,
            "unclear": True,
            "error_code": error_code,
            "options": options
        }

    def _is_unclear_mumble(self, text: str) -> bool:
        lowered = text.strip().lower()
        if len(lowered) <= 1:
            return True
        valid_conversational = {
            "aama", "aamam", "ama", "amam", "aam", "seri", "sari", "ok", "yes", "no", "right", "correct",
            "sure", "confirm", "proceed", "cancel", "stop", "wait", "change", "edit", "wrong", "thappu",
            "illa", "illai", "vendaam", "kandippa", "pannunga", "podunga", "submit", "register",
            "ஆமாம்", "சரி", "உறுதி", "பதிவு", "ஆம்", "இல்லை", "வேண்டாம்", "தவறு"
        }
        tokens = [t for t in re.split(r'[\s\.\,\-]+', lowered) if t]
        if any(t in valid_conversational for t in tokens):
            return False
        mumbles = {"umm", "uhh", "uhhh", "aaa", "hmm", "huh", "enna", "mm", "ah", "err", "uh", "um"}
        return all(t in mumbles for t in tokens if t)

    def _is_confirmation_response(self, text: str) -> Tuple[bool, bool]:
        lowered = text.strip().lower()
        positive = [
            "yes", "confirm", "confirmed", "register", "proceed", "okay", "ok", "correct", "right",
            "aama", "aamam", "ama", "amam", "aam", "seri", "sari", "pannunga", "podunga", "panlama",
            "pannidunga", "padhivu", "seiyunga", "seiyalam", "kandippa", "sure", "done", "fine", "super",
            "nandri", "thanks", "thank you", "go ahead"
        ]
        negative = [
            "no", "cancel", "stop", "wait", "change", "edit", "wrong", "thappu", "illai", "illa",
            "vendaam", "modify", "maathanum", "maathu"
        ]

        if any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in positive) or any(w in lowered for w in ["ஆமாம்", "சரி", "பதிவு", "ஆம்", "உறுதி", "செய்யலாம்"]):
            return True, True
        if any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in negative) or any(w in lowered for w in ["வேண்டாம்", "இல்லை", "தவறு", "மாற்ற வேண்டும்"]):
            return True, False
        return False, False

    def _save_ai_message(self, db: Session, session: TollFreeCallSession, content: str, spoken: str, lang: str) -> TollFreeMessage:
        msg = TollFreeMessage(
            session_id=session.id,
            role="ai",
            content=content,
            normalized_content=spoken,
            language=lang,
            created_at=datetime.now(timezone.utc)
        )
        db.add(msg)
        db.commit()
        return msg


tollfree_service = TollFreeService()
