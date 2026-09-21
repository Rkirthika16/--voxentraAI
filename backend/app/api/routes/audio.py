import os
import uuid
import aiofiles
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form

from app.config import settings
from app.ai.speech_service import speech_service
from app.schemas.analysis import AudioTranscriptionResponse
from app.utils.validators import validate_audio_file
from app.core.exceptions import BadRequestException

router = APIRouter(prefix="/audio", tags=["Audio & Speech"])


@router.post("/transcribe", response_model=AudioTranscriptionResponse)
async def transcribe_audio_file(
    file: UploadFile = File(...),
    language_hint: Optional[str] = Form(None)
):
    """
    Direct endpoint to transcribe an uploaded audio file using Whisper.
    """
    _, ext = validate_audio_file(file)

    unique_filename = f"{uuid.uuid4()}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    async with aiofiles.open(saved_path, "wb") as out_file:
        content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1024)
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise BadRequestException("Audio file exceeds maximum allowed size of 25MB")
        await out_file.write(content)

    result = speech_service.transcribe(saved_path, language_hint=language_hint)

    return AudioTranscriptionResponse(
        transcription=result.get("transcription", ""),
        language=result.get("language", "unknown"),
        duration_seconds=result.get("duration_seconds"),
        engine=result.get("engine", "none"),
        status=result.get("status", "unknown"),
        message=result.get("message")
    )


@router.get("/status")
def get_speech_engine_status():
    """Returns availability status of the local Whisper speech engine."""
    return speech_service.check_availability()
