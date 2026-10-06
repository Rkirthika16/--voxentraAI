"""Speech Correction & Normalization Service for VoxentraAI Conversational IVR.
Handles speech recognition errors, Whisper spacing mistakes, Tanglish phonetic normalization,
and spelled-out letter reconstruction.
"""
import re
import unicodedata
from typing import Optional, Dict
from app.ai.normalization_service import (
    clean_transcription as ai_clean_transcription,
    normalize_text as ai_normalize_text
)


class SpeechCorrectionService:
    """Corrects, cleans, and standardizes citizen speech transcripts."""

    def __init__(self):
        # Spacing and phonetic lookup
        self.whisper_spacing_fixes = [
            (r'\bgandhi\s*puram\s*(?:-|–)?\s*la\s*tani\s*vara\s*la\b', 'Gandhipuram-la thanni varala'),
            (r'\bgandhi\s*puram\s*la\s*tani\s*vara\s*la\b', 'Gandhipuram-la thanni varala'),
            (r'\bgandhi\s*puram\s*la\s*thani\s*vara\s*la\b', 'Gandhipuram-la thanni varala'),
            (r'\bgandhi\s*puram\s*la\s*thanni\s*varala\b', 'Gandhipuram-la thanni varala'),
            (r'\bgandhi\s*puram\s*la\b', 'Gandhipuram-la'),
            (r'\bgandhipuram\s*la\b', 'Gandhipuram-la'),
            (r'\bgandhi\s*puram\b', 'Gandhipuram'),
            (r'\bsaravana\s*patti\b', 'Saravanampatti'),
            (r'\bsaravanampatti\s*la\b', 'Saravanampatti-la'),
            (r'\bsinga\s*nallur\b', 'Singanallur'),
            (r'\bpeela\s*medu\b', 'Peelamedu'),
            (r'\br\s*s\s*puram\b', 'RS Puram'),
            (r'\br\.\s*s\.\s*puram\b', 'RS Puram'),
            (r'\bsaibaba\s*colony\b', 'Saibaba Colony'),
            (r'\bcross\s*cutting\b', 'Cross Cut Road'),
            (r'\bcross\s*cut\b', 'Cross Cut Road'),
            (r'\b100\s*feet\s*road\b', '100 Feet Road'),
            (r'\bhundred\s*feet\s*road\b', '100 Feet Road'),
            (r'\bd\s*b\s*road\b', 'DB Road'),
            (r'\bd\.?\s*b\.?\s*road\b', 'DB Road'),
            (r'\btani\s*vara\s*la\b', 'thanni varala'),
            (r'\btani\s*varala\b', 'thanni varala'),
            (r'\btani\s*varla\b', 'thanni varala'),
            (r'\bthani\s*vara\s*la\b', 'thanni varala'),
            (r'\bvara\s*la\b', 'varala'),
            (r'\bvara\s*le\b', 'varala'),
            (r'\bvarla\b', 'varala'),
            (r'\bthani\b', 'thanni'),
            (r'\bcurrent\s*cut\s*aagiduchu\b', 'current cut aaiduchu'),
            (r'\bcurrent\s*cut\s*aayiduchu\b', 'current cut aaiduchu'),
            (r'\bcurrent\s*cut\s*aachu\b', 'current cut aaiduchu'),
        ]

    def clean(self, raw_text: str) -> str:
        """Cleans and repairs STT transcript with Whisper spacing and phonetic fixes."""
        if not raw_text:
            return ""

        text = raw_text.strip()
        # Handle spelled out letters (e.g., 'P E E L A M E D U' -> 'Peelamedu')
        text = self.reconstruct_spelled_letters(text)

        # Apply base normalization
        cleaned = ai_clean_transcription(text)

        # Apply spacing patterns
        lowered = cleaned.lower()
        for pat, repl in self.whisper_spacing_fixes:
            cleaned = re.sub(pat, repl, cleaned, flags=re.IGNORECASE)

        return cleaned

    def normalize(self, text: str) -> str:
        """Performs full text normalization."""
        cleaned = self.clean(text)
        return ai_normalize_text(cleaned)

    def reconstruct_spelled_letters(self, text: str) -> str:
        """
        Reconstructs words that citizens spelled out letter by letter.
        Example: 'P E E L A M E D U' -> 'Peelamedu'
        'G A N D H I P U R A M' -> 'Gandhipuram'
        """
        if not text:
            return ""

        def join_letters(match):
            letters = re.findall(r'[A-Za-z]', match.group(0))
            word = "".join(letters)
            return word.title()

        pattern = r'\b(?:[A-Za-z]\s+){3,}[A-Za-z]\b'
        return re.sub(pattern, join_letters, text)


speech_correction_service = SpeechCorrectionService()
clean_transcription = speech_correction_service.clean
normalize_text = speech_correction_service.normalize
