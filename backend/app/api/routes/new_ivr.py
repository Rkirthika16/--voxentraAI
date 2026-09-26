import os
import tempfile
import aiofiles
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, Query, status, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.ivr import IVRSession, IVRState
from app.services.new_ivr_service import new_ivr_service
from app.ai.speech_service import speech_service
from app.ai.audio_converter import (
    convert_audio_to_16k_mono_wav,
    check_ffmpeg_available,
    EMPTY_AUDIO,
    AUDIO_TOO_LARGE,
    FFMPEG_NOT_FOUND,
    WHISPER_UNAVAILABLE,
    TRANSCRIPTION_FAILED
)
from app.utils.validators import validate_audio_file
from app.core.exceptions import BadRequestException, NotFoundException

logger = logging.getLogger("voxentra.api.new_ivr")

router = APIRouter(prefix="/new-ivr", tags=["New Live Two-Way AI IVR"])


# Request / Response Schemas
class CreateSessionRequest(BaseModel):
    caller_phone: Optional[str] = "+919843098765"
    language_preference: Optional[str] = "Auto"


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Citizen text or transcribed utterance")


@router.post("/session", status_code=status.HTTP_201_CREATED)
def create_ivr_session(
    payload: Optional[CreateSessionRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Starts a new live two-way AI IVR session.
    Returns the initial greeting and places the session into WAITING_FOR_CITIZEN state.
    """
    phone = payload.caller_phone if payload else "+919843098765"
    lang_pref = payload.language_preference if payload else "Auto"

    session, greeting_text, greeting_spoken = new_ivr_service.create_session(
        db=db,
        caller_phone=phone,
        language_preference=lang_pref
    )

    return {
        "success": True,
        "session_id": session.session_id,
        "caller_phone": session.caller_phone,
        "state": session.state,
        "greeting": greeting_text,
        "spoken_greeting": greeting_spoken,
        "language": session.language,
        "structured_memory": session.structured_memory
    }


@router.get("/session/{session_id}")
def get_ivr_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetches the full session state, structured conversation memory, and message history.
    """
    session = new_ivr_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"IVR session '{session_id}' not found")

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
        "session_id": session.session_id,
        "caller_phone": session.caller_phone,
        "state": session.state,
        "language": session.language,
        "language_confidence": session.language_confidence,
        "current_field_prompted": session.current_field_prompted,
        "structured_memory": session.structured_memory,
        "complaint_id": session.complaint_id,
        "complaint_number": session.complaint_number,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "messages": messages_data
    }


