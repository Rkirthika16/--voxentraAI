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

        # Call connects directly in WAITING_FOR_CITIZEN state so the citizen speaks first
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

        # 1. Store citizen's original message
        normalized_text_str = normalize_text(raw_text)
        cleaned = clean_transcription(raw_text)

        # 2. Language Detection with Session Stickiness
        current_lang = ivr_session.language if ivr_session.language not in ["Auto", "Auto-Detecting...", "", None] else None
        detected_lang, conf = detect_language(raw_text, current_session_lang=current_lang)
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
        prompted_slot = ivr_session.current_field_prompted
        memory = dict(ivr_session.structured_memory or {})
        self._extract_and_update_memory(raw_text, cleaned, memory, prompted_slot=prompted_slot)

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

        # 6. Check missing slots & generate next relevant question (ONE AT A TIME, MAX 10 QUESTIONS)
        next_missing = self._get_next_missing_slot(memory)

        if next_missing is None:
            # All essential info collected or max questions reached -> Move to CONFIRMATION
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
                "question_count": memory.get("questions_asked_count", 0),
                "max_questions": memory.get("max_questions", 10),
                "is_confirmation": True,
                "complaint_created": False
            }
        else:
            # Increment question count
            current_q_count = memory.get("questions_asked_count", 0) + 1
            memory["questions_asked_count"] = current_q_count
            ivr_session.structured_memory = memory

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
                "question_count": current_q_count,
                "max_questions": memory.get("max_questions", 10),
                "is_confirmation": False,
                "complaint_created": False
            }

    def _extract_and_update_memory(self, raw_text: str, cleaned: str, memory: Dict[str, Any], prompted_slot: Optional[str] = None) -> None:
        """
        Extracts civic entities and updates memory across all 38 Tamil Nadu districts.
        Leverages prompted_slot context so citizen answers are never lost or asked repeatedly.
        """
        lowered = raw_text.lower().strip()

        # 1. Problem & Category Detection
        if not memory.get("problem") or prompted_slot == "problem":
            cat, dept, cat_conf = classify_complaint(cleaned)
            if cat != "Other" or any(w in lowered for w in ["water", "thanni", "power", "current", "road", "garbage", "drainage", "light", "குடிநீர்", "மின்சாரம்", "குப்பை", "சாலை", "சாக்கடை", "விளக்கு"]) or prompted_slot == "problem" or not memory.get("problem"):
                if not memory.get("problem") or prompted_slot == "problem":
                    memory["problem"] = raw_text.strip()
                    memory["category"] = cat if cat != "Other" else (memory.get("category") or "Water Supply")
                    memory["department"] = CATEGORY_TO_DEPARTMENT.get(memory["category"], dept)

        # 2. Location & Coordinates Detection (across 38 TN Districts)
        loc_name, lat, lon, conf = extract_location(raw_text)
        if loc_name and loc_name != "Tamil Nadu":
            if not memory.get("location"):
                memory["location"] = loc_name
            elif loc_name.lower() not in memory.get("location", "").lower():
                memory["location"] = f"{loc_name}, {memory['location']}"
            if lat and lon:
                memory["latitude"] = lat
                memory["longitude"] = lon
            # Extract district name
            if "district" in loc_name.lower():
                m_dist = re.search(r'([A-Za-z\s]+)\s+District', loc_name, re.IGNORECASE)
                if m_dist:
                    memory["district"] = m_dist.group(1).strip()
            elif not memory.get("district"):
                memory["district"] = loc_name.split(",")[-1].strip()

        # Check explicit location patterns (e.g. Gandhipuram, Anna Nagar, Cross Cut Road)
        street_match = re.search(r'\b([A-Za-z0-9\s]+(?:street|road|salai|theru|cross|avenue|nagar|colony|ward|layout|bus\s*stand|village|town|circle|bypass|junction|bridge))\b', raw_text, re.IGNORECASE)
        if street_match and not memory.get("location"):
            memory["location"] = street_match.group(1).strip()

        # CONTEXTUAL FALLBACK for Location if AI specifically prompted for location
        if prompted_slot == "location" and not memory.get("location"):
            cleaned_loc = re.sub(r'^(?:in|at|near|the|enga|anga|unga|inda|indha|இந்த|அந்த|பகுதியில்|இடத்தில்|area\s*is|location\s*is)\s+', '', raw_text, flags=re.IGNORECASE).strip()
            if len(cleaned_loc) >= 2:
                memory["location"] = cleaned_loc

        # 3. Street / Road Name Detection
        street_match = re.search(r'\b([A-Za-z0-9\s]+(?:street|road|salai|theru|cross|avenue|nagar\s+main\s+road|lane|highway))\b', raw_text, re.IGNORECASE)
        if street_match and not memory.get("street_road_name"):
            cand_st = street_match.group(1).strip()
            if cand_st.lower() not in ["street", "road", "theru", "salai"] or prompted_slot == "street_road_name":
                memory["street_road_name"] = cand_st
        if prompted_slot == "street_road_name" and not memory.get("street_road_name"):
            memory["street_road_name"] = raw_text.strip()

        # 4. Specific Landmark Detection (e.g. near Bus Stand, opposite Temple, near GH Hospital)
        landmark_match = re.search(r'(?:near|opposite|behind|next to|beside|அருகே|அருகில்|பக்கத்தில்|எதிரில்|கிட்ட)\s+([A-Za-z0-9\u0B80-\u0BFF\s]{3,35})', raw_text, re.IGNORECASE)
        if landmark_match and not memory.get("landmark"):
            cand_landmark = landmark_match.group(1).strip()
            if len(cand_landmark) >= 3 and cand_landmark.lower() not in ["area", "street", "road", "problem", "thanni"]:
                memory["landmark"] = cand_landmark
        elif prompted_slot == "landmark" and not memory.get("landmark"):
            memory["landmark"] = raw_text.strip()

        # 5. Exact Location / Door Number / Pole Number Detection
        exact_match = re.search(r'(?:door\s*(?:no|number)?|d\.no|pole\s*(?:no|number)?|pillar\s*(?:no|number)?|கதவு\s*எண்|மின்\s*கம்பம்|கம்பம்|junction)\s*[:#\-]?\s*([A-Za-z0-9\/\-]+)', raw_text, re.IGNORECASE)
        if exact_match and not memory.get("exact_location"):
            memory["exact_location"] = exact_match.group(0).strip()
        elif prompted_slot == "exact_location" and not memory.get("exact_location"):
            memory["exact_location"] = raw_text.strip()

        # 6. Duration Detection (e.g. "two days", "3 days", "since yesterday", "today morning", "rendu naal", "nethu lendhu")
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
                break

        # CONTEXTUAL FALLBACK for Duration if AI specifically prompted for duration
        if prompted_slot == "duration" and not memory.get("duration"):
            memory["duration"] = raw_text.strip()

        # 7. Frequency Detection (e.g. first time, daily recurring, frequent)
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

        # 8. Scope / Affected Area (e.g. "whole area", "entire street", "my house only", "full-ah", "aama", "yes")
        area_wide_indicators = [
            "full-ah", "fulla", "entire street", "whole street", "area full", "street full", "எல்லா வீடுகளும்", "முழுவதும்", "முழு தெரு",
            "ellarukum", "all houses", "colony full", "whole area", "entire area", "full street"
        ]
        individual_indicators = [
            "only my house", "veedu mattum", "single house", "எங்கள் வீடு மட்டும்", "enga veedu mattum",
            "en veedu", "my house", "only house", "individual"
        ]
        if any(w in lowered for w in area_wide_indicators):
            memory["affected_scope"] = "Entire Locality / Street"
        elif any(w in lowered for w in individual_indicators):
            memory["affected_scope"] = "Single Building / House"
        elif prompted_slot == "affected_scope":
            # If citizen replies affirmatively or generally to the scope question
            if any(w in lowered for w in ["aama", "aamam", "ama", "aam", "yes", "seri", "sari", "ok", "okay", "correct", "right", "ஆமாம்", "சரி", "ஆம்", "sure", "kandippa"]):
                memory["affected_scope"] = "Entire Locality / Street"
            elif any(w in lowered for w in ["illa", "illai", "no", "vendaam", "இல்லை"]):
                memory["affected_scope"] = "Single Building / House"
            elif not memory.get("affected_scope"):
                memory["affected_scope"] = raw_text.strip()

        # 9. Severity & Safety Hazards
        hazard_keywords = ["danger", "hazard", "sparking", "live wire", "open wire", "pit", "hole", "fire", "smoke", "accident", "emergency", "flood", "stagnant", "smell", "mosquito", "கசிவு", "ஆபத்து", "விபத்து", "தீ", "துர்நாற்றம்", "கொசு"]
        if any(w in lowered for w in hazard_keywords):
            if not memory.get("severity"):
                memory["severity"] = "High Public Safety Concern"
                memory["priority"] = "HIGH"
        elif prompted_slot == "severity" and not memory.get("severity"):
            if any(w in lowered for w in ["aama", "aamam", "yes", "danger", "ஆமாம்", "aapathu"]):
                memory["severity"] = "High Public Safety Concern"
                memory["priority"] = "HIGH"
            else:
                memory["severity"] = raw_text.strip()

        # 10. Impact on Essential Services / Public Hazard
        if prompted_slot == "impact" and not memory.get("impact"):
            memory["impact"] = raw_text.strip()

        # 11. Previous Complaint / Prior Reporting Status
        if prompted_slot == "previous_complaint" and not memory.get("previous_complaint"):
            memory["previous_complaint"] = raw_text.strip()

        # 12. Citizen Name / Identity & Phone
        phone_match = re.search(r'\b[6-9]\d{9}\b', raw_text)
        if phone_match and not memory.get("citizen_phone"):
            memory["citizen_phone"] = phone_match.group(0)

        name_match = re.search(r'(?:name\s*is|i\s*am|my\s*name\s*is|பெயர்|naan|peyar|en\s*peru)\s*([A-Za-z\u0B80-\u0BFF\s]{2,25})', raw_text, re.IGNORECASE)
        if name_match and not memory.get("citizen_name"):
            cand = name_match.group(1).strip()
            if cand.lower() not in ["seri", "ok", "problem", "thanni", "water", "anna", "tamil", "english", "no", "yes", "illa"]:
                memory["citizen_name"] = cand.title() if cand.isascii() else cand
        elif prompted_slot == "citizen_name" and not memory.get("citizen_name"):
            memory["citizen_name"] = raw_text.strip()

        # Priority Assessment
        if memory.get("problem"):
            prio, _ = assess_priority(memory["problem"], memory.get("category", "General"))
            if memory.get("severity") == "High Public Safety Concern":
                memory["priority"] = "HIGH"
            else:
                memory["priority"] = prio.value if hasattr(prio, 'value') else str(prio)

    def _get_next_missing_slot(self, memory: Dict[str, Any]) -> Optional[str]:
        """
        Determines the next missing information slot to prompt.
        Ensures AI asks ONE question at a time and never asks for already collected information.
        Maintains conversation intake with a minimum of 6 questions before confirmation, up to maximum 10.
        """
        questions_count = memory.get("questions_asked_count", 0)
        max_q = memory.get("max_questions", 10)
        if questions_count >= max_q:
            return None

        # Priority slot checklist for complete grievance intake:
        # 1. Problem (if not stated in first turn)
        if not memory.get("problem"):
            return "problem"
        # 2. Location (District / Area)
        if not memory.get("location"):
            return "location"
        # 3. Duration (e.g. Since when? Rendu naala?)
        if not memory.get("duration"):
            return "duration"
        # 4. Exact Street / Road Name
        if not memory.get("street_road_name"):
            return "street_road_name"
        # 5. Affected Scope (Full street or single house)
        if not memory.get("affected_scope"):
            return "affected_scope"
        # 6. Severity / Outage Level (Complete or partial / safety risk)
        if not memory.get("severity"):
            return "severity"
        # 7. Impact (Drinking water / traffic / darkness / health impact)
        if not memory.get("impact"):
            return "impact"
        # 8. Previous Complaint Status (Already reported or first time)
        if not memory.get("previous_complaint"):
            return "previous_complaint"
        # 9. Landmark (Near bus stand, temple, school to help officer locate)
        if not memory.get("landmark"):
            return "landmark"

        # When at least 6 questions have been asked and all core slots are collected, proceed to confirmation
        if questions_count >= 6:
            return None

        # 10. Exact Spot / Door / Pole number (if more questions needed)
        if not memory.get("exact_location"):
            return "exact_location"
        # 11. Citizen Name / Contact
        if not memory.get("citizen_name"):
            return "citizen_name"

        return None

    def _generate_slot_question(self, slot: str, memory: Dict[str, Any], lang: str) -> Tuple[str, str]:
        """
        Generates context-aware, category-specific follow-up questions in the appropriate language (Tamil, Tanglish, English).
        """
        cat = memory.get("category", "General")
        loc = memory.get("location") or "your area"
        street = memory.get("street_road_name") or loc

        if slot == "problem":
            if lang == "Tamil":
                text = "வணக்கம். உங்களுக்கு ஏற்பட்டுள்ள பொதுப் பிரச்சினை என்ன என்று கூற முடியுமா?"
                spoken = "வணக்கம். உங்களுக்கு என்ன பிரச்சினை உள்ளது என்று கூறவும்."
            elif lang == "Tanglish":
                text = "Vanakkam! Ungalukku enna civic problem irukku nu describe pannunga."
                spoken = "Ungaloda problem enna nu sollunga."
            else:
                text = "Welcome to VoxentraAI Grievance Helpline. Could you please describe the civic problem you are facing?"
                spoken = "Please describe the problem you would like to report."
            return text, spoken

        if slot == "location":
            if lang == "Tamil":
                text = "சரி. இந்த பிரச்சினை தமிழ்நாட்டில் எந்த மாவட்டம், தாலுகா அல்லது குறிப்பிட்ட பகுதியில் உள்ளது?"
                spoken = "இந்த பிரச்சினை எந்த மாவட்டம் அல்லது பகுதியில் உள்ளது?"
            elif lang == "Tanglish":
                text = f"Okay, indha {cat} problem Tamil Nadu-la endha district, area or street-la irukku?"
                spoken = f"Indha problem endha area-la irukku?"
            else:
                text = f"In which District, Taluk, or Locality in Tamil Nadu is this {cat} issue located?"
                spoken = "In which District or area is this problem located?"
            return text, spoken

        if slot == "duration":
            if "water" in cat.lower():
                if lang == "Tamil":
                    text = f"⏱️ **{loc}** பகுதியில் குடிநீர் விநியோகம் எப்போது முதல் தடைப்பட்டுள்ளது? (எ.கா: இரண்டு நாட்களாக, இன்று காலை முதல்)"
                    spoken = "குடிநீர் விநியோகம் எப்போது முதல் தடைப்பட்டுள்ளது?"
                elif lang == "Tanglish":
                    text = f"⏱️ Okay, **{loc}**-la water supply eppo lendhu varala? (e.g. 2 days-ah, today morning-ah)"
                    spoken = "Idhu eppo lendhu varala?"
                else:
                    text = f"⏱️ Since when has the water supply been disrupted in **{loc}**? (e.g. 2 days, since morning)"
                    spoken = "Since when has this water problem been occurring?"
            elif "power" in cat.lower() or "electric" in cat.lower():
                if lang == "Tamil":
                    text = f"⏱️ **{loc}** பகுதியில் மின்சாரம் எப்போது முதல் தடைப்பட்டுள்ளது?"
                    spoken = "மின்சாரம் எப்போது முதல் தடைப்பட்டுள்ளது?"
                elif lang == "Tanglish":
                    text = f"⏱️ Okay, **{loc}**-la power eppo lendhu cut aagi irukku?"
                    spoken = "Power eppo lendhu cut aagi irukku?"
                else:
                    text = f"⏱️ Since when has the power outage occurred in **{loc}**?"
                    spoken = "Since when has this power cut been occurring?"
            else:
                if lang == "Tamil":
                    text = f"⏱️ **{loc}** பகுதியில் இந்தப் பிரச்சினை எப்போது முதல் நீடிக்கிறது? (எ.கா: இரண்டு நாட்களாக, இன்று காலை முதல்)"
                    spoken = "இந்தப் பிரச்சினை எப்போது முதல் நீடிக்கிறது?"
                elif lang == "Tanglish":
                    text = f"⏱️ Okay, **{loc}**-la indha problem eppo lendhu irukku? (e.g. 2 days-ah, today morning-ah)"
                    spoken = "Indha problem eppo lendhu irukku?"
                else:
                    text = f"⏱️ Since when has this issue been occurring in **{loc}**?"
                    spoken = "Since when has this problem been occurring?"
            return text, spoken

        if slot == "street_road_name":
            if lang == "Tamil":
                text = f"📍 **{loc}** பகுதியில் சரியான தெரு அல்லது சாலையின் பெயர் என்ன?"
                spoken = f"{loc} பகுதியில் எந்த தெருவில் இந்த பிரச்சினை?"
            elif lang == "Tanglish":
                text = f"📍 Seri. **{loc}**-la exact-ah endha street-la indha problem?"
                spoken = f"{loc}-la exact-ah endha street-la indha problem?"
            else:
                text = f"📍 Which exact street or road in **{loc}** is affected?"
                spoken = f"In {loc}, on which street or road is this problem located?"
            return text, spoken

        if slot == "affected_scope":
            if lang == "Tamil":
                text = f"🏘️ இந்தப் பிரச்சினை உங்கள் வீட்டிற்கு மட்டுமா, அல்லது **{street}** தெரு முழுவதும் பாதிக்கப்பட்டுள்ளதா?"
                spoken = "உங்கள் வீட்டிற்கு மட்டுமா அல்லது தெரு முழுவதும் பாதிக்கப்பட்டுள்ளதா?"
            elif lang == "Tanglish":
                text = f"🏘️ Okay. Indha problem unga veetukku mattuma, illa full street-kuma?"
                spoken = "Indha problem unga veetukku mattuma, illa full street-kuma?"
            else:
                text = f"🏘️ Is this problem affecting only your house/building, or the entire street of **{street}**?"
                spoken = "Is this affecting only your house or the entire street?"
            return text, spoken

        if slot == "severity":
            if "water" in cat.lower():
                if lang == "Tamil":
                    text = f"💧 தண்ணீர் விநியோகம் முற்றிலும் நின்றுவிட்டதா, அல்லது குறைந்த அளவில் வருகிறதா?"
                    spoken = "தண்ணீர் முற்றிலும் வரவில்லையா, அல்லது குறைவாக வருகிறதா?"
                elif lang == "Tanglish":
                    text = f"💧 Water completely varalaya, illa konjam konjama varudha?"
                    spoken = "Water completely varalaya, illa konjam konjama varudha?"
                else:
                    text = f"💧 Is the water supply completely stopped, or is it flowing with low pressure?"
                    spoken = "Is the water supply completely stopped or coming with low pressure?"
            elif "power" in cat.lower() or "electric" in cat.lower():
                if lang == "Tamil":
                    text = f"⚡ மின் கம்பம் அல்லது டிரான்ஸ்பார்மரில் தீப்பொறி/கசிவு போன்ற ஆபத்துகள் ஏதேனும் உள்ளதா?"
                    spoken = "மின் கம்பம் அல்லது டிரான்ஸ்பார்மரில் தீப்பொறி ஆபத்து ஏதேனும் உள்ளதா?"
                elif lang == "Tanglish":
                    text = f"⚡ Power completely off-aa, illa electric pole / transformer-la sparking / live wire danger edhavadhu irukka?"
                    spoken = "Transformer or pole-la sparking danger edhavadhu irukka?"
                else:
                    text = f"⚡ Is there any sparking, live wire hazard, or transformer issue involved?"
                    spoken = "Is there any sparking or live wire hazard involved?"
            elif "road" in cat.lower():
                if lang == "Tamil":
                    text = f"🛣️ சாலையில் பெரிய பள்ளங்கள் உள்ளதா அல்லது போக்குவரத்து பாதிக்கப்பட்டுள்ளதா?"
                    spoken = "சாலையில் பெரிய பள்ளங்கள் உள்ளதா அல்லது போக்குவரத்து பாதிக்கப்பட்டுள்ளதா?"
                elif lang == "Tanglish":
                    text = f"🛣️ Road-la periya gundu kuliyum irukka, illa traffic block aagudha?"
                    spoken = "Road-la periya gundu kuliyum irukka, illa traffic block aagudha?"
                else:
                    text = f"🛣️ Is there a severe pothole causing major vehicle damage or traffic blockage?"
                    spoken = "Is there a severe pothole or traffic blockage?"
            else:
                if lang == "Tamil":
                    text = f"🚨 இந்தப் பிரச்சினை தீவிரமாக உள்ளதா அல்லது பொதுமக்களுக்கு உடனடி ஆபத்து உள்ளதா?"
                    spoken = "உடனடி ஆபத்து அல்லது அவசர நிலை ஏதேனும் உள்ளதா?"
                elif lang == "Tanglish":
                    text = f"🚨 Indha problem completely severe-ah irukka, illa urgent danger edhavadhu irukka?"
                    spoken = "Indha problem-la urgent danger edhavadhu irukka?"
                else:
                    text = f"🚨 Is this issue completely severe or posing any immediate public danger?"
                    spoken = "Is there any severe danger involved?"
            return text, spoken

        if slot == "impact":
            if "water" in cat.lower():
                if lang == "Tamil":
                    text = f"🚰 இதனால் அன்றாட குடிநீர் பயன்பாடு மற்றும் சமையல் தேவைகள் பாதிக்கப்பட்டுள்ளதா?"
                    spoken = "இதனால் குடிநீர் பயன்பாடும் பாதிக்கப்பட்டுள்ளதா?"
                elif lang == "Tanglish":
                    text = f"🚰 Seri. Indha problem nala drinking water-kum daily use-kum impact irukka?"
                    spoken = "Indha problem nala drinking water-kum impact irukka?"
                else:
                    text = f"🚰 Is essential drinking water and daily domestic usage severely impacted?"
                    spoken = "Is drinking water supply also affected?"
            elif "road" in cat.lower():
                if lang == "Tamil":
                    text = f"🚗 இதனால் வாகன விபத்துகள் ஏற்படும் அபாயம் அல்லது பாதசாரிகளுக்கு ஆபத்து உள்ளதா?"
                    spoken = "இதனால் விபத்து அபாயம் ஏதேனும் உள்ளதா?"
                elif lang == "Tanglish":
                    text = f"🚗 Indha road damage-naala vehicle accident aagura risk or traffic issue irukka?"
                    spoken = "Vehicle accident aagura risk irukka?"
                else:
                    text = f"🚗 Is there a high risk of vehicle accidents or pedestrian safety hazards?"
                    spoken = "Is there a risk of accidents on this road?"
            elif "light" in cat.lower():
                if lang == "Tamil":
                    text = f"🌑 இரவு நேரத்தில் பகுதி இருட்டாக இருப்பதால் பெண்களுக்கு மற்றும் பொதுமக்களுக்கு பாதுகாப்பு அச்சுறுத்தல் உள்ளதா?"
                    spoken = "இரவு நேரத்தில் பாதுகாப்பு அச்சுறுத்தல் உள்ளதா?"
                elif lang == "Tanglish":
                    text = f"🌑 Night time-la full இருட்டு irukkuradhaala public safety or theft concern irukka?"
                    spoken = "Night time-la public safety concern irukka?"
                else:
                    text = f"🌑 Is there a serious public safety concern at night due to the darkness?"
                    spoken = "Is there a public safety concern at night?"
            else:
                if lang == "Tamil":
                    text = f"⚠️ இந்தப் பிரச்சினையால் பொதுமக்கள் இயல்பு வாழ்க்கை அல்லது சுகாதாரம் எவ்வாறு பாதிக்கப்பட்டுள்ளது?"
                    spoken = "இதனால் பொதுமக்கள் எவ்வாறு பாதிக்கப்பட்டுள்ளனர்?"
                elif lang == "Tanglish":
                    text = f"⚠️ Indha problem-naala public health or daily life evalo affect aagi irukku?"
                    spoken = "Public daily life evalo affect aagi irukku?"
                else:
                    text = f"⚠️ How significantly is daily public life or health impacted by this?"
                    spoken = "How is public life impacted by this issue?"
            return text, spoken

        if slot == "previous_complaint":
            if lang == "Tamil":
                text = f"📋 இந்தப் பிரச்சினை குறித்து இதற்கு முன் சம்பந்தப்பட்ட துறை அலுவலகத்திலோ அல்லது உதவி எண்ணிலோ புகார் அளித்திருக்கிறீர்களா?"
                spoken = "இந்தப் பிரச்சினை பற்றி ஏற்கனவே புகார் செய்துள்ளீர்களா?"
            elif lang == "Tanglish":
                text = f"📋 Indha problem pathi already municipality or department-la complaint pannirukeengala?"
                spoken = "Indha problem pathi already complaint pannirukeengala?"
            else:
                text = f"📋 Have you already reported or registered a complaint for this issue previously?"
                spoken = "Have you already complained about this issue before?"
            return text, spoken

        if slot == "landmark":
            if lang == "Tamil":
                text = f"🏛️ அரசு அதிகாரிகள் அந்த இடத்தை எளிதாகக் கண்டறிய **{street}** அருகில் உள்ள முக்கிய அடையாளம் (Landmark, பேருந்து நிறுத்தம், கோவில், பள்ளி) ஏதேனும் உள்ளதா?"
                spoken = "அதிகாரிகள் கண்டறிய அருகிலுள்ள லேண்ட்மார்க் அடையாளம் என்ன?"
            elif lang == "Tanglish":
                text = f"🏛️ Officer location-a easy-ah identify panna **{street}** pakkathula irukkura landmark (e.g. Bus stand, Temple, School, ATM) edhavathu sollunga."
                spoken = "Officer identify panna pakkathula irukkura landmark edhavathu sollunga."
            else:
                text = f"🏛️ Could you please mention a nearby landmark (e.g. Bus stand, Temple, School, Bank) near **{street}** to help the officer locate the exact spot?"
                spoken = "Please mention a nearby landmark so the officer can locate the spot."
            return text, spoken

        if slot == "exact_location":
            if lang == "Tamil":
                text = f"🎯 அந்த பகுதியில் உள்ள குறிப்பிட்ட கதவு எண், மின் கம்ப எண் அல்லது சரியான இடம் எது?"
                spoken = "குறிப்பிட்ட கதவு எண் அல்லது மின் கம்ப எண் என்ன?"
            elif lang == "Tanglish":
                text = f"🎯 **{street}**-la exact spot details, electric pole number or door number sollunga."
                spoken = "Specific spot details or door number sollunga."
            else:
                text = f"🎯 What is the exact spot detail, electric pole number, or door number on **{street}**?"
                spoken = "What is the exact spot detail or door number?"
            return text, spoken

        if slot == "frequency":
            if lang == "Tamil":
                text = f"🔄 இந்தப் பிரச்சினை எத்தனை முறை அல்லது எவ்வளவு அடிக்கடி நிகழ்கிறது? (எ.கா: முதல் முறையாக, தினமும் தொடர்ந்து)"
                spoken = "இந்தப் பிரச்சினை எவ்வளவு அடிக்கடி நிகழ்கிறது?"
            elif lang == "Tanglish":
                text = f"🔄 Indha problem evalo frequency-la varudhu? (e.g. First time, Daily recurring, Adikkadi nadakudhu)"
                spoken = "Indha problem evalo adikkadi nadakudhu?"
            else:
                text = f"🔄 How often does this problem occur? (e.g. Happening for the first time, recurring daily, frequent)"
                spoken = "How often has this problem occurred?"
            return text, spoken

        if slot == "citizen_name":
            if lang == "Tamil":
                text = f"👤 நன்றி. உங்கள் புகார் பதிவிற்காகவும், எஸ்.எம்.எஸ் (SMS) தகவலுக்காகவும் உங்கள் பெயர் மற்றும் தொடர்பு எண்ணை கூற முடியுமா?"
                spoken = "புகார் பதிவிற்காக உங்கள் பெயர் மற்றும் தொடர்பு எண்ணைக் கூறவும்."
            elif lang == "Tanglish":
                text = f"👤 Romba nandri. Unga complaint registration and SMS update-kaaga unga name and phone number sollunga?"
                spoken = "Unga name and phone number enna nu sollunga."
            else:
                text = f"👤 Thank you. May I please have your name and contact phone number for official registration and SMS status updates?"
                spoken = "Please provide your name and contact phone number."
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
        landmark = memory.get("landmark", "Not Specified")
        district = memory.get("district", "Tamil Nadu")
        duration = memory.get("duration", "Active")
        scope = memory.get("affected_scope", "Affected Locality")
        severity = memory.get("severity", "Standard Civic Priority")
        name = memory.get("citizen_name", "Citizen")

        if lang == "Tamil":
            text = (
                f"உங்கள் புகார் விவரங்களை முழுமையாக உறுதிப்படுத்துகிறேன்:\n\n"
                f"👤 பெயர்: {name}\n"
                f"⚠️ பிரச்சினை: {problem}\n"
                f"🏛️ துறை: {dept}\n"
                f"📍 இடம் & மாவட்டம்: {location}\n"
                f"🏢 அடையாளம் (Landmark): {landmark}\n"
                f"⏱️ கால அளவு: {duration}\n"
                f"🏘️ பரப்பளவு: {scope}\n"
                f"🚨 அவசர நிலை: {severity}\n\n"
                f"இந்த புகாரை அதிகாரப்பூர்வமாக பதிவு செய்யலாமா?"
            )
            spoken = (
                f"உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன். "
                f"பிரச்சினை: {problem}. இடம்: {location}. "
                f"இந்த புகாரை பதிவு செய்யலாமா?"
            )
        elif lang == "Tanglish":
            text = (
                f"Unga complaint details ah confirm panren:\n\n"
                f"👤 Name: {name}\n"
                f"⚠️ Problem: {problem}\n"
                f"🏛️ Department: {dept}\n"
                f"📍 Location: {location}\n"
                f"🏢 Landmark: {landmark}\n"
                f"⏱️ Duration: {duration}\n"
                f"🏘️ Scope: {scope}\n"
                f"🚨 Severity: {severity}\n\n"
                f"Indha details correct-ah irukka? Complaint-ah register pannalaama?"
            )
            spoken = (
                f"Okay, {location}-la {duration} {problem}. "
                f"Landmark {landmark}. Indha complaint-a register pannava?"
            )
        else:
            text = (
                f"Please confirm your complete complaint summary:\n\n"
                f"👤 Reporter: {name}\n"
                f"⚠️ Issue: {problem}\n"
                f"🏛️ Department: {dept}\n"
                f"📍 Location & District: {location}\n"
                f"🏢 Landmark: {landmark}\n"
                f"⏱️ Duration: {duration}\n"
                f"🏘️ Scope: {scope}\n"
                f"🚨 Severity: {severity}\n\n"
                f"Shall I register this complaint in the state portal now?"
            )
            spoken = (
                f"Let me confirm: {problem} at {location} near {landmark} for {duration}. "
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
