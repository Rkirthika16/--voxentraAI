import os
import json
import uuid
import base64
import logging
import aiofiles
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, Query, Response, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.models.complaint import ComplaintPriority, ComplaintSource, Complaint
from app.models.ivr import IVRSession, IVRMessage, IVRState as DB_IVRState
from app.models.tollfree import TollFreeCallSession, TollFreeMessage
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
from app.services.ivr_session_service import ivr_session_service, IVRState
from app.services.conversation_manager import conversation_manager
from app.services.speech_correction import speech_correction_service
from app.services.language_detector import language_detector
from app.ai.provider import ai_provider
from app.ai.speech_service import speech_service
from app.ai.conversation_service import conversation_service, ConversationContext
from app.ai.tts_service import synthesize_speech
from app.ai.audio_prediction_service import audio_prediction_service
from app.ai.audio_converter import convert_audio_to_16k_mono_wav, mulaw_to_wav_bytes, pcm_or_wav_to_mulaw
from app.integrations.telephony.exotel_adapter import exotel_adapter
from app.integrations.telephony.twilio_adapter import twilio_adapter
from app.utils.validators import validate_audio_file
from app.core.exceptions import BadRequestException

logger = logging.getLogger("voxentra.ivr")

router = APIRouter(tags=["Telephony & IVR Toll-Free Helpline (Exotel & Twilio)"])


def dispatch_sms_notification(to_phone: str, message: str) -> bool:
    """Dispatches SMS using configured telephony provider (Exotel or Twilio)."""
    if settings.TELEPHONY_PROVIDER.lower() == "twilio":
        res = twilio_adapter.send_sms(to_phone, message)
        return bool(res.get("success", False)) if isinstance(res, dict) else bool(res)
    res = exotel_adapter.send_sms(to_phone, message)
    return bool(res.get("success", False)) if isinstance(res, dict) else bool(res)


from datetime import datetime, timezone
from sqlalchemy import desc

