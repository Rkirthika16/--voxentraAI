# type: ignore
import os
import re
import uuid
import json
import base64
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Request, Response, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.models.ivr import IVRSession, IVRMessage, IVRState
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintSource
from app.models.department import Department
from app.services.conversation_manager import conversation_manager
from app.services.question_manager import question_manager
from app.services.location_resolver import location_resolver
from app.services.complaint_service import complaint_service
from app.ai.speech_service import speech_service
from app.ai.normalization_service import normalize_text, clean_transcription
from app.ai.language_service import detect_language
from app.ai.tts_service import synthesize_speech
from app.integrations.telephony.twilio_adapter import twilio_adapter
from app.integrations.telephony.exotel_adapter import exotel_adapter

logger = logging.getLogger("voxentra.telephony.routes")

router = APIRouter(prefix="/telephony", tags=["Real Telephony Helpline Integration"])

# In-memory storage for synthesized telephony audio payloads
TELEPHONY_AUDIO_CACHE: Dict[str, bytes] = {}
# Idempotency response cache for webhook retries (CallSid -> Response XML/JSON)
TELEPHONY_IDEMPOTENCY_CACHE: Dict[str, Dict[str, Any]] = {}


def _get_base_url(request: Request) -> str:
    """Resolves public base HTTPS URL for telephony provider audio callbacks."""
    configured_base = (settings.VOICE_REGISTER_BASE_URL or "").strip().rstrip("/")
    if configured_base and not configured_base.startswith("http://localhost") and not configured_base.startswith("http://127.0.0.1"):
        return configured_base

    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:8000"
    proto = request.headers.get("x-forwarded-proto") or ("https" if request.url.scheme == "https" else "http")
    return f"{proto}://{host}"


def _format_complaint_id_for_speech(complaint_number: str, lang: str = "Tamil") -> str:
    """
    Spaces out complaint ID characters and digits so telephone TTS clearly
    enunciates the code over mobile / keypad phone networks.
    Example: 'VX-20261026-000042' -> 'V X, 2 0 2 6 1 0 2 6, 0 0 0 0 4 2'
    """
    if not complaint_number:
        return ""
    
    parts = complaint_number.split("-")
    spaced_parts = []
    for part in parts:
        spaced_parts.append(" ".join(list(part)))
    return ", ".join(spaced_parts)


@router.get("/audio/{audio_id}")
@router.get("/audio/{audio_id}.mp3")
def get_telephony_audio(audio_id: str):
    """
    Serves dynamic synthesized MP3 audio files to telephony carriers (Twilio/Exotel)
    for playback through the caller's phone speaker.
    """
    clean_id = audio_id.replace(".mp3", "").replace(".wav", "")
    audio_bytes = TELEPHONY_AUDIO_CACHE.get(clean_id)
    if not audio_bytes:
        # Fallback silent audio
        audio_bytes = synthesize_speech("Hello", lang="en")

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": f"inline; filename={clean_id}.mp3"
        }
    )


