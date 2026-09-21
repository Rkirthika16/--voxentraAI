import re
import uuid
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session

from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text
from app.ai.provider import ai_provider
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus
from app.models.user import User
from app.schemas.assistant import (
    AssistantResponse,
    ComplaintDraft,
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
        """Extracts standard Voxentra complaint format like VX-2026-ABCD or numeric ID."""
        # Pattern 1: Standard VX-YYYY-XXXX format
        match = re.search(r'\b(VX-\d{4}-[A-Za-z0-9]+)\b', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Pattern 2: VX followed by numbers or digits
        match = re.search(r'\b(VX-?[A-Za-z0-9]{4,10})\b', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        return None

    def process_chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        language_hint: Optional[str] = None,
        db: Optional[Session] = None,
        current_user: Optional[User] = None
    ) -> AssistantResponse:
        """
        Core conversational AI engine:
        1. Multilingual language identification (Tamil / Tanglish / English)
        2. Intent parsing: GREETING, TRACK_STATUS, EMERGENCY, CIVIC_INQUIRY, FILE_COMPLAINT, GENERAL_HELP
        3. Database integration for live tracking lookup
        4. Auto grievance structuring with coordinates and department routing
        5. Spoken audio text generation formatted for natural TTS
        """
        raw_text = (message or "").strip()
        if not raw_text:
            return AssistantResponse(
                reply_text="Hello! How can I assist you with Tamil Nadu civic grievances or municipal services today?",
                spoken_text="Hello! How can I assist you today?",
                detected_language="English",
                intent="GREETING",
                session_id=session_id or str(uuid.uuid4())
            )

        detected_lang, _ = detect_language(raw_text)
        if language_hint and language_hint in ["Tamil", "English", "Tanglish"]:
            detected_lang = language_hint

        normalized = normalize_text(raw_text)
        lowered = normalized.lower()
        active_session = session_id or str(uuid.uuid4())

        # 1. Check for Greeting Intent
        greeting_words = [
            "hi", "hello", "hey", "vanakkam", "வணக்கம்", "namaste", "good morning",
            "good afternoon", "good evening", "greetings", "kaalai vanakkam", "nalvaravu"
        ]
        is_greeting = False
        if len(lowered.split()) <= 6:
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
                    "நான் தமிழ்நாடு நகராட்சி மற்றும் பொதுக் குறைகளைத் தீர்க்க உங்களுக்கு உதவ தயாராக உள்ளேன். நீங்கள் என்னிடம்:\n"
                    "- 💧 குடிநீர், மின்சாரம், குப்பை, சாலை பிரச்சினைகளை குரல் அல்லது உரையில் பதிவு செய்யலாம்.\n"
                    "- 🔍 உங்கள் புகாரின் நிலையை (Status) தெரிந்து கொள்ளலாம்.\n"
                    "- 🚨 அவசர உதவி எண்களைப் பெறலாம்.\n\n"
                    "உங்களுக்கு இன்று என்ன உதவி வேண்டும்?"
                )
                spoken = "வணக்கம்! நான் வோக்சென்ட்ரா ஏஐ உதவியாளர். உங்களுக்கு இன்று என்ன உதவி வேண்டும்?"
            elif detected_lang == "Tanglish":
                reply = (
                    "**Vanakkam!** 🙏 I am **Voxentra AI** Assistant.\n\n"
                    "Ungaloda civic complaints (Water, Current, Garbage, Road potholes, Street light) ah direct ah pesi or type panni submit pannalam.\n"
                    "Tracking number kudutha status check pannalam.\n\n"
                    "What issue would you like to report today?"
                )
                spoken = "Vanakkam! I am Voxentra AI Assistant. How can I help you report your grievance today?"
            else:
                reply = (
                    "**Hello and welcome!** 🙏 I am **Voxentra AI**, your smart civic assistant.\n\n"
                    "I can help you:\n"
                    "- 📝 **Register civic complaints** (Water leak, Electricity, Roads, Garbage, Streetlights) with automated AI location & department routing.\n"
                    "- 🔍 **Track grievance progress** and resolution updates.\n"
                    "- 🚨 **Find municipal helpline numbers** and civic schedules across Tamil Nadu.\n\n"
                    "How can I assist you today? You can speak or type your grievance."
                )
                spoken = "Hello! I am Voxentra AI, your civic grievance assistant. How can I help you today?"

            return AssistantResponse(
                reply_text=reply,
                spoken_text=spoken,
                detected_language=detected_lang,
                intent="GREETING",
                suggested_actions=[
                    ActionSuggestion(label="💧 Report Water Leakage", action_type="QUICK_PROMPT", payload={"prompt": "Water pipeline leakage near Gandhipuram"}),
                    ActionSuggestion(label="⚡ Report Power Outage", action_type="QUICK_PROMPT", payload={"prompt": "Power cut and fuse spark in my area"}),
                    ActionSuggestion(label="🔍 Track My Complaint", action_type="QUICK_PROMPT", payload={"prompt": "Track my complaint status"}),
                    ActionSuggestion(label="🚨 Emergency Helplines", action_type="CALL_HELPLINE", payload={"phone": "1913"})
                ],
                session_id=active_session
            )

        # 2. Check for Emergency / Helpline Intent
        emergency_triggers = [
            "emergency", "helpline", "toll free", "phone number", "contact number",
            "police number", "fire number", "ambulance number", "tneb number",
            "1913", "112", "108", "100", "அவசர எண்", "தொடர்பு எண்", "help line"
        ]
        if any(w in lowered for w in emergency_triggers):
            if detected_lang == "Tamil":
                reply = (
                    "### 🚨 தமிழ்நாடு அவசர உதவி மற்றும் நகராட்சி எண்கள்:\n\n"
                    "- 🚨 **அனைத்து அவசர உதவி (Emergency):** `112`\n"
                    "- 🏛️ **நகராட்சி குறைதீர்ப்பு (Civic Grievance):** `1913` (இலவச அழைப்பு)\n"
                    "- ⚡ **மின்சார வாரியம் (TNEB Power Helpline):** `1912`\n"
                    "- 🚑 **மருத்துவ அவசர ஊர்தி (Ambulance):** `108`\n"
                    "- 👮 **காவல்துறை (Police):** `100`\n"
                    "- 🚒 **தீயணைப்பு மற்றும் மீட்புப்பணி:** `101`\n\n"
                    "உடனடி அவசர உதவிக்கு மேலே உள்ள எண்களை தொடர்பு கொள்ளலாம்."
                )
                spoken = "தமிழ்நாடு அவசர உதவி எண்கள்: நகராட்சி குறைதீர்ப்புக்கு ஆயிரத்து தொள்ளாயிரத்து பதிமூன்று. மின்சார வாரியத்திற்கு ஆயிரத்து தொள்ளாயிரத்து பன்னிரண்டு. அனைத்து அவசர உதவிக்கு நூற்றி பன்னிரண்டு."
            else:
                reply = (
                    "### 🚨 Tamil Nadu Essential Civic & Emergency Helplines:\n\n"
                    "- 🚨 **All Emergencies (Police/Fire/Medical):** `112`\n"
                    "- 🏛️ **Municipal Corporation Grievance:** `1913` (Toll-Free)\n"
                    "- ⚡ **TNEB Power & Electricity Outage:** `1912`\n"
                    "- 🚑 **Medical Ambulance Service:** `108`\n"
                    "- 👮 **Police Assistance:** `100`\n"
                    "- 🚒 **Fire & Disaster Rescue:** `101`\n\n"
                    "You can tap below to dial municipal helpline `1913` or state emergency `112` directly."
                )
                spoken = "Here are the essential emergency numbers. For municipal corporation grievances call 1913, for power outages call 1912, and for general emergency call 112."

            return AssistantResponse(
                reply_text=reply,
                spoken_text=spoken,
                detected_language=detected_lang,
                intent="EMERGENCY_HELPLINE",
                suggested_actions=[
                    ActionSuggestion(label="📞 Call Civic Helpline (1913)", action_type="CALL_HELPLINE", payload={"phone": "1913"}, icon="phone"),
                    ActionSuggestion(label="🚨 Dial Emergency 112", action_type="CALL_HELPLINE", payload={"phone": "112"}, icon="alert-triangle"),
                    ActionSuggestion(label="⚡ Call TNEB (1912)", action_type="CALL_HELPLINE", payload={"phone": "1912"}, icon="zap")
                ],
                session_id=active_session
            )

        # 3. Check for Status / Tracking Intent
        status_triggers = [
            "track", "status", "where is my", "check status", "complaint status",
            "enoda complaint", "nilai", "புகார் நிலை", "புகார் என்னாச்சு", "tracking"
        ]
        tracking_number = self._extract_tracking_number(raw_text)

        if tracking_number or any(w in lowered for w in status_triggers):
            if tracking_number and db:
                complaint = db.query(Complaint).filter(Complaint.complaint_number == tracking_number).first()
                if complaint:
                    dept_name = complaint.department.name if complaint.department else "General Department"
                    officer_name = complaint.assigned_officer.full_name if complaint.assigned_officer else "Pending Assignment"

                    status_display = complaint.status.value.replace("_", " ").title()
                    reply = (
                        f"### 📋 Complaint Tracking Details\n\n"
                        f"- **Tracking ID:** `{complaint.complaint_number}`\n"
                        f"- **Title:** {complaint.title}\n"
                        f"- **Category:** {complaint.category}\n"
                        f"- **Status:** **`{status_display}`**\n"
                        f"- **Assigned Department:** {dept_name}\n"
                        f"- **Assigned Officer:** {officer_name}\n"
                        f"- **Location:** {complaint.location or 'Tamil Nadu'}\n"
                        f"- **Submitted On:** {complaint.created_at.strftime('%d %b %Y, %I:%M %p')}\n"
                    )
                    recent_note = complaint.history[0].notes if complaint.history else None
                    if recent_note:
                        reply += f"\n> **Officer Note:** {recent_note}"

                    spoken = f"Complaint {complaint.complaint_number} is currently {status_display}. It is assigned to {dept_name}."

                    return AssistantResponse(
                        reply_text=reply,
                        spoken_text=spoken,
                        detected_language=detected_lang,
                        intent="TRACK_STATUS",
                        status_info={
                            "complaint_number": complaint.complaint_number,
                            "tracking_number": complaint.complaint_number,
                            "id": complaint.id,
                            "status": complaint.status.value,
                            "title": complaint.title,
                            "category": complaint.category,
                            "department": dept_name,
                            "officer": officer_name
                        },
                        suggested_actions=[
                            ActionSuggestion(
                                label=f"👁️ View Live Tracking Page",
                                action_type="TRACK_COMPLAINT",
                                payload={"tracking_number": complaint.complaint_number, "complaint_id": complaint.id}
                            )
                        ],
                        session_id=active_session
                    )
                else:
                    reply = f"I could not find any active complaint with Tracking ID **`{tracking_number}`**. Please double-check your tracking number and try again."
                    spoken = f"I could not find complaint {tracking_number}. Please check the number and try again."
                    return AssistantResponse(
                        reply_text=reply,
                        spoken_text=spoken,
                        detected_language=detected_lang,
                        intent="TRACK_STATUS",
                        session_id=active_session
                    )
            elif not tracking_number:
                # If user is logged in, check recent complaints
                recent_info = ""
                if db and current_user:
                    recent = db.query(Complaint).filter(Complaint.citizen_id == current_user.id).order_by(Complaint.created_at.desc()).limit(3).all()
                    if recent:
                        recent_info = "\n\n**Your Recent Complaints:**\n" + "\n".join([
                            f"- `{c.complaint_number}`: **{c.title}** ({c.status.value})" for c in recent
                        ])

                reply = (
                    "To track your complaint, please provide your **Tracking Number** (e.g. `VX-2026-ABCD`)."
                    + recent_info +
                    "\n\nYou can also visit the **Complaint Tracking** page anytime."
                )
                spoken = "Please provide your complaint tracking number, for example VX 2026 ABCD, to check its current status."
                return AssistantResponse(
                    reply_text=reply,
                    spoken_text=spoken,
                    detected_language=detected_lang,
                    intent="TRACK_STATUS",
                    suggested_actions=[
                        ActionSuggestion(label="🔍 Go to Tracking Page", action_type="TRACK_COMPLAINT", payload={"route": "/track"})
                    ],
                    session_id=active_session
                )

        # 4. Check for Civic FAQs
        for faq_key, faq_data in CIVIC_FAQS.items():
            if any(kw in lowered for kw in faq_data["keywords"]):
                if detected_lang == "Tamil":
                    reply = faq_data["tamil"]
                    spoken = faq_data["tamil"]
                else:
                    reply = faq_data["english"]
                    spoken = faq_data["english"]

                return AssistantResponse(
                    reply_text=reply,
                    spoken_text=spoken,
                    detected_language=detected_lang,
                    intent="CIVIC_INQUIRY",
                    suggested_actions=[
                        ActionSuggestion(label="📝 File a Grievance Now", action_type="QUICK_PROMPT", payload={"prompt": f"I want to file a complaint regarding {faq_key.replace('_', ' ')}"})
                    ],
                    session_id=active_session
                )

        # 5. Check if this is a Grievance Report (FILE_COMPLAINT)
        # We run the AI provider analysis pipeline
        analysis = ai_provider.analyze(raw_text)

        # If high confidence or recognized category/location/priority keywords
        is_grievance = (
            analysis.category != "Other" or
            analysis.extracted_location is not None or
            analysis.priority in [ComplaintPriority.CRITICAL, ComplaintPriority.HIGH] or
            any(w in lowered for w in [
                "broken", "damage", "leak", "cut", "problem", "issue", "complaint", "help",
                "stench", "not working", "dark", "pothole", "overflow", "danger",
                "prachana", "odanju", "varala", "eriyala", "குறை", "புகார்", "சேதம்", "பழுது"
            ])
        )

        if is_grievance:
            title = f"{analysis.category} Grievance"
            if analysis.extracted_location:
                title += f" near {analysis.extracted_location}"

            draft = ComplaintDraft(
                title=title,
                description=raw_text,
                category=analysis.category,
                suggested_department=analysis.suggested_department,
                extracted_location=analysis.extracted_location,
                latitude=analysis.latitude,
                longitude=analysis.longitude,
                priority=analysis.priority,
                summary=analysis.summary
            )

            loc_text = f"📍 **Location:** `{analysis.extracted_location}`\n" if analysis.extracted_location else "📍 **Location:** *(Click to confirm street/ward)*\n"
            coords_text = f"🌐 **Coordinates:** `{analysis.latitude}, {analysis.longitude}`\n" if analysis.latitude else ""

            if detected_lang == "Tamil":
                reply = (
                    f"### 🤖 புகார் விவரங்கள் தயார் செய்யப்பட்டுள்ளன:\n\n"
                    f"- 🏷️ **வகை (Category):** `{analysis.category}`\n"
                    f"- 🏢 **துறை (Department):** `{analysis.suggested_department}`\n"
                    f"- ⚡ **முன்னுரிமை (Priority):** **`{analysis.priority.value}`**\n"
                    f"{loc_text}"
                    f"{coords_text}"
                    f"\n**சுருக்கம்:** {analysis.summary}\n\n"
                    f"இப்புகாரை உடனடியாக பதிவு செய்ய கீழே உள்ள **'பதிவு செய்க' (Submit)** பொத்தானை அழுத்தவும்."
                )
                spoken = f"உங்கள் {analysis.category} தொடர்பான புகார் விவரங்கள் தயாராக உள்ளன. முன்னுரிமை {analysis.priority.value}. சமர்ப்பிக்க பதிவு செய்க பொத்தானை அழுத்தவும்."
            elif detected_lang == "Tanglish":
                reply = (
                    f"### 🤖 Grievance Draft Ready for Submission:\n\n"
                    f"- 🏷️ **Category:** `{analysis.category}`\n"
                    f"- 🏢 **Department:** `{analysis.suggested_department}`\n"
                    f"- ⚡ **Assessed Priority:** **`{analysis.priority.value}`**\n"
                    f"{loc_text}"
                    f"{coords_text}"
                    f"\n**AI Summary:** {analysis.summary}\n\n"
                    f"Grievance submit panna keezha irukura **'One-Click Submit'** button ah click pannunga."
                )
                spoken = f"Your {analysis.category} grievance draft is ready with {analysis.priority.value} priority. Click submit to register."
            else:
                reply = (
                    f"### 🤖 AI Grievance Draft Generated:\n\n"
                    f"- 🏷️ **Category:** `{analysis.category}`\n"
                    f"- 🏢 **Department:** `{analysis.suggested_department}`\n"
                    f"- ⚡ **Assessed Priority:** **`{analysis.priority.value}`**\n"
                    f"{loc_text}"
                    f"{coords_text}"
                    f"\n**Summary:** {analysis.summary}\n\n"
                    f"Would you like to register this complaint now? Tap **'One-Click Submit Grievance'** below."
                )
                spoken = f"I have prepared your {analysis.category} complaint draft with {analysis.priority.value} priority. Tap submit to register it immediately."

            return AssistantResponse(
                reply_text=reply,
                spoken_text=spoken,
                detected_language=detected_lang,
                intent="FILE_COMPLAINT",
                draft_complaint=draft,
                suggested_actions=[
                    ActionSuggestion(
                        label="🚀 One-Click Submit Grievance",
                        action_type="SUBMIT_DRAFT",
                        payload=draft.model_dump(),
                        icon="check-circle"
                    ),
                    ActionSuggestion(
                        label="✏️ Edit in Detailed Form",
                        action_type="QUICK_PROMPT",
                        payload={"prompt": "edit_draft", "draft": draft.model_dump()},
                        icon="edit"
                    )
                ],
                session_id=active_session,
                metadata={"nlp_analysis": analysis.model_dump()}
            )

        # 6. General Help / Default Fallback
        if detected_lang == "Tamil":
            reply = (
                "நான் உங்கள் கேள்வியைப் புரிந்து கொண்டேன். நீங்கள் தமிழ்நாட்டில் உள்ள குடிநீர் கசிவு, மின்வெட்டு, "
                "சாக்கடை அடைப்பு, குப்பை அல்லது சாலை சேதம் போன்ற புகார்களை என்னிடம் தெரிவிக்கலாம். "
                "உதாரணமாக: *'காந்திபுரம் பேருந்து நிலையம் அருகில் குடிநீர் குழாய் உடைந்துள்ளது'* என்று கூறலாம்."
            )
            spoken = "நீங்கள் உங்கள் பொதுக் குறைகளை தமிழ் அல்லது ஆங்கிலத்தில் என்னிடம் கூறலாம். நான் உடனடியாக பதிவு செய்வேன்."
        else:
            reply = (
                "I understand your query. You can describe any civic grievance (such as broken pipes, electricity outage, uncollected garbage, or damaged roads in Tamil Nadu), and I will automatically structure and register it for you.\n\n"
                "**Example Prompts:**\n"
                "- *'Water pipeline broken near Gandhipuram bus stand'*\n"
                "- *'Streetlights not working on 100 feet road'*\n"
                "- *'Track my complaint status VX-2026-8812'*"
            )
            spoken = "You can speak or type any civic problem, or provide a tracking number to check your complaint status."

        return AssistantResponse(
            reply_text=reply,
            spoken_text=spoken,
            detected_language=detected_lang,
            intent="GENERAL_HELP",
            suggested_actions=[
                ActionSuggestion(label="💧 Water Grievance", action_type="QUICK_PROMPT", payload={"prompt": "Water pipeline leakage near my house"}),
                ActionSuggestion(label="🗑️ Sanitation Grievance", action_type="QUICK_PROMPT", payload={"prompt": "Garbage dump not cleared"}),
                ActionSuggestion(label="💡 Streetlight Issue", action_type="QUICK_PROMPT", payload={"prompt": "Streetlights are completely dark"})
            ],
            session_id=active_session
        )


assistant_service = AssistantService()
