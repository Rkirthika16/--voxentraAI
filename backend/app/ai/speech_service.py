import os
import logging
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("voxentra.speech")


class SpeechService:
    def __init__(self):
        self._model = None
        self._engine_type = None
        self._is_available = None
        self._init_error = None

    def check_availability(self) -> Dict[str, Any]:
        """Check if local speech recognition libraries are available."""
        if self._is_available is not None:
            return {
                "available": self._is_available,
                "engine": self._engine_type,
                "error": self._init_error
            }

        # Check for faster-whisper
        try:
            import faster_whisper
            self._engine_type = "faster-whisper"
            self._is_available = True
            return {"available": True, "engine": self._engine_type, "error": None}
        except ImportError:
            pass

        # Check for openai-whisper
        try:
            import whisper
            self._engine_type = "openai-whisper"
            self._is_available = True
            return {"available": True, "engine": self._engine_type, "error": None}
        except ImportError:
            pass

        self._is_available = False
        self._engine_type = "none"
        self._init_error = "Whisper libraries (faster-whisper or openai-whisper) are not installed in the environment."
        return {
            "available": False,
            "engine": "none",
            "error": self._init_error
        }

    def _get_model(self):
        """Lazy loader for Whisper model."""
        if self._model is not None:
            return self._model

        avail = self.check_availability()
        if not avail["available"]:
            return None

        try:
            if self._engine_type == "faster-whisper":
                from faster_whisper import WhisperModel
                logger.info(f"Loading faster-whisper model '{settings.WHISPER_MODEL_SIZE}' on {settings.WHISPER_DEVICE}...")
                self._model = WhisperModel(
                    settings.WHISPER_MODEL_SIZE,
                    device=settings.WHISPER_DEVICE,
                    compute_type=settings.WHISPER_COMPUTE_TYPE
                )
            elif self._engine_type == "openai-whisper":
                import whisper
                logger.info(f"Loading openai-whisper model '{settings.WHISPER_MODEL_SIZE}' on {settings.WHISPER_DEVICE}...")
                self._model = whisper.load_model(settings.WHISPER_MODEL_SIZE, device=settings.WHISPER_DEVICE)
            return self._model
        except Exception as e:
            logger.warning(f"Failed to load Whisper model: {e}")
            self._init_error = str(e)
            return None

    def transcribe(self, audio_file_path: str, language_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribes given audio file.
        Returns honest metadata and text; does NOT fabricate output if model is missing.
        """
        if not os.path.exists(audio_file_path):
            return {
                "success": False,
                "transcription": "",
                "language": "unknown",
                "engine": "none",
                "status": "file_not_found",
                "message": f"Audio file not found at {audio_file_path}"
            }

        avail = self.check_availability()
        if not avail["available"]:
            return {
                "success": False,
                "transcription": "",
                "language": "unknown",
                "engine": "unconfigured",
                "status": "speech_engine_not_configured",
                "message": "Speech recognition is not configured locally. Please enter your complaint as text or install faster-whisper/openai-whisper and FFmpeg."
            }

        model = self._get_model()
        if model is None:
            return {
                "success": False,
                "transcription": "",
                "language": "unknown",
                "engine": self._engine_type,
                "status": "model_load_failed",
                "message": f"Failed to initialize speech model: {self._init_error}"
            }

        try:
            if self._engine_type == "faster-whisper":
                segments, info = model.transcribe(
                    audio_file_path,
                    language=language_hint if language_hint in ["ta", "en"] else None,
                    beam_size=5
                )
                raw_transcription = " ".join([segment.text for segment in segments]).strip()
                from app.ai.normalization_service import clean_transcription
                transcription = clean_transcription(raw_transcription)
                detected_lang = info.language if hasattr(info, 'language') else "ta"
                return {
                    "success": True,
                    "transcription": transcription,
                    "raw_transcription": raw_transcription,
                    "language": "Tamil" if detected_lang == "ta" else "English",
                    "duration_seconds": getattr(info, 'duration', None),
                    "engine": "faster-whisper",
                    "status": "completed",
                    "message": "Transcription successful"
                }

            elif self._engine_type == "openai-whisper":
                result = model.transcribe(
                    audio_file_path,
                    language=language_hint if language_hint in ["ta", "en"] else None
                )
                raw_transcription = result.get("text", "").strip()
                from app.ai.normalization_service import clean_transcription
                transcription = clean_transcription(raw_transcription)
                return {
                    "success": True,
                    "transcription": transcription,
                    "raw_transcription": raw_transcription,
                    "language": "Tamil" if result.get("language") == "ta" else "English",
                    "engine": "openai-whisper",
                    "status": "completed",
                    "message": "Transcription successful"
                }

        except Exception as e:
            logger.error(f"Error during audio transcription: {e}")
            return {
                "success": False,
                "transcription": "",
                "language": "unknown",
                "engine": self._engine_type,
                "status": "transcription_error",
                "message": f"Speech transcription error: {str(e)}"
            }


speech_service = SpeechService()
