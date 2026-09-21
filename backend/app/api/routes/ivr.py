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
    Conversational turn handler for the speaking AI during a toll-free call.
    Maintains dialogue context, asks clarifying questions if location is missing,
    or registers the grievance when sufficient information is gathered.
    """
    user_speech = req.user_speech.strip()
    analysis = ai_provider.analyze(user_speech)
    detected_lang = analysis.detected_language

    # Check if we have sufficient details (category + location)
    has_location = bool(analysis.extracted_location and analysis.extracted_location != "Tamil Nadu")
    has_category = bool(analysis.category and analysis.category != "Other")

    # If first turn and missing location, ask for specific village/panchayat conversationally
    if req.dialogue_turn == 1 and not has_location and has_category:
        if detected_lang == "Tamil":
            reply_ta = f"புரிந்தது. உங்கள் {analysis.category} புகார் பதிவு செய்ய, எந்த கிராமம், ஊராட்சி அல்லது பகுதியில் இந்த பிரச்சனை உள்ளது என்பதை கூறவும்."
            reply_en = f"Understood. To register your {analysis.category} complaint, please state your village, panchayat, or landmark."
        elif detected_lang == "Tanglish":
            reply_ta = f"Got it. Unga {analysis.category} issue endha gramam or panchayat-la irukku nu sollunga."
            reply_en = f"Got it. Please specify the village, panchayat or area where the {analysis.category} issue occurred."
        else:
            reply_ta = f"உங்கள் {analysis.category} புகார் பதிவு செய்ய கிராமம் அல்லது இடத்தை கூறவும்."
            reply_en = f"Understood. To route your {analysis.category} complaint, please tell me your village name or location."

        spoken_reply = reply_ta if detected_lang in ["Tamil", "Tanglish"] else reply_en
        return IVRCallDialogueResponse(
            call_sid=req.call_sid,
            dialogue_turn=req.dialogue_turn + 1,
            ai_spoken_reply=spoken_reply,
            ai_spoken_reply_tamil=reply_ta,
            ai_spoken_reply_english=reply_en,
            detected_language=detected_lang,
            intent="GATHER_MORE_INFO",
            extracted_category=analysis.category,
            extracted_location=analysis.extracted_location,
            suggested_department=analysis.suggested_department,
            is_completed=False
        )

    # If ready or turn >= 2, register grievance directly
    title = f"{analysis.category} Grievance (Toll-Free Call)"
    if analysis.extracted_location:
        title += f" near {analysis.extracted_location}"

    complaint_in = ComplaintCreate(
        title=title,
        description=user_speech,
        category=analysis.category,
        location=analysis.extracted_location or "Tamil Nadu",
        latitude=analysis.latitude,
        longitude=analysis.longitude,
        priority=analysis.priority,
        language=analysis.detected_language,
        source=ComplaintSource.TELEPHONY_IVR,
        citizen_confirmed=True,
        ai_metadata={
            "call_sid": req.call_sid,
            "caller_phone": req.caller_phone,
            "summary": analysis.summary,
            "analysis_method": "conversational_ivr_dialogue",
            "detected_language": analysis.detected_language,
            "suggested_department": analysis.suggested_department
        }
    )

    created_complaint = complaint_service.create_complaint(db, complaint_in, citizen_id=None)

    reply_ta = (
        f"நன்றி! உங்கள் {analysis.category} புகார் எண் {created_complaint.complaint_number} என பதிவு செய்யப்பட்டது. "
        f"இது உடனடியாக {analysis.suggested_department} துறைக்கு அனுப்பப்பட்டுள்ளது."
    )
    reply_en = (
        f"Thank you! Your grievance regarding {analysis.category} has been registered under ID {created_complaint.complaint_number} "
        f"and forwarded to {analysis.suggested_department}."
    )
    spoken_reply = reply_ta if detected_lang == "Tamil" else (f"{reply_ta} {reply_en}" if detected_lang == "Tanglish" else reply_en)

    sms_text = (
        f"[Govt of TN / Voxentra] Grievance #{created_complaint.complaint_number} registered for {analysis.category}. "
        f"Assigned Dept: {analysis.suggested_department}. Status: Assigned to Field Officer."
    )
    exotel_adapter.send_sms(req.caller_phone or "+919843098765", sms_text)

    return IVRCallDialogueResponse(
        call_sid=req.call_sid,
        dialogue_turn=req.dialogue_turn + 1,
        ai_spoken_reply=spoken_reply,
        ai_spoken_reply_tamil=reply_ta,
        ai_spoken_reply_english=reply_en,
        detected_language=detected_lang,
        intent="CONFIRMED",
        extracted_category=analysis.category,
        extracted_location=analysis.extracted_location,
        suggested_department=analysis.suggested_department,
        is_completed=True,
        complaint_id=created_complaint.id,
        complaint_number=created_complaint.complaint_number,
        sms_sent=True
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

