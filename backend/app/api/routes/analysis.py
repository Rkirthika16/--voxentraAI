import os
import uuid
import aiofiles
from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import Optional

from app.config import settings
from app.ai.provider import ai_provider
from app.ai.speech_service import speech_service
from app.ai.audio_prediction_service import audio_prediction_service
from app.schemas.analysis import TextAnalysisRequest, AnalysisResponse, AudioPredictionResponse
from app.utils.validators import validate_audio_file
from app.core.exceptions import BadRequestException

router = APIRouter(prefix="/analysis", tags=["AI Analysis"])


@router.post("/text", response_model=AnalysisResponse)
def analyze_text_complaint(req: TextAnalysisRequest):
    """
    Analyzes citizen complaint text in Tamil, English, or Tanglish.
    Extracts category, location landmarks, severity priority, and generates summary.
    """
    return ai_provider.analyze(req.text, method="deterministic_fallback")


@router.post("/audio", response_model=AnalysisResponse)
async def analyze_audio_complaint(
    file: UploadFile = File(...),
    language_hint: Optional[str] = Form(None)
):
    """
    Accepts browser recording or audio file upload.
    Performs speech-to-text with Whisper (or transparent fallback) and runs complaint analysis.
    """
    _, ext = validate_audio_file(file)
    
    unique_filename = f"{uuid.uuid4()}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save uploaded file safely
    async with aiofiles.open(saved_path, "wb") as out_file:
        content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1024)
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise BadRequestException("Audio file exceeds maximum allowed size of 25MB")
        await out_file.write(content)

    # Transcribe
    transcription_result = speech_service.transcribe(saved_path, language_hint=language_hint)

    if transcription_result["success"] and transcription_result["transcription"]:
        text_to_analyze = transcription_result["transcription"]
        response = ai_provider.analyze(
            text=text_to_analyze,
            transcription=text_to_analyze,
            method="whisper_local"
        )
        return response
    else:
        # Honest fallback response when speech service is not configured
        error_msg = transcription_result.get("message", "Speech recognition unavailable.")
        return AnalysisResponse(
            original_text="",
            transcription=None,
            detected_language="Unknown",
            normalized_text="",
            category="Other",
            suggested_department="General Administration Department",
            extracted_location=None,
            latitude=None,
            longitude=None,
            priority="MEDIUM",
            summary="Audio grievance received. Speech engine status: " + transcription_result.get("status", "unconfigured"),
            analysis_method="speech_engine_unconfigured",
            requires_review=True,
            warnings=[error_msg, "Please type your complaint text directly or review once speech model is active."],
            metadata={"audio_file_path": saved_path, "speech_result": transcription_result}
        )


@router.post("/audio-prediction", response_model=AudioPredictionResponse)
async def predict_audio_complaint(
    file: UploadFile = File(...),
    language_hint: Optional[str] = Form(None),
    transcription_override: Optional[str] = Form(None)
):
    """
    Performs multimodal acoustic & semantic audio prediction on a voice audio file.
    Predicts category, urgency score (0-100), distress level, language,
    and extracts acoustic signal properties (RMS dB, SNR, peak, tempo, noise profile).
    """
    _, ext = validate_audio_file(file)
    
    unique_filename = f"pred_{uuid.uuid4()}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    async with aiofiles.open(saved_path, "wb") as out_file:
        content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1024)
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise BadRequestException("Audio file exceeds maximum allowed size of 25MB")
        await out_file.write(content)

    prediction = audio_prediction_service.analyze_audio_file(
        file_path=saved_path,
        language_hint=language_hint,
        transcription_override=transcription_override
    )
    return prediction