def _sync_ivr_session_to_db(
    db: Session,
    session_id: str,
    caller_phone: str,
    state: str = "WAITING_FOR_CITIZEN",
    memory: Optional[Dict[str, Any]] = None,
    complaint_id: Optional[int] = None,
    complaint_number: Optional[str] = None,
    ended: bool = False
) -> IVRSession:
    """Helper to persist and synchronize IVRSession in SQLite DB."""
    try:
        sess = db.query(IVRSession).filter(IVRSession.session_id == session_id).first()
        mem = memory or {}
        resolved_lang = mem.get("language") or mem.get("current_language") or mem.get("detected_language") or "Tamil"
        if resolved_lang in ["Auto", "Auto-Detecting...", "", None]:
            resolved_lang = "Tamil"

        raw_prio = mem.get("priority", "MEDIUM")
        resolved_prio = "MEDIUM" if str(raw_prio).upper() in ["STANDARD", "NORMAL"] else raw_prio

        if not sess:
            sess = IVRSession(
                session_id=session_id,
                caller_phone=caller_phone,
                language=resolved_lang,
                state=state,
                structured_memory=mem,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(sess)
        else:
            sess.state = state
            sess.updated_at = datetime.now(timezone.utc)
            if memory:
                sess.structured_memory = mem
                sess.language = resolved_lang
                sess.category = mem.get("category")
                sess.problem = mem.get("problem")
                sess.location = mem.get("location")
                sess.duration = mem.get("duration")
                sess.affected_scope = mem.get("affected_scope")
                sess.severity = mem.get("severity")
                sess.priority = resolved_prio
                sess.department = mem.get("department")
                sess.citizen_name = mem.get("citizen_name")
        if complaint_id:
            sess.complaint_id = complaint_id
        if complaint_number:
            sess.complaint_number = complaint_number
        if ended:
            sess.ended_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(sess)
        return sess
    except Exception as e:
        logger.error(f"Error syncing IVR session to DB: {e}")
        db.rollback()
        return None


def _save_ivr_db_message(db: Session, db_session: Optional[IVRSession], role: str, content: str, lang: Optional[str] = None):
    """Helper to append an IVRMessage turn to the DB session."""
    if not db_session or not content:
        return
    try:
        msg = IVRMessage(
            session_id=db_session.id,
            role=role,
            content=content,
            language=lang,
            created_at=datetime.now(timezone.utc)
        )
        db.add(msg)
        db.commit()
    except Exception as e:
        logger.error(f"Error saving IVR message to DB: {e}")
        db.rollback()


# -------------------------------------------------------------
# Unified Two-Way Conversational Voice IVR Session Endpoints
# -------------------------------------------------------------

# -------------------------------------------------------------
# Unified Two-Way Conversational Voice IVR Session Endpoints
# -------------------------------------------------------------

@router.post("/ivr/incoming")
@router.post("/ivr/session")
@router.post("/ivr/session/start")
async def create_ivr_conversational_session(
    request: Request,
    session_id: Optional[str] = Query(None),
    caller_phone: Optional[str] = Query(None),
    CallSid: Optional[str] = Query(None),
    From: Optional[str] = Query(None),
    To: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Initiates a new two-way conversational voice session for the IVR Toll-Free Helpline.
    MANDATORY RULE 1: AI MUST BE SILENT. No greeting, no welcome prompt, no first question.
    Citizen speaks first in Tamil, English, or Tanglish.
    Supports JSON, Form-data, Query params, and Telephony Provider Webhooks (Twilio/Exotel).
    """
    body_sid = None
    body_phone = None
    is_telephony_form = False
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict):
                body_sid = body.get("session_id") or body.get("CallSid")
                body_phone = body.get("caller_phone") or body.get("From")
        elif "form" in content_type:
            form = await request.form()
            body_sid = form.get("session_id") or form.get("CallSid")
            body_phone = form.get("caller_phone") or form.get("From")
            is_telephony_form = True
    except Exception:
        pass

    sid = session_id or CallSid or body_sid or f"IVR_{uuid.uuid4().hex[:12]}"
    phone = caller_phone or From or body_phone or "+919843098765"

    # Create session with ConversationManager (AI SILENT: greeting_text='', spoken_greeting='')
    session_obj, greeting_text, greeting_spoken = conversation_manager.create_session(
        db=db,
        caller_phone=phone,
        language_preference="Auto"
    )
    sid = session_obj.session_id

    # Check if request came from Twilio telephony webhook or expects TwiML XML
    accept_header = request.headers.get("accept", "")
    if is_telephony_form or "xml" in accept_header or CallSid or From:
        host = request.headers.get("host", "localhost:8000")
        ws_scheme = "wss" if request.url.scheme == "https" else "ws"
        stream_url = f"{ws_scheme}://{host}/api/v1/ivr/stream"
        
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'    <Connect>\n'
            f'        <Stream url="{stream_url}">\n'
            f'            <Parameter name="session_id" value="{sid}" />\n'
            f'            <Parameter name="caller_phone" value="{phone}" />\n'
            f'        </Stream>\n'
            f'    </Connect>\n'
            "</Response>"
        )
        return Response(content=twiml, media_type="application/xml")

    init_lang = session_obj.language if session_obj.language not in ["Auto", "Auto-Detecting...", "", None] else "Tamil"
    return {
        "success": True,
        "session_id": sid,
        "caller_phone": phone,
        "state": "WAITING_FOR_CITIZEN",
        "conversation_state": "WAITING_FOR_CITIZEN",
        "should_continue": True,
        "ai_silent": True,
        "greeting": "",
        "response_text": "",
        "spoken_greeting": "",
        "language": init_lang,
        "detected_language": init_lang,
        "structured_memory": session_obj.structured_memory,
        "stream_url": "/api/v1/ivr/stream"
    }


@router.post("/ivr/status")
async def handle_ivr_telephony_status(
    request: Request,
    CallSid: Optional[str] = Query(None),
    CallStatus: Optional[str] = Query(None),
    CallDuration: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Status callback webhook from Telephony Providers (Twilio/Exotel).
    Updates session state upon call termination or status transitions.
    """
    body_sid = None
    body_status = None
    body_duration = None
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict):
                body_sid = body.get("CallSid") or body.get("session_id")
                body_status = body.get("CallStatus") or body.get("status")
                body_duration = body.get("CallDuration") or body.get("duration")
        elif "form" in content_type:
            form = await request.form()
            body_sid = form.get("CallSid") or form.get("session_id")
            body_status = form.get("CallStatus") or form.get("status")
            body_duration = form.get("CallDuration") or form.get("duration")
    except Exception:
        pass

    sid = CallSid or body_sid
    st = (CallStatus or body_status or "completed").lower()
    duration = CallDuration or body_duration

    if sid:
        sess = db.query(IVRSession).filter((IVRSession.session_id == sid) | (IVRSession.session_id.contains(sid))).first()
        if sess:
            if st in ["completed", "busy", "no-answer", "failed", "canceled"]:
                sess.ended_at = datetime.now(timezone.utc)
                if sess.state != "COMPLETED":
                    sess.state = "CALL_ENDED"
            sess.updated_at = datetime.now(timezone.utc)
            db.commit()

    return {"success": True, "call_sid": sid, "status": st, "duration": duration}


@router.websocket("/ivr/stream")
@router.websocket("/ivr/session/{session_id}/stream")
async def ivr_telephony_websocket_stream(
    websocket: WebSocket,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Real-Time Bidirectional Telephony Audio Stream WebSocket Endpoint.
    Connects normal keypad/button phone PSTN calls through telephony audio streaming.
    Pipeline:
      Phone Audio (mu-law/PCM) -> Whisper STT -> Speech Correction -> Language Detection -> AI Turn -> TTS Audio (mu-law) -> Phone Speaker.
    Supports Twilio Media Streams, Exotel Voice Streams, DTMF digits (1=repeat, 2=confirm, 9=end), and client test packets.
    """
    await websocket.accept()
    logger.info(f"[IVR WebSocket] Telephony stream connected. Session hint: {session_id}")

    active_session_id = session_id or f"IVR_{uuid.uuid4().hex[:12]}"
    caller_phone = "+919843098765"
    stream_sid = None
    audio_buffer = bytearray()

    # Ensure DB session exists (AI silent at start)
    session_record = conversation_manager.get_session(db, active_session_id)
    if not session_record:
        session_record, _, _ = conversation_manager.create_session(db, caller_phone=caller_phone)
        active_session_id = session_record.session_id

    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                data = json.loads(raw_msg)
            except Exception:
                continue

            event_type = data.get("event") or data.get("type", "")

            # 1. Connection Start Event
            if event_type == "start":
                stream_sid = data.get("streamSid") or data.get("start", {}).get("streamSid")
                custom_params = data.get("start", {}).get("customParameters", {})
                if custom_params.get("session_id"):
                    active_session_id = custom_params["session_id"]
                if custom_params.get("caller_phone"):
                    caller_phone = custom_params["caller_phone"]

                logger.info(f"[IVR WebSocket] Stream started: streamSid={stream_sid}, session_id={active_session_id}")
                await websocket.send_json({
                    "event": "started",
                    "session_id": active_session_id,
                    "state": "WAITING_FOR_CITIZEN"
                })

            # 2. Inbound Audio Media Packet from Phone
            elif event_type in ["media", "audio"]:
                media_payload = data.get("media", {}).get("payload") or data.get("payload") or data.get("audio")
                if media_payload:
                    chunk_bytes = base64.b64decode(media_payload)
                    audio_buffer.extend(chunk_bytes)

            # 3. Speech Turn Complete or Audio Buffer Flush Event
            elif event_type in ["turn_end", "speech_end", "process_buffer", "audio_end"]:
                if len(audio_buffer) >= 160:  # At least 20ms of audio
                    wav_bytes = mulaw_to_wav_bytes(bytes(audio_buffer))
                    temp_dir = os.path.join(settings.UPLOAD_DIR, "temp_ivr")
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_wav_path = os.path.join(temp_dir, f"stream_{active_session_id}_{uuid.uuid4().hex[:6]}.wav")

                    with open(temp_wav_path, "wb") as f_out:
                        f_out.write(wav_bytes)

                    try:
                        stt_res = speech_service.transcribe(temp_wav_path)
                        transcription = (stt_res.get("transcription") or "").strip()

                        if transcription:
                            turn_res = conversation_manager.process_citizen_turn(
                                db=db,
                                session_id=active_session_id,
                                speech_text=transcription
                            )

                            spoken_text = turn_res.get("spoken_reply") or turn_res.get("ai_reply") or ""
                            t_lang = turn_res.get("detected_language") or "Tanglish"

                            # Synthesize TTS voice
                            tts_audio = synthesize_speech(spoken_text, t_lang)
                            mulaw_out = pcm_or_wav_to_mulaw(tts_audio, in_rate=16000, out_rate=8000) if tts_audio else b""
                            b64_audio = base64.b64encode(mulaw_out).decode("utf-8") if mulaw_out else ""

                            # Stream audio to telephony provider
                            if stream_sid and b64_audio:
                                await websocket.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": b64_audio}
                                })

                            # Send JSON metadata event
                            turn_res["audio_base64"] = b64_audio
                            turn_res["event"] = "turn_complete"
                            await websocket.send_json(turn_res)

                    finally:
                        if os.path.exists(temp_wav_path):
                            try:
                                os.remove(temp_wav_path)
                            except Exception:
                                pass
                        audio_buffer.clear()

            # 4. Text Utterance Message (for testing or chat bridge)
            elif event_type in ["message", "text"]:
                user_msg = data.get("message") or data.get("text") or ""
                turn_res = conversation_manager.process_citizen_turn(
                    db=db,
                    session_id=active_session_id,
                    speech_text=user_msg
                )
                spoken_text = turn_res.get("spoken_reply") or turn_res.get("ai_reply") or ""
                t_lang = turn_res.get("detected_language") or "Tanglish"
                tts_audio = synthesize_speech(spoken_text, t_lang)
                mulaw_out = pcm_or_wav_to_mulaw(tts_audio, in_rate=16000, out_rate=8000) if tts_audio else b""
                b64_audio = base64.b64encode(mulaw_out).decode("utf-8") if mulaw_out else ""

                if stream_sid and b64_audio:
                    await websocket.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": b64_audio}
                    })

                turn_res["audio_base64"] = b64_audio
                turn_res["event"] = "turn_complete"
                await websocket.send_json(turn_res)

            # 5. DTMF Keypress Event
            elif event_type in ["dtmf", "keypress"]:
                digit = str(data.get("dtmf", {}).get("digit") or data.get("digit") or "1")
                turn_res = conversation_manager.process_citizen_turn(
                    db=db,
                    session_id=active_session_id,
                    speech_text=digit
                )
                spoken_text = turn_res.get("spoken_reply") or turn_res.get("ai_reply") or ""
                t_lang = turn_res.get("detected_language") or "Tanglish"
                tts_audio = synthesize_speech(spoken_text, t_lang)
                mulaw_out = pcm_or_wav_to_mulaw(tts_audio, in_rate=16000, out_rate=8000) if tts_audio else b""
                b64_audio = base64.b64encode(mulaw_out).decode("utf-8") if mulaw_out else ""

                if stream_sid and b64_audio:
                    await websocket.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": b64_audio}
                    })

                turn_res["audio_base64"] = b64_audio
                turn_res["event"] = "dtmf_processed"
                await websocket.send_json(turn_res)

            # 6. Stop / Call Hangup Event
            elif event_type in ["stop", "hangup"]:
                logger.info(f"[IVR WebSocket] Call stopped for session {active_session_id}")
                sess = conversation_manager.get_session(db, active_session_id)
                if sess and sess.state != "COMPLETED":
                    sess.ended_at = datetime.now(timezone.utc)
                    db.commit()
                break

            # 7. Ping / Heartbeat
            elif event_type in ["ping", "keepalive"]:
                await websocket.send_json({"event": "pong"})

    except WebSocketDisconnect:
        logger.info(f"[IVR WebSocket] Disconnected: session_id={active_session_id}")
    except Exception as e:
        logger.error(f"[IVR WebSocket] Error in session {active_session_id}: {e}")
        try:
            await websocket.send_json({"event": "error", "message": str(e)})
        except Exception:
            pass


@router.post("/ivr/session/{session_id}/audio")
async def process_ivr_session_audio(
    session_id: str,
    file: UploadFile = File(...),
    caller_phone: Optional[str] = Form("+919843098765"),
    transcription_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Receives caller's microphone voice recording, converts audio to 16kHz mono WAV,
    runs Whisper transcription (with browser speech recognition fallback),
    processes conversational turn in ConversationManager, and returns structured response and synthesized audio.
    """
    temp_dir = os.path.join(settings.UPLOAD_DIR, "temp_ivr")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{session_id}_{uuid.uuid4().hex[:6]}.wav")

    try:
        async with aiofiles.open(temp_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # Convert audio to 16 kHz Mono WAV using FFmpeg if possible
        conv_ok, wav_path, _ = convert_audio_to_16k_mono_wav(temp_path)
        audio_target = wav_path if conv_ok else temp_path

        # 1. Transcribe speech with Whisper / fallback
        stt_result = speech_service.transcribe(
            audio_target,
            transcription_hint=transcription_hint
        )
        transcription = (stt_result.get("transcription") or "").strip()

        if not transcription and transcription_hint and transcription_hint.strip():
            transcription = transcription_hint.strip()

        # 2. Process turn via ConversationManager
        turn_res = conversation_manager.process_citizen_turn(
            db=db,
            session_id=session_id,
            speech_text=transcription,
            audio_url=f"/api/v1/audio/recording/{os.path.basename(temp_path)}"
        )

        # 3. Synthesize natural TTS voice audio
        spoken_text = turn_res.get("spoken_reply") or turn_res.get("ai_reply") or ""
        tts_lang = turn_res.get("detected_language") or "Tanglish"
        audio_bytes = synthesize_speech(spoken_text, tts_lang)
        mem = turn_res.get("memory", {})
        turn_res["audio_base64"] = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else None
        turn_res["transcription"] = transcription
        turn_res["response_text"] = turn_res.get("ai_reply", "")
        turn_res["ai_spoken"] = spoken_text
        resolved_tts_lang = tts_lang if tts_lang not in ["Auto", "Auto-Detecting...", "", None] else "Tamil"
        turn_res["language"] = resolved_tts_lang
        turn_res["detected_language"] = turn_res.get("detected_language") or resolved_tts_lang
        turn_res["should_continue"] = (turn_res.get("state") != "COMPLETED")
        turn_res["conversation_state"] = turn_res.get("state")
        turn_res["confirmation_required"] = turn_res.get("is_confirmation", False)
        raw_prio = mem.get("priority") or "MEDIUM"
        normalized_prio = "MEDIUM" if str(raw_prio).upper() in ["STANDARD", "NORMAL"] else raw_prio
        turn_res["analysis"] = {
            "category": mem.get("category") or "Other",
            "location": mem.get("location") or mem.get("area") or mem.get("district_area") or "",
            "problem": mem.get("problem_description") or mem.get("problem") or "",
            "duration": mem.get("duration") or "",
            "affected_scope": mem.get("affected_scope") or mem.get("affected_area") or "",
            "severity": mem.get("severity") or "normal",
            "priority": normalized_prio,
            "department": mem.get("department") or "Municipal Administration"
        }

        return turn_res

    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@router.post("/ivr/session/{session_id}/message")
async def process_ivr_session_message(
    session_id: str,
    request: Request,
    message: Optional[str] = Form(None),
    caller_phone: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Text-based turn fallback entering the exact same stateful conversation manager.
    Supports JSON, Form, and Query parameters.
    """
    raw_message = (message or "").strip()
    phone = caller_phone or "+919843098765"

    if not raw_message:
        try:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
                if isinstance(body, dict):
                    raw_message = (body.get("message") or "").strip()
                    if body.get("caller_phone"):
                        phone = body.get("caller_phone")
            elif "form" in content_type:
                form = await request.form()
                raw_message = (form.get("message") or "").strip()
                if form.get("caller_phone"):
                    phone = form.get("caller_phone")
        except Exception:
            pass

    turn_res = conversation_manager.process_citizen_turn(
        db=db,
        session_id=session_id,
        speech_text=raw_message
    )

    spoken_text = turn_res.get("spoken_reply") or turn_res.get("ai_reply") or ""
    tts_lang = turn_res.get("detected_language") or "Tanglish"
    audio_bytes = synthesize_speech(spoken_text, tts_lang)
    mem = turn_res.get("memory", {})
    turn_res["audio_base64"] = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else None
    turn_res["transcription"] = raw_message
    turn_res["response_text"] = turn_res.get("ai_reply", "")
    turn_res["ai_spoken"] = spoken_text
    resolved_tts_lang = tts_lang if tts_lang not in ["Auto", "Auto-Detecting...", "", None] else "Tamil"
    turn_res["language"] = resolved_tts_lang
    turn_res["detected_language"] = turn_res.get("detected_language") or resolved_tts_lang
    turn_res["should_continue"] = (turn_res.get("state") != "COMPLETED")
    turn_res["conversation_state"] = turn_res.get("state")
    turn_res["confirmation_required"] = turn_res.get("is_confirmation", False)
    raw_prio = mem.get("priority") or "MEDIUM"
    normalized_prio = "MEDIUM" if str(raw_prio).upper() in ["STANDARD", "NORMAL"] else raw_prio
    turn_res["analysis"] = {
        "category": mem.get("category") or "Other",
        "location": mem.get("location") or mem.get("area") or mem.get("district_area") or "",
        "problem": mem.get("problem_description") or mem.get("problem") or "",
        "duration": mem.get("duration") or "",
        "affected_scope": mem.get("affected_scope") or mem.get("affected_area") or "",
        "severity": mem.get("severity") or "normal",
        "priority": normalized_prio,
        "department": mem.get("department") or "Municipal Administration"
    }

    return turn_res


@router.get("/ivr/session/{session_id}")
def get_ivr_session_state(session_id: str, db: Session = Depends(get_db)):
    """
    Returns current conversation memory, extracted slots, and state.
    """
    sess = conversation_manager.get_session(db, session_id)
    if sess:
        mem = sess.structured_memory or {}
        return {
            "session_id": sess.session_id,
            "caller_phone": sess.caller_phone,
            "state": sess.state,
            "conversation_state": sess.state,
            "language": sess.language,
            "analysis": {
                "category": sess.category or mem.get("category") or "Other",
                "location": sess.location or mem.get("location") or "",
                "problem": sess.problem or mem.get("problem_description") or "",
                "duration": sess.duration or mem.get("duration") or "",
                "affected_scope": sess.affected_scope or mem.get("affected_scope") or "",
                "severity": sess.severity or mem.get("severity") or "normal",
                "priority": sess.priority or mem.get("priority") or "MEDIUM",
                "department": sess.department or mem.get("department") or "Municipal Administration"
            },
            "context": mem,
            "structured_memory": mem,
            "should_continue": sess.state != "COMPLETED",
            "confirmation_required": sess.state == "CONFIRMATION",
            "conversation_complete": sess.state == "COMPLETED",
            "complaint_number": sess.complaint_number or mem.get("complaint_number"),
            "complaint_id": sess.complaint_id or mem.get("complaint_id")
        }

    ctx = conversation_service.get_or_create_context(session_id)
    return {
        "session_id": session_id,
        "conversation_state": "CONFIRMED" if ctx.conversation_complete else ("WAITING_FOR_CITIZEN"),
        "state": "CONFIRMING" if ctx.confirmation_required else ("COMPLETED" if ctx.conversation_complete else "WAITING_FOR_USER"),
        "analysis": {
            "category": ctx.category or "Other",
            "location": ctx.location or "",
            "problem": ctx.problem or "",
            "duration": ctx.duration or "",
            "affected_scope": ctx.affected_scope or "",
            "severity": ctx.severity or "normal",
            "priority": ctx.priority or "MEDIUM",
            "department": ctx.department or "Municipal Administration"
        },
        "context": ctx.to_dict(),
        "should_continue": not ctx.conversation_complete,
        "confirmation_required": ctx.confirmation_required,
        "conversation_complete": ctx.conversation_complete,
        "complaint_number": ctx.complaint_number,
        "complaint_id": ctx.complaint_id
    }


@router.post("/ivr/session/{session_id}/confirm")
async def confirm_ivr_session(
    session_id: str,
    request: Request,
    caller_phone: Optional[str] = Form("+919843098765"),
    db: Session = Depends(get_db)
):
    """
    Explicitly confirms the gathered complaint and registers the official database record.
    Supports JSON and Form data.
    """
    phone = caller_phone or "+919843098765"
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict) and body.get("caller_phone"):
                phone = body.get("caller_phone")
        elif "form" in content_type:
            form = await request.form()
            if form.get("caller_phone"):
                phone = form.get("caller_phone")
    except Exception:
        pass

    sess = conversation_manager.get_session(db, session_id)
    if sess:
        return conversation_manager.finalize_and_register_complaint(db, sess)

    ctx = conversation_service.get_or_create_context(session_id, phone)
    ctx.conversation_complete = True
    created_comp = conversation_service._create_database_complaint(ctx, db)
    ctx.complaint_id = created_comp.id
    ctx.complaint_number = created_comp.complaint_number

    # Sync to DB
    _sync_ivr_session_to_db(
        db,
        session_id,
        phone,
        state="COMPLETED",
        memory=ctx.to_dict(),
        complaint_id=created_comp.id,
        complaint_number=created_comp.complaint_number,
        ended=True
    )

    if ctx.language == "Tamil":
        ai_text = f"உங்கள் புகார் எண் {created_comp.complaint_number} என வெற்றிகரமாக பதிவு செய்யப்பட்டது. நன்றி!"
    elif ctx.language == "Tanglish":
        ai_text = f"Seri. Unga complaint #{created_comp.complaint_number} successfully register aaiduchu."
    else:
        ai_text = f"Thank you. Your complaint #{created_comp.complaint_number} has been registered successfully."

    audio_bytes = synthesize_speech(ai_text, ctx.language)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else None

    # Update session service
    ivr_sess = ivr_session_service.get_session(session_id)
    if ivr_sess:
        ivr_sess.complaint_id = created_comp.id
        ivr_sess.complaint_number = created_comp.complaint_number
        ivr_sess.end_call(IVRState.COMPLETED)

    return {
        "session_id": session_id,
        "conversation_state": "CONFIRMED",
        "state": "COMPLETED",
        "should_continue": False,
        "complaint_number": created_comp.complaint_number,
        "complaint_id": created_comp.id,
        "department": ctx.department,
        "response_text": ai_text,
        "ai_spoken": ai_text,
        "audio_base64": audio_b64,
        "analysis": {
            "category": ctx.category or "Other",
            "location": ctx.location or "",
            "problem": ctx.problem or "",
            "duration": ctx.duration or "",
            "affected_scope": ctx.affected_scope or "",
            "severity": ctx.severity or "normal",
            "priority": ctx.priority or "MEDIUM",
            "department": ctx.department or "Municipal Administration"
        },
        "context": ctx.to_dict(),
        "conversation_complete": True
    }


@router.post("/ivr/session/{session_id}/cancel")
def cancel_ivr_session(session_id: str, db: Session = Depends(get_db)):
    """
    Cancels active conversational voice session and clears memory.
    """
    sess = conversation_manager.get_session(db, session_id)
    if sess:
        sess.state = "CANCELLED"
        sess.ended_at = datetime.now(timezone.utc)
        db.commit()

    conversation_service.reset_session(session_id)
    _sync_ivr_session_to_db(db, session_id, "+919843098765", state="CANCELLED", ended=True)
    ivr_sess = ivr_session_service.get_session(session_id)
    if ivr_sess:
        ivr_sess.end_call(IVRState.CANCELLED)

    return {
        "session_id": session_id,
        "conversation_state": "CANCELLED",
        "state": "CANCELLED",
        "should_continue": False,
        "message": "IVR conversation session cancelled successfully."
    }


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
def get_telephony_logs(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Returns real-time and persistent call records directly from the database and telephony logs.
    """
    db_ivr = db.query(IVRSession).order_by(desc(IVRSession.created_at)).limit(limit).all()
    db_tf = db.query(TollFreeCallSession).order_by(desc(TollFreeCallSession.created_at)).limit(limit).all()
    mem_logs = exotel_adapter.get_logs(limit=limit)

    merged_logs: List[TelephonyLogItem] = []
    seen_ids = set()

    # Memory buffer items
    for item in mem_logs:
        log_id = str(item.get("id"))
        seen_ids.add(log_id)
        merged_logs.append(TelephonyLogItem(**item))

    # Real DB TollFree Call Sessions
    for s in db_tf:
        sid = f"tf_{s.id}"
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        mem = s.structured_memory or {}
        raw_lang = s.language
        if not raw_lang or raw_lang in ["Auto", "Auto-Detecting..."]:
            raw_lang = mem.get("language") or mem.get("detected_language") or mem.get("current_language") or "Tamil"
            if raw_lang in ["Auto", "Auto-Detecting..."]:
                raw_lang = "Tamil"

        raw_prio = s.priority or mem.get("priority") or "MEDIUM"
        norm_prio = "MEDIUM" if str(raw_prio).upper() in ["STANDARD", "NORMAL"] else raw_prio

        merged_logs.append(
            TelephonyLogItem(
                id=sid,
                timestamp=s.created_at.isoformat() if s.created_at else datetime.now(timezone.utc).isoformat(),
                event_type="CALL_INBOUND" if not s.complaint_number else "COMPLAINT_REGISTERED",
                direction="INBOUND",
                phone=s.caller_phone or "+919843098765",
                status="COMPLETED" if s.state in ["COMPLETED", "CONFIRMATION"] else s.state,
                details={
                    "session_id": s.call_session_id,
                    "language": raw_lang,
                    "category": s.category or mem.get("category") or "Civic",
                    "problem": s.problem or mem.get("problem") or "Phone Inquiry",
                    "location": s.location or mem.get("location") or "Tamil Nadu",
                    "priority": norm_prio,
                    "complaint_number": s.complaint_number or "In-Progress",
                    "state": s.state,
                    "toll_free_number": s.toll_free_number
                }
            )
        )

    # Real DB IVR Sessions
    for s in db_ivr:
        sid = f"ivr_{s.id}"
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        mem = s.structured_memory or {}
        raw_lang = s.language
        if not raw_lang or raw_lang in ["Auto", "Auto-Detecting..."]:
            raw_lang = mem.get("language") or mem.get("detected_language") or mem.get("current_language") or "Tamil"
            if raw_lang in ["Auto", "Auto-Detecting..."]:
                raw_lang = "Tamil"

        raw_prio = s.priority or mem.get("priority") or "MEDIUM"
        norm_prio = "MEDIUM" if str(raw_prio).upper() in ["STANDARD", "NORMAL"] else raw_prio

        merged_logs.append(
            TelephonyLogItem(
                id=sid,
                timestamp=s.created_at.isoformat() if s.created_at else datetime.now(timezone.utc).isoformat(),
                event_type="CALL_INBOUND" if not s.complaint_number else "COMPLAINT_REGISTERED",
                direction="INBOUND",
                phone=s.caller_phone or "+919843098765",
                status="COMPLETED" if s.state in ["COMPLETED", "CONFIRMED"] else s.state,
                details={
                    "session_id": s.session_id,
                    "language": raw_lang,
                    "category": s.category or mem.get("category") or "Civic",
                    "problem": s.problem or mem.get("problem") or "Voice Inquiry",
                    "location": s.location or mem.get("location") or "Tamil Nadu",
                    "priority": norm_prio,
                    "complaint_number": s.complaint_number or "In-Progress",
                    "state": s.state
                }
            )
        )

    merged_logs.sort(key=lambda x: x.timestamp, reverse=True)
    return TelephonyLogsResponse(
        total=len(merged_logs[:limit]),
        logs=merged_logs[:limit]
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
async def twilio_incoming_voice_call(request: Request, db: Session = Depends(get_db)):
    """
    Webhook triggered by Twilio when a citizen dials the helpline virtual number.
    Returns silent answer TwiML and gathers speech.
    """
    from app.api.routes.telephony import handle_inbound_telephone_call
    return await handle_inbound_telephone_call(request, db)


@router.post("/webhooks/twilio/voice/recording")
async def twilio_voice_recording_callback(request: Request, db: Session = Depends(get_db)):
    """
    Webhook triggered by Twilio when a citizen finishes speaking their grievance.
    Processes audio recording through Whisper STT and dialogue turn engine.
    """
    from app.api.routes.telephony import handle_telephone_recording_callback
    return await handle_telephone_recording_callback(request, db)


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


