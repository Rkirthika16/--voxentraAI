"""Language Detector Service for VoxentraAI Conversational IVR.
Accurately detects Tamil, English, and Tanglish from spoken and written utterances,
supporting seamless real-time language switching across dialogue turns.
"""
import re
from typing import Tuple, Optional
from app.ai.language_service import detect_language as ai_detect_language, is_tamil_script

class LanguageDetector:
    """Detects and manages language across multi-turn IVR phone calls."""

    @staticmethod
    def detect(text: str, current_session_lang: Optional[str] = None) -> Tuple[str, float]:
        """
        Detects language from citizen speech:
        - Tamil: Native Tamil script
        - English: Pure English speech
        - Tanglish: Tamil spoken in Latin / English transliteration (e.g. 'thanni varala', 'current cut aachu')
        Returns (language_name, confidence)
        """
        return ai_detect_language(text, current_session_lang=current_session_lang)

    @staticmethod
    def is_tamil(text: str) -> bool:
        return is_tamil_script(text)

    @staticmethod
    def should_switch_language(text: str, current_lang: str) -> Tuple[bool, str]:
        """Detects if citizen switched languages mid-call."""
        new_lang, conf = ai_detect_language(text, current_session_lang=None)
        if conf >= 0.90 and new_lang != current_lang:
            return True, new_lang
        return False, current_lang


language_detector = LanguageDetector()
detect_language = LanguageDetector.detect
