import re
import uuid
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session

from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text
from app.ai.classification_service import classify_complaint
from app.ai.priority_service import assess_priority
from app.ai.complaint_collector import (
    complaint_collector,
    FIELD_KEYS,
    FIELD_METADATA
)
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus
from app.models.user import User
from app.schemas.assistant import (
    AssistantResponse,
    ComplaintDraft,
    ComplaintCollectionStateSchema,
    ActionSuggestion,
    SuggestionsResponse
)

# Tamil Nadu Civic FAQs and Helpline Data
EMERGENCY_HELPLINES = [
    {"service": "All-in-One Emergency", "number": "112", "desc": "National Emergency Support System (Police/Fire/Medical)"},
    {"service": "TN Civic Grievance Helpline", "number": "1913", "desc": "Municipal Corporation Toll-Free Grievance Portal"},
    {"service": "TNEB Power & Electricity", "number": "1912", "desc": "Tamil Nadu Electricity Board Outage & Fuse Complaint"},
    {"service": "Medical Emergency / Ambulance", "number": "108", "desc": "Emergency Ambulance Medical Assistance"},
    {"service": "Police Helpline", "number": "100", "desc": "Tamil Nadu State Police Immediate Assistance"},
    {"service": "Fire & Rescue Services", "number": "101", "desc": "Tamil Nadu Fire and Disaster Management"}
]

CIVIC_FAQS = {
    "water_supply": {
        "keywords": ["water timing", "water supply schedule", "drinking water time", "kudineer timing", "thanni varum neram", "தண்ணீர் நேரம்"],
        "tamil": "பொதுவாக குடிநீர் விநியோகம் காலை 6:00 மணி முதல் 9:00 மணி வரை மற்றும் மாலை 5:00 மணி முதல் 7:00 மணி வரை நடைபெறும். ஏதேனும் குழாய் உடைப்பு அல்லது விநியோக தாமதம் இருந்தால், உடனடியாக இங்கு புகார் பதிவு செய்யலாம்.",
        "english": "Municipal drinking water supply is typically provided between 6:00 AM - 9:00 AM and 5:00 PM - 7:00 PM on designated supply days. If you are experiencing low pressure or broken pipelines, you can file a complaint directly here."
    },
    "garbage_collection": {
        "keywords": ["garbage time", "waste collection", "kuppai vandi", "dustbin collection", "door to door", "குப்பை வண்டி"],
        "tamil": "தூய்மைப் பணியாளர்கள் தினமும் காலை 6:30 மணி முதல் 11:00 மணி வரை வீடு வீடாக வந்து மக்கும் மற்றும் மக்காத குப்பைகளை சேகரிப்பர். குப்பை அள்ளப்படாவிட்டால், 'குப்பை அள்ளவில்லை' என்று புகார் பதிவு செய்யலாம்.",
        "english": "Door-to-door solid waste collection takes place daily from 6:30 AM to 11:00 AM. Please segregate wet and dry waste. If garbage is not collected in your street, you can report it to us immediately."
    },
    "tax_payment": {
        "keywords": ["property tax", "tax payment", "sothu vari", "kattanam", "சொத்து வரி", "வரி செலுத்துதல்"],
        "tamil": "சொத்து வரி மற்றும் குடிநீர் கட்டணங்களை தமிழ்நாட்டின் tnurbanepay.tn.gov.in இணையதளம் வழியாகவோ அல்லது உங்கள் அருகிலுள்ள மாநகராட்சி மண்டல அலுவலகத்திலோ செலுத்தலாம்.",
        "english": "Property tax and water charges can be paid online via the official Tamil Nadu Urban e-Pay portal (tnurbanepay.tn.gov.in) or at your local Municipal Ward/Zonal Office."
    },
    "streetlight_timing": {
        "keywords": ["street light timing", "theru vilakku time", "lamp post time", "தெரு விளக்கு நேரம்"],
        "tamil": "தெருவிளக்குகள் தினமும் மாலை 6:00 மணிக்கு ஒளிரச் செய்யப்பட்டு, காலை 6:00 மணிக்கு அணைக்கப்படும். விளக்கு எரியவில்லை எனில் தெருப் பெயரை குறிப்பிட்டு புகார் தெரிவிக்கலாம்.",
        "english": "Automatic and manual street lighting is switched on at 6:00 PM and turned off at 6:00 AM. If a street light or lamp post is broken or dark, please submit a grievance with the location name."
    }
}


