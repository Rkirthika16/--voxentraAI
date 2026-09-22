import os
import uuid
import aiofiles
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.core.dependencies import get_optional_current_user
from app.models.user import User
from app.ai.assistant_service import assistant_service
from app.ai.speech_service import speech_service
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantResponse,
    AssistantVoiceChatResponse,
    ActionSuggestion,
    SuggestionsResponse
)
from app.utils.validators import validate_audio_file
from app.core.exceptions import BadRequestException

router = APIRouter(prefix="/assistant", tags=["AI Voice & Talking Assistant"])


@router.post("/chat", response_model=AssistantResponse)
def chat_with_assistant(
    req: AssistantChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Conversational AI endpoint for citizens.
    Processes user query in Tamil, English, or Tanglish, extracts grievance entities,
    looks up tracking statuses, and generates talking speech responses.
    """
    return assistant_service.process_chat(
        message=req.message,
        session_id=req.session_id,
        language_hint=req.language_hint,
        db=db,
        current_user=current_user
    )


@router.post("/voice-chat", response_model=AssistantVoiceChatResponse)
async def voice_chat_with_assistant(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    language_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Accepts voice audio from microphone / file upload.
    Transcribes audio to text via Whisper, processes through the AI dialogue engine,
    and returns rich multimodal talking assistant responses with spoken text.
    """
    _, ext = validate_audio_file(file)

    unique_filename = f"voice_assist_{uuid.uuid4()}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save audio stream safely
    async with aiofiles.open(saved_path, "wb") as out_file:
        content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1024)
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise BadRequestException("Voice recording exceeds maximum allowed size of 25MB")
        await out_file.write(content)

    # Transcribe speech
    transcription_result = speech_service.transcribe(saved_path, language_hint=language_hint)

    if transcription_result["success"] and transcription_result["transcription"]:
        spoken_query = transcription_result["transcription"]
        response = assistant_service.process_chat(
            message=spoken_query,
            session_id=session_id,
            language_hint=language_hint or transcription_result.get("language"),
            db=db,
            current_user=current_user
        )
        return AssistantVoiceChatResponse(
            reply_text=response.reply_text,
            spoken_text=response.spoken_text,
            detected_language=response.detected_language,
            intent=response.intent,
            draft_complaint=response.draft_complaint,
            status_info=response.status_info,
            suggested_actions=response.suggested_actions,
            session_id=response.session_id,
            metadata=response.metadata,
            transcription=spoken_query,
            speech_status="completed",
            duration_seconds=transcription_result.get("duration_seconds")
        )
    else:
        # Transparent fallback when speech engine is not yet configured locally
        status_msg = transcription_result.get("message", "Speech recognition unavailable.")
        active_session = session_id or str(uuid.uuid4())
        samples = assistant_service.get_suggestions().sample_questions[:3]
        fallback_actions = [
            ActionSuggestion(label=s["label"], action_type="QUICK_PROMPT", payload={"prompt": s["query"]})
            for s in samples
        ]
        return AssistantVoiceChatResponse(
            reply_text=(
                "**Voice Audio Received.**\n\n"
                f"ℹ️ *Local Speech Status:* {status_msg}\n\n"
                "You can type your grievance directly in the chat box below or choose one of the quick assistance options."
            ),
            spoken_text="Voice audio received. You can type your message in the chat or choose one of the options below.",
            detected_language="English",
            intent="GENERAL_HELP",
            transcription="",
            speech_status=transcription_result.get("status", "unconfigured"),
            suggested_actions=fallback_actions,
            session_id=active_session,
            metadata={"saved_audio": saved_path, "speech_result": transcription_result}
        )


from fastapi.responses import Response
from app.ai.tts_service import synthesize_speech

@router.get("/suggestions", response_model=SuggestionsResponse)
def get_assistant_suggestions():
    """
    Returns curated sample prompts, category quick-starters, and emergency helplines.
    """
    return assistant_service.get_suggestions()


@router.get("/tts")
def stream_tts_audio(text: str, lang: Optional[str] = None):
    """
    Generates high-definition streaming MP3 voice audio for Tamil, Hindi, or English.
    Enables crystal-clear spoken Tamil responses on any browser, device, or operating system.
    """
    if not text or not text.strip():
        return Response(content=b"", media_type="audio/mpeg")

    audio_bytes = synthesize_speech(text, lang=lang)
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": "inline; filename=speech.mp3"
        }
    )

