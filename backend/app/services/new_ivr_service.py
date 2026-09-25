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
from app.ai.location_service import extract_location
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
    "Public Health": "Public Health & Sanitation Department",
    "Public Safety": "Public Safety & Municipal Enforcement",
    "Animal Control": "Animal Control & Public Safety",
    "Revenue / Property Tax": "Revenue & Property Tax Department",
    "Civil Registration": "Civil Registration Department",
    "Other": "General Municipal Administration"
}


class NewIVRService:
    """
    Two-Way Conversational AI Engine for Live Citizen IVR.
    Maintains turn-by-turn memory, dynamically detects language (Tamil, English, Tanglish),
    asks one relevant question at a time, summarizes details, and registers real complaints.
    """

    def create_session(
        self,
        db: Session,
        caller_phone: Optional[str] = "+919843098765",
        language_preference: Optional[str] = "Auto"
    ) -> Tuple[IVRSession, str, str]:
        """
        Creates a new live IVR session, posts the initial greeting,
        and sets state to WAITING_FOR_CITIZEN (Citizen speaks first).
        """
        session_id = f"ivr_sess_{uuid.uuid4().hex[:12]}"
        
        initial_memory = {
            "category": None,
            "problem": None,
            "location": None,
            "duration": None,
            "affected_scope": None,
            "frequency": None,
            "severity": None,
            "priority": "MEDIUM",
            "department": None,
            "citizen_name": None
        }

        ivr_session = IVRSession(
            session_id=session_id,
            caller_phone=caller_phone,
            language=language_preference or "Auto",
            state=IVRState.WAITING_FOR_CITIZEN.value,
            structured_memory=initial_memory,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(ivr_session)
        db.commit()
        db.refresh(ivr_session)

        # Build multilingual greeting
        greeting_text = (
            "Vanakkam! Welcome to VoxentraAI Citizen Grievance Helpline. "
            "Please describe your civic complaint in Tamil, English, or Tanglish."
        )
        greeting_ta = (
            "வணக்கம்! வாக்ஸென்ட்ரா AI பொது குறைதீர்ப்பு சேவைக்கு நல்வரவு. "
            "உங்கள் புகாரை தமிழ், ஆங்கிலம் அல்லது தங்க்லீஷில் கூறவும்."
        )
        greeting_spoken = (
            "Vanakkam! VoxentraAI citizen complaint service-ku welcome. "
            "Ungaloda complaint-a sollunga."
        )

        # Store initial AI greeting message
        ai_msg = IVRMessage(
            session_id=ivr_session.id,
            role="ai",
            content=greeting_text,
            normalized_content=greeting_spoken,
            language="Tanglish",
            created_at=datetime.now(timezone.utc)
        )
        db.add(ai_msg)
        db.commit()

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

        # 1. Store citizen's original message
        normalized_text_str = normalize_text(raw_text)
        cleaned = clean_transcription(raw_text)

        # 2. Language Detection
        detected_lang, conf = detect_language(raw_text)
        ivr_session.language = detected_lang
        ivr_session.language_confidence = float(conf)

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
        memory = dict(ivr_session.structured_memory or {})
        self._extract_and_update_memory(raw_text, cleaned, memory)

        # Synchronize model columns with memory
        ivr_session.category = memory.get("category")
        ivr_session.problem = memory.get("problem")
        ivr_session.location = memory.get("location")
        ivr_session.duration = memory.get("duration")
        ivr_session.affected_scope = memory.get("affected_scope")
        ivr_session.frequency = memory.get("frequency")
        ivr_session.severity = memory.get("severity")
        ivr_session.priority = memory.get("priority", "MEDIUM")
        ivr_session.department = memory.get("department")
        ivr_session.citizen_name = memory.get("citizen_name")
        ivr_session.structured_memory = memory
        db.commit()

        # 6. Check missing slots & generate next relevant question (ONE AT A TIME)
        next_missing = self._get_next_missing_slot(memory)

        if next_missing is None:
            # All essential info collected -> Move to CONFIRMATION
            ivr_session.state = IVRState.CONFIRMATION.value
            ivr_session.current_field_prompted = None
            db.commit()

            summary_text, spoken_summary = self._build_confirmation_summary(memory, detected_lang)
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
                "is_confirmation": True,
                "complaint_created": False
            }
        else:
            # Ask the next relevant question based on category and missing slot
            ivr_session.state = IVRState.WAITING_FOR_CITIZEN.value
            ivr_session.current_field_prompted = next_missing
            db.commit()

            ai_reply, spoken_reply = self._generate_slot_question(next_missing, memory, detected_lang)
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
                "is_confirmation": False,
                "complaint_created": False
            }

    def _extract_and_update_memory(self, raw_text: str, cleaned: str, memory: Dict[str, Any]) -> None:
        """
        Extracts civic entities and updates memory without overwriting existing details
        unless an explicit correction was stated.
        """
        lowered = raw_text.lower()

        # 1. Problem & Category Detection
        if not memory.get("problem"):
            cat, dept, cat_conf = classify_complaint(cleaned)
            if cat != "Other" or any(w in lowered for w in ["water", "thanni", "power", "current", "road", "garbage", "drainage", "light", "குடிநீர்", "மின்சாரம்", "குப்பை", "சாலை", "சாக்கடை"]):
                memory["problem"] = raw_text
                memory["category"] = cat
                memory["department"] = CATEGORY_TO_DEPARTMENT.get(cat, dept)

        # 2. Location Detection
        loc_name, lat, lon, conf = extract_location(raw_text)
        if loc_name and loc_name != "Tamil Nadu":
            if not memory.get("location"):
                memory["location"] = loc_name
            elif loc_name.lower() not in memory.get("location", "").lower():
                memory["location"] = f"{loc_name}, {memory['location']}"

        # Check explicit location patterns (e.g. Gandhipuram, Anna Nagar, Cross Cut Road)
        street_match = re.search(r'\b([A-Za-z0-9\s]+(?:street|road|salai|theru|cross|avenue|nagar|colony))\b', raw_text, re.IGNORECASE)
        if street_match and not memory.get("location"):
            memory["location"] = street_match.group(1).strip()

        # 3. Duration Detection (e.g. "two days", "3 days", "since yesterday", "today morning")
        dur_patterns = [
            r'\b(\d+\s*(?:days?|hours?|weeks?|months?)(?:-ah)?)\b',
            r'\b((?:two|three|four|five|six|seven|one)\s*(?:days?|hours?|weeks?)(?:-ah)?)\b',
            r'\b(since\s*(?:yesterday|morning|last\s*week|\d+\s*days?))\b',
            r'\b(yesterday|today\s*morning|last\s*night|netru|inniku|kaalai)\b',
            r'\b(\d+\s*(?:நாட்களாக|நாளாக|நாளா|வாரமாக))\b',
            r'\b((?:ரெண்டு|மூணு|நாலு|அஞ்சு|இரண்டு|மூன்று)\s*(?:நாட்களாக|நாளாக|நாளா))\b'
        ]
        for pat in dur_patterns:
            m = re.search(pat, lowered)
            if m:
                memory["duration"] = m.group(0).strip()
                break

        # 4. Scope / Affected Area (e.g. "whole area", "entire street", "my house only", "full-ah")
        if any(w in lowered for w in ["full", "full-ah", "fulla", "entire", "whole", "area full", "street full", "எல்லா", "முழுவதும்"]):
            memory["affected_scope"] = "Entire Area / Street Affected"
        elif any(w in lowered for w in ["only my house", "veedu mattum", "single house", "எங்கள் வீடு மட்டும்"]):
            memory["affected_scope"] = "Single House Affected"

        # 5. Frequency
        if any(w in lowered for w in ["daily", "every day", "dinamum", "thinamum", "தினமும்"]):
            memory["frequency"] = "Daily Recurring"
        elif any(w in lowered for w in ["first time", "mudhal murai", "முதல் முறை"]):
            memory["frequency"] = "First Time"

        # 6. Citizen Name / Contact
        phone_match = re.search(r'\b[6-9]\d{9}\b', raw_text)
        name_match = re.search(r'(?:name\s*is|i\s*am|பெயர்|naan|peyar)\s*([A-Za-z\u0B80-\u0BFF\s]+)', raw_text, re.IGNORECASE)
        if name_match:
            cand = name_match.group(1).strip()
            if cand.lower() not in ["seri", "ok", "problem", "thanni", "water"]:
                memory["citizen_name"] = cand

        # 7. Priority Assessment
        if memory.get("problem"):
            prio, _ = assess_priority(memory["problem"], memory.get("category", "General"))
            memory["priority"] = prio.value if hasattr(prio, 'value') else str(prio)

    def _get_next_missing_slot(self, memory: Dict[str, Any]) -> Optional[str]:
        """
        Determines the next missing information slot to prompt.
        Ensures AI asks ONE question at a time and avoids re-asking collected info.
        """
        if not memory.get("problem"):
            return "problem"
        if not memory.get("location"):
            return "location"
        if not memory.get("duration"):
            return "duration"
        if not memory.get("affected_scope"):
            return "affected_scope"
        return None

    def _generate_slot_question(self, slot: str, memory: Dict[str, Any], lang: str) -> Tuple[str, str]:
        """
        Generates context-aware, category-specific follow-up questions in the appropriate language.
        """
        cat = memory.get("category", "General")
        loc = memory.get("location") or "your area"

        if slot == "problem":
            if lang == "Tamil":
                text = "வணக்கம். உங்களுக்கு ஏற்பட்டுள்ள பொதுப் பிரச்சினை என்ன என்று கூற முடியுமா?"
                spoken = "வணக்கம். உங்களுக்கு என்ன பிரச்சினை உள்ளது என்று கூறவும்."
            elif lang == "Tanglish":
                text = "Vanakkam! Ungalukku enna civic problem irukku nu describe pannunga."
                spoken = "Ungaloda problem enna nu sollunga."
            else:
                text = "Welcome. Could you please describe the civic problem you are facing?"
                spoken = "Please describe the problem you would like to report."
            return text, spoken

        if slot == "location":
            if lang == "Tamil":
                text = "சரி. இந்த பிரச்சினை எந்த பகுதியில் அல்லது தெருவில் உள்ளது?"
                spoken = "இந்த பிரச்சினை எந்த பகுதியில் அல்லது தெருவில் உள்ளது?"
            elif lang == "Tanglish":
                text = f"Okay, indha {cat} problem endha area or street-la irukku?"
                spoken = f"Indha problem endha area-la irukku?"
            else:
                text = f"In which area, street, or locality is this {cat} issue located?"
                spoken = "In which area or street is this problem located?"
            return text, spoken

        if slot == "duration":
            if lang == "Tamil":
                text = f"சரி, **{loc}** பகுதியில் இந்தப் பிரச்சினை எப்போது முதல் நீடிக்கிறது? (எ.கா: இரண்டு நாட்களாக, இன்று காலை முதல்)"
                spoken = f"இந்தப் பிரச்சினை எப்போது முதல் நீடிக்கிறது?"
            elif lang == "Tanglish":
                text = f"Okay, **{loc}**-la indha problem eppo lendhu irukku? (e.g. 2 days-ah, today morning-ah)"
                spoken = f"Indha problem eppo lendhu irukku?"
            else:
                text = f"Since when has this issue been occurring in **{loc}**? (e.g. 2 days, today morning)"
                spoken = "Since when has this problem been occurring?"
            return text, spoken

        if slot == "affected_scope":
            if lang == "Tamil":
                text = f"அந்த பகுதி முழுவதும் பாதிக்கப்பட்டுள்ளதா அல்லது உங்கள் தெருவில் மட்டுமா?"
                spoken = "பகுதி முழுவதும் பாதிக்கப்பட்டுள்ளதா?"
            elif lang == "Tanglish":
                text = f"Seri. **{loc}** area full-ah indha problem irukka, illa unga street mattumaa?"
                spoken = "Area full-ah problem-aa?"
            else:
                text = f"Is the entire area of **{loc}** affected, or only your specific street/building?"
                spoken = "Is the entire area affected?"
            return text, spoken

        return "Could you please provide more details?", "Please provide more details."

    def _build_confirmation_summary(self, memory: Dict[str, Any], lang: str) -> Tuple[str, str]:
        """
        Builds a crisp, clear pre-registration summary in Tamil, Tanglish, or English.
        """
        problem = memory.get("problem", "Civic Grievance")
        category = memory.get("category", "General")
        dept = memory.get("department") or CATEGORY_TO_DEPARTMENT.get(category, "Municipal Administration")
        location = memory.get("location", "Tamil Nadu")
        duration = memory.get("duration", "Active")
        scope = memory.get("affected_scope", "Affected Locality")

        if lang == "Tamil":
            text = (
                f"உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன்.\n\n"
                f"பிரச்சினை: {problem}\n"
                f"துறை: {dept}\n"
                f"இடம்: {location}\n"
                f"கால அளவு: {duration}\n"
                f"பாதிக்கப்பட்ட அளவு: {scope}\n\n"
                f"இந்த புகாரை பதிவு செய்யலாமா?"
            )
            spoken = (
                f"உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன். "
                f"பிரச்சினை: {problem}. இடம்: {location}. "
                f"இந்த புகாரை பதிவு செய்யலாமா?"
            )
        elif lang == "Tanglish":
            text = (
                f"Unga complaint details ah confirm panren.\n\n"
                f"Problem: {problem}\n"
                f"Department: {dept}\n"
                f"Location: {location}\n"
                f"Duration: {duration}\n"
                f"Scope: {scope}\n\n"
                f"Indha details correct-ah irukka? Complaint-ah register pannalaama?"
            )
            spoken = (
                f"Okay, {location}-la {duration} {problem}. "
                f"{scope}. Indha complaint-a register pannava?"
            )
        else:
            text = (
                f"Let me confirm your complaint details.\n\n"
                f"Issue: {problem}\n"
                f"Department: {dept}\n"
                f"Location: {location}\n"
                f"Duration: {duration}\n"
                f"Scope: {scope}\n\n"
                f"Shall I register this complaint now?"
            )
            spoken = (
                f"Let me confirm: {problem} at {location} for {duration}. "
                f"Shall I register this complaint now?"
            )
        return text, spoken

    def _finalize_and_register_complaint(self, db: Session, ivr_session: IVRSession) -> Dict[str, Any]:
        """
        Creates real Complaint database record, generates unique ID (VX-YYYYMMDD-XXXXXX / VX-YYYY-XXXXXX),
        dispatches Twilio confirmation SMS, and returns final spoken response.
        """
        memory = dict(ivr_session.structured_memory or {})
        problem = memory.get("problem") or "Civic grievance registered via AI Voice IVR"
        category = memory.get("category") or "Water Supply"
        location = memory.get("location") or "Tamil Nadu"
        priority_str = memory.get("priority", "MEDIUM")
        
        try:
            prio_enum = ComplaintPriority[priority_str]
        except Exception:
            prio_enum = ComplaintPriority.MEDIUM

        # Geocode coordinates if possible
        _, lat, lon, _ = extract_location(location)

        full_description = (
            f"**Citizen Voice Grievance Summary:**\n\n"
            f"- Problem: {problem}\n"
            f"- Category: {category}\n"
            f"- Location: {location}\n"
            f"- Duration: {memory.get('duration', 'N/A')}\n"
            f"- Scope: {memory.get('affected_scope', 'N/A')}\n"
            f"- Frequency: {memory.get('frequency', 'N/A')}\n"
            f"- Caller Phone: {ivr_session.caller_phone}\n"
            f"- Session ID: {ivr_session.session_id}"
        )

        complaint_in = ComplaintCreate(
            title=f"{category} issue at {location}"[:200],
            description=full_description,
            category=category,
            location=location[:255],
            latitude=lat,
            longitude=lon,
            priority=prio_enum,
            language=ivr_session.language or "English",
            source=ComplaintSource.TELEPHONY_IVR,
            citizen_confirmed=True,
            ai_metadata={
                "ivr_session_id": ivr_session.session_id,
                "memory": memory,
                "intake": "two_way_ai_voice_ivr"
            }
        )

        created_complaint = complaint_service.create_complaint(db=db, complaint_in=complaint_in)

        # Update IVR Session
        ivr_session.complaint_id = created_complaint.id
        ivr_session.complaint_number = created_complaint.complaint_number
        ivr_session.state = IVRState.COMPLETED.value
        ivr_session.ended_at = datetime.now(timezone.utc)
        db.commit()

        # Send Twilio Confirmation SMS
        dept_name = created_complaint.department.name if created_complaint.department else "Municipal Administration"
        sms_body = twilio_adapter.build_complaint_sms(
            complaint_number=created_complaint.complaint_number,
            description=problem,
            department=dept_name,
            location=location,
            lang=ivr_session.language
        )
        sms_res = twilio_adapter.send_sms(ivr_session.caller_phone or "+919843098765", sms_body)

        # Spoken confirmation
        c_num = created_complaint.complaint_number
        lang = ivr_session.language
        if lang == "Tamil":
            reply_text = f"நன்றி! உங்கள் புகார் எண் **{c_num}** வெற்றிகரமாக பதிவு செய்யப்பட்டது. இது **{dept_name}** துறைக்கு அனுப்பப்பட்டுள்ளது."
            spoken_text = f"நன்றி! உங்கள் புகார் எண் {c_num} வெற்றிகரமாக பதிவு செய்யப்பட்டது. விவரங்கள் எஸ்.எம்.எஸ் மூலம் அனுப்பப்பட்டுள்ளது."
        elif lang == "Tanglish":
            reply_text = f"Thank you! Unga complaint ID **{c_num}** register aaiduchu. Idhu **{dept_name}**-ku forward panniyaachu."
            spoken_text = f"Thank you! Unga complaint number {c_num}. Complaint register aaiduchu. Nandri!"
        else:
            reply_text = f"Thank you! Your complaint has been registered under ID **{c_num}** and routed to **{dept_name}**."
            spoken_text = f"Thank you! Your complaint has been registered under ID {c_num}. You will receive status updates via SMS."

        self._save_ai_message(db, ivr_session, reply_text, spoken_text, lang)

        logger.info(f"[NewIVR] Complaint registered: {c_num} for session {ivr_session.session_id}")

        return {
            "success": True,
            "session_id": ivr_session.session_id,
            "state": IVRState.COMPLETED.value,
            "detected_language": lang,
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
        elif lang == "Tanglish":
            reply = "Seri, endha details ah maathanum nu sollunga."
            spoken = "Endha details maathanum nu sollunga."
        else:
            reply = "Understood. Which detail would you like to correct or update?"
            spoken = "Which detail would you like to update?"

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
            "complaint_created": False
        }

    def _handle_unclear_input(self, db: Session, ivr_session: IVRSession, error_code: str) -> Dict[str, Any]:
        lang = ivr_session.language or "English"
        if lang == "Tamil":
            reply = "மன்னிக்கவும், உங்கள் குரல் தெளிவாக கேட்கவில்லை. தயவுசெய்து மீண்டும் ஒருமுறை கூற முடியுமா?"
            spoken = "மன்னிக்கவும், மீண்டும் ஒருமுறை கூற முடியுமா?"
        elif lang == "Tanglish":
            reply = "Sorry, unga voice clear-ah kekkala. Please once again sollunga."
            spoken = "Sorry, unga voice clear-ah kekkala. Please once again sollunga."
        else:
            reply = "Sorry, I couldn't understand that clearly. Could you please say it again?"
            spoken = "Sorry, I couldn't understand that clearly. Could you please say it again?"

        self._save_ai_message(db, ivr_session, reply, spoken, lang)
        return {
            "success": True,
            "session_id": ivr_session.session_id,
            "state": ivr_session.state,
            "detected_language": lang,
            "ai_reply": reply,
            "spoken_reply": spoken,
            "memory": ivr_session.structured_memory,
            "unclear": True,
            "error_code": error_code
        }

    def _is_unclear_or_mumble(self, text: str) -> bool:
        lowered = text.strip().lower()
        if len(lowered) <= 1:
            return True
        mumbles = {"umm", "uhh", "uhhh", "aaa", "hmm", "huh", "enna", "mm", "ah", "err", "uh", "um"}
        tokens = re.split(r'[\s\.\,\-]+', lowered)
        return all(t in mumbles for t in tokens if t)

    def _is_confirmation_response(self, text: str) -> Tuple[bool, bool]:
        lowered = text.strip().lower()
        positive = ["yes", "confirm", "confirmed", "register", "proceed", "okay", "ok", "correct", "right", "aama", "aamam", "seri", "pannunga", "podunga", "ஆமாம்", "சரி", "உறுதி", "பதிவு", "ஆம்", "sure"]
        negative = ["no", "cancel", "stop", "wait", "change", "edit", "wrong", "thappu", "illai", "illa", "vendaam", "வேண்டாம்", "இல்லை", "தவறு"]

        if any(w in lowered for w in positive) or any(w in lowered for w in ["ஆமாம்", "சரி", "பதிவு"]):
            return True, True
        if any(w in lowered for w in negative) or any(w in lowered for w in ["வேண்டாம்", "இல்லை", "தவறு"]):
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
