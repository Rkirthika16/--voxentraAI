"""Voice Assistant Core Service for VoxentraAI.
Coordinates live audio intake, Whisper STT, conversation state tracking, and TTS.
"""
import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.services.conversation_manager import conversation_manager
from app.services.speech_correction import speech_correction_service
from app.services.language_detector import language_detector
from app.services.location_resolver import location_resolver
from app.services.question_manager import question_manager
from app.ai.speech_service import speech_service
from app.ai.tts_service import synthesize_speech

logger = logging.getLogger("voxentra.voice_assistant")


class VoiceAssistantService:
    """Production Voice Assistant Interface for Web and Telephony."""

    def __init__(self):
        self.conversation_manager = conversation_manager
        self.speech_service = speech_service
        self.speech_correction = speech_correction_service
        self.language_detector = language_detector
        self.location_resolver = location_resolver
        self.question_manager = question_manager

    def create_call_session(
        self,
        db: Session,
        caller_phone: Optional[str] = "+919843098765",
        language_preference: Optional[str] = "Auto"
    ):
        """Creates session where AI remains silent until citizen speaks first."""
        return self.conversation_manager.create_session(
            db=db,
            caller_phone=caller_phone,
            language_preference=language_preference
        )

    def process_turn(
        self,
        db: Session,
        session_id: str,
        speech_text: str,
        audio_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Processes one conversational turn."""
        return self.conversation_manager.process_citizen_turn(
            db=db,
            session_id=session_id,
            speech_text=speech_text,
            audio_url=audio_url
        )

    def synthesize_voice(self, text: str, lang: str = "ta") -> bytes:
        """Synthesizes high-fidelity audio stream for phone or browser."""
        return synthesize_speech(text, lang=lang)


voice_assistant = VoiceAssistantService()