@router.post("/session/{session_id}/audio")
async def process_ivr_audio(
    session_id: str,
    audio: UploadFile = File(...),
    transcription_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Receives recorded microphone audio from the browser MediaRecorder.
    Converts audio via FFmpeg (if necessary) to 16kHz mono WAV, executes real Whisper transcription,
    and conducts a turn of two-way natural dialogue.
    """
    session = new_ivr_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"IVR session '{session_id}' not found")

    # Validate audio MIME/Extension
    try:
        sanitized_name, ext = validate_audio_file(audio)
    except BadRequestException as e:
        if transcription_hint and transcription_hint.strip():
            return new_ivr_service.process_citizen_turn(db, session_id, speech_text=transcription_hint.strip())
        return {
            "success": False,
            "error_code": "INVALID_AUDIO",
            "message": str(e),
            "state": session.state
        }

    # Save uploaded audio to temp file
    temp_dir = tempfile.gettempdir()
    input_audio_path = os.path.join(temp_dir, f"ivr_in_{session_id}_{os.path.basename(sanitized_name)}")
    
    try:
        async with aiofiles.open(input_audio_path, 'wb') as out_f:
            content = await audio.read()
            if len(content) < 200:
                if transcription_hint and transcription_hint.strip():
                    return new_ivr_service.process_citizen_turn(db, session_id, speech_text=transcription_hint.strip())
                return {
                    "success": False,
                    "error_code": EMPTY_AUDIO,
                    "message": "Recorded audio is empty or too short. Please speak clearly into your microphone.",
                    "state": session.state
                }
            await out_f.write(content)
    except Exception as e:
        logger.error(f"Error saving audio upload: {e}")
        if transcription_hint and transcription_hint.strip():
            return new_ivr_service.process_citizen_turn(db, session_id, speech_text=transcription_hint.strip())
        return {
            "success": False,
            "error_code": "UPLOAD_FAILED",
            "message": f"Failed to save audio: {str(e)}",
            "state": session.state
        }

    # Convert audio to 16 kHz Mono WAV using FFmpeg
    conv_ok, wav_path, conv_err = convert_audio_to_16k_mono_wav(input_audio_path)
    audio_for_transcription = wav_path if conv_ok else input_audio_path

    transcription_result = speech_service.transcribe(
        audio_for_transcription,
        transcription_hint=transcription_hint
    )

    transcribed_text = transcription_result.get("transcription", "").strip()
    if not transcribed_text and transcription_hint and transcription_hint.strip():
        transcribed_text = transcription_hint.strip()

    # If still empty, gracefully ask citizen to repeat
    if not transcribed_text:
        return new_ivr_service.process_citizen_turn(db, session_id, speech_text="")

    # Process turn in conversation engine
    turn_response = new_ivr_service.process_citizen_turn(
        db=db,
        session_id=session_id,
        speech_text=transcribed_text,
        audio_url=f"/api/v1/audio/recording/{os.path.basename(input_audio_path)}"
    )
    turn_response["original_transcription"] = transcription_result.get("raw_transcription", transcribed_text)
    turn_response["cleaned_transcription"] = transcribed_text
    return turn_response


@router.post("/session/{session_id}/message")
def process_ivr_message(
    session_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Text-based turn fallback that uses the exact same conversational memory and state machine.
    """
    return new_ivr_service.process_citizen_turn(
        db=db,
        session_id=session_id,
        speech_text=payload.message
    )


@router.post("/session/{session_id}/confirm")
def confirm_ivr_complaint(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Explicit confirmation endpoint to finalize and register complaint in DB.
    """
    session = new_ivr_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"IVR session '{session_id}' not found")

    return new_ivr_service._finalize_and_register_complaint(db, session)


@router.post("/session/{session_id}/cancel")
def cancel_ivr_complaint(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Allows citizen to cancel confirmation or request edits.
    """
    session = new_ivr_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"IVR session '{session_id}' not found")

    session.state = IVRState.WAITING_FOR_CITIZEN.value
    db.commit()
    return new_ivr_service._generate_edit_prompt(db, session, session.language or "English")


@router.post("/session/{session_id}/end")
def end_ivr_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Politely ends the IVR call session.
    """
    session = new_ivr_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"IVR session '{session_id}' not found")

    session.state = IVRState.COMPLETED.value
    db.commit()

    return {
        "success": True,
        "session_id": session_id,
        "state": IVRState.COMPLETED.value,
        "message": "Call completed. Thank you for using VoxentraAI."
    }


@router.get("/session/{session_id}/status")
def get_ivr_status(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Lightweight status polling endpoint.
    """
    session = new_ivr_service.get_session(db, session_id)
    if not session:
        raise NotFoundException(f"IVR session '{session_id}' not found")

    return {
        "session_id": session.session_id,
        "state": session.state,
        "language": session.language,
        "complaint_id": session.complaint_id,
        "complaint_number": session.complaint_number
    }


@router.get("/tts")
@router.get("/session/{session_id}/tts")
def get_new_ivr_tts_audio(
    text: str = Query(..., description="Text to synthesize to speech"),
    lang: Optional[str] = Query("ta", description="Language code (ta, en, hi)")
):
    """
    Synthesizes crystal-clear native Tamil, Tanglish, or English audio for IVR playback.
    """
    from app.ai.tts_service import synthesize_speech
    from fastapi import Response
    audio_bytes = synthesize_speech(text, lang=lang)
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(audio_bytes)),
            "Cache-Control": "public, max-age=86400"
        }
    )

