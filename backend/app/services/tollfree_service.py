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
from app.ai.location_service import extract_location
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
    "Public Health": "Public Health & Sanitation Department",
    "Public Safety": "Public Safety & Municipal Enforcement",
    "Animal Control": "Animal Control & Public Safety",
    "Revenue / Property Tax": "Revenue & Property Tax Department",
    "Civil Registration": "Civil Registration Department",
    "Other": "General Municipal Administration"
}


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
        Creates incoming toll-free call session, logs initial greeting,
        and sets state to WAITING_FOR_CITIZEN (Citizen speaks first).
        """
        session_id = f"tf_sess_{uuid.uuid4().hex[:12]}"

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

        # Build initial greeting (Tanglish/Tamil/English)
        greeting_text = (
            "Vanakkam! VoxentraAI citizen complaint service-ku welcome. "
            "Ungaloda problem-a sollunga."
        )
        greeting_spoken = greeting_text

        # Record AI greeting in message history
        ai_msg = TollFreeMessage(
            session_id=session.id,
            role="ai",
            content=greeting_text,
            normalized_content=greeting_spoken,
            language="Tanglish",
            created_at=datetime.now(timezone.utc)
        )
        db.add(ai_msg)
        db.commit()

        logger.info(f"[TollFree] Call connected: {session_id} from {caller_phone}. Waiting for citizen.")
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
        Executes one complete two-way conversational turn:
        1. Normalizes raw speech while preserving raw transcript.
        2. Detects/adapts language (Tamil, English, Tanglish).
        3. Updates conversation memory & handles citizen corrections.
        4. Handles confirmation/rejection if in CONFIRMATION state.
        5. Asks next missing question (one at a time) or initiates final confirmation.
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

        # 2. Dynamic Language Detection & Adaptation
        detected_lang, conf = detect_language(raw_text)
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
                    # Citizen wants to edit or correct details
                    session.state = TollFreeState.WAITING_FOR_CITIZEN.value
                    db.commit()
                    return self._generate_edit_prompt(db, session, detected_lang)

        # 5. Extract slots & update structured memory (Handling explicit corrections)
        memory = dict(session.structured_memory or {})
        self._extract_and_update_memory(raw_text, cleaned, memory)

        # Synchronize columns with memory
        session.category = memory.get("category")
        session.problem = memory.get("problem")
        session.location = memory.get("location")
        session.duration = memory.get("duration")
        session.affected_scope = memory.get("affected_scope")
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
            # All essential slots collected -> Move to CONFIRMATION
            session.state = TollFreeState.CONFIRMATION.value
            session.current_field_prompted = None
            db.commit()

            summary_text, spoken_summary = self._build_confirmation_summary(memory, detected_lang)
            self._save_ai_message(db, session, summary_text, spoken_summary, detected_lang)

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
                "complaint_created": False
            }
        else:
            # Ask the next missing relevant question
            session.state = TollFreeState.WAITING_FOR_CITIZEN.value
            session.current_field_prompted = next_missing
            db.commit()

            ai_reply, spoken_reply = self._generate_slot_question(next_missing, memory, detected_lang)
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
                "complaint_created": False
            }

    def _extract_and_update_memory(self, raw_text: str, cleaned: str, memory: Dict[str, Any]) -> None:
        """
        Extracts civic entities and updates memory.
        Handles explicit corrections (e.g. "No, water problem", "No, actually Saibaba Colony").
        """
        lowered = raw_text.lower()

        # Check explicit correction for category
        if any(w in lowered for w in ["water problem", "water issue", "தண்ணீர்", "thanni", "குடிநீர்"]):
            memory["category"] = "Water Supply"
            memory["department"] = "Water Supply Department"
            memory["problem"] = raw_text
        elif any(w in lowered for w in ["current problem", "power problem", "electricity problem", "மின்வெட்டு", "மின்சாரம்"]):
            memory["category"] = "Electricity"
            memory["department"] = "Electricity & Power Department"
            memory["problem"] = raw_text

        # 1. Problem & Category Detection
        if not memory.get("problem"):
            cat, dept, cat_conf = classify_complaint(cleaned)
            if cat != "Other" or any(w in lowered for w in ["water", "thanni", "power", "current", "road", "garbage", "drainage", "light", "குடிநீர்", "மின்சாரம்", "குப்பை", "சாலை", "சாக்கடை"]):
                memory["problem"] = raw_text
                memory["category"] = cat
                memory["department"] = DEPARTMENT_MASTER.get(cat, dept)

        # 2. Location Detection
        loc_name, lat, lon, conf = extract_location(raw_text)
        if loc_name and loc_name != "Tamil Nadu":
            if not memory.get("location") or "no" in lowered or "actually" in lowered or "change" in lowered:
                memory["location"] = loc_name
            elif loc_name.lower() not in memory.get("location", "").lower():
                memory["location"] = f"{loc_name}, {memory['location']}"

        # Explicit location road/street regex
        street_match = re.search(r'\b([A-Za-z0-9\s]+(?:street|road|salai|theru|cross|avenue|nagar|colony|bus\s*stand))\b', raw_text, re.IGNORECASE)
        if street_match and (not memory.get("location") or "actually" in lowered or "no" in lowered):
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

        # 4. Scope / Affected Area
        if any(w in lowered for w in ["full", "full-ah", "fulla", "entire", "whole", "area full", "street full", "எல்லா", "முழுவதும்"]):
            memory["affected_scope"] = "Entire Area / Street Affected"
        elif any(w in lowered for w in ["only my house", "veedu mattum", "single house", "எங்கள் வீடு மட்டும்"]):
            memory["affected_scope"] = "Single House Affected"

        # 5. Frequency
        if any(w in lowered for w in ["daily", "every day", "dinamum", "thinamum", "தினமும்"]):
            memory["frequency"] = "Daily Recurring"
        elif any(w in lowered for w in ["first time", "mudhal murai", "முதல் முறை"]):
            memory["frequency"] = "First Time"

        # 6. Citizen Name
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
        Determines the next missing information slot.
        Enforces one question at a time and avoids re-asking collected information.
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
        Generates contextual follow-up questions tailored to previously collected slots.
        """
        cat = memory.get("category", "General")
        loc = memory.get("location") or "your area"

        if slot == "problem":
            if lang == "Tamil":
                text = "வணக்கம்! உங்களுக்கு ஏற்பட்டுள்ள பொதுப் பிரச்சனை என்ன என்பதை தயவுசெய்து கூறவும்."
                spoken = "வணக்கம்! உங்களுக்கு என்ன பிரச்சனை உள்ளது என்று கூறவும்."
            elif lang == "Tanglish":
                text = "Vanakkam! Ungaloda civic problem enna nu describe pannunga."
                spoken = "Ungaloda problem enna nu sollunga."
            else:
                text = "Hello! Could you please describe the civic problem you are reporting?"
                spoken = "Please describe the problem you would like to report."
            return text, spoken

        if slot == "location":
            if lang == "Tamil":
                text = "சரி. இந்த பிரச்சனை எந்த பகுதியில் அல்லது தெருவில் உள்ளது?"
                spoken = "இந்த பிரச்சனை எந்த பகுதியில் உள்ளது?"
            elif lang == "Tanglish":
                text = f"Okay, indha {cat} problem endha area or street-la irukku?"
                spoken = f"Indha problem endha area-la irukku?"
            else:
                text = f"In which area, street, or locality is this {cat} problem located?"
                spoken = "In which area or street is this problem located?"
            return text, spoken

        if slot == "duration":
            if lang == "Tamil":
                text = f"சரி, **{loc}** பகுதியில் இந்தப் பிரச்சனை எப்போது முதல் நீடிக்கிறது?"
                spoken = f"இந்தப் பிரச்சனை எப்போது முதல் நீடிக்கிறது?"
            elif lang == "Tanglish":
                text = f"Okay, **{loc}**-la indha problem eppo lendhu varala?"
                spoken = f"Idhu eppo lendhu varala?"
            else:
                text = f"How long has this issue been happening in **{loc}**?"
                spoken = "How long has this problem been happening?"
            return text, spoken

        if slot == "affected_scope":
            if lang == "Tamil":
                text = f"அந்த பகுதி முழுவதும் பாதிக்கப்பட்டுள்ளதா அல்லது உங்கள் வீட்டில் மட்டுமா?"
                spoken = "பகுதி முழுவதும் பாதிக்கப்பட்டுள்ளதா?"
            elif lang == "Tanglish":
                text = f"Seri. Area full-ah water varalaya?"
                spoken = f"Area full-ah problem-aa?"
            else:
                text = f"Is the entire area of **{loc}** affected, or only your specific building?"
                spoken = "Is the entire area affected?"
            return text, spoken

        return "Could you please provide more details?", "Please provide more details."

    def _build_confirmation_summary(self, memory: Dict[str, Any], lang: str) -> Tuple[str, str]:
        """
        Builds the final pre-registration summary asking: 'Are all these details correct?'.
        """
        problem = memory.get("problem", "Civic Grievance")
        category = memory.get("category", "General")
        dept = memory.get("department") or DEPARTMENT_MASTER.get(category, "Municipal Administration")
        location = memory.get("location", "Tamil Nadu")
        duration = memory.get("duration", "Active")
        scope = memory.get("affected_scope", "Affected Locality")

        if lang == "Tamil":
            text = (
                f"சரி. நீங்கள் கொடுத்த தகவல்படி, {location} பகுதியில் {duration} {problem}.\n\n"
                f"துறை: {dept}\n"
                f"பாதிக்கப்பட்ட அளவு: {scope}\n\n"
                f"இந்த புகாரை {dept}-க்கு அனுப்பலாமா? இந்த தகவல்கள் எல்லாம் சரிதானா?"
            )
            spoken = (
                f"சரி. நீங்கள் கொடுத்த தகவல்படி, {location} பகுதியில் {duration} {problem}. "
                f"இந்த புகாரை {dept}-க்கு அனுப்பலாமா? இந்த தகவல்கள் எல்லாம் சரிதானா?"
            )
        elif lang == "Tanglish":
            text = (
                f"Okay, {location}-la {duration} {problem}.\n\n"
                f"Department: {dept}\n"
                f"Scope: {scope}\n\n"
                f"Idha {dept}-ku send panren. Naan sonna details ellam correct-aa?"
            )
            spoken = (
                f"Okay, {location}-la {duration} water supply illa. "
                f"Idha {dept}-ku send panren. Naan sonna details ellam correct-aa?"
            )
        else:
            text = (
                f"Let me confirm your complaint.\n\n"
                f"Issue: {problem}\n"
                f"Location: {location}\n"
                f"Duration: {duration}\n"
                f"Scope: {scope}\n"
                f"Department: {dept}\n\n"
                f"I will route this to the {dept}. Are all these details correct?"
            )
            spoken = (
                f"Let me confirm your complaint. There has been an issue at {location} for {duration}. "
                f"I will route this to the {dept}. Are all these details correct?"
            )
        return text, spoken

    def _finalize_and_register_complaint(self, db: Session, session: TollFreeCallSession) -> Dict[str, Any]:
        """
        Creates the official database Complaint with status 'SUBMITTED',
        generates unique ID (e.g. VX-2026-000001), routes to department,
        and provides final spoken confirmation.
        """
        memory = dict(session.structured_memory or {})
        problem = memory.get("problem") or "Civic grievance reported via Toll-Free IVR"
        category = memory.get("category") or "Water Supply"
        location = memory.get("location") or "Tamil Nadu"
        priority_str = memory.get("priority", "MEDIUM")

        try:
            prio_enum = ComplaintPriority[priority_str]
        except Exception:
            prio_enum = ComplaintPriority.MEDIUM

        _, lat, lon, _ = extract_location(location)

        full_description = (
            f"**Toll-Free Citizen Voice Grievance:**\n\n"
            f"- Problem: {problem}\n"
            f"- Category: {category}\n"
            f"- Location: {location}\n"
            f"- Duration: {memory.get('duration', 'N/A')}\n"
            f"- Scope: {memory.get('affected_scope', 'N/A')}\n"
            f"- Caller Phone: {session.caller_phone}\n"
            f"- Toll-Free Session: {session.call_session_id}\n\n"
            f"**Full Transcript:**\n{session.raw_transcript}"
        )

        complaint_in = ComplaintCreate(
            title=f"{category} grievance at {location}"[:200],
            description=full_description,
            category=category,
            location=location[:255],
            latitude=lat,
            longitude=lon,
            priority=prio_enum,
            language=session.language or "English",
            source=ComplaintSource.TELEPHONY_IVR,
            citizen_confirmed=True,
            ai_metadata={
                "toll_free_session_id": session.call_session_id,
                "toll_free_number": session.toll_free_number,
                "memory": memory
            }
        )

        created_complaint = complaint_service.create_complaint(db=db, complaint_in=complaint_in)

        # Update TollFree Session
        session.complaint_id = created_complaint.id
        session.complaint_number = created_complaint.complaint_number
        session.state = TollFreeState.COMPLETED.value
        session.ended_at = datetime.now(timezone.utc)
        db.commit()

        # Send Twilio SMS Confirmation
        dept_name = created_complaint.department.name if created_complaint.department else "Municipal Administration"
        c_num = created_complaint.complaint_number
        sms_msg = f"VoxentraAI: Complaint {c_num} registered for {problem}. Routed to {dept_name}."
        generic_telephony_provider.send_sms(session.caller_phone or "+919843098765", sms_msg)

        # Spoken confirmation with complaint ID
        lang = session.language
        if lang == "Tamil":
            reply_text = f"உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது. உங்கள் Complaint ID **{c_num}**. இது **{dept_name}**-க்கு அனுப்பப்பட்டுள்ளது."
            spoken_text = f"உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது. உங்கள் Complaint ID {c_num}. இது {dept_name}-க்கு அனுப்பப்பட்டுள்ளது."
        elif lang == "Tanglish":
            reply_text = f"Unga complaint successfully register aayiduchu. Complaint ID **{c_num}**. Idhu **{dept_name}**-ku route pannirukku."
            spoken_text = f"Unga complaint successfully register aayiduchu. Complaint ID {c_num}. Idhu {dept_name}-ku route pannirukku."
        else:
            reply_text = f"Your complaint has been successfully registered. Your complaint ID is **{c_num}**. It has been routed to the **{dept_name}**."
            spoken_text = f"Your complaint has been successfully registered. Your complaint ID is {c_num}. It has been routed to the {dept_name}."

        self._save_ai_message(db, session, reply_text, spoken_text, lang)
        logger.info(f"[TollFree] Complaint created: {c_num} for session {session.call_session_id}")

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
        elif lang == "Tanglish":
            reply = "Seri, endha details ah maathanum nu sollunga."
            spoken = "Endha details maathanum nu sollunga."
        else:
            reply = "Understood. Which detail would you like to correct or update?"
            spoken = "Which detail would you like to update?"

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
            "complaint_created": False
        }

    def _handle_unclear_input(self, db: Session, session: TollFreeCallSession, error_code: str) -> Dict[str, Any]:
        lang = session.language or "English"
        if lang == "Tamil":
            reply = "Sorry, உங்கள் குரல் தெளிவாக கேட்கவில்லை. மீண்டும் சொல்லுங்கள்."
            spoken = "மன்னிக்கவும், உங்கள் குரல் தெளிவாக கேட்கவில்லை. மீண்டும் சொல்லுங்கள்."
        elif lang == "Tanglish":
            reply = "Sorry, unga voice clear-ah kekkala. Please once again sollunga."
            spoken = "Sorry, unga voice clear-ah kekkala. Please once again sollunga."
        else:
            reply = "Sorry, I couldn't understand your voice clearly. Please say that again."
            spoken = "Sorry, I couldn't understand your voice clearly. Please say that again."

        self._save_ai_message(db, session, reply, spoken, lang)
        return {
            "success": True,
            "session_id": session.call_session_id,
            "state": session.state,
            "detected_language": lang,
            "ai_reply": reply,
            "spoken_reply": spoken,
            "memory": session.structured_memory,
            "unclear": True,
            "error_code": error_code
        }

    def _is_unclear_mumble(self, text: str) -> bool:
        lowered = text.strip().lower()
        if len(lowered) <= 1:
            return True
        mumbles = {"umm", "uhh", "uhhh", "aaa", "hmm", "huh", "enna", "mm", "ah", "err", "uh", "um"}
        tokens = re.split(r'[\s\.\,\-]+', lowered)
        return all(t in mumbles for t in tokens if t)

    def _is_confirmation_response(self, text: str) -> Tuple[bool, bool]:
        lowered = text.strip().lower()
        positive = ["yes", "aama", "aamam", "ஆம்", "சரி", "correct", "correct-ah", "right", "confirm", "proceed", "register", "sure"]
        negative = ["no", "illa", "இல்லை", "wrong", "change", "cancel", "stop", "thappu"]

        if any(w in lowered for w in positive) or any(w in lowered for w in ["ஆமாம்", "சரி", "ஆம்"]):
            return True, True
        if any(w in lowered for w in negative) or any(w in lowered for w in ["இல்லை", "தவறு"]):
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
        session.raw_transcript = (session.raw_transcript + f"\nAI: {content}").strip()
        session.normalized_transcript = (session.normalized_transcript + f"\nAI: {spoken}").strip()
        db.commit()
        return msg


tollfree_service = TollFreeService()
