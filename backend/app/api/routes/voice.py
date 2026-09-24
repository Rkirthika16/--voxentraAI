import os
import uuid
import base64
import logging
import aiofiles
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.ai.conversation_service import conversation_service, ConversationContext
from app.ai.speech_service import speech_service
from app.ai.tts_service import synthesize_speech
from app.services.complaint_service import complaint_service
from app.schemas.complaint import ComplaintCreate
from app.models.complaint import ComplaintPriority, ComplaintSource

logger = logging.getLogger("voxentra.voice")

router = APIRouter(prefix="/voice", tags=["Live Conversational Voice Assistant"])


class VoiceSessionStartRequest(BaseModel):
    session_id: Optional[str] = None
    caller_phone: Optional[str] = "+919843098765"
    language_hint: Optional[str] = "Auto"


class VoiceSessionMessageRequest(BaseModel):
    message: str = Field(..., description="Citizen spoken transcription or text input")
    caller_phone: Optional[str] = None


class VoiceSessionConfirmRequest(BaseModel):
    citizen_name: Optional[str] = "Citizen Caller"
    caller_phone: Optional[str] = "+919843098765"


@router.post("/session", status_code=status.HTTP_200_OK)
def create_voice_session(req: VoiceSessionStartRequest = VoiceSessionStartRequest()):
    """
    Initiates a new Live Conversational Voice Assistant session.
    The citizen speaks FIRST without selecting Tamil/English or category upfront.
    """
    sid = req.session_id or f"VS_{uuid.uuid4().hex[:12]}"
    ctx = conversation_service.get_or_create_context(sid, req.caller_phone)

    welcome_text = "வணக்கம். வாக்ஸென்ட்ரா தமிழ்நாடு அரசு குரல் சேவைக்கு நல்வரவு. உங்கள் புகாரை தமிழ், ஆங்கிலம் அல்லது தங்கிலீஷில் கூறலாம்."
    welcome_spoken = "வணக்கம். வாக்ஸென்ட்ரா தமிழ்நாடு அரசு குரல் சேவைக்கு நல்வரவு. உங்கள் புகாரை தமிழ், ஆங்கிலம் அல்லது தங்கிலீஷில் கூறலாம்."

    # Pre-synthesize initial welcoming TTS audio
    welcome_audio_bytes = synthesize_speech(welcome_spoken, "Tamil")
    welcome_audio_b64 = base64.b64encode(welcome_audio_bytes).decode("utf-8") if welcome_audio_bytes else None

    return {
        "session_id": sid,
        "state": "WAITING_FOR_USER",
        "greeting_text": welcome_text,
        "greeting_spoken": welcome_spoken,
        "audio_base64": welcome_audio_b64,
        "detected_language": "Auto-Detecting...",
        "context": ctx.to_dict(),
        "speech_engine_available": speech_service.check_availability()["available"]
    }


