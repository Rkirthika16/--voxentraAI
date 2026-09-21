from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.complaint import ComplaintPriority


class TextAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=2, description="Complaint text in Tamil, English, or Tanglish")
    language_hint: Optional[str] = None


class ExtractedLocation(BaseModel):
    name: str
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    confidence: float
    matched_keyword: Optional[str] = None


class AnalysisResponse(BaseModel):
    original_text: str
    transcription: Optional[str] = None
    detected_language: str
    normalized_text: str
    category: str
    suggested_department: str
    extracted_location: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    priority: ComplaintPriority
    summary: str
    analysis_method: str  # e.g., 'deterministic_fallback', 'whisper_local', 'ml_classifier'
    requires_review: bool = True
    warnings: List[str] = []
    metadata: Optional[Dict[str, Any]] = None


class AudioTranscriptionResponse(BaseModel):
    transcription: str
    language: str
    duration_seconds: Optional[float] = None
    engine: str
    status: str
    message: Optional[str] = None


class AcousticMetrics(BaseModel):
    duration_seconds: float
    rms_energy_db: float
    peak_amplitude: float
    speech_activity_ratio: float
    estimated_snr_db: float
    noise_profile: str
    speech_tempo: str
    file_size_bytes: int


class SecondaryCategoryPrediction(BaseModel):
    category: str
    confidence: float


class AudioPredictionResponse(BaseModel):
    success: bool
    transcription: str
    predicted_category: str
    category_confidence: float
    suggested_department: str
    department_confidence: float
    predicted_priority: str
    urgency_score: float
    distress_level: str
    predicted_language: str
    language_confidence: float
    extracted_location: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    summary: str
    acoustic_metrics: AcousticMetrics
    secondary_categories: List[SecondaryCategoryPrediction] = []
    speech_engine_info: Optional[Dict[str, Any]] = None

