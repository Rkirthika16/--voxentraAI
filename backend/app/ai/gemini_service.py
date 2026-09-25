import os
import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field
import httpx

from app.config import settings
from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text, clean_transcription
from app.ai.classification_service import classify_complaint
from app.ai.location_service import extract_location
from app.ai.priority_service import assess_priority

logger = logging.getLogger("voxentra.ai.gemini")

# Standard Department Mapping for Tamil Nadu Civic Grievances
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


class GeminiAnalysisResult(BaseModel):
    """
    Validated structured output from Gemini AI for Real-Time Conversational Voice IVR.
    Strictly validated by Pydantic.
    """
    language: str = Field(default="Tamil", description="Detected language: 'Tamil', 'Tanglish', or 'English'")
    normalized_text: str = Field(description="Normalized and spelling-corrected transcript")
    category: Optional[str] = Field(None, description="Complaint category")
    department: Optional[str] = Field(None, description="Target municipal department")
    location: Optional[str] = Field(None, description="Extracted civic locality/street in Tamil Nadu")
    landmark: Optional[str] = Field(None, description="Nearby landmark if provided")
    duration: Optional[str] = Field(None, description="Duration/timeline of the issue")
    affected_scope: Optional[str] = Field(None, description="Scope of affected area (e.g. 'Entire Locality / Street', 'Single Building / House')")
    severity: Optional[str] = Field(None, description="Severity assessment or safety hazard")
    priority: str = Field(default="MEDIUM", description="'LOW', 'MEDIUM', 'HIGH', or 'EMERGENCY'")
    intent: str = Field(default="citizen_complaint", description="Identified intent: 'citizen_complaint', 'provide_detail', 'confirmation_yes', 'confirmation_no', 'chitchat', 'unclear'")
    missing_information: List[str] = Field(default_factory=list, description="List of essential slots still needed ('duration', 'location', 'affected_scope')")
    next_question: Optional[str] = Field(None, description="Single natural next question in citizen's language")
    spoken_reply: Optional[str] = Field(None, description="Phonetic speech text for Text-to-Speech")
    ai_reply: Optional[str] = Field(None, description="Markdown/formatted text for UI chat feed")
    is_confirmation: bool = Field(default=False, description="True if sufficient info is gathered and confirmation should be prompted")
    needs_clarification: bool = Field(default=False, description="True if transcription is ambiguous or garbled")


