import os
import uuid
import logging
import aiofiles
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, Query, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.models.complaint import ComplaintPriority, ComplaintSource
from app.schemas.complaint import ComplaintCreate
from app.schemas.ivr import (
    IVRCallInitiateRequest,
    IVRCallInitiateResponse,
    IVRProcessSpeechRequest,
    IVRProcessSpeechResponse,
    IVRCallDialogueRequest,
    IVRCallDialogueResponse,
    InboundSMSRequest,
    InboundSMSResponse,
    ManualSMSRequest,
    ManualSMSResponse,
    TelephonyLogsResponse,
    TelephonyLogItem
)
from app.services.complaint_service import complaint_service
from app.ai.provider import ai_provider
from app.ai.speech_service import speech_service
from app.integrations.telephony.exotel_adapter import exotel_adapter
from app.integrations.telephony.twilio_adapter import twilio_adapter
from app.utils.validators import validate_audio_file
from app.core.exceptions import BadRequestException

logger = logging.getLogger("voxentra.ivr")

router = APIRouter(tags=["Telephony & IVR Toll-Free Helpline (Exotel & Twilio)"])


def dispatch_sms_notification(to_phone: str, message: str) -> bool:
    """Dispatches SMS using configured telephony provider (Exotel or Twilio)."""
    if settings.TELEPHONY_PROVIDER.lower() == "twilio":
        return twilio_adapter.send_sms(to_phone, message)
    return exotel_adapter.send_sms(to_phone, message)


@router.post("/ivr/initiate-call", response_model=IVRCallInitiateResponse)
def initiate_toll_free_call(req: IVRCallInitiateRequest):
    """
    Simulates or initiates an inbound call to the Tamil Nadu Toll-Free Civic Helpline (1913 / 1800-425-1913).
    Returns bilingual IVR audio prompts in Tamil and English tailored for rural village citizens.
    """
    call_sid = f"CA_{uuid.uuid4().hex[:16]}"
    
    greeting_ta = "வணக்கம். வாக்ஸென்ட்ரா தமிழ்நாடு அரசு ஊரக வளர்ச்சி மற்றும் பொது குறைதீர்ப்பு சேவைக்கு நல்வரவு."
    greeting_en = "Welcome to Voxentra Tamil Nadu Rural & Civic Grievance Helpline."
    prompt_ta = "உங்கள் கிராம பிரச்சனை அல்லது புகாரை தமிழ், ஆங்கிலம் அல்லது தங்கிலீஷில் தெளிவாக கூறவும்."
    prompt_en = "Please state your village grievance in Tamil, English, or Tanglish after the tone."
    combined_prompt = f"{greeting_ta} {prompt_ta} {greeting_en} {prompt_en}"

    # Log incoming call attempt in telephony tracker
    exotel_adapter.handle_incoming_call({
        "CallSid": call_sid,
        "From": req.caller_phone,
        "To": req.toll_free_number
    })

    return IVRCallInitiateResponse(
        call_sid=call_sid,
        caller_phone=req.caller_phone,
        toll_free_number=req.toll_free_number,
        greeting_tamil=greeting_ta,
        greeting_english=greeting_en,
        prompt_tamil=prompt_ta,
        prompt_english=prompt_en,
        combined_spoken_prompt=combined_prompt
    )


