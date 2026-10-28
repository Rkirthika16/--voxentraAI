# type: ignore
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from app.models.ivr import IVRSession, IVRMessage, IVRState
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintSource
from app.models.department import Department
from app.schemas.complaint import ComplaintCreate
from app.services.complaint_service import complaint_service
from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text, clean_transcription
from app.ai.classification_service import classify_complaint
from app.ai.location_service import extract_location, normalize_structured_location
from app.ai.priority_service import assess_priority
from app.integrations.telephony.twilio_adapter import twilio_adapter

logger = logging.getLogger("voxentra.new_ivr")

# Configurable Department Mappings
CATEGORY_TO_DEPARTMENT = {
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


class NewIVRService:
    """
    Two-Way Conversational AI Engine for Live Citizen IVR.
    1. Call starts in silent LISTENING mode (Citizen speaks first).
    2. Transcription error correction, spelling & Tanglish STT mistake normalization.
    3. Automatic language detection (Tamil, English, Tanglish) with dynamic switching.
    4. Dynamic questioning asking AT LEAST 10 meaningful questions without repeating answered points.
    5. Structured location normalization (Area, Street, Landmark, City, District, State).
    6. Category & Priority classification.
    7. Final confirmation summary in citizen's language.
    8. Real database complaint creation with unique Complaint ID (e.g. VX-2026-XXXXX).
    """

    def create_session(
        self,
        db: Session,
        caller_phone: Optional[str] = "+919843098765",
        language_preference: Optional[str] = "Auto"
    ) -> Tuple[IVRSession, str, str]:
        """
        Creates a new live IVR session and places call in silent LISTENING mode (Citizen speaks first).
        """
        session_id = f"ivr_sess_{uuid.uuid4().hex[:12]}"
        
        initial_memory = {
            "problem_description": None,
            "problem": None,
            "category": None,
            "department": None,
            "district_area": None,
            "area": None,
            "location": None,
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
            "impact": None,
            "safety_hazard": None,
            "additional_details": None,
            "citizen_name": None,
            "citizen_phone": caller_phone or "+919843098765",
            "priority": "MEDIUM",
            "questions_asked_count": 0,
            "max_questions": 20,
            "raw_citizen_input": "",
            "corrected_transcription": ""
        }

        init_lang = language_preference if (language_preference and language_preference not in ["Auto", "Auto-Detecting..."]) else "Auto"
        ivr_session = IVRSession(
            session_id=session_id,
            caller_phone=caller_phone or "+919843098765",
            language=init_lang,
            state=IVRState.WAITING_FOR_CITIZEN.value,
            structured_memory=initial_memory,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(ivr_session)
        db.commit()
        db.refresh(ivr_session)

        # Rule 1 & 2: When citizen calls, the AI MUST NOT speak first. Call starts in listening mode.
        greeting_text = ""
        greeting_spoken = ""

        logger.info(f"[NewIVR] Session created: {session_id}, waiting for citizen to speak first.")
        return ivr_session, greeting_text, greeting_spoken

    def get_session(self, db: Session, session_id: str) -> Optional[IVRSession]:
        return db.query(IVRSession).filter(IVRSession.session_id == session_id).first()

    def process_citizen_turn(
        self,
        db: Session,
        session_id: str,
        speech_text: str,
        audio_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes one dialogue turn from citizen voice or text input.
        """
        ivr_session = self.get_session(db, session_id)
        if not ivr_session:
            return {
                "success": False,
                "error_code": "SESSION_NOT_FOUND",
                "message": f"Session {session_id} not found",
                "state": IVRState.ERROR.value
            }

        raw_text = speech_text.strip()
        if not raw_text:
            return self._handle_unclear_input(db, ivr_session, "EMPTY_INPUT")

        # 1. Clean & normalize speech transcript (Correct STT errors before understanding complaint)
        cleaned = clean_transcription(raw_text)
        normalized_text_str = normalize_text(raw_text)

        # 2. Dynamic Language Detection & Switching (Tamil, English, Tanglish)
        current_lang = ivr_session.language if ivr_session.language not in ["Auto", "Auto-Detecting...", "", None] else None
        detected_lang, conf = detect_language(raw_text, current_session_lang=current_lang)
        ivr_session.language = detected_lang
        ivr_session.language_confidence = float(conf)

        # Save citizen message turn
        citizen_msg = IVRMessage(
            session_id=ivr_session.id,
            role="citizen",
            content=raw_text,
            normalized_content=cleaned,
            language=detected_lang,
            audio_url=audio_url,
            created_at=datetime.now(timezone.utc)
        )
        db.add(citizen_msg)
        db.commit()

        # Update full transcript records in memory
        memory: Dict[str, Any] = dict(ivr_session.structured_memory or {})
        memory["raw_citizen_input"] = (memory.get("raw_citizen_input", "") + f"\n{raw_text}").strip()
        memory["corrected_transcription"] = (memory.get("corrected_transcription", "") + f"\n{cleaned}").strip()

        # 3. Check for Unclear / Mumbled Speech
        if self._is_unclear_or_mumble(raw_text):
            return self._handle_unclear_input(db, ivr_session, "UNCLEAR_SPEECH")

        # 4. Check if currently in CONFIRMATION state
        if ivr_session.state == IVRState.CONFIRMATION.value:
            is_decision, is_confirmed = self._is_confirmation_response(raw_text)
            if is_decision:
                if is_confirmed:
                    return self._finalize_and_register_complaint(db, ivr_session)
                else:
                    # Citizen wants to edit/change details
                    ivr_session.state = IVRState.WAITING_FOR_CITIZEN.value
                    db.commit()
                    return self._generate_edit_prompt(db, ivr_session, detected_lang)

        # 5. Extract slots and update conversation memory
        prompted_slot = ivr_session.current_field_prompted
        self._extract_and_update_memory(raw_text, cleaned, memory, prompted_slot=prompted_slot)

        # Synchronize model columns with memory
        ivr_session.category = memory.get("category")
        ivr_session.problem = memory.get("problem_description") or memory.get("problem")
        ivr_session.location = memory.get("area") or memory.get("district_area") or memory.get("location")
        ivr_session.duration = memory.get("duration")
        ivr_session.affected_scope = memory.get("affected_scope") or memory.get("affected_area")
        ivr_session.frequency = memory.get("frequency")
        ivr_session.severity = memory.get("severity")
        raw_prio = memory.get("priority", "MEDIUM")
        norm_prio = "MEDIUM" if str(raw_prio).upper() in ["STANDARD", "NORMAL"] else raw_prio
        memory["priority"] = norm_prio
        ivr_session.priority = norm_prio
        ivr_session.department = memory.get("department")
        ivr_session.citizen_name = memory.get("citizen_name")
        ivr_session.structured_memory = memory
        db.commit()

        # 6. Check missing slots & generate next relevant question (ONE AT A TIME, AT LEAST 10 QUESTIONS)
        next_missing = self._get_next_missing_slot(memory)

        if next_missing is None:
            # All essential info collected or at least 10 questions answered -> Move to CONFIRMATION
            ivr_session.state = IVRState.CONFIRMATION.value
            ivr_session.current_field_prompted = None
            db.commit()

            summary_text, spoken_summary = self._build_confirmation_summary(memory, detected_lang)
            self._save_ai_message(db, ivr_session, summary_text, spoken_summary, detected_lang)

            confirmation_options = [
                {"label": "✅ ஆம், பதிவு செய்க (Register)", "text": "ஆம், புகாரை பதிவு செய்யுங்கள்"},
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
                "session_id": ivr_session.session_id,
                "state": IVRState.CONFIRMATION.value,
                "language": detected_lang,
                "detected_language": detected_lang,
                "language_confidence": conf,
                "ai_reply": summary_text,
                "spoken_reply": spoken_summary,
                "memory": memory,
                "question_count": memory.get("questions_asked_count", 0),
                "max_questions": memory.get("max_questions", 20),
                "is_confirmation": True,
                "complaint_created": False,
                "options": confirmation_options
            }
        else:
            # Increment question count
            current_q_count = memory.get("questions_asked_count", 0) + 1
            memory["questions_asked_count"] = current_q_count
            ivr_session.structured_memory = memory

            # Ask the next relevant question
            ivr_session.state = IVRState.WAITING_FOR_CITIZEN.value
            ivr_session.current_field_prompted = next_missing
            db.commit()

            ai_reply, spoken_reply, options = self._generate_slot_question(next_missing, memory, detected_lang, last_raw_text=raw_text)
            self._save_ai_message(db, ivr_session, ai_reply, spoken_reply, detected_lang)

            return {
                "success": True,
                "session_id": ivr_session.session_id,
                "state": IVRState.WAITING_FOR_CITIZEN.value,
                "language": detected_lang,
                "detected_language": detected_lang,
                "language_confidence": conf,
                "ai_reply": ai_reply,
                "spoken_reply": spoken_reply,
                "memory": memory,
                "next_field": next_missing,
                "question_count": current_q_count,
                "max_questions": memory.get("max_questions", 20),
                "is_confirmation": False,
                "complaint_created": False,
                "options": options
            }

    def _extract_and_update_memory(self, raw_text: str, cleaned: str, memory: Dict[str, Any], prompted_slot: Optional[str] = None) -> None:
        """
        Extracts civic entities across all 14 structured slots and updates memory.
        Uses prompted_slot context so citizen answers are never lost or asked repeatedly.
        """
        lowered = cleaned.lower().strip()

        # Handle explicit corrections
        self._check_explicit_corrections(raw_text, cleaned, memory)

        # 1. Problem & Category Detection
        if not memory.get("problem_description") or prompted_slot == "problem_description":
            cat, dept, cat_conf = classify_complaint(cleaned)
            if cat != "Other" or any(w in lowered for w in ["water", "thanni", "power", "current", "road", "garbage", "drainage", "light", "குடிநீர்", "மின்சாரம்", "குப்பை", "சாலை", "சாக்கடை", "விளக்கு"]) or prompted_slot == "problem_description":
                memory["problem_description"] = raw_text.strip()
                memory["problem"] = raw_text.strip()
                memory["category"] = cat if cat != "Other" else (memory.get("category") or "Water Supply")
                memory["department"] = CATEGORY_TO_DEPARTMENT.get(memory["category"], dept)
            elif prompted_slot == "problem_description" and not memory.get("problem_description"):
                memory["problem_description"] = raw_text.strip()
                memory["problem"] = raw_text.strip()
                memory["category"] = memory.get("category") or "General Grievance"
                memory["department"] = CATEGORY_TO_DEPARTMENT.get(memory["category"], "Municipal Administration")

        # 2. Location Normalization (Area, Street, Landmark, City, District, State)
        loc_struct = normalize_structured_location(
            cleaned,
            existing_area=memory.get("area") or memory.get("district_area"),
            existing_street=memory.get("street") or memory.get("street_road_name"),
            existing_landmark=memory.get("landmark"),
            existing_city=memory.get("city"),
            existing_district=memory.get("district")
        )

        if loc_struct.get("area") and not memory.get("district_area"):
            memory["district_area"] = loc_struct["area"]
            memory["area"] = loc_struct["area"]
        if loc_struct.get("street") and not memory.get("street_road_name"):
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

        # CONTEXTUAL FALLBACK if AI explicitly prompted for specific location slots
        if prompted_slot == "district_area" and not memory.get("district_area"):
            cleaned_area = re.sub(r'^(?:in|at|near|the|enga|anga|unga|inda|indha|இந்த|அந்த|பகுதியில்|இடத்தில்|area\s*is|location\s*is)\s+', '', raw_text, flags=re.IGNORECASE).strip()
            if len(cleaned_area) >= 2:
                memory["district_area"] = cleaned_area
                memory["area"] = cleaned_area

        if prompted_slot == "street_road_name" and not memory.get("street_road_name"):
            cleaned_st = re.sub(r'^(?:in\s+the|on\s+the|at\s+the|the|this|that|inda|indha|இந்த|அந்த|எங்கள்|என்)\s+', '', raw_text, flags=re.IGNORECASE).strip()
            if len(cleaned_st) >= 2:
                memory["street_road_name"] = cleaned_st
                memory["street"] = cleaned_st

        if prompted_slot == "exact_location" and not memory.get("exact_location"):
            memory["exact_location"] = raw_text.strip()

        if prompted_slot == "landmark" and not memory.get("landmark"):
            memory["landmark"] = raw_text.strip()

        # 3. Start Time & Duration Detection (e.g. "two days", "3 days", "since yesterday", "today morning", "rendu naala", "nethu lendhu")
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
                dur_val = m.group(0).strip()
                memory["duration"] = dur_val
                if not memory.get("start_time"):
                    memory["start_time"] = dur_val
                break

        if prompted_slot == "duration" and not memory.get("duration"):
            memory["duration"] = raw_text.strip()
        if prompted_slot == "start_time" and not memory.get("start_time"):
            memory["start_time"] = raw_text.strip()

        # 4. Scope / Affected Area (Whole street vs single house)
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

        # 5. Frequency Detection (e.g. first time, daily recurring, frequent)
        freq_patterns = [
            (r'\b(first\s*time|mudhal\s*murai|முதல்\s*முறை)\b', "First time"),
            (r'\b(daily|every\s*day|dinamum|thinamum|தினமும்|daily-ah)\b', "Daily recurring"),
            (r'\b(frequent|often|adikkadi|அடிக்கடி|always|continuous|eppovum)\b', "Frequent / Continuous"),
            (r'\b(rain|rainy\s*day|mazhai|மழை\s*நேரம்)\b', "Rainy season / Occasional")
        ]
        for pat, val in freq_patterns:
            if re.search(pat, lowered) and not memory.get("frequency"):
                memory["frequency"] = val
                break
        if prompted_slot == "frequency" and not memory.get("frequency"):
            memory["frequency"] = raw_text.strip()

        # 6. Previous Complaint & Token Number
        if prompted_slot == "previous_complaint" and not memory.get("previous_complaint"):
            if any(w in lowered for w in ["yes", "aama", "already", "reported", "aamam", "ஆமாம்", "பண்ணிட்டேன்"]):
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
                memory["priority"] = "HIGH"

        # 8. Additional Slots (Timing, Contamination, Population, Alternate Source, Contact Details)
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

        # 9. Additional Details
        if prompted_slot == "additional_details" or any(w in lowered for w in ["no other details", "nothing else", "no details", "nothing more", "avvalavuthaan", "avlodhaan", "கூடுதல் தகவல் இல்லை", "அவ்வளவுதான்", "வேறில்லை"]):
            if any(w in lowered for w in ["no", "nothing", "nothing else", "illa", "illai", "none", "வேறு இல்லை", "இல்லை", "கூடுதல் தகவல் இல்லை", "அவ்வளவுதான்"]):
                memory["additional_details"] = "None"
            elif not memory.get("additional_details"):
                memory["additional_details"] = raw_text.strip()
            memory["is_citizen_confirmed_ready"] = True
        elif any(p in lowered for p in ["register pannunga", "register it", "register my complaint", "பதிவு பண்ணுங்க", "பதிவு செய்யுங்க", "போதும்", "enough"]) and memory.get("problem_description") and (memory.get("area") or memory.get("location")):
            memory["is_citizen_confirmed_ready"] = True

        # Citizen Name / Contact
        phone_match = re.search(r'\b[6-9]\d{9}\b', raw_text)
        if phone_match and not memory.get("citizen_phone"):
            memory["citizen_phone"] = phone_match.group(0)

        name_pattern = r'''(?x)
            (?:
                (?:(?:நான்|நாங்க|நானு|inga)?\s*(?:வந்துட்டு|வந்து)?\s*([A-Za-z\u0B80-\u0BFF]{2,25})\s*(?:பேசுறேன்|பேசுகிறேன்|pesuren|pesuranga|speaking))
                |
                (?:(?:name\s*is|i\s*am|my\s*name\s*is|பெயர்|en\s*peyar|en\s*peru|peru|this\s*is)\s*[:=]?\s*([A-Za-z\u0B80-\u0BFF]{2,25}))
            )
        '''
        name_stopwords = {"seri", "ok", "problem", "thanni", "water", "anna", "tamil", "english", "no", "yes", "illa", "illai", "irundhu", "vanakkam", "hello", "நாங்க", "நான்", "வந்துட்டு"}
        name_match = re.search(name_pattern, raw_text, re.IGNORECASE)
        if name_match and not memory.get("citizen_name"):
            cand = (name_match.group(1) or name_match.group(2) or "").strip()
            cand = re.sub(r'^(?:நான்|நாங்க|நானு|வந்துட்டு|வந்து)\s+', '', cand).strip()
            if cand.lower() not in name_stopwords and len(cand) >= 2:
                cand_clean = cand.title() if cand.isascii() else cand
                memory["citizen_name"] = cand_clean
                if not memory.get("contact_person"):
                    memory["contact_person"] = cand_clean

        # Impact handling
        if prompted_slot == "impact" and not memory.get("impact"):
            memory["impact"] = raw_text.strip()
        elif not memory.get("impact") and any(w in lowered for w in ["drinking water", "hospital", "school", "traffic", "vehicle", "kudineer", "ambulance"]):
            memory["impact"] = raw_text.strip()

        # Synchronize location alias in memory
        if memory.get("area") or memory.get("district_area") or memory.get("street"):
            if memory.get("street") and memory.get("area"):
                memory["location"] = f"{memory['street']}, {memory['area']}, Coimbatore"
            else:
                memory["location"] = memory.get("area") or memory.get("district_area") or memory.get("street")
        else:
            memory["location"] = None

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

    def _check_explicit_corrections(self, raw_text: str, cleaned: str, memory: Dict[str, Any]) -> None:
        """Handles explicit user corrections like 'Change area to Gandhipuram', 'Street is 5th Street'."""
        lowered = raw_text.lower()
        
        # Location / Area correction
        if any(w in lowered for w in ["change area", "location is", "area is", "இடம்", "பகுதி மாற்று", "maathunga"]):
            loc_match = re.search(r'(?:area|location|place|பகுதி|இடம்)\s+(?:is|to|:)?\s*([A-Za-z0-9\u0B80-\u0BFF\s]+)', raw_text, re.IGNORECASE)
            if loc_match:
                cand = loc_match.group(1).strip()
                if len(cand) >= 3 and cand.lower() not in ["is", "to", "the"]:
                    memory["district_area"] = cand
                    memory["area"] = cand

        # Street correction
        if any(w in lowered for w in ["change street", "street is", "street name", "தெரு"]):
            st_match = re.search(r'(?:street|road|தெரு|சாலை)\s*(?:is|to|:)?\s*([A-Za-z0-9\u0B80-\u0BFF\s]+)', raw_text, re.IGNORECASE)
            if st_match:
                cand_st = st_match.group(1).strip()
                if len(cand_st) >= 2 and cand_st.lower() not in ["is", "to", "the"]:
                    memory["street_road_name"] = cand_st
                    memory["street"] = cand_st

    def _is_slot_filled(self, memory: Dict[str, Any], slot: str) -> bool:
        return question_manager._is_slot_filled(memory, slot)

    def _get_next_missing_slot(self, memory: Dict[str, Any]) -> Optional[str]:
        """Returns the next missing question slot from question_manager (supports up to 20 questions)."""
        return question_manager.get_next_missing_slot(memory, min_questions=10)

    def _generate_slot_question(self, slot: str, memory: Dict[str, Any], lang: str, last_raw_text: str = "") -> Tuple[str, str, List[Dict[str, str]]]:
        """Generates dynamic, polite follow-up questions in Tamil, Tanglish, or English via question_manager."""
        return question_manager.generate_question(slot, memory, lang, last_raw_text=last_raw_text)

    def _build_confirmation_summary(self, memory: Dict[str, Any], lang: str) -> Tuple[str, str]:
        """Builds confirmation summary in Tamil, Tanglish, or English via question_manager."""
        return question_manager.build_confirmation_summary(memory, lang)

    def _finalize_and_register_complaint(self, db: Session, ivr_session: IVRSession) -> Dict[str, Any]:
        """
        Creates official Complaint record in DB, generates unique Complaint ID (e.g. VX-2026-00001),
        saves all structured fields, sends Twilio SMS, and returns final spoken response.
        """
        memory: Dict[str, Any] = dict(ivr_session.structured_memory or {})
        problem = memory.get("problem_description") or memory.get("problem") or "Civic grievance reported via AI voice IVR"
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
            f"**Citizen Voice Grievance Intake:**\n\n"
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
            f"- Caller Phone: {ivr_session.caller_phone}\n"
            f"- Session ID: {ivr_session.session_id}"
        )

        complaint_in = ComplaintCreate(
            title=f"{category} issue at {area} {street}"[:200].strip(),
            description=full_description,
            category=category,
            location=full_location[:255],
            latitude=lat,
            longitude=lon,
            priority=prio_enum,
            language=ivr_session.language if ivr_session.language not in ["Auto", "Auto-Detecting...", "", None] else "Tamil",
            source=ComplaintSource.TELEPHONY_IVR,
            citizen_confirmed=True,
            ai_metadata={
                "complaint_id": None, # populated after creation
                "citizen_input": memory.get("raw_citizen_input", ""),
                "corrected_transcription": memory.get("corrected_transcription", ""),
                "language": ivr_session.language,
                "category": category,
                "department": CATEGORY_TO_DEPARTMENT.get(category, "Municipal Administration"),
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
                "session_id": ivr_session.session_id
            }
        )

        created_complaint = complaint_service.create_complaint(db=db, complaint_in=complaint_in)
        c_num = created_complaint.complaint_number
        dept_name = created_complaint.department.name if created_complaint.department else "Municipal Administration"

        # Update IVR Session
        ivr_session.complaint_id = created_complaint.id
        ivr_session.complaint_number = c_num
        ivr_session.state = IVRState.COMPLETED.value
        ivr_session.ended_at = datetime.now(timezone.utc)
        db.commit()

        lang_str: str = str(ivr_session.language) if (ivr_session.language and ivr_session.language not in ["Auto", "Auto-Detecting...", ""]) else "Tamil"
        ivr_session.language = lang_str

        # Send Twilio Confirmation SMS
        sms_body = twilio_adapter.build_complaint_sms(
            complaint_number=c_num,
            description=problem,
            department=dept_name,
            location=full_location,
            lang=lang_str
        )
        sms_res = twilio_adapter.send_sms(ivr_session.caller_phone or "+919843098765", sms_body)

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

        self._save_ai_message(db, ivr_session, reply_text, spoken_text, lang_str)
        logger.info(f"[NewIVR] Complaint registered: {c_num} for session {ivr_session.session_id}")

        return {
            "success": True,
            "session_id": ivr_session.session_id,
            "state": IVRState.COMPLETED.value,
            "detected_language": lang_str,
            "ai_reply": reply_text,
            "spoken_reply": spoken_text,
            "complaint_created": True,
            "complaint_id": created_complaint.id,
            "complaint_number": c_num,
            "department": dept_name,
            "sms_sent": sms_res.get("success", False),
            "memory": memory
        }

    def _generate_edit_prompt(self, db: Session, ivr_session: IVRSession, lang: str) -> Dict[str, Any]:
        if lang == "Tamil":
            reply = "சரி, எந்த விவரத்தை மாற்ற வேண்டும்? தயவுசெய்து கூறவும்."
            spoken = "எந்த விவரத்தை மாற்ற வேண்டும் என்று கூறவும்."
            options = [
                {"label": "📍 இடத்தை மாற்று", "text": "இடத்தை மாற்ற வேண்டும்"},
                {"label": "⏱️ கால அளவை மாற்று", "text": "கால அளவை மாற்ற வேண்டும்"},
                {"label": "⚠️ பிரச்சினையை மாற்று", "text": "பிரச்சினையை மாற்ற வேண்டும்"}
            ]
        elif lang == "Tanglish":
            reply = "Seri, endha details ah maathanum nu sollunga."
            spoken = "Endha details maathanum nu sollunga."
            options = [
                {"label": "📍 Change Location", "text": "Location maathanum"},
                {"label": "⏱️ Change Duration", "text": "Duration maathanum"},
                {"label": "⚠️ Change Problem", "text": "Problem details maathanum"}
            ]
        else:
            reply = "Understood. Which detail would you like to correct or update?"
            spoken = "Which detail would you like to update?"
            options = [
                {"label": "📍 Update Location", "text": "I want to change the location"},
                {"label": "⏱️ Update Duration", "text": "I want to change the duration"},
                {"label": "⚠️ Update Problem", "text": "I want to update the problem description"}
            ]

        self._save_ai_message(db, ivr_session, reply, spoken, lang)
        return {
            "success": True,
            "session_id": ivr_session.session_id,
            "state": IVRState.WAITING_FOR_CITIZEN.value,
            "detected_language": lang,
            "ai_reply": reply,
            "spoken_reply": spoken,
            "memory": ivr_session.structured_memory,
            "is_confirmation": False,
            "complaint_created": False,
            "options": options
        }

    def _handle_unclear_input(self, db: Session, ivr_session: IVRSession, error_code: str) -> Dict[str, Any]:
        lang = ivr_session.language or "Tamil"
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

        self._save_ai_message(db, ivr_session, reply, spoken, lang)
        return {
            "success": True,
            "session_id": ivr_session.session_id,
            "state": ivr_session.state,
            "detected_language": lang,
            "ai_reply": reply,
            "spoken_reply": spoken,
            "memory": ivr_session.structured_memory,
            "is_confirmation": ivr_session.state == IVRState.CONFIRMATION.value,
            "complaint_created": False,
            "unclear": True,
            "error_code": error_code,
            "options": options
        }

    def _is_unclear_or_mumble(self, text: str) -> bool:
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

        if any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in positive) or any(w in lowered for w in ["ஆமாம்", "சரி", "பதிவு", "ஆம்", "உறுதி", "செய்யலாம்", "பதிவு செய்க"]):
            return True, True
        if any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in negative) or any(w in lowered for w in ["வேண்டாம்", "இல்லை", "தவறு", "மாற்ற வேண்டும்"]):
            return True, False
        return False, False

    def _save_ai_message(self, db: Session, session: IVRSession, content: str, spoken: str, lang: str) -> IVRMessage:
        msg = IVRMessage(
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


new_ivr_service = NewIVRService()
