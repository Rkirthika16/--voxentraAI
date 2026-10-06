"""Stateful AI Conversation Manager for VoxentraAI Conversational IVR.
Coordinates speech correction, dynamic language detection, Coimbatore location resolution,
10+ dynamic question management, confirmation summary, and reliable DB complaint creation.
"""
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from app.models.ivr import IVRSession, IVRMessage, IVRState
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintSource
from app.models.department import Department
from app.services.speech_correction import speech_correction_service
from app.services.language_detector import language_detector
from app.services.location_resolver import location_resolver
from app.services.question_manager import question_manager, ORDERED_QUESTION_SLOTS
from app.services.complaint_service import complaint_service
from app.ai.classification_service import classify_complaint
from app.ai.priority_service import assess_priority

logger = logging.getLogger("voxentra.conversation_manager")

CATEGORY_TO_DEPARTMENT = {
    "Water Supply": "Water Supply & Sewage Department",
    "Water": "Water Supply & Sewage Department",
    "Electricity": "Electricity & Power Department",
    "Power": "Electricity & Power Department",
    "Roads": "Roads & Transport Department",
    "Roads & Infrastructure": "Roads & Transport Department",
    "Sanitation / Solid Waste Management": "Sanitation & Solid Waste Department",
    "Sanitation": "Sanitation & Solid Waste Department",
    "Garbage": "Sanitation & Solid Waste Department",
    "Drainage": "Drainage & Stormwater Department",
    "Drainage / Sewerage": "Drainage & Stormwater Department",
    "Street Lighting": "Street Lighting Department",
    "Streetlights": "Street Lighting Department",
    "Public Transport": "Roads & Transport Department",
    "Public Safety": "Public Safety & Emergency Department",
    "Other": "General Administration Department"
}


