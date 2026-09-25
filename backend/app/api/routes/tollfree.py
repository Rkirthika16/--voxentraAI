import os
import tempfile
import aiofiles
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, Request, Response, status, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.tollfree import TollFreeCallSession, TollFreeState
from app.services.tollfree_service import tollfree_service
from app.ai.speech_service import speech_service
from app.ai.audio_converter import (
    convert_audio_to_16k_mono_wav,
    EMPTY_AUDIO,
    AUDIO_TOO_LARGE,
    FFMPEG_NOT_FOUND,
    WHISPER_UNAVAILABLE,
    TRANSCRIPTION_FAILED
)
from app.utils.validators import validate_audio_file
from app.core.exceptions import BadRequestException, NotFoundException
from app.integrations.telephony.provider_interface import generic_telephony_provider

logger = logging.getLogger("voxentra.api.tollfree")

router = APIRouter(prefix="/tollfree", tags=["Toll-Free AI Two-Way Conversational IVR"])


# Request / Response Schemas
class CreateTollFreeSessionRequest(BaseModel):
    caller_phone: Optional[str] = "+919843098765"
    provider_call_id: Optional[str] = None
    toll_free_number: Optional[str] = "1800-425-8693"


class TollFreeMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Citizen utterance or text response")


@router.post("/session", status_code=status.HTTP_201_CREATED)
def create_tollfree_session(
    payload: Optional[CreateTollFreeSessionRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Starts a new two-way conversational toll-free session.
    AI delivers the initial greeting and enters WAITING_FOR_CITIZEN state (Citizen speaks first).
    """
    phone = payload.caller_phone if payload else "+919843098765"
    call_id = payload.provider_call_id if payload else None
    tf_num = payload.toll_free_number if payload else "1800-425-8693"

    session, greeting_text, greeting_spoken = tollfree_service.create_call_session(
        db=db,
        caller_phone=phone,
        provider_call_id=call_id,
        toll_free_number=tf_num
    )

    return {
        "success": True,
        "session_id": session.call_session_id,
        "caller_phone": session.caller_phone,
        "toll_free_number": session.toll_free_number,
        "state": session.state,
        "greeting": greeting_text,
        "spoken_greeting": greeting_spoken,
        "language": session.language,
        "structured_memory": session.structured_memory
    }


@router.get("/session/{session_id}")
def get_tollfree_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetches full session state, structured memory, and conversation history.
    """
    session = tollfree_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"Toll-free session '{session_id}' not found")

    messages_data = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "normalized_content": m.normalized_content,
            "language": m.language,
            "audio_url": m.audio_url,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in session.messages
    ]

    return {
        "session_id": session.call_session_id,
        "provider_call_id": session.provider_call_id,
        "caller_phone": session.caller_phone,
        "toll_free_number": session.toll_free_number,
        "state": session.state,
        "language": session.language,
        "language_confidence": session.language_confidence,
        "current_field_prompted": session.current_field_prompted,
        "structured_memory": session.structured_memory,
        "complaint_id": session.complaint_id,
        "complaint_number": session.complaint_number,
        "raw_transcript": session.raw_transcript,
        "normalized_transcript": session.normalized_transcript,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "messages": messages_data
    }


