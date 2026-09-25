import os
import uuid
import aiofiles
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends

from app.config import settings
from app.ai.provider import ai_provider
from app.ai.speech_service import speech_service
from app.schemas.analysis import TextAnalysisRequest, AnalysisResponse, AudioTranscriptionResponse
from app.utils.validators import validate_audio_file
from app.core.exceptions import BadRequestException

router = APIRouter(prefix="/ai", tags=["AI Processing & Diagnostics"])


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_text_complaint(req: TextAnalysisRequest):
    """
    Analyzes citizen complaint text in Tamil, English, or Tanglish.
    Extracts category, location landmarks, severity priority, and department routing.
    """
    return ai_provider.analyze(req.text, method="deterministic_fallback")


@router.post("/transcribe", response_model=AudioTranscriptionResponse)
async def transcribe_audio_file(
    file: UploadFile = File(...),
    language_hint: Optional[str] = Form(None)
):
    """
    Transcribes an uploaded audio file using Whisper.
    """
    _, ext = validate_audio_file(file)

    unique_filename = f"ai_trans_{uuid.uuid4()}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    async with aiofiles.open(saved_path, "wb") as out_file:
        content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1024)
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise BadRequestException("Audio file exceeds maximum allowed size of 25MB")
        await out_file.write(content)

    result = speech_service.transcribe(saved_path, language_hint=language_hint)

    if os.path.exists(saved_path):
        try:
            os.remove(saved_path)
        except Exception:
            pass

    return AudioTranscriptionResponse(
        transcription=result.get("transcription", ""),
        language=result.get("language", "unknown"),
        duration_seconds=result.get("duration_seconds"),
        engine=result.get("engine", "none"),
        status=result.get("status", "unknown"),
        message=result.get("message")
    )