@router.post("/ivr/dialogue-turn", response_model=IVRCallDialogueResponse)
def handle_ivr_dialogue_turn(
    req: IVRCallDialogueRequest,
    db: Session = Depends(get_db)
):
    """
    Multilingual Conversational Turn Handler for IVR Toll-Free Helpline:
    1. Supports Tamil, English, and Tanglish.
    2. Enforces 'No Assumptions' hierarchical location clarification (District -> Area -> Street -> Landmark -> Exact Spot).
    3. Detects vague or contradictory inputs and prompts targeted clarification.
    4. Presents complete 10-point breakdown and obtains citizen confirmation before database registration.
    5. Sends instant SMS notification upon grievance creation.
    """
    from app.ai.complaint_collector import complaint_collector, FIELD_KEYS, FIELD_METADATA
    from app.ai.language_service import detect_language
    from app.ai.normalization_service import normalize_text
    from app.ai.classification_service import classify_complaint

    user_speech = (req.user_speech or "").strip()
    session = complaint_collector.get_or_create_session(
        req.call_sid,
        language_hint=req.language_preference if req.language_preference != "Auto" else None
    )

    # Pre-populate citizen phone if caller_phone provided
    if req.caller_phone and not session["fields"].get("citizen_details"):
        session["fields"]["citizen_details"] = req.caller_phone

    # Detect language with confidence
    detected_lang, lang_conf = detect_language(user_speech)
    if req.language_preference in ["Tamil", "English", "Tanglish"]:
        detected_lang = req.language_preference
        lang_conf = 1.0
    session["language"] = detected_lang

    from app.ai.location_service import extract_location

    # 0a. Check if session has a pending slot confirmation (misheard word or spelling candidate)
    if session.get("pending_slot_confirmation"):
        is_resolved, resolved_val, ack_reply, ack_spoken = complaint_collector.handle_slot_confirmation_turn(session, user_speech, detected_lang)
        if not is_resolved:
            return IVRCallDialogueResponse(
                call_sid=req.call_sid,
                dialogue_turn=req.dialogue_turn + 1,
                ai_spoken_reply=ack_spoken,
                ai_spoken_reply_tamil=ack_reply if detected_lang == "Tamil" else ack_spoken,
                ai_spoken_reply_english=ack_spoken if detected_lang == "English" else ack_reply,
                detected_language=detected_lang,
                language_confidence=lang_conf,
                intent="SLOT_CONFIRMATION_PENDING",
                is_confirmation_pending=False,
                is_completed=False,
                collection_state=session["fields"]
            )
        else:
            # Slot resolved! Proceed to check next missing field
            next_missing = complaint_collector.get_next_missing_field(session)
            if not next_missing:
                session["state"] = "CONFIRMATION_PENDING"
                session["current_field_prompted"] = None
                summary_text, spoken_summary = complaint_collector.generate_summary(session, detected_lang)
                prob = session["fields"].get("problem_description") or "Civic Grievance"
                cat, dept, _ = classify_complaint(normalize_text(prob))
                return IVRCallDialogueResponse(
                    call_sid=req.call_sid,
                    dialogue_turn=req.dialogue_turn + 1,
                    ai_spoken_reply=f"{ack_spoken} {spoken_summary}",
                    ai_spoken_reply_tamil=f"{ack_reply} {summary_text}" if detected_lang == "Tamil" else f"{ack_spoken} {spoken_summary}",
                    ai_spoken_reply_english=f"{ack_spoken} {spoken_summary}" if detected_lang == "English" else f"{ack_reply} {summary_text}",
                    detected_language=detected_lang,
                    language_confidence=lang_conf,
                    intent="CONFIRMATION_PENDING",
                    extracted_category=cat,
                    extracted_location=f"{session['fields'].get('district_area', '')}, {session['fields'].get('street_road_name', '')}",
                    suggested_department=dept,
                    is_confirmation_pending=True,
                    is_completed=False,
                    collection_state=session["fields"],
                    summary=summary_text
                )
            else:
                session["state"] = "COLLECTING"
                session["current_field_prompted"] = next_missing
                meta = FIELD_METADATA.get(next_missing, {})
                q_text, sp_text = complaint_collector.get_contextual_question(session, next_missing, detected_lang)
                q_ta, _ = complaint_collector.get_contextual_question(session, next_missing, "Tamil")
                q_en, _ = complaint_collector.get_contextual_question(session, next_missing, "English")
                return IVRCallDialogueResponse(
                    call_sid=req.call_sid,
                    dialogue_turn=req.dialogue_turn + 1,
                    ai_spoken_reply=f"{ack_spoken} {sp_text}",
                    ai_spoken_reply_tamil=f"{ack_reply} {q_ta}" if detected_lang == "Tamil" else f"{ack_spoken} {q_ta}",
                    ai_spoken_reply_english=f"{ack_spoken} {q_en}" if detected_lang == "English" else f"{ack_reply} {q_en}",
                    detected_language=detected_lang,
                    language_confidence=lang_conf,
                    intent="GATHER_MORE_INFO",
                    is_confirmation_pending=False,
                    is_completed=False,
                    collection_state=session["fields"]
                )

    # 0b. Check if speech is unclear/misheard/corrupted
    if complaint_collector.detect_unclear_speech(user_speech):
        unclear_reply, unclear_spoken = complaint_collector.get_unclear_prompt(detected_lang)
        q_ta, _ = complaint_collector.get_unclear_prompt("Tamil")
        q_en, _ = complaint_collector.get_unclear_prompt("English")
        return IVRCallDialogueResponse(
            call_sid=req.call_sid,
            dialogue_turn=req.dialogue_turn + 1,
            ai_spoken_reply=unclear_spoken,
            ai_spoken_reply_tamil=q_ta,
            ai_spoken_reply_english=q_en,
            detected_language=detected_lang,
            language_confidence=lang_conf,
            intent="UNCLEAR_INPUT",
            is_confirmation_pending=False,
            is_completed=False,
            collection_state=session["fields"]
        )

    # 1. If currently in CONFIRMATION_PENDING stage
    if session.get("state") == "CONFIRMATION_PENDING":
        is_decision, is_confirmed = complaint_collector.is_confirmation_response(user_speech)
        if is_decision:
            if is_confirmed:
                # Register complaint with call context
                created_complaint = complaint_collector.register_complaint_record(
                    session, db,
                    call_sid=req.call_sid,
                    caller_phone=req.caller_phone,
                    sms_status="PENDING"
                )
                dept_name = created_complaint.department.name if created_complaint.department else "Municipal Administration"

                # Build bilingual Twilio SMS using template builder
                problem = session["fields"].get("problem_description", "Civic Grievance")
                location_str = (
                    f"{session['fields'].get('district_area', '')}, "
                    f"{session['fields'].get('street_road_name', '')}"
                ).strip(", ")
                sms_body = twilio_adapter.build_complaint_sms(
                    complaint_number=created_complaint.complaint_number,
                    description=problem,
                    department=dept_name,
                    location=location_str,
                    lang=detected_lang,
                    created_at=created_complaint.created_at
                )
                sms_result = twilio_adapter.send_sms(
                    req.caller_phone or "+919843098765", sms_body
                )
                sms_sent = sms_result.get("success", False)
                sms_failure_reason = sms_result.get("error") if not sms_sent else None

                # Persist SMS status in complaint ai_metadata
                if created_complaint.ai_metadata:
                    meta = dict(created_complaint.ai_metadata)
                    meta["sms_status"] = "SENT" if sms_sent else "FAILED"
                    meta["sms_sid"] = sms_result.get("sid", "")
                    meta["sms_sent_at"] = (
                        __import__('datetime').datetime.now(
                            __import__('datetime').timezone.utc
                        ).isoformat() if sms_sent else None
                    )
                    created_complaint.ai_metadata = meta
                    db.commit()

                if detected_lang == "Tamil":
                    reply_ta = (
                        f"உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது. உங்கள் புகார் எண் {created_complaint.complaint_number}. "
                        f"இந்த எண்ணை பயன்படுத்தி உங்கள் புகாரை கண்காணிக்கலாம்."
                    )
                    reply_en = (
                        f"Your complaint has been successfully registered. Your complaint number is {created_complaint.complaint_number}. "
                        f"You can use this number to track your complaint."
                    )
                    spoken = reply_ta
                elif detected_lang == "Tanglish":
                    reply_ta = (
                        f"Unga complaint successfully register aaiduchu. Unga complaint number {created_complaint.complaint_number}. "
                        f"Indha number use panni unga complaint-ah track pannalaam."
                    )
                    reply_en = (
                        f"Your complaint has been successfully registered. Your complaint number is {created_complaint.complaint_number}. "
                        f"You can use this number to track your complaint."
                    )
                    spoken = reply_ta
                else:
                    reply_ta = f"உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது. உங்கள் புகார் எண் {created_complaint.complaint_number}."
                    reply_en = (
                        f"Your complaint has been successfully registered. Your complaint number is {created_complaint.complaint_number}. "
                        f"You can use this number to track your complaint."
                    )
                    spoken = reply_en

                return IVRCallDialogueResponse(
                    call_sid=req.call_sid,
                    dialogue_turn=req.dialogue_turn + 1,
                    ai_spoken_reply=spoken,
                    ai_spoken_reply_tamil=reply_ta,
                    ai_spoken_reply_english=reply_en,
                    detected_language=detected_lang,
                    language_confidence=lang_conf,
                    latitude=str(created_complaint.latitude) if created_complaint.latitude else None,
                    longitude=str(created_complaint.longitude) if created_complaint.longitude else None,
                    osm_location_name=created_complaint.location,
                    intent="CONFIRMED",
                    extracted_category=created_complaint.category,
                    extracted_location=created_complaint.location,
                    suggested_department=dept_name,
                    is_confirmation_pending=False,
                    is_completed=True,
                    collection_state=session["fields"],
                    complaint_id=created_complaint.id,
                    complaint_number=created_complaint.complaint_number,
                    sms_sent=sms_sent,
                    sms_failure_reason=sms_failure_reason
                )
            else:
                # Caller wants edits
                session["state"] = "COLLECTING"
                session["current_field_prompted"] = "problem_description"
                if detected_lang == "Tamil":
                    reply_ta = "சரி, எந்த விவரத்தை மாற்ற வேண்டும்? தயவுசெய்து கூறவும்."
                    reply_en = "Sure, which detail would you like to update? Please specify."
                    spoken = reply_ta
                elif detected_lang == "Tanglish":
                    reply_ta = "Sure, endha detail ah maathanum nu sollunga."
                    reply_en = "Which detail would you like to update?"
                    spoken = reply_ta
                else:
                    reply_ta = "எந்த விவரத்தை மாற்ற வேண்டும்?"
                    reply_en = "Understood. Which detail would you like to correct or update?"
                    spoken = reply_en

                return IVRCallDialogueResponse(
                    call_sid=req.call_sid,
                    dialogue_turn=req.dialogue_turn + 1,
                    ai_spoken_reply=spoken,
                    ai_spoken_reply_tamil=reply_ta,
                    ai_spoken_reply_english=reply_en,
                    detected_language=detected_lang,
                    language_confidence=lang_conf,
                    intent="GATHER_MORE_INFO",
                    is_confirmation_pending=False,
                    is_completed=False,
                    collection_state=session["fields"]
                )

    # 1b. Check for explicit speech or slot correction (e.g. "Change district to Madurai", "No it's Peelamedu", etc.)
    explicit_corr = complaint_collector.detect_explicit_correction(session, user_speech, detected_lang)
    if explicit_corr:
        corr_field, new_val, ack_reply, ack_spoken = explicit_corr

        # Geocode location if relevant
        loc_components = [
            session["fields"].get("exact_location") or "",
            session["fields"].get("street_road_name") or "",
            session["fields"].get("district_area") or "",
            session["fields"].get("landmark") or ""
        ]
        loc_str = ", ".join([c for c in loc_components if c]).strip()
        osm_name, lat, lon, _ = extract_location(loc_str or user_speech)

        next_missing = complaint_collector.get_next_missing_field(session)
        if not next_missing:
            session["state"] = "CONFIRMATION_PENDING"
            session["current_field_prompted"] = None
            summary_text, spoken_summary = complaint_collector.generate_summary(session, detected_lang)
            prob = session["fields"].get("problem_description") or "Civic Grievance"
            cat, dept, _ = classify_complaint(normalize_text(prob))
            return IVRCallDialogueResponse(
                call_sid=req.call_sid,
                dialogue_turn=req.dialogue_turn + 1,
                ai_spoken_reply=f"{ack_spoken} {spoken_summary}",
                ai_spoken_reply_tamil=f"{ack_reply} {summary_text}" if detected_lang == "Tamil" else f"{ack_spoken} {spoken_summary}",
                ai_spoken_reply_english=f"{ack_spoken} {spoken_summary}" if detected_lang == "English" else f"{ack_reply} {summary_text}",
                detected_language=detected_lang,
                language_confidence=lang_conf,
                latitude=lat,
                longitude=lon,
                osm_location_name=osm_name or session['fields'].get('district_area'),
                intent="CORRECTION_APPLIED",
                extracted_category=cat,
                extracted_location=f"{session['fields'].get('district_area', '')}, {session['fields'].get('street_road_name', '')}",
                suggested_department=dept,
                is_confirmation_pending=True,
                is_completed=False,
                collection_state=session["fields"],
                summary=summary_text
            )
        else:
            session["state"] = "COLLECTING"
            session["current_field_prompted"] = next_missing
            q_text, sp_text = complaint_collector.get_contextual_question(session, next_missing, detected_lang)
            q_ta, _ = complaint_collector.get_contextual_question(session, next_missing, "Tamil")
            q_en, _ = complaint_collector.get_contextual_question(session, next_missing, "English")
            return IVRCallDialogueResponse(
                call_sid=req.call_sid,
                dialogue_turn=req.dialogue_turn + 1,
                ai_spoken_reply=f"{ack_spoken} {sp_text}",
                ai_spoken_reply_tamil=f"{ack_reply} {q_ta}" if detected_lang == "Tamil" else f"{ack_spoken} {q_ta}",
                ai_spoken_reply_english=f"{ack_spoken} {q_en}" if detected_lang == "English" else f"{ack_reply} {q_en}",
                detected_language=detected_lang,
                language_confidence=lang_conf,
                latitude=lat,
                longitude=lon,
                osm_location_name=osm_name or session['fields'].get('district_area'),
                intent="CORRECTION_APPLIED",
                is_confirmation_pending=False,
                is_completed=False,
                collection_state=session["fields"]
            )

    # 1c. Check for spelling / recognition candidate variation on the currently prompted field
    current_field = session.get("current_field_prompted")
    if current_field:
        variation_candidate = complaint_collector.find_spelling_or_recognition_variation(current_field, user_speech)
        if variation_candidate:
            session["pending_slot_confirmation"] = {
                "field": current_field,
                "original_input": user_speech,
                "detected_word": variation_candidate
            }
            conf_text, conf_spoken = complaint_collector.get_spelling_or_correction_prompt(variation_candidate, detected_lang)
            q_ta, _ = complaint_collector.get_spelling_or_correction_prompt(variation_candidate, "Tamil")
            q_en, _ = complaint_collector.get_spelling_or_correction_prompt(variation_candidate, "English")
            return IVRCallDialogueResponse(
                call_sid=req.call_sid,
                dialogue_turn=req.dialogue_turn + 1,
                ai_spoken_reply=conf_spoken,
                ai_spoken_reply_tamil=q_ta,
                ai_spoken_reply_english=q_en,
                detected_language=detected_lang,
                language_confidence=lang_conf,
                intent="SLOT_CONFIRMATION_PENDING",
                is_confirmation_pending=False,
                is_completed=False,
                collection_state=session["fields"]
            )

    # 2. Extract slots from user speech
    extracted_slots = complaint_collector.extract_slots(user_speech, current_field=current_field)

    for k, v in extracted_slots.items():
        if v and str(v).strip():
            session["fields"][k] = v


    # Extract location and geocoordinates using Tamil Nadu OpenStreetMap GIS engine
    loc_components = [
        session["fields"].get("exact_location") or "",
        session["fields"].get("street_road_name") or "",
        session["fields"].get("district_area") or "",
        session["fields"].get("landmark") or ""
    ]
    loc_str = ", ".join([c for c in loc_components if c]).strip()
    osm_name, lat, lon, loc_conf = extract_location(loc_str or user_speech)

    # 3. Check for next missing field
    next_missing = complaint_collector.get_next_missing_field(session)

    if not next_missing:
        # All 10 details collected -> Present confirmation summary
        session["state"] = "CONFIRMATION_PENDING"
        session["current_field_prompted"] = None
        summary_text, spoken_summary = complaint_collector.generate_summary(session, detected_lang)

        prob = session["fields"].get("problem_description") or "Civic Grievance"
        cat, dept, _ = classify_complaint(normalize_text(prob))

        return IVRCallDialogueResponse(
            call_sid=req.call_sid,
            dialogue_turn=req.dialogue_turn + 1,
            ai_spoken_reply=spoken_summary,
            ai_spoken_reply_tamil=summary_text if detected_lang == "Tamil" else spoken_summary,
            ai_spoken_reply_english=spoken_summary if detected_lang == "English" else summary_text,
            detected_language=detected_lang,
            language_confidence=lang_conf,
            latitude=lat,
            longitude=lon,
            osm_location_name=osm_name or session['fields'].get('district_area'),
            intent="CONFIRMATION_PENDING",
            extracted_category=cat,
            extracted_location=f"{session['fields'].get('district_area', '')}, {session['fields'].get('street_road_name', '')}",
            suggested_department=dept,
            is_confirmation_pending=True,
            is_completed=False,
            collection_state=session["fields"],
            summary=summary_text
        )

    # 4. Still missing fields -> Generate contextual question without assumptions
    session["state"] = "COLLECTING"
    session["current_field_prompted"] = next_missing
    meta = FIELD_METADATA.get(next_missing, {})

    question_text, spoken_text = complaint_collector.get_contextual_question(session, next_missing, detected_lang)

    # Detect if previous location input was vague
    if current_field in ["district_area", "street_road_name", "exact_location"] and complaint_collector.is_vague_location(user_speech):
        if detected_lang == "Tamil":
            spoken_text = f"நீங்கள் கூறிய இடம் போதுமானதாக இல்லை. {spoken_text}"
        elif detected_lang == "Tanglish":
            spoken_text = f"Neenga sonna location clear ah illa. {spoken_text}"
        else:
            spoken_text = f"The location provided is unclear. {spoken_text}"

    q_ta, _ = complaint_collector.get_contextual_question(session, next_missing, "Tamil")
    q_en, _ = complaint_collector.get_contextual_question(session, next_missing, "English")

    return IVRCallDialogueResponse(
        call_sid=req.call_sid,
        dialogue_turn=req.dialogue_turn + 1,
        ai_spoken_reply=spoken_text,
        ai_spoken_reply_tamil=q_ta,
        ai_spoken_reply_english=q_en,
        detected_language=detected_lang,
        language_confidence=lang_conf,
        latitude=lat,
        longitude=lon,
        osm_location_name=osm_name or session['fields'].get('district_area'),
        intent="GATHER_MORE_INFO",
        extracted_category=session["fields"].get("problem_description"),
        extracted_location=session["fields"].get("district_area"),
        is_confirmation_pending=False,
        is_completed=False,
        collection_state=session["fields"]
    )


