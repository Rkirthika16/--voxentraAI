import os
import logging
import importlib.util
import importlib
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
        if self._is_available is True:
            return {
                "available": True,
                "engine": self._engine_type,
                "error": None
            }

        # Check for faster-whisper
        if importlib.util.find_spec("faster_whisper") is not None:
            try:
                importlib.import_module("faster_whisper")
                self._engine_type = "faster-whisper"
                self._is_available = True
                self._init_error = None
                return {"available": True, "engine": self._engine_type, "error": None}
            except Exception as e:
                logger.debug(f"faster-whisper found but import failed: {e}")

        # Check for openai-whisper
        if importlib.util.find_spec("whisper") is not None:
            try:
                importlib.import_module("whisper")
                self._engine_type = "openai-whisper"
                self._is_available = True
                self._init_error = None
                return {"available": True, "engine": self._engine_type, "error": None}
            except Exception as e:
                logger.debug(f"openai-whisper found but import failed: {e}")

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

        device = getattr(settings, "WHISPER_DEVICE", "cpu")
        model_size = getattr(settings, "WHISPER_MODEL_SIZE", "base")
        compute_type = getattr(settings, "WHISPER_COMPUTE_TYPE", "int8")

        try:
            if self._engine_type == "faster-whisper":
                faster_mod = importlib.import_module("faster_whisper")
                WhisperModel = getattr(faster_mod, "WhisperModel")
                logger.info(f"Loading faster-whisper model '{model_size}' on {device}...")
                try:
                    self._model = WhisperModel(
                        model_size,
                        device=device,
                        compute_type=compute_type
                    )
                except Exception as ex_dev:
                    logger.warning(f"Failed faster-whisper on {device}, falling back to cpu: {ex_dev}")
                    self._model = WhisperModel(
                        model_size,
                        device="cpu",
                        compute_type="int8"
                    )
            elif self._engine_type == "openai-whisper":
                whisper_mod = importlib.import_module("whisper")
                logger.info(f"Loading openai-whisper model '{model_size}' on {device}...")
                try:
                    self._model = whisper_mod.load_model(model_size, device=device)
                except Exception as ex_dev:
                    logger.warning(f"Failed openai-whisper on {device}, falling back to cpu: {ex_dev}")
                    self._model = whisper_mod.load_model(model_size, device="cpu")
            return self._model
        except Exception as e:
            logger.warning(f"Failed to load Whisper model: {e}")
            self._init_error = str(e)
            return None

    def transcribe(
        self,
        audio_file_path: str,
        language_hint: Optional[str] = None,
        transcription_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribes given audio file.
        Returns honest metadata and text; seamlessly incorporates client transcription hint if available.
        """
        hint_text = (transcription_hint or "").strip()
        if not os.path.exists(audio_file_path):
            if hint_text:
                return {
                    "success": True,
                    "transcription": hint_text,
                    "raw_transcription": hint_text,
                    "language": "Tamil" if any('\u0B80' <= c <= '\u0BFF' for c in hint_text) else "English",
                    "engine": "browser_speech_recognition",
                    "status": "completed",
                    "message": "Used browser speech recognition fallback."
                }
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
            if hint_text:
                return {
                    "success": True,
                    "transcription": hint_text,
                    "raw_transcription": hint_text,
                    "language": "Tamil" if any('\u0B80' <= c <= '\u0BFF' for c in hint_text) else "English",
                    "engine": "browser_speech_recognition",
                    "status": "completed",
                    "message": "Used browser speech recognition fallback."
                }
            return {
                "success": False,
                "transcription": "",
                "language": "unknown",
                "engine": "unconfigured",
                "status": "speech_engine_not_configured",
                "message": "Speech recognition is not configured locally. Please enter your complaint as text."
            }

        model = self._get_model()
        if model is None:
            if hint_text:
                return {
                    "success": True,
                    "transcription": hint_text,
                    "raw_transcription": hint_text,
                    "language": "Tamil" if any('\u0B80' <= c <= '\u0BFF' for c in hint_text) else "English",
                    "engine": "browser_speech_recognition",
                    "status": "completed",
                    "message": "Used browser speech recognition fallback."
                }
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
                if not raw_transcription and hint_text:
                    raw_transcription = hint_text
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
                if not raw_transcription and hint_text:
                    raw_transcription = hint_text
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
            if hint_text:
                return {
                    "success": True,
                    "transcription": hint_text,
                    "raw_transcription": hint_text,
                    "language": "Tamil" if any('\u0B80' <= c <= '\u0BFF' for c in hint_text) else "English",
                    "engine": "browser_speech_recognition",
                    "status": "completed",
                    "message": "Used browser speech recognition fallback after local transcription exception."
                }
            return {
                "success": False,
                "transcription": "",
                "language": "unknown",
                "engine": self._engine_type,
                "status": "transcription_error",
                "message": f"Speech transcription error: {str(e)}"
            }


speech_service = SpeechService()
