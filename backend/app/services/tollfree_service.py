# type: ignore
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

from app.services.question_manager import question_manager, ORDERED_QUESTION_SLOTS


class TollFreeService:
    """
    Two-Way Conversational Engine for the VoxentraAI Toll-Free Grievance Helpline.
    Enforces strict turn-taking (Citizen speaks first, AI asks one question at a time),
    continuous conversation memory, language adaptation (Tamil, English, Tanglish),
    pre-registration confirmation, and real database complaint generation.
    Supports asking multiple questions up to a maximum of 20 questions.
    """

    def create_call_session(
        self,
        db: Session,
        caller_phone: Optional[str] = "+919843098765",
        provider_call_id: Optional[str] = None,
        toll_free_number: str = "1800-425-8693",
        language_preference: str = "Auto"
    ) -> Tuple[TollFreeCallSession, str, str]:
        """
        Creates incoming toll-free call session and places call in silent LISTENING mode (Citizen speaks first).
        """
        session_id = f"tf_sess_{uuid.uuid4().hex[:12]}"
        initial_lang = language_preference if language_preference not in ["Auto", "Auto-Detecting...", "", None] else "Auto"

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
            "max_questions": 20,
            "raw_citizen_input": "",
            "corrected_transcription": "",
            "detected_language": initial_lang
        }

        session = TollFreeCallSession(
            call_session_id=session_id,
            provider_call_id=provider_call_id,
            caller_phone=caller_phone or "+919843098765",
            toll_free_number=toll_free_number,
            language=initial_lang,
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
        memory: Dict[str, Any] = dict(session.structured_memory or {})
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
        raw_prio = memory.get("priority", "MEDIUM")
        norm_prio = "MEDIUM" if str(raw_prio).upper() in ["STANDARD", "NORMAL"] else raw_prio
        memory["priority"] = norm_prio
        session.priority = norm_prio
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
                "language": detected_lang,
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

            ai_reply, spoken_reply, options = self._generate_slot_question(next_missing, memory, detected_lang, last_raw_text=raw_text)
            self._save_ai_message(db, session, ai_reply, spoken_reply, detected_lang)

            return {
                "success": True,
                "session_id": session.call_session_id,
                "state": TollFreeState.WAITING_FOR_CITIZEN.value,
                "language": detected_lang,
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
                memory["priority"] = "CRITICAL"
        if prompted_slot == "severity" and not memory.get("severity"):
            memory["severity"] = raw_text.strip()
        if prompted_slot == "safety_hazard" and not memory.get("safety_hazard"):
            if any(w in lowered for w in ["no", "illa", "illai", "nothing", "இல்லை", "ஆபத்து இல்லை"]):
                memory["safety_hazard"] = "None (No immediate safety hazard)"
            else:
                memory["safety_hazard"] = raw_text.strip()
                memory["priority"] = "CRITICAL"

        # 8. Impact
        if prompted_slot == "impact" and not memory.get("impact"):
            memory["impact"] = raw_text.strip()

        # 9. Additional Slots (Timing, Contamination, Population, Alternate Source, Contact Details)
        if prompted_slot == "water_supply_timing" and not memory.get("water_supply_timing"):
            memory["water_supply_timing"] = raw_text.strip()

        if prompted_slot == "leakage_or_contamination" and not memory.get("leakage_or_contamination"):
            memory["leakage_or_contamination"] = raw_text.strip()

        if prompted_slot == "affected_population" and not memory.get("affected_population"):
            memory["affected_population"] = raw_text.strip()

        if prompted_slot == "alternate_source" and not memory.get("alternate_source"):
            memory["alternate_source"] = raw_text.strip()

        if prompted_slot == "contact_person" and not memory.get("contact_person"):
            memory["contact_person"] = raw_text.strip()

        if prompted_slot == "preferred_contact_time" and not memory.get("preferred_contact_time"):
            memory["preferred_contact_time"] = raw_text.strip()

        # 10. Additional details
        if prompted_slot == "additional_details" or any(w in lowered for w in ["no other details", "nothing else", "no details", "nothing more", "avvalavuthaan", "avlodhaan", "கூடுதல் தகவல் இல்லை", "அவ்வளவுதான்", "வேறில்லை"]):
            if any(w in lowered for w in ["no", "nothing", "nothing else", "illa", "illai", "none", "வேறு இல்லை", "இல்லை", "கூடுதல் தகவல் இல்லை", "அவ்வளவுதான்"]):
                memory["additional_details"] = "None"
            elif not memory.get("additional_details"):
                memory["additional_details"] = raw_text.strip()
            memory["is_citizen_confirmed_ready"] = True
        elif any(p in lowered for p in ["register pannunga", "register it", "register my complaint", "பதிவு பண்ணுங்க", "பதிவு செய்யுங்க", "போதும்", "enough"]) and memory.get("problem_description") and (memory.get("area") or memory.get("location")):
            memory["is_citizen_confirmed_ready"] = True

        # Priority Assessment with full conversational context
        full_problem = f"{memory.get('problem_description', '')} {memory.get('severity', '')} {memory.get('safety_hazard', '')} {raw_text}".strip()
        if full_problem:
            prio, _ = assess_priority(
                text=full_problem,
                category=memory.get("category", "General"),
                duration=memory.get("duration"),
                scope=memory.get("impact") or memory.get("affected_scope"),
                hazard=memory.get("safety_hazard")
            )
            prio_val = prio.value if hasattr(prio, 'value') else str(prio)
            if prio_val.upper() in ["STANDARD", "NORMAL"]:
                prio_val = "MEDIUM"
            memory["priority"] = prio_val

    def _get_next_missing_slot(self, memory: Dict[str, Any]) -> Optional[str]:
        """Returns the next missing question slot from question_manager (supports up to 20 questions)."""
        return question_manager.get_next_missing_slot(memory, min_questions=10)

    def _generate_slot_question(self, slot: str, memory: Dict[str, Any], lang: str, last_raw_text: str = "") -> Tuple[str, str, List[Dict[str, str]]]:
        """Generates dynamic, polite follow-up questions in Tamil, Tanglish, or English via question_manager."""
        return question_manager.generate_question(slot, memory, lang, last_raw_text=last_raw_text)

    def _build_confirmation_summary(self, memory: Dict[str, Any], lang: str) -> Tuple[str, str]:
        """Builds confirmation summary in Tamil, Tanglish, or English via question_manager."""
        return question_manager.build_confirmation_summary(memory, lang)

    def _finalize_and_register_complaint(self, db: Session, session: TollFreeCallSession) -> Dict[str, Any]:
        """Creates complaint record in DB, generates unique Complaint ID, and saves all structured fields."""
        memory: Dict[str, Any] = dict(session.structured_memory or {})
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
        if str(priority_str).upper() in ["STANDARD", "NORMAL"]:
            priority_str = "MEDIUM"
            memory["priority"] = "MEDIUM"
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
            f"- Severity: {memory.get('severity', 'Medium')}\n"
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
            language=session.language if session.language not in ["Auto", "Auto-Detecting...", "", None] else "Tamil",
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

        lang_str: str = str(session.language) if (session.language and session.language not in ["Auto", "Auto-Detecting...", ""]) else "Tamil"
        session.language = lang_str

        # Spoken confirmation in detected language
        if lang_str == "Tamil":
            reply_text = f"நன்றி! உங்கள் புகார் எண் **{c_num}** வெற்றிகரமாக பதிவு செய்யப்பட்டது. இது **{dept_name}** துறைக்கு அனுப்பப்பட்டுள்ளது."
            spoken_text = f"நன்றி! உங்கள் புகார் எண் {c_num} வெற்றிகரமாக பதிவு செய்யப்பட்டது. உரிய நடவடிக்கை எடுக்கப்படும்."
        elif lang_str == "Tanglish":
            reply_text = f"Thank you! Unga complaint ID **{c_num}** register aaiduchu. Idhu **{dept_name}**-ku forward panniyaachu."
            spoken_text = f"Thank you! Unga complaint ID {c_num} register aaiduchu. Department udane action edupaanga."
        else:
            reply_text = f"Thank you! Your complaint has been registered under ID **{c_num}** and routed to **{dept_name}**."
            spoken_text = f"Thank you! Your complaint has been registered under ID {c_num}. Our team will take action shortly."

        self._save_ai_message(db, session, reply_text, spoken_text, lang_str)
        logger.info(f"[TollFree] Complaint registered: {c_num} for session {session.call_session_id}")

        return {
            "success": True,
            "session_id": session.call_session_id,
            "state": TollFreeState.COMPLETED.value,
            "detected_language": lang_str,
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
        lang = session.language or "Tamil"
        if lang in ["Auto", "Auto-Detecting...", ""]:
            lang = "Tamil"
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