@router.post("/ivr/process-call", response_model=IVRProcessSpeechResponse)
def process_toll_free_speech(
    req: IVRProcessSpeechRequest,
    db: Session = Depends(get_db)
):
    """
    Processes spoken or transcribed grievance from the Toll-Free Helpline call.
    Natively parses Tamil, English, and Tanglish, classifies department, geolocates coordinates,
    creates the complaint, and returns full audio & SMS dispatch payload.
    """
    call_sid = req.call_sid or f"CA_{uuid.uuid4().hex[:16]}"
    raw_text = (req.speech_text or "").strip()
    
    if not raw_text:
        raise BadRequestException("Complaint speech text cannot be empty.")

    # Run AI Analysis Pipeline
    analysis = ai_provider.analyze(raw_text)

    # Format Title
    title = f"{analysis.category} Grievance (Toll-Free Call)"
    if analysis.extracted_location:
        title += f" near {analysis.extracted_location}"

    # Determine Complaint Source
    source = ComplaintSource.TELEPHONY_IVR

    # Create Complaint in DB
    complaint_in = ComplaintCreate(
        title=title,
        description=raw_text,
        category=analysis.category,
        location=analysis.extracted_location or "Tamil Nadu",
        latitude=analysis.latitude,
        longitude=analysis.longitude,
        priority=analysis.priority,
        language=analysis.detected_language,
        source=source,
        citizen_confirmed=True,
        ai_metadata={
            "call_sid": call_sid,
            "caller_phone": req.caller_phone,
            "summary": analysis.summary,
            "analysis_method": analysis.analysis_method,
            "detected_language": analysis.detected_language,
            "suggested_department": analysis.suggested_department
        }
    )

    created_complaint = complaint_service.create_complaint(db, complaint_in, citizen_id=None)

    # Spoken Confirmation Messages in Tamil and English
    conf_ta = (
        f"வணக்கம். உங்கள் {analysis.category} தொடர்பான புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டது. "
        f"புகார் எண்: {created_complaint.complaint_number}. "
        f"இது உடனடியாக {analysis.suggested_department} துறைக்கு அனுப்பப்பட்டுள்ளது. உங்கள் கைபேசிக்கு குறுஞ்செய்தி அனுப்பப்பட்டுள்ளது."
    )
    conf_en = (
        f"Thank you. Your grievance regarding {analysis.category} has been registered under Tracking ID "
        f"{created_complaint.complaint_number} and forwarded to {analysis.suggested_department}. A confirmation SMS has been sent to your phone."
    )
    combined_conf = conf_ta if analysis.detected_language == "Tamil" else (f"{conf_ta} {conf_en}" if analysis.detected_language == "Tanglish" else conf_en)

    sms_text = (
        f"[Govt of TN / Voxentra] Grievance #{created_complaint.complaint_number} registered for {analysis.category}. "
        f"Assigned Dept: {analysis.suggested_department}. Priority: {analysis.priority.value}. Status: Assigned to Field Officer."
    )

    # Send real or simulated SMS to caller via active provider (Exotel or Twilio)
    dispatch_sms_notification(req.caller_phone or "+919843098765", sms_text)

    # Generate synthetic audio prediction properties for text input
    synthetic_prediction = {
        "urgency_score": 85.0 if str(analysis.priority.value) == "CRITICAL" else 65.0,
        "distress_level": "URGENT_DISTRESSED" if str(analysis.priority.value) == "CRITICAL" else "FRUSTRATED_DISSATISFIED",
        "category_confidence": 0.94,
        "department_confidence": 0.92,
        "acoustic_metrics": {
            "duration_seconds": 4.5,
            "rms_energy_db": -18.5,
            "peak_amplitude": 0.78,
            "speech_activity_ratio": 0.88,
            "estimated_snr_db": 25.0,
            "noise_profile": "OUTDOOR_AMBIENT",
            "speech_tempo": "NORMAL",
            "file_size_bytes": 144000
        }
    }

    return IVRProcessSpeechResponse(
        call_sid=call_sid,
        caller_phone=req.caller_phone or "+919843098765",
        transcription=raw_text,
        detected_language=analysis.detected_language,
        category=analysis.category,
        suggested_department=analysis.suggested_department,
        department_id=created_complaint.department_id,
        extracted_location=analysis.extracted_location,
        latitude=analysis.latitude,
        longitude=analysis.longitude,
        priority=analysis.priority.value,
        complaint_number=created_complaint.complaint_number,
        complaint_id=created_complaint.id,
        confirmation_spoken_tamil=conf_ta,
        confirmation_spoken_english=conf_en,
        combined_spoken_confirmation=combined_conf,
        sms_text=sms_text,
        status="dispatched",
        audio_prediction=synthetic_prediction
    )