@router.post("/session/{session_id}/audio")
async def process_voice_audio_turn(
    session_id: str,
    file: UploadFile = File(...),
    caller_phone: Optional[str] = Form("+919843098765"),
    db: Session = Depends(get_db)
):
    """
    Receives caller's voice audio, performs Speech-to-Text with Whisper,
    runs the conversational understanding engine, and synthesizes natural audio response.
    """
    temp_dir = os.path.join(os.path.dirname(__file__), "..", "..", "temp_voice")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{session_id}_{uuid.uuid4().hex[:6]}.wav")

    try:
        async with aiofiles.open(temp_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # 1. Transcribe speech honestly with Whisper
        stt_result = speech_service.transcribe(temp_path)
        transcription = (stt_result.get("transcription") or "").strip()

        if not transcription:
            if not stt_result.get("success") and stt_result.get("status") == "engine_unavailable":
                return {
                    "session_id": session_id,
                    "state": "ERROR",
                    "error": "Voice recognition is not configured. Please type your complaint.",
                    "transcription": "",
                    "speech_recognition_available": False,
                    "ai_text": "Voice recognition is currently not configured on this server. Please type your complaint.",
                    "ai_spoken": "",
                    "audio_base64": None
                }

            # Unclear speech
            unclear_txt, unclear_spk = conversation_service.get_unclear_response("Tamil")
            unclear_audio = synthesize_speech(unclear_spk, "Tamil")
            return {
                "session_id": session_id,
                "state": "WAITING_FOR_USER",
                "transcription": "",
                "original_transcription": "",
                "normalized_transcription": "",
                "detected_language": "Unknown",
                "ai_text": unclear_txt,
                "ai_spoken": unclear_spk,
                "audio_base64": base64.b64encode(unclear_audio).decode("utf-8") if unclear_audio else None,
                "context": conversation_service.get_or_create_context(session_id).to_dict(),
                "confirmation_required": False,
                "conversation_complete": False
            }

        # 2. Process multi-turn conversational dialogue turn
        turn_res = conversation_service.process_turn(session_id, transcription, db=db, caller_phone=caller_phone)

        # 3. Synthesize natural TTS voice audio in detected language
        spoken_text = turn_res.get("ai_spoken") or turn_res.get("ai_text") or ""
        tts_lang = turn_res.get("detected_language") or "Tamil"
        audio_bytes = synthesize_speech(spoken_text, tts_lang)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else None

        turn_res["audio_base64"] = audio_b64
        turn_res["transcription"] = transcription
        turn_res["speech_recognition_available"] = True
        return turn_res

    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@router.post("/session/{session_id}/message")
def process_voice_text_message(
    session_id: str,
    req: VoiceSessionMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Text-based turn fallback for live conversational voice assistant.
    Maintains continuous multi-turn state without pre-selecting language or category.
    """
    turn_res = conversation_service.process_turn(
        session_id=session_id,
        user_speech=req.message,
        db=db,
        caller_phone=req.caller_phone
    )

    spoken_text = turn_res.get("ai_spoken") or turn_res.get("ai_text") or ""
    tts_lang = turn_res.get("detected_language") or "Tamil"
    audio_bytes = synthesize_speech(spoken_text, tts_lang)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else None

    turn_res["audio_base64"] = audio_b64
    turn_res["transcription"] = req.message
    turn_res["speech_recognition_available"] = True
    return turn_res


@router.get("/session/{session_id}")
def get_voice_session(session_id: str):
    """
    Returns current conversation memory, extracted slots, and confirmation status.
    """
    ctx = conversation_service.get_or_create_context(session_id)
    return {
        "session_id": session_id,
        "state": "CONFIRMING" if ctx.confirmation_required else ("COMPLETED" if ctx.conversation_complete else "WAITING_FOR_USER"),
        "context": ctx.to_dict(),
        "confirmation_required": ctx.confirmation_required,
        "conversation_complete": ctx.conversation_complete,
        "complaint_number": ctx.complaint_number,
        "complaint_id": ctx.complaint_id
    }


@router.post("/session/{session_id}/confirm")
def confirm_voice_session(
    session_id: str,
    req: VoiceSessionConfirmRequest = VoiceSessionConfirmRequest(),
    db: Session = Depends(get_db)
):
    """
    Explicitly confirms the gathered complaint information and creates the official database record.
    Generates unique Complaint Tracking ID (e.g., VX-2026-000001) and routes to department.
    """
    ctx = conversation_service.get_or_create_context(session_id, req.caller_phone)
    if req.citizen_name:
        ctx.citizen_name = req.citizen_name

    ctx.conversation_complete = True
    created_comp = conversation_service._create_database_complaint(ctx, db)
    ctx.complaint_id = created_comp.id
    ctx.complaint_number = created_comp.complaint_number

    if ctx.language == "Tamil":
        ai_text = f"உங்கள் புகார் எண் {created_comp.complaint_number} என வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது. நன்றி!"
    elif ctx.language == "Tanglish":
        ai_text = f"Unga complaint #{created_comp.complaint_number} successfully register aaiduchu. Thanks!"
    else:
        ai_text = f"Your complaint #{created_comp.complaint_number} has been registered successfully. Thank you!"

    audio_bytes = synthesize_speech(ai_text, ctx.language)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else None

    return {
        "session_id": session_id,
        "state": "COMPLETED",
        "complaint_number": created_comp.complaint_number,
        "complaint_id": created_comp.id,
        "department": ctx.department,
        "ai_text": ai_text,
        "audio_base64": audio_b64,
        "context": ctx.to_dict(),
        "conversation_complete": True
    }


@router.post("/session/{session_id}/cancel")
def cancel_voice_session(session_id: str):
    """
    Cancels active conversational voice session and clears memory.
    """
    conversation_service.reset_session(session_id)
    return {
        "session_id": session_id,
        "state": "CANCELLED",
        "message": "Voice session cancelled successfully."
    }