class AssistantService:
    def __init__(self):
        pass

    def get_suggestions(self) -> SuggestionsResponse:
        """Returns helpful sample prompts and categories for quick-click interaction."""
        sample_questions = [
            {"label": "💧 Water pipe leaking in Gandhipuram", "query": "Water pipe is broken and leaking severely near Gandhipuram bus stand, Coimbatore"},
            {"label": "⚡ Power cut & sparking wire in Peelamedu", "query": "Current cut and electric spark from transformer in Peelamedu, need urgent help"},
            {"label": "🗑️ Garbage not collected in RS Puram", "query": "Kuppai alli podala for 3 days in RS Puram, severe stench"},
            {"label": "🔍 Track complaint status", "query": "How can I check the status of my complaint?"},
            {"label": "🚨 Emergency helpline numbers", "query": "What are the emergency helpline numbers in Tamil Nadu?"},
            {"label": "💡 தெருவிளக்கு எரியவில்லை புகார்", "query": "எங்கள் தெருவில் தெருவிளக்கு எரியவில்லை, இருட்டாக உள்ளது"},
        ]

        quick_categories = [
            {"name": "Water Supply", "icon": "droplet", "sample": "Report drinking water pipeline leak or contamination"},
            {"name": "Electricity", "icon": "zap", "sample": "Report power outage, loose wire, or transformer spark"},
            {"name": "Roads & Potholes", "icon": "road", "sample": "Report deep potholes or damaged roads"},
            {"name": "Sanitation/Garbage", "icon": "trash", "sample": "Report uncollected waste or overflowing garbage bins"},
            {"name": "Drainage", "icon": "waves", "sample": "Report choked stormwater drains or sewage overflow"},
            {"name": "Streetlights", "icon": "sun", "sample": "Report non-functional streetlights or dark roads"},
            {"name": "Public Safety", "icon": "shield-alert", "sample": "Report fallen trees, fire hazard, or stray dog threat"},
        ]

        return SuggestionsResponse(
            sample_questions=sample_questions,
            emergency_helplines=EMERGENCY_HELPLINES,
            quick_categories=quick_categories
        )

    def _extract_tracking_number(self, text: str) -> Optional[str]:
        """Extracts standard Voxentra complaint format like VOX-2026-0001 or VX-2026-ABCD."""
        match = re.search(r'\b(VOX-\d{4}-\d+|VX-\d{4}-[A-Za-z0-9]+)\b', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        match = re.search(r'\b(VOX-?[A-Za-z0-9]{4,10}|VX-?[A-Za-z0-9]{4,10})\b', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        return None

    def _build_collection_state_schema(self, session: Dict[str, Any]) -> ComplaintCollectionStateSchema:
        fields = session["fields"]
        completed = sum(1 for k in FIELD_KEYS if fields.get(k) and str(fields[k]).strip())
        pct = int((completed / len(FIELD_KEYS)) * 100)

        return ComplaintCollectionStateSchema(
            session_id=session["session_id"],
            stage=session.get("state", "COLLECTING"),
            language=session.get("language", "English"),
            fields=fields,
            current_field_prompted=session.get("current_field_prompted"),
            completed_fields_count=completed,
            total_fields=len(FIELD_KEYS),
            completion_percentage=pct,
            created_complaint_number=session.get("created_complaint_number"),
            created_complaint_id=session.get("created_complaint_id")
        )

    def process_chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        language_hint: Optional[str] = None,
        db: Optional[Session] = None,
        current_user: Optional[User] = None
    ) -> AssistantResponse:
        """
        Multilingual AI Citizen Interaction and Complaint Collection:
        1. Auto-detects language (Tamil, Tanglish, English) and continues in the same language.
        2. Intelligently extracts up to 10 complaint details (Problem, Exact Location, Street, District/Area,
           Landmark, Date/Time, Frequency, Current Status, Additional Details, Citizen Contact).
        3. Prompts missing required fields one-by-one with contextual follow-ups without making assumptions.
        4. Generates a clear 10-point summary and requests explicit confirmation.
        5. Registers complaint directly to the database and forwards it to the designated municipal department.
        """
        raw_text = (message or "").strip()
        active_session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        session = complaint_collector.get_or_create_session(active_session_id, current_user, language_hint)

        if not raw_text:
            return AssistantResponse(
                reply_text="👋 **Vanakkam & Welcome to Voxentra AI!**\n\nI am your Tamil Nadu Civic Voice Assistant. You can speak or type in **Tamil, English, or Tanglish**.\n\nPlease describe the civic problem you would like to report.",
                spoken_text="Welcome to Voxentra AI. How can I help you report your civic issue today?",
                detected_language="English",
                intent="GREETING",
                collection_state=self._build_collection_state_schema(session),
                session_id=active_session_id
            )

        # 1. Detect language
        detected_lang, _ = detect_language(raw_text)
        if language_hint and language_hint in ["Tamil", "English", "Tanglish"]:
            detected_lang = language_hint
        session["language"] = detected_lang

        normalized = normalize_text(raw_text)
        lowered = normalized.lower()

        # 1b. Check for Greeting Intent
        greeting_words = [
            "hi", "hello", "hey", "vanakkam", "வணக்கம்", "namaste", "good morning",
            "good afternoon", "good evening", "greetings", "kaalai vanakkam", "nalvaravu"
        ]
        is_greeting = False
        if len(lowered.split()) <= 4:
            for w in greeting_words:
                if any(ord(c) > 127 for c in w):
                    if w in lowered:
                        is_greeting = True
                        break
                else:
                    if re.search(r'\b' + re.escape(w) + r'\b', lowered):
                        is_greeting = True
                        break

        if is_greeting:
            if detected_lang == "Tamil":
                reply = (
                    "**வணக்கம்!** 🙏 நான் **Voxentra AI** குரல் உதவியாளர்.\n\n"
                    "நான் தமிழ்நாடு நகராட்சி மற்றும் ஊரக பொதுக் குறைகளைத் தீர்க்க உங்களுக்கு உதவ தயாராக உள்ளேன். நீங்கள் என்னிடம்:\n"
                    "- 💧 குடிநீர், மின்சாரம், குப்பை, சாலை பிரச்சினைகளைப் பேசி அல்லது தட்டச்சு செய்து பதிவு செய்யலாம்.\n"
                    "- 🔍 உங்கள் புகாரின் நிலையை (Status) தெரிந்து கொள்ளலாம்.\n"
                    "- 🚨 அவசர உதவி எண்களைப் பெறலாம்.\n\n"
                    "உங்களுக்கு இன்று என்ன உதவி வேண்டும்?"
                )
                spoken = "வணக்கம்! நான் வோக்சென்ட்ரா ஏஐ உதவியாளர். உங்களுக்கு இன்று என்ன உதவி வேண்டும்?"
            elif detected_lang == "Tanglish":
                reply = (
                    "**Vanakkam!** 🙏 I am **Voxentra AI** Assistant.\n\n"
                    "Ungaloda civic complaints ah direct ah pesi or type panni submit pannalam.\n"
                    "What problem would you like to report today?"
                )
                spoken = "Vanakkam! I am Voxentra AI Assistant. How can I help you report your grievance today?"
            else:
                reply = (
                    "**Hello and welcome!** 🙏 I am **Voxentra AI**, your smart civic assistant.\n\n"
                    "I can guide you step-by-step to collect all 10 required details and register your complaint directly with the department.\n\n"
                    "How can I assist you today? Please describe the civic problem you are facing."
                )
                spoken = "Hello! I am Voxentra AI, your civic grievance assistant. How can I help you today?"

            return AssistantResponse(
                reply_text=reply,
                spoken_text=spoken,
                detected_language=detected_lang,
                intent="GREETING",
                collection_state=self._build_collection_state_schema(session),
                suggested_actions=[
                    ActionSuggestion(label="💧 Water Leakage", action_type="QUICK_PROMPT", payload={"prompt": "Water pipeline leakage near Gandhipuram"}),
                    ActionSuggestion(label="⚡ Power Outage", action_type="QUICK_PROMPT", payload={"prompt": "Power cut and electric spark"}),
                    ActionSuggestion(label="🔍 Track Complaint", action_type="QUICK_PROMPT", payload={"prompt": "Track my complaint status"}),
                    ActionSuggestion(label="🚨 Helpline 1913", action_type="CALL_HELPLINE", payload={"phone": "1913"})
                ],
                session_id=active_session_id
            )

        # 2. Check for Emergency / Helpline Triggers
        is_emergency_inquiry = (
            any(w in lowered for w in ["helpline", "emergency number", "toll free", "police number", "ambulance number", "tneb number", "அவசர எண்", "தொடர்பு எண்", "helpline number"]) or
            (len(lowered.split()) <= 4 and any(w in lowered for w in ["1913", "112", "108", "1912", "emergency", "police"]))
        )
        if is_emergency_inquiry:
            if detected_lang == "Tamil":
                reply = (
                    "### 🚨 தமிழ்நாடு அவசர உதவி மற்றும் நகராட்சி எண்கள்:\n\n"
                    "- 🚨 **அனைத்து அவசர உதவி (Emergency):** `112`\n"
                    "- 🏛️ **நகராட்சி குறைதீர்ப்பு (Civic Grievance):** `1913` (இலவச அழைப்பு)\n"
                    "- ⚡ **மின்சார வாரியம் (TNEB Power):** `1912`\n"
                    "- 🚑 **மருத்துவ அவசர ஊர்தி (Ambulance):** `108`\n"
                    "- 👮 **காவல்துறை (Police):** `100`\n"
                    "- 🚒 **தீயணைப்பு மற்றும் மீட்புப்பணி:** `101`"
                )
                spoken = "தமிழ்நாடு அவசர உதவி எண்கள்: நகராட்சிக்கு ஆயிரத்து தொள்ளாயிரத்து பதிமூன்று. மின்சாரத்திற்கு ஆயிரத்து தொள்ளாயிரத்து பன்னிரண்டு. அவசர உதவிக்கு நூற்றி பன்னிரண்டு."
            else:
                reply = (
                    "### 🚨 Tamil Nadu Civic & Emergency Helplines:\n\n"
                    "- 🚨 **All Emergencies:** `112`\n"
                    "- 🏛️ **Municipal Corporation Grievance:** `1913`\n"
                    "- ⚡ **TNEB Power & Electricity:** `1912`\n"
                    "- 🚑 **Ambulance Service:** `108`\n"
                    "- 👮 **Police Assistance:** `100`"
                )
                spoken = "Here are the essential emergency numbers. For municipal grievances call 1913, for power outages call 1912, and for general emergency call 112."

            return AssistantResponse(
                reply_text=reply,
                spoken_text=spoken,
                detected_language=detected_lang,
                intent="EMERGENCY_HELPLINE",
                collection_state=self._build_collection_state_schema(session),
                suggested_actions=[
                    ActionSuggestion(label="📞 Call Helpline 1913", action_type="CALL_HELPLINE", payload={"phone": "1913"}),
                    ActionSuggestion(label="🚨 Dial Emergency 112", action_type="CALL_HELPLINE", payload={"phone": "112"}),
                ],
                session_id=active_session_id
            )

        # 3. Check for Status / Tracking Intent
        tracking_number = self._extract_tracking_number(raw_text)
        status_triggers = ["track", "status", "check status", "enoda complaint", "நிலை", "புகார் என்னாச்சு"]
        if tracking_number or (any(w in lowered for w in status_triggers) and len(lowered.split()) <= 4):
            if tracking_number and db:
                complaint = db.query(Complaint).filter(
                    (Complaint.complaint_number == tracking_number) |
                    (Complaint.complaint_number == tracking_number.replace("VOX", "VX")) |
                    (Complaint.complaint_number == tracking_number.replace("VX", "VOX"))
                ).first()

                if complaint:
                    dept_name = complaint.department.name if complaint.department else "General Department"
                    status_display = complaint.status.value.replace("_", " ").title()

                    reply = (
                        f"### 📋 Complaint Status Details\n\n"
                        f"- **Tracking ID:** `{complaint.complaint_number}`\n"
                        f"- **Title:** {complaint.title}\n"
                        f"- **Category:** {complaint.category}\n"
                        f"- **Status:** **`{status_display}`**\n"
                        f"- **Assigned Department:** {dept_name}\n"
                        f"- **Location:** {complaint.location or 'Tamil Nadu'}\n"
                        f"- **Registered On:** {complaint.created_at.strftime('%d %b %Y, %I:%M %p')}\n"
                    )
                    spoken = f"Complaint {complaint.complaint_number} is currently {status_display}. It is assigned to {dept_name}."
                    return AssistantResponse(
                        reply_text=reply,
                        spoken_text=spoken,
                        detected_language=detected_lang,
                        intent="TRACK_STATUS",
                        collection_state=self._build_collection_state_schema(session),
                        status_info={
                            "complaint_number": complaint.complaint_number,
                            "tracking_number": complaint.complaint_number,
                            "status": complaint.status.value,
                            "category": complaint.category,
                            "department": dept_name
                        },
                        suggested_actions=[
                            ActionSuggestion(label="👁️ View Live Tracking", action_type="TRACK_COMPLAINT", payload={"tracking_number": complaint.complaint_number})
                        ],
                        session_id=active_session_id
                    )


        # 3b. Check if session has a pending slot confirmation (e.g., confirming a misheard word or spelling candidate)
        if session.get("pending_slot_confirmation"):
            is_resolved, resolved_val, ack_reply, ack_spoken = complaint_collector.handle_slot_confirmation_turn(session, raw_text, detected_lang)
            if not is_resolved:
                # Still waiting for proper confirmation or correct spelling
                pending = session.get("pending_slot_confirmation", {})
                cand = pending.get("detected_word", "the detail")
                actions = [
                    ActionSuggestion(label=f"✅ Yes, {cand}", action_type="QUICK_PROMPT", payload={"prompt": f"Yes, {cand} is correct"}),
                    ActionSuggestion(label="✏️ Provide Spelling", action_type="QUICK_PROMPT", payload={"prompt": "Let me provide the correct spelling"})
                ]
                return AssistantResponse(
                    reply_text=ack_reply,
                    spoken_text=ack_spoken,
                    detected_language=detected_lang,
                    intent="SLOT_CONFIRMATION_PENDING",
                    collection_state=self._build_collection_state_schema(session),
                    suggested_actions=actions,
                    session_id=active_session_id
                )
            else:
                # Slot successfully confirmed or corrected! Continue to check next missing field.
                next_missing = complaint_collector.get_next_missing_field(session)
                if not next_missing:
                    session["state"] = "CONFIRMATION_PENDING"
                    session["current_field_prompted"] = None
                    summary_text, spoken_summary = complaint_collector.generate_summary(session, detected_lang)
                    prob = session["fields"].get("problem_description") or "Civic Grievance"
                    cat, dept, _ = classify_complaint(normalize_text(prob))
                    prio, _ = assess_priority(normalize_text(prob), cat)
                    draft = ComplaintDraft(
                        title=f"{cat} issue at {session['fields'].get('district_area') or 'Location'}",
                        description=prob,
                        category=cat,
                        suggested_department=dept,
                        extracted_location=f"{session['fields'].get('exact_location', '')}, {session['fields'].get('street_road_name', '')}",
                        priority=prio,
                        summary=f"{cat} grievance ready for registration"
                    )
                    return AssistantResponse(
                        reply_text=f"{ack_reply}\n\n{summary_text}",
                        spoken_text=f"{ack_spoken} {spoken_summary}",
                        detected_language=detected_lang,
                        intent="CONFIRMATION_PENDING",
                        draft_complaint=draft,
                        collection_state=self._build_collection_state_schema(session),
                        suggested_actions=[
                            ActionSuggestion(label="✅ Confirm & Register Grievance", action_type="QUICK_PROMPT", payload={"prompt": "Yes, please register this complaint"}),
                            ActionSuggestion(label="✏️ Change a Detail", action_type="QUICK_PROMPT", payload={"prompt": "I want to edit some details"})
                        ],
                        session_id=active_session_id
                    )
                else:
                    session["state"] = "COLLECTING"
                    session["current_field_prompted"] = next_missing
                    meta = FIELD_METADATA[next_missing]
                    q_text, sp_text = complaint_collector.get_contextual_question(session, next_missing, detected_lang)
                    step_num = FIELD_KEYS.index(next_missing) + 1
                    step_label = meta.get('label_' + ('ta' if detected_lang == 'Tamil' else ('tanglish' if detected_lang == 'Tanglish' else 'en')), meta['label_en'])
                    full_reply = f"{ack_reply}**Step {step_num} of 10: {step_label}**\n\n{q_text}"
                    return AssistantResponse(
                        reply_text=full_reply,
                        spoken_text=f"{ack_spoken} {sp_text}",
                        detected_language=detected_lang,
                        intent="COLLECTING_FIELD",
                        collection_state=self._build_collection_state_schema(session),
                        session_id=active_session_id
                    )

        # 3c. Check if speech/input is unclear, corrupted, or unintelligible noise
        if complaint_collector.detect_unclear_speech(raw_text):
            unclear_reply, unclear_spoken = complaint_collector.get_unclear_prompt(detected_lang)
            return AssistantResponse(
                reply_text=unclear_reply,
                spoken_text=unclear_spoken,
                detected_language=detected_lang,
                intent="UNCLEAR_INPUT",
                collection_state=self._build_collection_state_schema(session),
                suggested_actions=[
                    ActionSuggestion(label="💧 Water Pipe Leak", action_type="QUICK_PROMPT", payload={"prompt": "Water pipeline leakage near bus stand"}),
                    ActionSuggestion(label="⚡ Power Outage", action_type="QUICK_PROMPT", payload={"prompt": "Power outage and transformer spark"}),
                    ActionSuggestion(label="🗑️ Garbage Waste", action_type="QUICK_PROMPT", payload={"prompt": "Garbage not collected for days"})
                ],
                session_id=active_session_id
            )

        # 4. If session is waiting for CONFIRMATION
        if session.get("state") == "CONFIRMATION_PENDING":
            is_decision, is_confirmed = complaint_collector.is_confirmation_response(raw_text)
            if is_decision:
                if is_confirmed:
                    # Register the complaint in the database
                    if db:
                        created = complaint_collector.register_complaint_record(session, db, current_user)
                        dept_name = created.department.name if created.department else "Municipal Administration"

                        if detected_lang == "Tamil":
                            reply = (
                                f"🎉 **உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டு விட்டது!**\n\n"
                                f"- 🔢 **புகார் கண்காணிப்பு எண் (Tracking ID):** **`{created.complaint_number}`**\n"
                                f"- 🏢 **ஒதுக்கப்பட்ட துறை (Department):** `{dept_name}`\n"
                                f"- ⚡ **முன்னுரிமை (Priority):** **`{created.priority.value}`**\n"
                                f"- 📍 **இடம்:** {created.location}\n"
                                f"- 📊 **நிலை (Status):** **சமர்ப்பிக்கப்பட்டது (Submitted)**\n\n"
                                "உங்கள் புகார் கள ஆய்வு அதிகாரியின் ஆய்வுக்கு அனுப்பப்பட்டுள்ளது. எஸ்.எம்.எஸ் மூலம் தொடர் நிலை அறிவிப்புகள் உங்களுக்கு அனுப்பப்படும்.\n\n"
                                "கீழே உள்ள பொத்தானை அழுத்தி எப்போது வேண்டுமானாலும் உங்கள் புகாரின் நிலையை கண்காணிக்கலாம்."
                            )
                            spoken = f"உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டது. கண்காணிப்பு எண் {created.complaint_number}. இது {dept_name} துறைக்கு அனுப்பப்பட்டுள்ளது."
                        elif detected_lang == "Tanglish":
                            reply = (
                                f"🎉 **Grievance Registered Successfully!**\n\n"
                                f"- 🔢 **Tracking ID:** **`{created.complaint_number}`**\n"
                                f"- 🏢 **Assigned Department:** `{dept_name}`\n"
                                f"- ⚡ **Priority:** **`{created.priority.value}`**\n"
                                f"- 📍 **Location:** {created.location}\n"
                                f"- 📊 **Status:** **Submitted**\n\n"
                                "Ungaloda complaint field officer ku forward panniyaachu. SMS updates ungalukku anuppapadum."
                            )
                            spoken = f"Your complaint has been successfully registered with Tracking ID {created.complaint_number} and forwarded to {dept_name}."
                        else:
                            reply = (
                                f"🎉 **Complaint Successfully Registered & Forwarded!**\n\n"
                                f"- 🔢 **Complaint Tracking Number:** **`{created.complaint_number}`**\n"
                                f"- 🏢 **Forwarded Department:** `{dept_name}`\n"
                                f"- ⚡ **Assessed Priority:** **`{created.priority.value}`**\n"
                                f"- 📍 **Location:** {created.location}\n"
                                f"- 📊 **Current Status:** **Submitted (Assigned to Department)**\n\n"
                                "The complaint has been dispatched to official municipal field units. You can track real-time resolution progress anytime with your Tracking ID."
                            )
                            spoken = f"Your grievance has been successfully registered with Tracking ID {created.complaint_number} and forwarded to {dept_name}."

                        return AssistantResponse(
                            reply_text=reply,
                            spoken_text=spoken,
                            detected_language=detected_lang,
                            intent="COMPLAINT_REGISTERED",
                            collection_state=self._build_collection_state_schema(session),
                            suggested_actions=[
                                ActionSuggestion(label="👁️ Track Complaint Status", action_type="TRACK_COMPLAINT", payload={"tracking_number": created.complaint_number}),
                                ActionSuggestion(label="📝 File Another Grievance", action_type="QUICK_PROMPT", payload={"prompt": "File another grievance"})
                            ],
                            session_id=active_session_id
                        )
                    else:
                        # Fallback if DB not directly passed
                        dummy_id = f"VOX-2026-{uuid.uuid4().hex[:4].upper()}"
                        session["created_complaint_number"] = dummy_id
                        session["state"] = "REGISTERED"
                        reply = f"🎉 **Complaint Registered with ID `{dummy_id}`!**"
                        spoken = f"Your complaint has been registered with Tracking ID {dummy_id}."
                        return AssistantResponse(
                            reply_text=reply,
                            spoken_text=spoken,
                            detected_language=detected_lang,
                            intent="COMPLAINT_REGISTERED",
                            collection_state=self._build_collection_state_schema(session),
                            session_id=active_session_id
                        )
                else:
                    # User said No / Wants change
                    session["state"] = "COLLECTING"
                    session["current_field_prompted"] = "problem_description"
                    if detected_lang == "Tamil":
                        reply = "சரி, எந்த விவரத்தை மாற்ற வேண்டும்? தயவுசெய்து சரியான விவரத்தைக் கூறவும்."
                        spoken = "எந்த விவரத்தை மாற்ற வேண்டும்? தயவுசெய்து கூறவும்."
                    elif detected_lang == "Tanglish":
                        reply = "Sure, endha detail ah change pannanum nu sollunga."
                        spoken = "Which detail would you like to edit or change?"
                    else:
                        reply = "Understood. Which detail would you like to change or correct? Please specify."
                        spoken = "Which detail would you like to update? Please specify."

                    return AssistantResponse(
                        reply_text=reply,
                        spoken_text=spoken,
                        detected_language=detected_lang,
                        intent="COLLECTING_FIELD",
                        collection_state=self._build_collection_state_schema(session),
                        session_id=active_session_id
                    )

        # 5. If state was already REGISTERED and user sends a new message
        if session.get("state") == "REGISTERED":
            # Reset session for fresh intake
            complaint_collector.reset_session(active_session_id)
            session = complaint_collector.get_or_create_session(active_session_id, current_user, language_hint)

        # 5b. Check for explicit speech or slot correction (e.g. "Change district to Madurai", "No it's Peelamedu", "P E E L A M E D U")
        explicit_corr = complaint_collector.detect_explicit_correction(session, raw_text, detected_lang)
        if explicit_corr:
            corr_field, new_val, ack_reply, ack_spoken = explicit_corr
            next_missing = complaint_collector.get_next_missing_field(session)
            if not next_missing:
                session["state"] = "CONFIRMATION_PENDING"
                session["current_field_prompted"] = None
                summary_text, spoken_summary = complaint_collector.generate_summary(session, detected_lang)
                prob = session["fields"].get("problem_description") or "Civic Grievance"
                cat, dept, _ = classify_complaint(normalize_text(prob))
                prio, _ = assess_priority(normalize_text(prob), cat)
                draft = ComplaintDraft(
                    title=f"{cat} issue at {session['fields'].get('district_area') or 'Location'}",
                    description=prob,
                    category=cat,
                    suggested_department=dept,
                    extracted_location=f"{session['fields'].get('exact_location', '')}, {session['fields'].get('street_road_name', '')}",
                    priority=prio,
                    summary=f"{cat} grievance ready for registration"
                )
                return AssistantResponse(
                    reply_text=f"{ack_reply}\n\n{summary_text}",
                    spoken_text=f"{ack_spoken} {spoken_summary}",
                    detected_language=detected_lang,
                    intent="CORRECTION_APPLIED",
                    draft_complaint=draft,
                    collection_state=self._build_collection_state_schema(session),
                    suggested_actions=[
                        ActionSuggestion(label="✅ Confirm & Register Grievance", action_type="QUICK_PROMPT", payload={"prompt": "Yes, please register this complaint"}),
                        ActionSuggestion(label="✏️ Change a Detail", action_type="QUICK_PROMPT", payload={"prompt": "I want to edit some details"})
                    ],
                    session_id=active_session_id
                )
            else:
                session["state"] = "COLLECTING"
                session["current_field_prompted"] = next_missing
                meta = FIELD_METADATA[next_missing]
                q_text, sp_text = complaint_collector.get_contextual_question(session, next_missing, detected_lang)
                step_num = FIELD_KEYS.index(next_missing) + 1
                step_label = meta.get('label_' + ('ta' if detected_lang == 'Tamil' else ('tanglish' if detected_lang == 'Tanglish' else 'en')), meta['label_en'])
                full_reply = f"{ack_reply}**Step {step_num} of 10: {step_label}**\n\n{q_text}"
                return AssistantResponse(
                    reply_text=full_reply,
                    spoken_text=f"{ack_spoken} {sp_text}",
                    detected_language=detected_lang,
                    intent="CORRECTION_APPLIED",
                    collection_state=self._build_collection_state_schema(session),
                    session_id=active_session_id
                )

        # 5c. Check for spelling / recognition variation on the currently prompted field before saving
        current_field = session.get("current_field_prompted")
        if current_field:
            variation_candidate = complaint_collector.find_spelling_or_recognition_variation(current_field, raw_text)
            if variation_candidate:
                session["pending_slot_confirmation"] = {
                    "field": current_field,
                    "original_input": raw_text,
                    "detected_word": variation_candidate
                }
                conf_text, conf_spoken = complaint_collector.get_spelling_or_correction_prompt(variation_candidate, detected_lang)
                actions = [
                    ActionSuggestion(label=f"✅ Yes, {variation_candidate}", action_type="QUICK_PROMPT", payload={"prompt": f"Yes, {variation_candidate} is correct"}),
                    ActionSuggestion(label="✏️ Provide Correct Spelling", action_type="QUICK_PROMPT", payload={"prompt": "Let me provide the correct spelling"})
                ]
                return AssistantResponse(
                    reply_text=conf_text,
                    spoken_text=conf_spoken,
                    detected_language=detected_lang,
                    intent="SLOT_CONFIRMATION_PENDING",
                    collection_state=self._build_collection_state_schema(session),
                    suggested_actions=actions,
                    session_id=active_session_id
                )

        # 6. Extract slots from the current user input
        extracted_slots = complaint_collector.extract_slots(raw_text, current_field=current_field)

        # Merge extracted slots into session
        for k, v in extracted_slots.items():
            if v and str(v).strip():
                session["fields"][k] = v


        # If user is logged in, ensure citizen details default is kept
        if current_user and not session["fields"].get("citizen_details"):
            phone = getattr(current_user, "phone", "") or ""
            name = getattr(current_user, "full_name", "") or getattr(current_user, "username", "") or ""
            if name or phone:
                session["fields"]["citizen_details"] = f"{name} ({phone})".strip()

        # 7. Check if all 10 fields are now filled
        next_missing = complaint_collector.get_next_missing_field(session)

        if not next_missing:
            # All 10 details collected! Present the summary and ask for confirmation
            session["state"] = "CONFIRMATION_PENDING"
            session["current_field_prompted"] = None
            summary_text, spoken_summary = complaint_collector.generate_summary(session, detected_lang)

            # Extract category & department for draft payload
            prob = session["fields"].get("problem_description") or "Civic Grievance"
            cat, dept, _ = classify_complaint(normalize_text(prob))
            prio, _ = assess_priority(normalize_text(prob), cat)

            draft = ComplaintDraft(
                title=f"{cat} issue at {session['fields'].get('district_area') or 'Location'}",
                description=prob,
                category=cat,
                suggested_department=dept,
                extracted_location=f"{session['fields'].get('exact_location', '')}, {session['fields'].get('street_road_name', '')}",
                priority=prio,
                summary=f"{cat} grievance ready for registration"
            )

            actions = [
                ActionSuggestion(label="✅ Confirm & Register Grievance", action_type="QUICK_PROMPT", payload={"prompt": "Yes, please register this complaint"}),
                ActionSuggestion(label="✏️ Change a Detail", action_type="QUICK_PROMPT", payload={"prompt": "I want to edit some details"})
            ]

            return AssistantResponse(
                reply_text=summary_text,
                spoken_text=spoken_summary,
                detected_language=detected_lang,
                intent="CONFIRMATION_PENDING",
                draft_complaint=draft,
                collection_state=self._build_collection_state_schema(session),
                suggested_actions=actions,
                session_id=active_session_id
            )

        # 8. Still missing required fields: Ask the next question naturally with contextual awareness
        session["state"] = "COLLECTING"
        session["current_field_prompted"] = next_missing
        meta = FIELD_METADATA[next_missing]

        # Generate contextual question tailored to previously collected details
        question_text, spoken_text = complaint_collector.get_contextual_question(session, next_missing, detected_lang)

        # Build acknowledgement or clarification prefix
        completed_count = sum(1 for k in FIELD_KEYS if session["fields"].get(k))
        ack = ""

        # Check if user entered a vague location
        if current_field in ["district_area", "street_road_name", "exact_location"] and complaint_collector.is_vague_location(raw_text):
            if detected_lang == "Tamil":
                ack = "⚠️ நீங்கள் குறிப்பிட்ட இடம் போதுமானதாக இல்லை. துல்லியமான இடம் தேவை.\n\n"
            elif detected_lang == "Tanglish":
                ack = "⚠️ Neenga sonna location konjam unclear-ah irukku. Specific details sollunga.\n\n"
            else:
                ack = "⚠️ The provided location is unclear. Please provide more specific details.\n\n"
        elif completed_count == 1:
            if detected_lang == "Tamil":
                ack = "உங்கள் பிரச்சனை விவரம் பெறப்பட்டது. 👍\n\n"
            elif detected_lang == "Tanglish":
                ack = "Got your problem description. 👍\n\n"
            else:
                ack = "I have noted the problem description. 👍\n\n"
        elif completed_count > 1 and current_field:
            prev_label = FIELD_METADATA.get(current_field, {}).get("label_" + ("ta" if detected_lang == "Tamil" else "en"), "Detail")
            if detected_lang == "Tamil":
                ack = f"நன்றி, பதிவு செய்யப்பட்டது. ({completed_count}/10 விவரங்கள்)\n\n"
            elif detected_lang == "Tanglish":
                ack = f"Noted. ({completed_count}/10 details gathered)\n\n"
            else:
                ack = f"Thank you, noted. ({completed_count}/10 details gathered)\n\n"

        step_num = FIELD_KEYS.index(next_missing) + 1
        step_label = meta.get('label_' + ('ta' if detected_lang == 'Tamil' else ('tanglish' if detected_lang == 'Tanglish' else 'en')), meta['label_en'])

        full_reply = (
            f"{ack}"
            f"**Step {step_num} of 10: {step_label}**\n\n"
            f"{question_text}"
        )

        # Contextual action suggestions
        actions = []
        if next_missing == "current_status":
            actions = [
                ActionSuggestion(label="⚡ Still Happening / Active", action_type="QUICK_PROMPT", payload={"prompt": "It is still happening and active"}),
                ActionSuggestion(label="⏸️ Temporarily Paused", action_type="QUICK_PROMPT", payload={"prompt": "Temporarily stopped"}),
                ActionSuggestion(label="✅ Already Resolved", action_type="QUICK_PROMPT", payload={"prompt": "It has been resolved"})
            ]
        elif next_missing == "frequency":
            actions = [
                ActionSuggestion(label="1️⃣ Happening First Time", action_type="QUICK_PROMPT", payload={"prompt": "Happening for the first time"}),
                ActionSuggestion(label="🔁 Daily Recurring", action_type="QUICK_PROMPT", payload={"prompt": "Recurring every day"}),
                ActionSuggestion(label="🌧️ Only During Rainy Days", action_type="QUICK_PROMPT", payload={"prompt": "Happens every rainy day"})
            ]
        elif next_missing == "additional_details":
            actions = [
                ActionSuggestion(label="🚫 No Additional Details", action_type="QUICK_PROMPT", payload={"prompt": "None, no other details"}),
                ActionSuggestion(label="⚠️ Severe Safety Hazard", action_type="QUICK_PROMPT", payload={"prompt": "Severe public hazard and traffic risk"})
            ]
        elif next_missing == "citizen_details" and current_user:
            actions = [
                ActionSuggestion(label=f"👤 Use My Profile ({current_user.full_name or current_user.email})", action_type="QUICK_PROMPT", payload={"prompt": f"{current_user.full_name or 'Citizen'}, {getattr(current_user, 'phone', '9840012345')}"})
            ]

        return AssistantResponse(
            reply_text=full_reply,
            spoken_text=spoken_text,
            detected_language=detected_lang,
            intent="COLLECTING_FIELD",
            collection_state=self._build_collection_state_schema(session),
            suggested_actions=actions,
            session_id=active_session_id
        )


assistant_service = AssistantService()
