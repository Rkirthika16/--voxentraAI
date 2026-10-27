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
            (r'(?:^|\s)டி\.?\s*பி\.?\s*ரோட்(?:டு|டில்|ட்டில்|ட்[டி]*ல்|ல்)?(?:\s|$|[.,!?])', ' DB Road '),
            (r'(?:^|\s)டி\s*பி\s*ரோடு(?:\s|$|[.,!?])', ' DB Road '),
            (r'(?:^|\s)டி\.?\s*பி\.?\s*ரோடு(?:\s|$|[.,!?])', ' DB Road '),
            (r'\btani\s*vara\s*la\b', 'thanni varala'),
            (r'\btani\s*varala\b', 'thanni varala'),
            (r'\btani\s*varla\b', 'thanni varala'),
            (r'\bthani\s*vara\s*la\b', 'thanni varala'),
            (r'\bvara\s*la\b', 'varala'),
            (r'\bvara\s*le\b', 'varala'),
            (r'\bvarla\b', 'varala'),
            (r'\bthani\b', 'thanni'),
            (r'\bcoimbatore\s+vada\s*veli\b', 'Coimbatore Vadavalli'),
            (r'\bcoimbatore\s+vadaveli\b', 'Coimbatore Vadavalli'),
            (r'\bcoimbatore\s+vada\s*valli\b', 'Coimbatore Vadavalli'),
            (r'\bvada\s*veli\b', 'Vadavalli'),
            (r'\bvada\s*valli\b', 'Vadavalli'),
            (r'\bvadavelli\b', 'Vadavalli'),
            (r'\bvadavali\b', 'Vadavalli'),
            (r'\bvaadavalli\b', 'Vadavalli'),
            (r'\banna\s*nagar\s*rendu\s*street\b', 'Anna Nagar 2nd Street'),
            (r'\banna\s*nagar\s*second\s*street\b', 'Anna Nagar 2nd Street'),
            (r'\banna\s*nagar\s*2\s*street\b', 'Anna Nagar 2nd Street'),
            (r'\banna\s*nagar\s*rendavathu\s*(?:theru|street)\b', 'Anna Nagar 2nd Street'),
            (r'\bgovernment\s*school\s*pakkathula\b', 'Government School pakkathula'),
            (r'\bgovernment\s*school\s*pakkam\b', 'Government School pakkam'),
            (r'\bgovt\s*school\s*pakkathula\b', 'Government School pakkathula'),
            (r'\bgovt\s*school\s*kitta\b', 'Government School kitta'),
            (r'\bcurrent\s*cut\s*aagiduchu\b', 'current cut aaiduchu'),
            (r'\bcurrent\s*cut\s*aayiduchu\b', 'current cut aaiduchu'),
            (r'\bcurrent\s*cut\s*aachu\b', 'current cut aaiduchu'),
            (r'\bvada\s*valli\s*la\s*thanni\s*varala\b', 'Vadavalli-la thanni varala'),
            (r'\bvada\s*valli\s*la\s*problem\b', 'Vadavalli-la problem'),
            (r'\bvada\s*valli\s*la\b', 'Vadavalli-la'),
            (r'\benga\s*oor\s*la\b', 'enga oorla'),
            (r'\benga\s*area\s*la\b', 'enga areala'),
            (r'\bthree\s*days\s*ah\s*water\s*varala\b', '3 days-ah water varala'),
            (r'\b3\s*days\s*ah\s*water\s*varala\b', '3 days-ah water varala'),
            (r'\bthree\s*days\s*ah\b', '3 days-ah'),
            (r'\b3\s*days\s*ah\b', '3 days-ah'),
            (r'\bmoonu\s*naala\b', '3 naala'),
            (r'\brendu\s*naala\b', '2 naala'),
            (r'\bfull\s*street\s*la\b', 'full street-la'),
            (r'\bfull\s*street\s*layum\b', 'full street-layum'),
            (r'\bstreet\s*light\s*eriyala\b', 'street light eriyala'),
            (r'\bstreet\s*light\s*eriyave\s*illa\b', 'street light eriyala'),
            (r'\bstreet\s*light\s*eriyadhu\b', 'street light eriyala'),
            (r'\broad\s*romba\s*damage\s*ah\s*irukku\b', 'road romba damage-ah irukku'),
            (r'\broad\s*damage\s*ah\s*irukku\b', 'road damage-ah irukku'),
            (r'\broad\s*damage\s*aayirukku\b', 'road damage-ah irukku'),
            (r'\broad\s*sari\s*illa\b', 'road sari illa'),
            (r'\bgandhipuram\s*bus\s*stand\s*pakkam\s*road\s*sari\s*illa\b', 'Gandhipuram bus stand pakkam road sari illa'),
            (r'\bbus\s*stand\s*pakkam\b', 'bus stand pakkam'),
            (r'\bbus\s*stand\s*kitta\b', 'bus stand kitta'),
            (r'\bkuppa\s*edukkave\s*varala\b', 'kuppai edukkave varala'),
            (r'\bkuppa\s*edukka\s*varala\b', 'kuppai edukkave varala'),
            (r'\bkuppa\s*allave\s*illa\b', 'kuppai allave illa'),
            (r'\bkuppa\s*allamaatenguranga\b', 'kuppai allamaatenguranga'),
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

    def correct_with_metadata(self, raw_text: str) -> Dict[str, str]:
        """
        Preserves original transcript, normalized transcript, and corrected transcript separately
        for debugging, auditing, and multi-stage evaluation.
        """
        raw = raw_text.strip() if raw_text else ""
        cleaned = self.clean(raw)
        norm = self.normalize(raw)
        return {
            "original_transcript": raw,
            "normalized_transcript": norm,
            "corrected_transcript": cleaned
        }

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
correct_with_metadata = speech_correction_service.correct_with_metadata