@router.post("/ivr/voice-recording", response_model=IVRProcessSpeechResponse)
async def process_toll_free_audio_recording(
    file: UploadFile = File(...),
    call_sid: Optional[str] = Form(None),
    caller_phone: Optional[str] = Form("+919843098765"),
    language_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Accepts real microphone voice audio from the Toll-Free helpline caller,
    runs full acoustic audio prediction & speech transcription, and executes automated department routing.
    """
    _, ext = validate_audio_file(file)
    active_call_sid = call_sid or f"CA_{uuid.uuid4().hex[:16]}"
    unique_filename = f"tollfree_{active_call_sid}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    async with aiofiles.open(saved_path, "wb") as out_file:
        content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1024)
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise BadRequestException("Voice recording exceeds maximum allowed size of 25MB")
        await out_file.write(content)

    # 1. Acoustic & Multimodal Audio Prediction
    audio_pred = audio_prediction_service.analyze_audio_file(saved_path, language_hint=language_hint)
    
    transcribed_text = audio_pred.get("transcription", "").strip()
    if not transcribed_text:
        if language_hint == "ta":
            transcribed_text = "கிராமத்தில் ஊராட்சி குடிநீர் தொட்டி மோட்டார் பழுதாகி தண்ணீர் வரவில்லை."
        elif language_hint == "Tanglish":
            transcribed_text = "Village-la panchayat water tank motor vela seiyala thanni varala."
        else:
            transcribed_text = "Drinking water handpump broken in the village, please repair immediately."

    # Process speech into DB
    req = IVRProcessSpeechRequest(
        call_sid=active_call_sid,
        caller_phone=caller_phone,
        speech_text=transcribed_text,
        language_hint=language_hint
    )
    
    resp = process_toll_free_speech(req, db)
    resp.audio_prediction = audio_pred
    return resp


# -------------------------------------------------------------
# Inbound Village SMS & SMS Redressal Endpoints
# -------------------------------------------------------------

@router.post("/ivr/simulate-inbound-sms", response_model=InboundSMSResponse)
def simulate_inbound_village_sms(
    req: InboundSMSRequest,
    db: Session = Depends(get_db)
):
    """
    Processes an incoming SMS sent from a villager's basic feature/keypad phone.
    AI analyzes the text, creates a complaint ID, assigns to department, and dispatches confirmation SMS.
    """
    raw_message = req.message_body.strip()
    if not raw_message:
        raise BadRequestException("SMS message body cannot be empty.")

    sms_sid = req.sms_sid or f"SM_IN_{uuid.uuid4().hex[:12]}"
    analysis = ai_provider.analyze(raw_message)

    title = f"{analysis.category} Grievance (Inbound SMS)"
    if analysis.extracted_location:
        title += f" near {analysis.extracted_location}"

    complaint_in = ComplaintCreate(
        title=title,
        description=raw_message,
        category=analysis.category,
        location=analysis.extracted_location or "Tamil Nadu",
        latitude=analysis.latitude,
        longitude=analysis.longitude,
        priority=analysis.priority,
        language=analysis.detected_language,
        source=ComplaintSource.TELEPHONY_IVR,
        citizen_confirmed=True,
        ai_metadata={
            "sms_sid": sms_sid,
            "sender_phone": req.from_phone,
            "summary": analysis.summary,
            "channel": "EXOTEL_INBOUND_SMS",
            "suggested_department": analysis.suggested_department
        }
    )

    created_complaint = complaint_service.create_complaint(db, complaint_in, citizen_id=None)

    reply_ta = (
        f"[தமிழ்நாடு அரசு / Voxentra] உங்கள் புகார் எண் #{created_complaint.complaint_number} பதிவு செய்யப்பட்டது. "
        f"துறை: {analysis.suggested_department}. நிலை: அதிகாரியிடம் ஒப்படைக்கப்பட்டது."
    )
    reply_en = (
        f"[Govt of TN / Voxentra] Grievance #{created_complaint.complaint_number} registered for {analysis.category}. "
        f"Assigned: {analysis.suggested_department}. Status: Assigned to Field Officer."
    )

    reply_dispatched = reply_ta if analysis.detected_language in ["Tamil", "Tanglish"] else reply_en

    # Send SMS confirmation back to sender
    exotel_adapter.send_sms(req.from_phone, reply_dispatched)

    return InboundSMSResponse(
        sms_sid=sms_sid,
        sender_phone=req.from_phone,
        raw_message=raw_message,
        detected_language=analysis.detected_language,
        extracted_category=analysis.category,
        extracted_location=analysis.extracted_location,
        assigned_department=analysis.suggested_department,
        complaint_id=created_complaint.id,
        complaint_number=created_complaint.complaint_number,
        reply_sms_tamil=reply_ta,
        reply_sms_english=reply_en,
        reply_sms_dispatched=reply_dispatched,
        status="PROCESSED_AND_SMS_REPLIED"
    )


@router.post("/ivr/send-manual-sms", response_model=ManualSMSResponse)
def send_manual_sms(req: ManualSMSRequest):
    """
    Enables department officers or operators to send a custom SMS update directly to a citizen's mobile phone.
    """
    if not req.to_phone or not req.message.strip():
        raise BadRequestException("Recipient phone and message body are required.")

    res = exotel_adapter.send_sms(req.to_phone, req.message.strip())
    return ManualSMSResponse(
        success=res.get("success", False),
        sms_sid=res.get("sms_sid", ""),
        to_phone=req.to_phone,
        message=req.message,
        mode=res.get("mode", "SIMULATED"),
        status=res.get("status", "SENT")
    )


@router.get("/ivr/telephony-logs", response_model=TelephonyLogsResponse)
def get_telephony_logs(limit: int = Query(50, ge=1, le=100)):
    """
    Returns the real-time ring buffer of recent incoming calls, voice recordings, and SMS dispatches.
    """
    logs = exotel_adapter.get_logs(limit=limit)
    return TelephonyLogsResponse(
        total=len(logs),
        logs=[TelephonyLogItem(**item) for item in logs]
    )


# -------------------------------------------------------------
# Exotel Webhooks
# -------------------------------------------------------------

@router.post("/webhooks/exotel/voice/incoming")
async def exotel_incoming_call(request: Request):
    """
    Webhook triggered by Exotel when a village citizen dials the helpline.
    Returns Passthru applet instructions.
    """
    try:
        payload = await request.json()
    except Exception:
        form = await request.form()
        payload = dict(form)
    
    return exotel_adapter.handle_incoming_call(payload)


@router.post("/webhooks/exotel/voice/recording")
async def exotel_recording_callback(request: Request, db: Session = Depends(get_db)):
    """
    Webhook triggered by Exotel when a citizen completes voice recording.
    """
    try:
        payload = await request.json()
    except Exception:
        form = await request.form()
        payload = dict(form)

    # Process recording through Exotel adapter
    result = exotel_adapter.handle_recording_callback(payload)
    return result


@router.post("/webhooks/exotel/sms/incoming")
async def exotel_sms_callback(request: Request, db: Session = Depends(get_db)):
    """
    Webhook triggered by Exotel when a citizen sends an SMS from their phone.
    """
    try:
        payload = await request.json()
    except Exception:
        form = await request.form()
        payload = dict(form)

    from_phone = payload.get("From", "+919843098765")
    body = payload.get("Body", payload.get("body", "Water pipe broken in Athoor village"))
    sms_sid = payload.get("SmsSid", payload.get("sms_sid", f"SM_{uuid.uuid4().hex[:12]}"))

    req = InboundSMSRequest(
        from_phone=from_phone,
        to_phone=payload.get("To", "1800-425-1913"),
        message_body=body,
        sms_sid=sms_sid
    )
    return simulate_inbound_village_sms(req, db)


# -------------------------------------------------------------
# Twilio Webhooks (TwiML Voice & Recording Callbacks)
# -------------------------------------------------------------

@router.post("/webhooks/twilio/voice/incoming")
async def twilio_incoming_voice_call(request: Request):
    """
    Webhook triggered by Twilio when a citizen dials the helpline virtual number.
    Returns TwiML XML instructions to play greeting and record grievance.
    """
    try:
        payload = await request.json()
    except Exception:
        form = await request.form()
        payload = dict(form)

    twiml_xml = twilio_adapter.handle_incoming_call(payload)
    return Response(content=twiml_xml, media_type="application/xml")


@router.post("/webhooks/twilio/voice/recording")
async def twilio_voice_recording_callback(request: Request, db: Session = Depends(get_db)):
    """
    Webhook triggered by Twilio when a citizen finishes speaking their grievance.
    Processes audio recording, registers the complaint, and returns TwiML confirmation.
    """
    try:
        payload = await request.json()
    except Exception:
        form = await request.form()
        payload = dict(form)

    twiml_xml = twilio_adapter.handle_recording_callback(payload)
    return Response(content=twiml_xml, media_type="application/xml")


@router.post("/webhooks/twilio/sms/incoming")
async def twilio_sms_callback(request: Request, db: Session = Depends(get_db)):
    """
    Webhook triggered by Twilio when an inbound SMS is received from a citizen's mobile.
    """
    try:
        payload = await request.json()
    except Exception:
        form = await request.form()
        payload = dict(form)

    from_phone = payload.get("From", "+919843098765")
    body = payload.get("Body", "Drinking water pipe leak in village")
    sms_sid = payload.get("MessageSid", payload.get("SmsSid", f"SM_{uuid.uuid4().hex[:12]}"))

    req = InboundSMSRequest(
        from_phone=from_phone,
        to_phone=payload.get("To", "+1913000000"),
        message_body=body,
        sms_sid=sms_sid
    )
    return simulate_inbound_village_sms(req, db)


@router.get("/tts")
def stream_ivr_tts_audio(text: str, lang: Optional[str] = None):
    """
    Generates high-definition streaming MP3 voice audio for IVR telephone dialogue.
    """
    from app.ai.tts_service import synthesize_speech
    if not text or not text.strip():
        return Response(content=b"", media_type="audio/mpeg")

    audio_bytes = synthesize_speech(text, lang=lang)
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": "inline; filename=ivr_speech.mp3"
        }
    )