class GeminiService:
    """
    Modular Gemini Language & Conversation Service for VoxentraAI.
    Responsibilities:
    1. Understand Whisper raw transcript
    2. Normalize and correct spelling variations (e.g. 'Gandipuram la tanni varla' -> 'Gandhipuram-la thanni varala')
    3. Detect conversation language (Tamil, Tanglish, English)
    4. Extract civic entities (Category, Location, Duration, Scope, Severity, Priority)
    5. Maintain multi-turn slot memory
    6. Determine missing information dynamically (no rigid 11-question scripts)
    7. Generate natural, single relevant next questions in the citizen's language
    8. Generate conversational summaries for final confirmation
    
    IMPORTANT: This service does NOT directly create database records.
    It returns structured, Pydantic-validated JSON.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
        self.model_name = "gemini-2.5-flash"

    def analyze_turn(
        self,
        raw_text: str,
        current_memory: Dict[str, Any],
        prompted_slot: Optional[str] = None,
        session_language: Optional[str] = "Tamil",
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> GeminiAnalysisResult:
        """
        Processes one citizen turn using Gemini (or high-accuracy deterministic fallback).
        Returns a Pydantic-validated GeminiAnalysisResult.
        """
        raw_cleaned = (raw_text or "").strip()
        if not raw_cleaned:
            return self._build_unclear_result(session_language or "Tamil")

        # 1. If Gemini API key is available, attempt Gemini structured inference
        if self.api_key:
            try:
                gemini_res = self._call_gemini_api(
                    raw_cleaned,
                    current_memory,
                    prompted_slot,
                    session_language,
                    conversation_history or []
                )
                if gemini_res:
                    return gemini_res
            except Exception as e:
                logger.warning(f"[GeminiService] Gemini API call failed or timed out: {e}. Falling back to deterministic NLP engine.")

        # 2. High-accuracy Deterministic NLP Fallback Engine
        return self._deterministic_fallback_analysis(
            raw_cleaned,
            current_memory,
            prompted_slot,
            session_language
        )

    def _call_gemini_api(
        self,
        raw_text: str,
        current_memory: Dict[str, Any],
        prompted_slot: Optional[str],
        session_language: Optional[str],
        conversation_history: List[Dict[str, str]]
    ) -> Optional[GeminiAnalysisResult]:
        """Calls Google Gemini REST API with structured JSON schema response."""
        system_prompt = (
            "You are VoxentraAI, an intelligent conversational AI helpline assistant for Tamil Nadu Municipal Administration.\n"
            "Your role is to listen to citizens, normalize speech transcription errors without changing meaning, "
            "extract civic complaint details (Category, Location, Duration, Scope), and ask ONE relevant follow-up question at a time.\n"
            "Languages supported: ONLY Tamil (தமிழ்), Tanglish (Tamil in Latin script), and English.\n"
            "Respond ONLY with valid JSON conforming to the requested schema.\n"
            "Never fabricate citizen details, locations, or coordinates. If uncertain, ask for clarification."
        )

        user_payload = {
            "citizen_raw_speech": raw_text,
            "session_language_preference": session_language or "Tamil",
            "prompted_field_in_last_turn": prompted_slot,
            "current_conversation_memory": current_memory,
            "recent_turns": conversation_history[-4:] if conversation_history else []
        }

        prompt = f"{system_prompt}\n\nCurrent Turn Context:\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
                "max_output_tokens": 1000
            }
        }

        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                candidate_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if candidate_text:
                    parsed_json = json.loads(candidate_text)
                    # Validate output using Pydantic schema
                    return GeminiAnalysisResult(**parsed_json)
        return None

    def _deterministic_fallback_analysis(
        self,
        raw_text: str,
        current_memory: Dict[str, Any],
        prompted_slot: Optional[str],
        session_language: Optional[str]
    ) -> GeminiAnalysisResult:
        """
        Comprehensive local NLP engine that strictly adheres to the requested conversational flow.
        """
        lowered = raw_text.lower().strip()
        cleaned = clean_transcription(raw_text)
        normalized = normalize_text(raw_text)

        # 1. Language Detection with Session Stickiness
        detected_lang, _ = detect_language(raw_text, current_session_lang=session_language)

        # Clone memory to avoid in-place mutation side-effects
        mem = dict(current_memory or {})

        # 2. Check for Confirmation / Decision
        positives = [
            "yes", "confirm", "confirmed", "register", "proceed", "okay", "ok", "correct", "right",
            "aama", "aamam", "ama", "amam", "aam", "seri", "sari", "pannunga", "podunga", "panlama",
            "pannidunga", "padhivu", "seiyunga", "seiyalam", "kandippa", "sure", "done", "fine", "super",
            "nandri", "thanks", "thank you", "go ahead"
        ]
        negatives = [
            "no", "cancel", "stop", "wait", "change", "edit", "wrong", "thappu", "illai", "illa",
            "vendaam", "modify", "maathanum", "maathu"
        ]

        is_affirmative = any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in positives) or any(w in lowered for w in ["ஆமாம்", "சரி", "பதிவு", "ஆம்", "உறுதி", "செய்யலாம்"])
        is_negative = any(re.search(r'\b' + re.escape(w) + r'\b', lowered) for w in negatives) or any(w in lowered for w in ["வேண்டாம்", "இல்லை", "தவறு", "மாற்ற வேண்டும்"])

        # 3. Extract Problem & Category
        if not mem.get("problem") or prompted_slot == "problem":
            cat, dept, _ = classify_complaint(cleaned)
            if cat != "Other" or any(w in lowered for w in ["water", "thanni", "power", "current", "road", "garbage", "drainage", "light", "குடிநீர்", "மின்சாரம்", "குப்பை", "சாலை", "சாக்கடை", "விளக்கு"]) or prompted_slot == "problem" or not mem.get("problem"):
                mem["problem"] = raw_text.strip()
                mem["category"] = cat if cat != "Other" else (mem.get("category") or "Water Supply")
                mem["department"] = CATEGORY_TO_DEPARTMENT.get(mem["category"], dept)

        # 4. Extract Location
        loc_name, lat, lon, _ = extract_location(raw_text)
        if loc_name and loc_name != "Tamil Nadu":
            if not mem.get("location"):
                mem["location"] = loc_name
            elif loc_name.lower() not in mem.get("location", "").lower():
                mem["location"] = f"{loc_name}, {mem['location']}"
            if lat and lon:
                mem["latitude"] = lat
                mem["longitude"] = lon

        street_match = re.search(r'\b([A-Za-z0-9\s]+(?:street|road|salai|theru|cross|avenue|nagar|colony|ward|layout|bus\s*stand|village|town|junction|bridge))\b', raw_text, re.IGNORECASE)
        if street_match and not mem.get("location"):
            mem["location"] = street_match.group(1).strip()

        if prompted_slot == "location" and not mem.get("location"):
            cleaned_loc = re.sub(r'^(?:in|at|near|the|enga|anga|unga|inda|indha|இந்த|அந்த|பகுதியில்|இடத்தில்|area\s*is|location\s*is)\s+', '', raw_text, flags=re.IGNORECASE).strip()
            if len(cleaned_loc) >= 2:
                mem["location"] = cleaned_loc

        # 5. Extract Duration
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
            if m and not mem.get("duration"):
                mem["duration"] = m.group(0).strip()
                break

        if prompted_slot == "duration" and not mem.get("duration"):
            mem["duration"] = raw_text.strip()

        # 6. Extract Affected Scope
        area_wide_indicators = [
            "full", "full-ah", "fulla", "entire", "whole", "area full", "street full", "எல்லா", "முழுவதும்", "முழு தெரு",
            "ellarukum", "all houses", "ellam", "all", "colony full", "area", "street", "perusa"
        ]
        individual_indicators = [
            "only my house", "veedu mattum", "single house", "எங்கள் வீடு மட்டும்", "enga veedu mattum",
            "en veedu", "my house", "only house", "individual"
        ]
        if any(w in lowered for w in area_wide_indicators):
            mem["affected_scope"] = "Entire Locality / Street"
        elif any(w in lowered for w in individual_indicators):
            mem["affected_scope"] = "Single Building / House"
        elif prompted_slot == "affected_scope":
            if is_affirmative:
                mem["affected_scope"] = "Entire Locality / Street"
            elif is_negative:
                mem["affected_scope"] = "Single Building / House"
            elif not mem.get("affected_scope"):
                mem["affected_scope"] = raw_text.strip()

        # 7. Priority Assessment
        if mem.get("problem"):
            prio, _ = assess_priority(mem["problem"], mem.get("category", "General"))
            mem["priority"] = prio.value if hasattr(prio, 'value') else str(prio)

        # 8. Determine Missing Information & Next Step
        missing: List[str] = []
        if not mem.get("problem"):
            missing.append("problem")
        if not mem.get("location"):
            missing.append("location")
        if not mem.get("duration"):
            missing.append("duration")
        if not mem.get("affected_scope"):
            missing.append("affected_scope")

        # 9. Formulate Contextual Response & Next Question
        category = mem.get("category") or "General"
        location = mem.get("location") or "your area"
        problem = mem.get("problem") or "the civic issue"
        dept = mem.get("department") or CATEGORY_TO_DEPARTMENT.get(category, "Municipal Administration")
        duration = mem.get("duration") or "recently"
        scope = mem.get("affected_scope") or "Entire Locality"

        if len(missing) == 0:
            # All slots ready -> Formulate confirmation summary
            if detected_lang == "Tamil":
                ai_reply = (
                    f"உங்கள் புகார் விவரங்களை முழுமையாக உறுதிப்படுத்துகிறேன்:\n\n"
                    f"⚠️ பிரச்சினை: {problem}\n"
                    f"🏛️ துறை: {dept}\n"
                    f"📍 இடம்: {location}\n"
                    f"⏱️ கால அளவு: {duration}\n"
                    f"🏘️ பரப்பளவு: {scope}\n\n"
                    f"இந்த புகாரை அதிகாரப்பூர்வமாக பதிவு செய்யலாமா?"
                )
                spoken = f"உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன். {location}-ல் {duration} {problem}. இந்த புகாரை {dept} துறைக்கு பதிவு செய்யலாமா?"
                next_q = "இந்த புகாரை பதிவு செய்யலாமா?"
            elif detected_lang == "Tanglish":
                ai_reply = (
                    f"Unga complaint details ah confirm panren:\n\n"
                    f"⚠️ Problem: {problem}\n"
                    f"🏛️ Department: {dept}\n"
                    f"📍 Location: {location}\n"
                    f"⏱️ Duration: {duration}\n"
                    f"🏘️ Scope: {scope}\n\n"
                    f"Indha details correct-ah? Complaint-ah register pannalaama?"
                )
                spoken = f"Okay, {location}-la {duration} {problem}. {scope} affected. Indha complaint-a register pannava?"
                next_q = "Indha complaint-a register pannalaama?"
            else:
                ai_reply = (
                    f"Please confirm your complete complaint summary:\n\n"
                    f"⚠️ Issue: {problem}\n"
                    f"🏛️ Department: {dept}\n"
                    f"📍 Location: {location}\n"
                    f"⏱️ Duration: {duration}\n"
                    f"🏘️ Scope: {scope}\n\n"
                    f"Shall I register this complaint in the state portal now?"
                )
                spoken = f"Let me confirm: {problem} at {location} for {duration}. Shall I register this complaint now?"
                next_q = "Shall I register this complaint now?"

            return GeminiAnalysisResult(
                language=detected_lang,
                normalized_text=normalized,
                category=category,
                department=dept,
                location=mem.get("location"),
                duration=mem.get("duration"),
                affected_scope=mem.get("affected_scope"),
                priority=mem.get("priority", "MEDIUM"),
                intent="citizen_complaint",
                missing_information=[],
                next_question=next_q,
                spoken_reply=spoken,
                ai_reply=ai_reply,
                is_confirmation=True,
                needs_clarification=False
            )

        # Next Missing Slot Question
        next_slot = missing[0]
        if next_slot == "problem":
            if detected_lang == "Tamil":
                ai_reply = "வணக்கம். உங்களுக்கு ஏற்பட்டுள்ள பொதுப் பிரச்சினை என்ன என்று கூற முடியுமா?"
                spoken = "வணக்கம். உங்களுக்கு என்ன பிரச்சினை உள்ளது என்று கூறவும்."
            elif detected_lang == "Tanglish":
                ai_reply = "Vanakkam! Ungalukku enna civic problem irukku nu describe pannunga."
                spoken = "Ungaloda problem enna nu sollunga."
            else:
                ai_reply = "Welcome to VoxentraAI Grievance Helpline. Could you please describe the civic problem you are facing?"
                spoken = "Please describe the problem you would like to report."
        elif next_slot == "location":
            if detected_lang == "Tamil":
                ai_reply = f"சரி, இந்தப் பிரச்சினை தமிழ்நாட்டில் எந்த மாவட்டம் அல்லது பகுதியில் உள்ளது?"
                spoken = "இந்தப் பிரச்சினை எந்த மாவட்டம் அல்லது பகுதியில் உள்ளது?"
            elif detected_lang == "Tanglish":
                ai_reply = f"Okay, indha {category} problem endha area or street-la irukku?"
                spoken = f"Indha problem endha area-la irukku?"
            else:
                ai_reply = f"In which District, Area, or Street is this {category} issue located?"
                spoken = f"In which area is this problem located?"
        elif next_slot == "duration":
            if detected_lang == "Tamil":
                ai_reply = f"சரி, **{location}** பகுதியில் இந்தப் பிரச்சினை எப்போது முதல் நீடிக்கிறது? (எ.கா: இரண்டு நாட்களாக, இன்று காலை முதல்)"
                spoken = f"இந்தப் பிரச்சினை எப்போது முதல் நீடிக்கிறது?"
            elif detected_lang == "Tanglish":
                ai_reply = f"Okay, indha problem **{location}**-la eppo lendhu irukku? (e.g. Two days-ah, today morning lendha?)"
                spoken = f"Indha problem eppo lendhu irukku?"
            else:
                ai_reply = f"Since when has this issue been happening in **{location}**? (e.g. 2 days, since today morning)"
                spoken = f"Since when has this issue been happening in {location}?"
        elif next_slot == "affected_scope":
            if detected_lang == "Tamil":
                ai_reply = f"இந்தப் பிரச்சினை **{location}** பகுதியில் உங்கள் தெரு முழுவதும் உள்ளதா அல்லது குறிப்பிட்ட சில வீடுகளுக்கு மட்டுமா?"
                spoken = "இந்தப் பிரச்சினை பகுதி முழுவதும் உள்ளதா அல்லது உங்கள் வீட்டில் மட்டுமா?"
            elif detected_lang == "Tanglish":
                ai_reply = f"Indha problem **{location}**-la unga street / area full-ah irukka, illa unga veetla mattuma?"
                spoken = "Area full-ah problem-aa illa unga veetla mattuma?"
            else:
                ai_reply = f"Does this issue affect the entire street / locality in **{location}**, or only your individual house?"
                spoken = "Is the entire area affected or only your house?"
        else:
            ai_reply = "Could you please provide more details?"
            spoken = "Please provide more details."

        return GeminiAnalysisResult(
            language=detected_lang,
            normalized_text=normalized,
            category=mem.get("category"),
            department=mem.get("department"),
            location=mem.get("location"),
            duration=mem.get("duration"),
            affected_scope=mem.get("affected_scope"),
            priority=mem.get("priority", "MEDIUM"),
            intent="citizen_complaint",
            missing_information=missing,
            next_question=spoken,
            spoken_reply=spoken,
            ai_reply=ai_reply,
            is_confirmation=False,
            needs_clarification=False
        )

    def _build_unclear_result(self, lang: str) -> GeminiAnalysisResult:
        if lang == "Tamil":
            text = "மன்னிக்கவும், உங்கள் குரல் தெளிவாக கேட்கவில்லை. தயவுசெய்து மீண்டும் ஒருமுறை கூற முடியுமா?"
            spoken = "மன்னிக்கவும், மீண்டும் ஒருமுறை கூற முடியுமா?"
        elif lang == "Tanglish":
            text = "Sorry, unga voice clear-ah kekkala. Please once again sollunga."
            spoken = "Sorry, unga voice clear-ah kekkala. Please once again sollunga."
        else:
            text = "Sorry, I couldn't understand that clearly. Could you please say it again?"
            spoken = "Sorry, I couldn't understand that clearly. Could you please say it again?"

        return GeminiAnalysisResult(
            language=lang,
            normalized_text="",
            intent="unclear",
            missing_information=["problem"],
            next_question=spoken,
            spoken_reply=spoken,
            ai_reply=text,
            is_confirmation=False,
            needs_clarification=True
        )


gemini_service = GeminiService()