class ConversationManager:
    """Core stateful orchestrator for live voice & text IVR grievance registration."""

    def create_session(
        self,
        db: Session,
        caller_phone: Optional[str] = "+919843098765",
        language_preference: Optional[str] = "Auto"
    ) -> Tuple[IVRSession, str, str]:
        """
        Creates a new live IVR session.
        CRITICAL REQUIREMENT: AI MUST NOT SPEAK FIRST.
        Places session in silent LISTENING state (WAITING_FOR_CITIZEN).
        """
        session_id = f"ivr_sess_{uuid.uuid4().hex[:12]}"
        
        initial_memory = {
            "conversation_id": session_id,
            "call_id": session_id,
            "language": language_preference or "Auto",
            "previous_language": None,
            "citizen_input": "",
            "raw_citizen_input": "",
            "corrected_transcription": "",
            "problem_description": None,
            "problem": None,
            "category": None,
            "department": None,
            "priority": "MEDIUM",
            "district_area": None,
            "area": None,
            "taluk": None,
            "firka": None,
            "revenue_village": None,
            "corporation_zone": None,
            "ward": None,
            "street_road_name": None,
            "street": None,
            "exact_location": None,
            "landmark": None,
            "latitude": None,
            "longitude": None,
            "city": "Coimbatore",
            "district": "Coimbatore",
            "state": "Tamil Nadu",
            "start_time": None,
            "duration": None,
            "affected_scope": None,
            "affected_area": None,
            "frequency": None,
            "previous_complaint": None,
            "previous_complaint_id": None,
            "previous_complaint_number": None,
            "severity": None,
            "impact": None,
            "safety_hazard": None,
            "additional_details": None,
            "additional_information": None,
            "citizen_name": None,
            "citizen_phone": caller_phone or "+919843098765",
            "confirmation_status": "PENDING",
            "current_question": None,
            "questions_asked": [],
            "questions_answered": [],
            "questions_asked_count": 0,
            "max_questions": 10,
            "call_status": "ACTIVE",
            "location": None
        }

        ivr_session = IVRSession(
            session_id=session_id,
            caller_phone=caller_phone or "+919843098765",
            language=language_preference or "Auto",
            state=IVRState.WAITING_FOR_CITIZEN.value,
            structured_memory=initial_memory,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(ivr_session)
        db.commit()
        db.refresh(ivr_session)

        logger.info(f"[ConversationManager] Session created: {session_id}, AI silent, waiting for citizen to speak first.")
        return ivr_session, "", ""

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
        Executes a turn of two-way conversation:
        1. Speech cleanup & Whisper mistake correction
        2. Dynamic language detection (Tamil, English, Tanglish) & switching
        3. Information extraction & location resolution
        4. Memory update (never forgetting previous details)
        5. Next missing question generation (dynamic, 10+ questions)
        6. Summary confirmation & DB complaint creation on approval
        """
        ivr_session = self.get_session(db, session_id)
        if not ivr_session:
            return {
                "success": False,
                "error_code": "SESSION_NOT_FOUND",
                "message": f"Session {session_id} not found",
                "state": IVRState.ERROR.value
            }

        raw_text = speech_text.strip() if speech_text else ""
        if not raw_text:
            return self._handle_silence_or_empty(db, ivr_session)

        # 1. Clean & correct transcription mistakes
        cleaned = speech_correction_service.clean(raw_text)

        # 2. Dynamic Language Detection
        current_lang = ivr_session.language if ivr_session.language not in ["Auto", "Auto-Detecting...", "", None] else None
        detected_lang, conf = language_detector.detect(raw_text, current_session_lang=current_lang)
        prev_lang = ivr_session.language
        ivr_session.language = detected_lang
        ivr_session.language_confidence = float(conf)

        # Save citizen message record
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

        # Update full transcript memory
        memory = dict(ivr_session.structured_memory or {})
        memory["conversation_id"] = session_id
        memory["call_id"] = session_id
        memory["language"] = detected_lang
        memory["previous_language"] = prev_lang
        memory["citizen_input"] = (memory.get("citizen_input", "") + f"\n{raw_text}").strip()
        memory["raw_citizen_input"] = memory["citizen_input"]
        memory["corrected_transcription"] = (memory.get("corrected_transcription", "") + f"\n{cleaned}").strip()

        # 3. Check if currently in CONFIRMATION state
        if ivr_session.state == IVRState.CONFIRMATION.value:
            is_decision, is_confirmed = self._is_confirmation_response(raw_text)
            if is_decision:
                if is_confirmed:
                    memory["confirmation_status"] = "CONFIRMED"
                    ivr_session.structured_memory = memory
                    db.commit()
                    return self.finalize_and_register_complaint(db, ivr_session)
                else:
                    # Citizen wants to modify or correct details
                    memory["confirmation_status"] = "REJECTED"
                    ivr_session.state = IVRState.WAITING_FOR_CITIZEN.value
                    ivr_session.structured_memory = memory
                    db.commit()
                    return self._generate_edit_prompt(db, ivr_session, detected_lang)

        # 4. Extract slots and update conversation memory
        prompted_slot = ivr_session.current_field_prompted
        self._extract_and_update_memory(raw_text, cleaned, memory, prompted_slot=prompted_slot)

        # Synchronize location alias in memory
        if memory.get("area") or memory.get("district_area") or memory.get("street"):
            if memory.get("street") and memory.get("area"):
                memory["location"] = f"{memory['street']}, {memory['area']}, Coimbatore"
            else:
                memory["location"] = memory.get("area") or memory.get("district_area") or memory.get("street")
        else:
            memory["location"] = None

        # Update session DB columns
        ivr_session.category = memory.get("category")
        ivr_session.problem = memory.get("problem_description") or memory.get("problem")
        ivr_session.location = memory.get("location")
        ivr_session.duration = memory.get("duration")
        ivr_session.affected_scope = memory.get("affected_scope") or memory.get("affected_area")
        ivr_session.frequency = memory.get("frequency")
        ivr_session.severity = memory.get("severity")
        ivr_session.priority = memory.get("priority", "MEDIUM")
        ivr_session.department = memory.get("department")
        ivr_session.citizen_name = memory.get("citizen_name")
        ivr_session.structured_memory = memory
        db.commit()

        # 5. Check next missing slot
        next_missing = question_manager.get_next_missing_slot(memory, min_questions=10)

        if next_missing is None:
            # All needed details or at least 10 interaction points collected -> Confirmation Summary
            ivr_session.state = IVRState.CONFIRMATION.value
            ivr_session.current_field_prompted = None
            db.commit()

            summary_text, spoken_summary = question_manager.build_confirmation_summary(memory, detected_lang)
            self._save_ai_message(db, ivr_session, summary_text, spoken_summary, detected_lang)

            return {
                "success": True,
                "session_id": ivr_session.session_id,
                "state": IVRState.CONFIRMATION.value,
                "detected_language": detected_lang,
                "language_confidence": conf,
                "ai_reply": summary_text,
                "spoken_reply": spoken_summary,
                "memory": memory,
                "question_count": memory.get("questions_asked_count", 0),
                "max_questions": memory.get("max_questions", 10),
                "is_confirmation": True,
                "complaint_created": False,
                "options": self._get_confirmation_options(detected_lang)
            }
        else:
            # Increment question counter and record question
            current_q_count = memory.get("questions_asked_count", 0) + 1
            memory["questions_asked_count"] = current_q_count
            memory["current_question"] = next_missing
            asked_list = memory.get("questions_asked", [])
            if next_missing not in asked_list:
                asked_list.append(next_missing)
            memory["questions_asked"] = asked_list
            ivr_session.structured_memory = memory

            ivr_session.state = IVRState.WAITING_FOR_CITIZEN.value
            ivr_session.current_field_prompted = next_missing
            db.commit()

            ai_reply, spoken_reply, options = question_manager.generate_question(next_missing, memory, detected_lang)
            self._save_ai_message(db, ivr_session, ai_reply, spoken_reply, detected_lang)

            return {
                "success": True,
                "session_id": ivr_session.session_id,
                "state": IVRState.WAITING_FOR_CITIZEN.value,
                "detected_language": detected_lang,
                "language_confidence": conf,
                "ai_reply": ai_reply,
                "spoken_reply": spoken_reply,
                "memory": memory,
                "next_field": next_missing,
                "question_count": current_q_count,
                "max_questions": memory.get("max_questions", 10),
                "is_confirmation": False,
                "complaint_created": False,
                "options": options
            }

    def _extract_and_update_memory(
        self,
        raw_text: str,
        cleaned: str,
        memory: Dict[str, Any],
        prompted_slot: Optional[str] = None
    ) -> None:
        """Extracts slots without losing previous information."""
        lowered = cleaned.lower().strip()

        # 1. Handle user corrections (e.g. 'No, not 5th street, 6th street', 'Area is RS Puram')
        self._handle_user_corrections(raw_text, cleaned, memory)

        # 2. Problem & Category Detection
        if not memory.get("problem_description") or prompted_slot == "problem_description":
            cat, dept, _ = classify_complaint(cleaned)
            if cat != "Other" or any(w in lowered for w in ["water", "thanni", "current", "power", "road", "garbage", "drainage", "light", "குடிநீர்", "மின்சாரம்", "குப்பை", "சாலை", "சாக்கடை", "விளக்கு"]) or prompted_slot == "problem_description":
                memory["problem_description"] = raw_text.strip()
                memory["problem"] = raw_text.strip()
                memory["category"] = cat if cat != "Other" else (memory.get("category") or "Water")
                dept_name = CATEGORY_TO_DEPARTMENT.get(memory["category"], dept)
                memory["department"] = dept_name

        # 3. Location Resolution via Coimbatore Location Resolver
        cbe_res = location_resolver.resolve(cleaned)
        if cbe_res and cbe_res.get("confidence", 0.0) >= 0.70:
            if cbe_res.get("area") and not memory.get("district_area"):
                memory["district_area"] = cbe_res["area"]
                memory["area"] = cbe_res["area"]
            if cbe_res.get("street") and not memory.get("street_road_name"):
                memory["street_road_name"] = cbe_res["street"]
                memory["street"] = cbe_res["street"]
            if cbe_res.get("landmark") and not memory.get("landmark"):
                memory["landmark"] = cbe_res["landmark"]
            if cbe_res.get("taluk"):
                memory["taluk"] = cbe_res["taluk"]
            if cbe_res.get("firka"):
                memory["firka"] = cbe_res["firka"]
            if cbe_res.get("revenue_village"):
                memory["revenue_village"] = cbe_res["revenue_village"]
            if cbe_res.get("corporation_zone"):
                memory["corporation_zone"] = cbe_res["corporation_zone"]
            if cbe_res.get("ward_no"):
                memory["ward"] = f"Ward {cbe_res['ward_no']}"
            if cbe_res.get("latitude"):
                memory["latitude"] = str(cbe_res["latitude"])
            if cbe_res.get("longitude"):
                memory["longitude"] = str(cbe_res["longitude"])

        # Fallback slot prompts if explicitly asked
        if prompted_slot == "district_area" and not memory.get("district_area"):
            cand_area = re.sub(r'^(?:in|at|near|the|enga|anga|unga|inda|indha|இந்த|அந்த|பகுதியில்|இடத்தில்)\s+', '', raw_text, flags=re.IGNORECASE).strip()
            if len(cand_area) >= 2:
                memory["district_area"] = cand_area
                memory["area"] = cand_area

        if prompted_slot == "street_road_name" and not memory.get("street_road_name"):
            cand_st = re.sub(r'^(?:in\s+the|on\s+the|at\s+the|the|this|that|inda|indha|இந்த|அந்த|எங்கள்|என்)\s+', '', raw_text, flags=re.IGNORECASE).strip()
            if len(cand_st) >= 2:
                memory["street_road_name"] = cand_st
                memory["street"] = cand_st

        if prompted_slot == "exact_location" and not memory.get("exact_location"):
            memory["exact_location"] = raw_text.strip()

        if prompted_slot == "landmark" and not memory.get("landmark"):
            cand_lm = re.sub(r'^(?:near|opposite|opp|behind|kitta|pakkam|பக்கத்தில்|அருகில்)\s+', '', raw_text, flags=re.IGNORECASE).strip()
            memory["landmark"] = f"Near {cand_lm}" if cand_lm else raw_text.strip()

        # 4. Duration & Start Time
        dur_patterns = [
            r'\b(\d+\s*(?:days?|hours?|weeks?|months?)(?:-ah)?)\b',
            r'\b((?:two|three|four|five|six|seven|one|ten)\s*(?:days?|hours?|weeks?)(?:-ah)?)\b',
            r'\b(since\s*(?:yesterday|morning|last\s*week|\d+\s*days?))\b',
            r'\b(yesterday|today\s*morning|last\s*night|netru|inniku|kaalai|just\s*now)\b',
            r'\b(\d+\s*(?:நாட்களாக|நாளாக|நாளா|வாரமாக|மணி நேரமாக|நாட்கள்|நாள்))\b',
            r'\b((?:ரெண்டு|மூணு|நாலு|அஞ்சு|பத்து|இரண்டு|மூன்று|ஒரு வாரம்)\s*(?:நாட்களாக|நாளாக|நாளா|நாள்|வாரம்))\b',
            r'\b(rendu\s*naal[a-z]*|moonu\s*naal[a-z]*|nethu\s*lendhu|nethula\s*irundhu|kaalaila\s*irundhu|morning\s*lendhu|romba\s*naal[a-z]*|palanaal[a-z]*|oru\s*varam[a-z]*|oru\s*masam[a-z]*)\b'
        ]
        for pat in dur_patterns:
            m = re.search(pat, lowered)
            if m and not memory.get("duration"):
                memory["duration"] = m.group(0).strip()
                memory["start_time"] = memory["duration"]
                break

        if prompted_slot == "duration" and not memory.get("duration"):
            memory["duration"] = raw_text.strip()
            memory["start_time"] = raw_text.strip()

        # 5. Scope
        if any(w in lowered for w in ["full-ah", "fulla", "full street", "entire street", "whole street", "area full", "street full", "எல்லா வீடுகளும்", "முழு தெரு", "ellarukum", "all houses"]):
            memory["affected_scope"] = "Entire street / area"
            memory["affected_area"] = "Entire street / area"
        elif any(w in lowered for w in ["only my house", "veedu mattum", "single house", "எங்கள் வீடு மட்டும்", "enga veedu mattum", "my house"]):
            memory["affected_scope"] = "Single house"
            memory["affected_area"] = "Single house"
        elif prompted_slot == "affected_scope" and not memory.get("affected_scope"):
            memory["affected_scope"] = raw_text.strip()
            memory["affected_area"] = raw_text.strip()

        # 6. Severity & Safety Hazards
        if prompted_slot == "severity" and not memory.get("severity"):
            memory["severity"] = raw_text.strip()

        if any(w in lowered for w in ["danger", "hazard", "sparking", "live wire", "fire", "smoke", "accident", "emergency", "கசிவு", "ஆபத்து", "விபத்து", "தீ", "aapathu"]):
            memory["safety_hazard"] = "Immediate safety risk reported"
            memory["priority"] = "HIGH"
        elif prompted_slot == "safety_hazard" and not memory.get("safety_hazard"):
            if any(w in lowered for w in ["no", "illa", "illai", "nothing", "இல்லை", "ஆபத்து இல்லை"]):
                memory["safety_hazard"] = "None"
            else:
                memory["safety_hazard"] = raw_text.strip()
                memory["priority"] = "HIGH"

        # 7. Impact
        if prompted_slot == "impact" and not memory.get("impact"):
            memory["impact"] = raw_text.strip()

        # 8. Frequency
        if prompted_slot == "frequency" and not memory.get("frequency"):
            memory["frequency"] = raw_text.strip()
        elif any(w in lowered for w in ["daily", "recurring", "frequent", "often", "adikkadi", "always", "first time"]):
            if not memory.get("frequency"):
                memory["frequency"] = raw_text.strip()

        # 9. Previous Complaint
        if prompted_slot == "previous_complaint" and not memory.get("previous_complaint"):
            if any(w in lowered for w in ["yes", "aama", "already", "reported", "ஆமாம்"]):
                memory["previous_complaint"] = "Yes (Previously reported)"
            elif any(w in lowered for w in ["no", "first time", "illa", "illai", "இல்லை"]):
                memory["previous_complaint"] = "No (First time)"
                memory["previous_complaint_number"] = "N/A"
            else:
                memory["previous_complaint"] = raw_text.strip()

        if prompted_slot == "previous_complaint_number" and not memory.get("previous_complaint_number"):
            memory["previous_complaint_number"] = raw_text.strip()

        # 10. Additional details
        if prompted_slot == "additional_details" and not memory.get("additional_details"):
            if any(w in lowered for w in ["no", "nothing", "illa", "illai", "none", "இல்லை"]):
                memory["additional_details"] = "None"
            else:
                memory["additional_details"] = raw_text.strip()

        # Priority calculation
        if memory.get("problem_description"):
            prio, _ = assess_priority(memory["problem_description"], memory.get("category", "General"))
            if memory.get("safety_hazard") and "risk" in memory.get("safety_hazard", "").lower():
                memory["priority"] = "HIGH"
            else:
                memory["priority"] = prio.value if hasattr(prio, 'value') else str(prio)

    def _handle_user_corrections(self, raw_text: str, cleaned: str, memory: Dict[str, Any]) -> None:
        """Handles user turn corrections (e.g. 'No, not 5th street, 6th street')."""
        lowered = raw_text.lower()
        if any(neg in lowered for neg in ["no,", "not", "illa,", "illai,", "இல்லை"]):
            # Street correction
            st_match = re.search(r'(?:not\s+[A-Za-z0-9\s]+,?\s*(?:it\s*is\s*)?|illa\s+)([0-9]+(?:st|nd|rd|th)?\s+(?:street|road|cross|salai|theru))', raw_text, re.IGNORECASE)
            if st_match:
                memory["street_road_name"] = st_match.group(1).strip()
                memory["street"] = st_match.group(1).strip()

            # Area correction
            area_match = re.search(r'(?:not\s+[A-Za-z0-9\s]+,?\s*(?:it\s*is\s*)?|illa\s+)([A-Za-z\u0B80-\u0BFF\s]+(?:area|nagar|colony|puram|palayam))', raw_text, re.IGNORECASE)
            if area_match:
                memory["district_area"] = area_match.group(1).strip()
                memory["area"] = area_match.group(1).strip()

    def _is_confirmation_response(self, text: str) -> Tuple[bool, bool]:
        """Detects if response confirms or rejects registration."""
        lowered = text.lower().strip()
        positive_markers = [
            "yes", "yeah", "yep", "correct", "confirm", "register", "aama", "aamam", "aamaa",
            "ama", "amam", "seri", "sari", "pannunga", "register pannunga", "correct dhaan",
            "ஆம்", "சரி", "பதிவு செய்", "பதிவு பண்ணுங்க", "உண்மை", "சரிதான்", "கட்டாயம்"
        ]
        negative_markers = [
            "no", "nope", "wrong", "change", "edit", "modify", "maathanum", "maathu", "illa", "illai",
            "இல்லை", "தவறு", "மாற்று", "மாற்ற வேண்டும்", "வேண்டாம்"
        ]
        if any(w in lowered for w in positive_markers):
            return True, True
        if any(w in lowered for w in negative_markers):
            return True, False
        return False, False

    def finalize_and_register_complaint(self, db: Session, session: IVRSession) -> Dict[str, Any]:
        """
        Finalizes complaint in SQLite DB.
        CRITICAL RULE: Complaint ID is generated ONLY AFTER successful DB insertion.
        If DB fails, safe fallback is executed without generating a fake complaint ID.
        """
        memory = dict(session.structured_memory or {})
        lang = session.language or "Tanglish"

        category = memory.get("category") or "General"
        department_name = CATEGORY_TO_DEPARTMENT.get(category, "General Administration Department")
        dept = db.query(Department).filter(Department.name.ilike(f"%{category}%")).first()
        if not dept:
            dept = db.query(Department).first()

        priority_str = memory.get("priority", "MEDIUM").upper()
        prio_enum = ComplaintPriority[priority_str] if priority_str in ComplaintPriority.__members__ else ComplaintPriority.MEDIUM

        problem_title = memory.get("problem_description") or memory.get("problem") or "Civic Grievance"
        if len(problem_title) > 90:
            problem_title = problem_title[:87] + "..."

        area = memory.get("area") or memory.get("district_area") or "Coimbatore"
        street = memory.get("street") or memory.get("street_road_name") or ""
        landmark = memory.get("landmark") or ""
        loc_str = f"{street}, {area}".strip(", ") if street else area

        try:
            # Generate unique ID upon insertion
            year = datetime.now().year
            count = db.query(Complaint).count() + 1
            complaint_number = f"VX-{year}-{count:05d}"

            # Verify uniqueness
            while db.query(Complaint).filter(Complaint.complaint_number == complaint_number).first():
                count += 1
                complaint_number = f"VX-{year}-{count:05d}"

            complaint = Complaint(
                complaint_number=complaint_number,
                title=f"{category} Grievance in {loc_str}",
                description=f"{problem_title}. Location: {loc_str}. Landmark: {landmark}. Duration: {memory.get('duration', 'N/A')}. Scope: {memory.get('affected_scope', 'N/A')}.",
                original_text=memory.get("raw_citizen_input", problem_title),
                normalized_text=memory.get("corrected_transcription", problem_title),
                language=lang,
                category=category,
                location=loc_str,
                latitude=memory.get("latitude") or "11.016800",
                longitude=memory.get("longitude") or "76.955800",
                priority=prio_enum,
                status=ComplaintStatus.SUBMITTED,
                source=ComplaintSource.TELEPHONY_IVR,
                department_id=dept.id if dept else None,
                citizen_confirmed=True,
                ai_metadata=memory
            )
            db.add(complaint)
            db.flush()

            # Link session to complaint
            session.complaint_id = complaint.id
            session.complaint_number = complaint_number
            session.state = IVRState.COMPLETED.value
            memory["complaint_id"] = complaint.id
            memory["complaint_number"] = complaint_number
            memory["call_status"] = "COMPLETED"
            session.structured_memory = memory
            db.commit()

            # Multilingual success voice response
            if lang == "Tamil":
                ai_reply = f"உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டது. உங்கள் புகார் எண் {complaint_number}. தற்போதைய நிலை: பரிசீலனையில் உள்ளது (Pending). நன்றி!"
            elif lang == "Tanglish":
                ai_reply = f"Unga complaint successfully register aayiduchu. Unga Complaint ID {complaint_number}. Current status: Pending. VoxentraAI-ku call pannadhuku nandri!"
            else:
                ai_reply = f"Your complaint has been registered successfully. Your complaint ID is {complaint_number}. The current status is Pending. Thank you for calling VoxentraAI!"

            self._save_ai_message(db, session, ai_reply, ai_reply, lang)

            return {
                "success": True,
                "session_id": session.session_id,
                "state": IVRState.COMPLETED.value,
                "complaint_created": True,
                "complaint_id": complaint.id,
                "complaint_number": complaint_number,
                "department": department_name,
                "category": category,
                "location": loc_str,
                "status": "Pending",
                "ai_reply": ai_reply,
                "spoken_reply": ai_reply,
                "memory": memory
            }

        except Exception as e:
            logger.error(f"[ConversationManager] Database insertion failed: {e}")
            db.rollback()
            session.state = IVRState.ERROR.value
            db.commit()

            if lang == "Tamil":
                err_msg = "மன்னிக்கவும், தொழில்நுட்பக் கோளாறு காரணமாக புகாரைப் பதிவு செய்ய முடியவில்லை. சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்."
            elif lang == "Tanglish":
                err_msg = "Sorry, technical problem naala complaint save panna mudiyala. Konjam neram kazhichu try pannunga."
            else:
                err_msg = "Sorry, we could not save your complaint due to a technical error. Please try again later."

            return {
                "success": False,
                "session_id": session.session_id,
                "state": IVRState.ERROR.value,
                "complaint_created": False,
                "error_code": "DATABASE_ERROR",
                "message": err_msg,
                "ai_reply": err_msg,
                "spoken_reply": err_msg
            }

    def _generate_edit_prompt(self, db: Session, session: IVRSession, lang: str) -> Dict[str, Any]:
        """Prompts citizen on which field they wish to update."""
        if lang == "Tamil":
            reply = "எந்த விவரத்தை மாற்ற விரும்புகிறீர்கள்? இடம், தெரு அல்லது பிரச்சினை விவரத்தைக் கூறுங்கள்."
        elif lang == "Tanglish":
            reply = "Enna detail maathanum? Location, street illa problem detail sollunga."
        else:
            reply = "Which detail would you like to modify? Please mention the area, street, or issue."

        self._save_ai_message(db, session, reply, reply, lang)
        return {
            "success": True,
            "session_id": session.session_id,
            "state": IVRState.WAITING_FOR_CITIZEN.value,
            "ai_reply": reply,
            "spoken_reply": reply,
            "memory": session.structured_memory
        }

    def _handle_silence_or_empty(self, db: Session, session: IVRSession) -> Dict[str, Any]:
        """Handles silence or empty mic audio gracefully."""
        lang = session.language if session.language not in ["Auto", None] else "Tanglish"
        if lang == "Tamil":
            reply = "மன்னிக்கவும், உங்கள் குரல் தெளிவாக கேட்கவில்லை. மறுபடியும் சொல்லுங்கள்."
        elif lang == "Tanglish":
            reply = "Sorry, voice clear-ah kekkala. Innum oru thadava sollunga."
        else:
            reply = "Sorry, I could not hear you clearly. Could you please repeat?"

        return {
            "success": True,
            "session_id": session.session_id,
            "state": session.state,
            "ai_reply": reply,
            "spoken_reply": reply,
            "memory": session.structured_memory
        }

    def _get_confirmation_options(self, lang: str) -> List[Dict[str, str]]:
        if lang == "Tamil":
            return [
                {"label": "✅ ஆம், பதிவு செய்க (Register)", "text": "ஆம், புகாரை பதிவு செய்யுங்கள்"},
                {"label": "✏️ விவரங்களை மாற்று (Edit)", "text": "விவரங்களை மாற்ற வேண்டும்"}
            ]
        elif lang == "Tanglish":
            return [
                {"label": "✅ Aama, Register Pannunga", "text": "Aama, complaint-a register pannunga"},
                {"label": "✏️ Details Maathanum", "text": "Details maathanum"}
            ]
        else:
            return [
                {"label": "✅ Yes, Register Complaint", "text": "Yes, please register the complaint"},
                {"label": "✏️ Modify Details", "text": "I want to change the details"}
            ]

    def _save_ai_message(self, db: Session, session: IVRSession, text: str, spoken: str, lang: str) -> None:
        ai_msg = IVRMessage(
            session_id=session.id,
            role="assistant",
            content=text,
            normalized_content=spoken,
            language=lang,
            created_at=datetime.now(timezone.utc)
        )
        db.add(ai_msg)
        db.commit()


conversation_manager = ConversationManager()