@router.post("/session/{session_id}/audio")
async def process_tollfree_audio(
    session_id: str,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Receives voice audio from citizen microphone/telephony stream.
    Converts via FFmpeg to 16kHz mono WAV, executes Whisper transcription,
    and conducts a turn of two-way dialogue.
    """
    session = tollfree_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"Toll-free session '{session_id}' not found")

    # Validate audio MIME/Extension
    try:
        sanitized_name, ext = validate_audio_file(audio)
    except BadRequestException as e:
        return {
            "success": False,
            "error_code": "INVALID_AUDIO",
            "message": str(e),
            "state": session.state
        }

    # Save to temp audio file
    temp_dir = tempfile.gettempdir()
    input_audio_path = os.path.join(temp_dir, f"tf_in_{session_id}_{os.path.basename(sanitized_name)}")

    try:
        async with aiofiles.open(input_audio_path, 'wb') as out_f:
            content = await audio.read()
            if len(content) < 200:
                return {
                    "success": False,
                    "error_code": EMPTY_AUDIO,
                    "message": "Audio recording is empty or silent. Please speak clearly.",
                    "state": session.state
                }
            await out_f.write(content)
    except Exception as e:
        logger.error(f"Error saving audio file: {e}")
        return {
            "success": False,
            "error_code": "UPLOAD_FAILED",
            "message": f"Failed to save audio: {str(e)}",
            "state": session.state
        }

    # Convert audio to 16 kHz Mono WAV using FFmpeg
    conv_ok, wav_path, conv_err = convert_audio_to_16k_mono_wav(input_audio_path)
    if not conv_ok:
        if conv_err == FFMPEG_NOT_FOUND:
            return {
                "success": False,
                "error_code": FFMPEG_NOT_FOUND,
                "message": "FFmpeg is not installed on system PATH. Please use text response fallback.",
                "state": session.state
            }
        return {
            "success": False,
            "error_code": conv_err or "AUDIO_CONVERSION_FAILED",
            "message": "Audio conversion failed. Please try speaking again.",
            "state": session.state
        }

    # Speech recognition via Whisper
    avail = speech_service.check_availability()
    if not avail["available"]:
        return {
            "success": False,
            "error_code": WHISPER_UNAVAILABLE,
            "message": "Whisper speech engine is not configured locally. Please use text fallback.",
            "state": session.state
        }

    transcription_result = speech_service.transcribe(wav_path)
    if not transcription_result.get("success"):
        return {
            "success": False,
            "error_code": TRANSCRIPTION_FAILED,
            "message": transcription_result.get("message", "Speech transcription failed. Please try again."),
            "state": session.state
        }

    transcribed_text = transcription_result.get("transcription", "").strip()
    if not transcribed_text:
        return tollfree_service.process_dialogue_turn(db, session_id, speech_text="")

    turn_response = tollfree_service.process_dialogue_turn(
        db=db,
        session_id=session_id,
        speech_text=transcribed_text,
        audio_url=f"/api/v1/audio/recording/{os.path.basename(input_audio_path)}"
    )
    turn_response["raw_transcription"] = transcription_result.get("raw_transcription", transcribed_text)
    turn_response["cleaned_transcription"] = transcribed_text
    return turn_response


@router.post("/session/{session_id}/message")
def process_tollfree_message(
    session_id: str,
    payload: TollFreeMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Text dialogue turn fallback using the exact same conversational memory and state machine.
    """
    return tollfree_service.process_dialogue_turn(
        db=db,
        session_id=session_id,
        speech_text=payload.message
    )


@router.post("/session/{session_id}/confirm")
def confirm_tollfree_complaint(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Explicit confirmation endpoint to finalize and create official DB complaint.
    """
    session = tollfree_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"Toll-free session '{session_id}' not found")

    return tollfree_service._finalize_and_register_complaint(db, session)


@router.post("/session/{session_id}/cancel")
def cancel_tollfree_complaint(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Cancel or request corrections.
    """
    session = tollfree_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"Toll-free session '{session_id}' not found")

    session.state = TollFreeState.WAITING_FOR_CITIZEN.value
    db.commit()
    return tollfree_service._generate_edit_prompt(db, session, session.language or "English")


@router.post("/session/{session_id}/end")
def end_tollfree_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Politely terminates call session.
    """
    session = tollfree_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"Toll-free session '{session_id}' not found")

    session.state = TollFreeState.COMPLETED.value
    db.commit()

    return {
        "success": True,
        "session_id": session_id,
        "state": TollFreeState.COMPLETED.value,
        "message": "Call completed. Thank you for using VoxentraAI Toll-Free Helpline."
    }


@router.get("/session/{session_id}/status")
def get_tollfree_status(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Lightweight status polling endpoint.
    """
    session = tollfree_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"Toll-free session '{session_id}' not found")

    return {
        "session_id": session.call_session_id,
        "state": session.state,
        "language": session.language,
        "complaint_id": session.complaint_id,
        "complaint_number": session.complaint_number
    }


# ==========================================
# Telephony Provider Webhook Endpoints
# ==========================================

@router.post("/webhook/incoming")
async def tollfree_incoming_call_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Telephony Provider Inbound Call Webhook (Exotel / Twilio / SIP).
    Creates session and returns TwiML / XML payload to greet caller and open audio recording.
    """
    form_data = await request.form()
    caller_phone = form_data.get("From") or form_data.get("CallFrom") or "+919843098765"
    call_sid = form_data.get("CallSid") or form_data.get("CallSid") or f"CA_{tempfile.mktemp()}"

    session, greeting_text, _ = tollfree_service.create_call_session(
        db=db,
        caller_phone=str(caller_phone),
        provider_call_id=str(call_sid)
    )

    action_url = f"/api/v1/tollfree/webhook/audio?session_id={session.call_session_id}"
    twiml_xml = generic_telephony_provider.generate_incoming_call_response(
        call_session_id=session.call_session_id,
        greeting_text=greeting_text,
        speech_action_url=action_url,
        lang="Tanglish"
    )
    return Response(content=twiml_xml, media_type="application/xml")


@router.post("/webhook/audio")
async def tollfree_audio_callback_webhook(
    request: Request,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Telephony Provider Speech Recording Callback Webhook.
    Receives speech recording URL or transcribed text, processes turn, and returns next XML instruction.
    """
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult") or form_data.get("RecordingUrl") or ""
    sid = session_id or form_data.get("CallSid")

    turn_res = tollfree_service.process_dialogue_turn(
        db=db,
        session_id=str(sid),
        speech_text=str(speech_result)
    )

    if turn_res.get("state") == TollFreeState.COMPLETED.value:
        xml_resp = generic_telephony_provider.generate_hangup_response(
            call_session_id=str(sid),
            final_message=turn_res.get("spoken_reply", "Thank you. Your complaint has been registered.")
        )
    else:
        next_action_url = f"/api/v1/tollfree/webhook/audio?session_id={sid}"
        xml_resp = generic_telephony_provider.generate_speech_gather_response(
            call_session_id=str(sid),
            prompt_text=turn_res.get("spoken_reply", "Please tell me more about your complaint."),
            speech_action_url=next_action_url
        )
    return Response(content=xml_resp, media_type="application/xml")


@router.post("/webhook/events")
def tollfree_call_events_webhook(payload: Dict[str, Any] = Body(...)):
    """Logs carrier call events (ringing, answered, completed)."""
    logger.info(f"[TollFree Webhook Event] {payload}")
    return {"status": "received"}


@router.get("/webhook/status")
def tollfree_webhook_status():
    """Returns status of toll-free webhook receiver."""
    return {
        "status": "active",
        "provider": "GenericTelephonyProvider (Exotel/Twilio/SIP Ready)",
        "toll_free_number": "1800-425-8693",
        "supported_modes": ["Tamil", "English", "Tanglish"]
    }