@router.post("/voice/incoming")
@router.post("/voice/answer")
async def handle_inbound_telephone_call(request: Request, db: Session = Depends(get_db)):
    """
    Webhook triggered by programmable telephony carrier (Twilio/Exotel) when an ordinary
    mobile or keypad phone dials the helpline number.
    MANDATORY OBJECTIVE: AI MUST NOT speak first. Call starts in silent listening mode.
    """
    # 1. Parse payload (supports Form-data and JSON)
    form_data = {}
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            form_data = await request.json()
        else:
            raw_form = await request.form()
            form_data = dict(raw_form)
    except Exception:
        pass

    call_sid = form_data.get("CallSid") or form_data.get("session_id") or f"CA_{uuid.uuid4().hex[:16]}"
    caller_phone = form_data.get("From") or form_data.get("caller_phone") or "+919843098765"
    to_number = form_data.get("To") or settings.TELEPHONY_CALLER_ID or "1800-425-1913"

    # 2. Webhook Signature Validation (if configured)
    signature = request.headers.get("X-Twilio-Signature")
    if settings.TELEPHONY_WEBHOOK_VALIDATE_SIGNATURE and signature:
        full_url = str(request.url)
        if not twilio_adapter.validate_signature(full_url, form_data, signature):
            logger.warning(f"[Telephony] Signature verification failed for call {call_sid}")
            return Response(content="Forbidden: Invalid Signature", status_code=403)

    logger.info(f"[Telephony] Real Inbound Call connected: {caller_phone} -> {to_number} (CallSid: {call_sid})")

    # 3. Create or locate IVRSession in database
    session = db.query(IVRSession).filter(IVRSession.session_id == call_sid).first()
    if not session:
        session, _, _ = conversation_manager.create_session(
            db=db,
            caller_phone=caller_phone,
            language_preference="Auto"
        )
        session.session_id = call_sid
        db.commit()

    base_url = _get_base_url(request)
    turn_action_url = f"{base_url}/api/v1/telephony/voice/turn"

    # Check provider type
    provider = settings.TELEPHONY_PROVIDER.lower()
    if provider == "exotel":
        passthru = exotel_adapter.build_silent_passthru(callback_url=turn_action_url)
        passthru["call_sid"] = call_sid
        return passthru

    # Default Twilio TwiML
    stream_url = None
    if settings.TELEPHONY_STREAM_URL:
        stream_url = settings.TELEPHONY_STREAM_URL
        if stream_url.startswith("/"):
            ws_proto = "wss" if base_url.startswith("https") else "ws"
            ws_host = base_url.replace("https://", "").replace("http://", "")
            stream_url = f"{ws_proto}://{ws_host}{stream_url}"

    twiml = twilio_adapter.build_silent_answer_twiml(
        turn_action_url=turn_action_url,
        stream_url=stream_url
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/turn")
async def handle_telephone_dialogue_turn(request: Request, db: Session = Depends(get_db)):
    """
    Core two-way conversational voice turn endpoint.
    Receives caller speech from telephony provider (<Gather input="speech"> or SpeechResult),
    runs speech cleaning, language detection, location resolution, updates memory, and returns
    synthesized natural audio prompt with TwiML instructions.
    """
    form_data = {}
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            form_data = await request.json()
        else:
            raw_form = await request.form()
            form_data = dict(raw_form)
    except Exception:
        pass

    call_sid = form_data.get("CallSid") or form_data.get("session_id") or request.query_params.get("session_id")
    raw_speech = form_data.get("SpeechResult") or form_data.get("user_speech") or form_data.get("speech_text") or ""
    is_timeout = form_data.get("timeout") == "true" or request.query_params.get("timeout") == "true"
    digits = form_data.get("Digits") or ""
    caller_phone = form_data.get("From") or "+919843098765"

    base_url = _get_base_url(request)
    turn_action_url = f"{base_url}/api/v1/telephony/voice/turn"

    # Check for idempotency: if webhook is retried for an already-completed call, return cached TwiML
    if call_sid and call_sid in TELEPHONY_IDEMPOTENCY_CACHE:
        cached = TELEPHONY_IDEMPOTENCY_CACHE[call_sid]
        logger.info(f"[Telephony Idempotency] Returning cached response for CallSid {call_sid}")
        return Response(content=cached["twiml"], media_type="application/xml")

    # Locate session
    session = None
    if call_sid:
        session = db.query(IVRSession).filter(
            (IVRSession.session_id == call_sid) | (IVRSession.session_id.contains(call_sid))
        ).first()

    if not session:
        session, _, _ = conversation_manager.create_session(
            db=db,
            caller_phone=caller_phone,
            language_preference="Auto"
        )
        if call_sid:
            session.session_id = call_sid
        db.commit()

    memory = dict(session.structured_memory or {})
    silence_count = memory.get("silence_retries", 0)

    # 4. Handle Silence / Speech Timeout
    if (not raw_speech.strip() and not digits.strip()) or is_timeout:
        silence_count += 1
        memory["silence_retries"] = silence_count
        session.structured_memory = memory
        db.commit()

        lang = session.language if session.language not in ["Auto", None] else "Tamil"

        if silence_count < settings.TELEPHONY_MAX_SILENCE_RETRIES:
            if lang == "Tamil":
                silence_msg = "வணக்கம், நீங்கள் பேசுவது கேட்கவில்லை. உங்கள் கிராம அல்லது நகராட்சி புகாரைக் கூறுங்கள்."
            elif lang == "Tanglish":
                silence_msg = "Vanakkam, voice kekkala. Unga problem enna nu sollunga."
            else:
                silence_msg = "Sorry, I could not hear you. Please state your complaint or village problem."

            audio_id = f"silence_{uuid.uuid4().hex[:8]}"
            audio_bytes = synthesize_speech(silence_msg, lang=lang)
            TELEPHONY_AUDIO_CACHE[audio_id] = audio_bytes
            play_url = f"{base_url}/api/v1/telephony/audio/{audio_id}.mp3"

            twiml = twilio_adapter.build_turn_twiml(play_audio_url=play_url, turn_action_url=turn_action_url)
            return Response(content=twiml, media_type="application/xml")
        else:
            # Silence retries exceeded: politely end call
            if lang == "Tamil":
                hangup_msg = "உங்களிடமிருந்து எந்த பதிலும் பெறப்படவில்லை. அழைப்பு துண்டிக்கப்படுகிறது. நன்றி!"
            elif lang == "Tanglish":
                hangup_msg = "Response varala. Call end pannuroam. Nandri!"
            else:
                hangup_msg = "No response was detected. Ending call now. Thank you!"

            audio_id = f"hangup_{uuid.uuid4().hex[:8]}"
            audio_bytes = synthesize_speech(hangup_msg, lang=lang)
            TELEPHONY_AUDIO_CACHE[audio_id] = audio_bytes
            play_url = f"{base_url}/api/v1/telephony/audio/{audio_id}.mp3"

            twiml = twilio_adapter.build_completion_twiml(play_audio_url=play_url)
            return Response(content=twiml, media_type="application/xml")

    # Citizen spoke: reset silence counter
    memory["silence_retries"] = 0
    session.structured_memory = memory
    db.commit()

    speech_input = raw_speech.strip() if raw_speech.strip() else digits.strip()

    # 5. Process turn with ConversationManager
    mem_before = session.structured_memory or {}
    has_prob_before = bool(mem_before.get("problem_description") or mem_before.get("problem"))
    has_loc_before = bool(mem_before.get("area") or mem_before.get("district_area") or mem_before.get("street") or mem_before.get("location"))
    is_dec, is_conf = conversation_manager._is_confirmation_response(speech_input)
    if is_dec and is_conf and has_prob_before and has_loc_before:
        session.state = IVRState.CONFIRMATION.value
        db.commit()

    turn_res = conversation_manager.process_citizen_turn(
        db=db,
        session_id=session.session_id,
        speech_text=speech_input
    )

    t_lang = turn_res.get("detected_language") or session.language or "Tamil"
    spoken_text = turn_res.get("spoken_reply") or turn_res.get("ai_reply") or ""

    # Refresh session memory after turn processing
    db.refresh(session)
    mem_after = session.structured_memory or {}
    has_problem = bool(mem_after.get("problem_description") or mem_after.get("problem"))
    has_area = bool(mem_after.get("area") or mem_after.get("district_area"))
    has_street = bool(mem_after.get("street") or mem_after.get("street_road_name"))
    has_duration = bool(mem_after.get("duration") or mem_after.get("start_time"))
    has_scope = bool(mem_after.get("affected_scope") or mem_after.get("affected_area"))
    all_core_fields = has_problem and has_area and has_street and has_duration and has_scope

    # If caller confirmed during this turn and complaint was not created yet, finalize now
    if is_dec and is_conf and (session.state == IVRState.CONFIRMATION.value or all_core_fields) and not turn_res.get("complaint_created"):
        turn_res = conversation_manager.finalize_and_register_complaint(db, session)

    # If all core details are collected and not yet confirmed, present confirmation summary
    elif all_core_fields and not turn_res.get("complaint_created") and session.state != IVRState.CONFIRMATION.value:
        session.state = IVRState.CONFIRMATION.value
        session.current_field_prompted = None
        db.commit()
        summary_text, spoken_summary = question_manager.build_confirmation_summary(mem_after, t_lang)
        conversation_manager._save_ai_message(db, session, summary_text, spoken_summary, t_lang)
        spoken_text = spoken_summary

    # 6. Check if Complaint Was Successfully Registered
    if turn_res.get("complaint_created"):
        complaint_number = turn_res.get("complaint_number", "")
        spaced_id = _format_complaint_id_for_speech(complaint_number, t_lang)

        # Build clear voice announcement with spaced complaint ID
        if t_lang == "Tamil":
            announcement = (
                f"நன்றி! உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டது. "
                f"உங்கள் புகார் எண்: {spaced_id}. "
                f"புகார் விவரங்கள் எஸ்.எம்.எஸ் மூலம் அனுப்பப்பட்டுள்ளது. உரிய நடவடிக்கை எடுக்கப்படும்."
            )
        elif t_lang == "Tanglish":
            announcement = (
                f"Thank you! Unga complaint successfully register aayiduchu. "
                f"Unga Complaint ID: {spaced_id}. "
                f"Details SMS-la anupiyachu. Department udane action edupaanga."
            )
        else:
            announcement = (
                f"Thank you! Your complaint has been registered successfully. "
                f"Your complaint tracking ID is: {spaced_id}. "
                f"Confirmation SMS has been sent to your phone. Our officers will take action shortly."
            )

        audio_id = f"confirm_final_{uuid.uuid4().hex[:8]}"
        audio_bytes = synthesize_speech(announcement, lang=t_lang)
        TELEPHONY_AUDIO_CACHE[audio_id] = audio_bytes
        play_url = f"{base_url}/api/v1/telephony/audio/{audio_id}.mp3"

        twiml = twilio_adapter.build_completion_twiml(play_audio_url=play_url)

        # Cache for idempotency against webhook retries
        TELEPHONY_IDEMPOTENCY_CACHE[session.session_id] = {
            "complaint_number": complaint_number,
            "twiml": twiml,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        return Response(content=twiml, media_type="application/xml")

    # 7. Intermediate Turn: Follow-up Question or Confirmation Summary
    audio_id = f"turn_{uuid.uuid4().hex[:8]}"
    audio_bytes = synthesize_speech(spoken_text, lang=t_lang)
    TELEPHONY_AUDIO_CACHE[audio_id] = audio_bytes
    play_url = f"{base_url}/api/v1/telephony/audio/{audio_id}.mp3"

    twiml = twilio_adapter.build_turn_twiml(play_audio_url=play_url, turn_action_url=turn_action_url)
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/recording")
async def handle_telephone_recording_callback(request: Request, db: Session = Depends(get_db)):
    """
    Webhook triggered when citizen finishes an audio recording turn via telephony provider.
    Transcribes audio with Whisper and continues the dialogue turn loop.
    """
    form_data = {}
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            form_data = await request.json()
        else:
            raw_form = await request.form()
            form_data = dict(raw_form)
    except Exception:
        pass

    call_sid = form_data.get("CallSid") or form_data.get("session_id")
    recording_url = form_data.get("RecordingUrl") or ""
    caller_phone = form_data.get("From") or "+919843098765"

    transcription = ""
    # Download and transcribe recording if recording URL is provided
    if recording_url:
        try:
            import httpx
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(recording_url)
                if resp.status_code == 200:
                    temp_dir = os.path.join(settings.UPLOAD_DIR, "telephony_recordings")
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_wav = os.path.join(temp_dir, f"{call_sid}_{uuid.uuid4().hex[:6]}.wav")
                    with open(temp_wav, "wb") as f_out:
                        f_out.write(resp.content)
                    stt = speech_service.transcribe(temp_wav)
                    transcription = (stt.get("transcription") or "").strip()
                    if os.path.exists(temp_wav):
                        try:
                            os.remove(temp_wav)
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"[Telephony] Error processing recording {recording_url}: {e}")

    # Fallback to existing transcription provided in webhook payload
    if not transcription:
        transcription = form_data.get("TranscriptionText") or ""

    form_data["SpeechResult"] = transcription
    return await handle_telephone_dialogue_turn(request, db)


@router.post("/voice/status")
async def handle_telephone_call_status(request: Request, db: Session = Depends(get_db)):
    """
    Status callback webhook from Telephony Providers (Twilio/Exotel).
    Updates session state upon call termination (completed, busy, failed, canceled).
    """
    form_data = {}
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            form_data = await request.json()
        else:
            raw_form = await request.form()
            form_data = dict(raw_form)
    except Exception:
        pass

    call_sid = form_data.get("CallSid") or form_data.get("session_id")
    status = (form_data.get("CallStatus") or form_data.get("status") or "completed").lower()
    duration = form_data.get("CallDuration") or form_data.get("duration")

    if call_sid:
        session = db.query(IVRSession).filter(
            (IVRSession.session_id == call_sid) | (IVRSession.session_id.contains(call_sid))
        ).first()
        if session:
            session.updated_at = datetime.now(timezone.utc)
            if status in ["completed", "busy", "no-answer", "failed", "canceled"]:
                session.ended_at = datetime.now(timezone.utc)
                if session.state != IVRState.COMPLETED.value:
                    session.state = "CALL_ENDED"
            db.commit()

    return {"success": True, "call_sid": call_sid, "status": status, "duration": duration}


@router.websocket("/voice/stream")
async def handle_telephony_websocket_stream(
    websocket: WebSocket,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Full-Duplex Twilio Media Stream WebSocket handler.
    Transfers 8kHz μ-law audio bidirectional stream for low-latency live calling.
    """
    from app.api.routes.ivr import ivr_telephony_websocket_stream
    await ivr_telephony_websocket_stream(websocket, session_id=session_id, db=db)


@router.get("/status")
def get_telephony_system_status():
    """
    Diagnostic status endpoint for Telephony integration, provider configuration,
    and webhook URLs.
    """
    provider = settings.TELEPHONY_PROVIDER.lower()
    twilio_ready = bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN)
    exotel_ready = bool(settings.EXOTEL_ACCOUNT_SID and settings.EXOTEL_API_KEY and settings.EXOTEL_API_TOKEN)

    return {
        "active_provider": provider,
        "configured": (twilio_ready if provider == "twilio" else exotel_ready if provider == "exotel" else True),
        "phone_number": settings.TWILIO_PHONE_NUMBER if provider == "twilio" else settings.EXOTEL_CALLER_ID or "1800-425-1913",
        "webhook_url": f"{settings.VOICE_REGISTER_BASE_URL}/api/v1/telephony/voice/incoming",
        "status_callback_url": f"{settings.VOICE_REGISTER_BASE_URL}/api/v1/telephony/voice/status",
        "turn_url": f"{settings.VOICE_REGISTER_BASE_URL}/api/v1/telephony/voice/turn",
        "audio_stream_url": f"{settings.VOICE_REGISTER_BASE_URL.replace('http', 'ws')}/api/v1/telephony/voice/stream",
        "signature_verification_active": settings.TELEPHONY_WEBHOOK_VALIDATE_SIGNATURE,
        "silence_retry_limit": settings.TELEPHONY_MAX_SILENCE_RETRIES,
        "providers": {
            "twilio": {
                "configured": twilio_ready,
                "phone_number": settings.TWILIO_PHONE_NUMBER
            },
            "exotel": {
                "configured": exotel_ready,
                "caller_id": settings.EXOTEL_CALLER_ID
            }
        }
    }


@router.get("/logs")
def get_telephony_recent_logs(limit: int = Query(50, ge=1, le=100)):
    """Returns combined recent inbound/outbound telephony logs."""
    logs = twilio_adapter.get_logs(limit=limit) + exotel_adapter.get_logs(limit=limit)
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"total": len(logs[:limit]), "logs": logs[:limit]}
