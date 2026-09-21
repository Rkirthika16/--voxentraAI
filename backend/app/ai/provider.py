from typing import Optional, Dict, Any, List
from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text
from app.ai.classification_service import classify_complaint
from app.ai.location_service import extract_location
from app.ai.priority_service import assess_priority
from app.schemas.analysis import AnalysisResponse


class AIProvider:
    def analyze(
        self,
        text: str,
        transcription: Optional[str] = None,
        method: str = "deterministic_fallback"
    ) -> AnalysisResponse:
        """
        Executes full NLP pipeline for civic complaint analysis:
        1. Language Detection (Tamil, English, Tanglish)
        2. Text Normalization
        3. Category Classification & Department Routing
        4. Location & Coordinate Extraction
        5. Severity & Priority Assessment
        6. Summary and Review Guidance
        """
        raw_text = text or ""
        normalized = normalize_text(raw_text)
        detected_lang, lang_confidence = detect_language(raw_text)
        
        category, suggested_dept, cat_confidence = classify_complaint(normalized)
        loc_name, lat, lon, loc_confidence = extract_location(raw_text)
        priority, priority_confidence = assess_priority(normalized, category)

        # Generate summary
        loc_str = f" near {loc_name}" if loc_name else ""
        if detected_lang == "Tamil":
            summary = f"{category} தொடர்பான புகார்{loc_str} (முன்னுரிமை: {priority.value})"
        elif detected_lang == "Tanglish":
            summary = f"{category} grievance reported{loc_str} with {priority.value} priority."
        else:
            summary = f"{category} issue reported{loc_str} requiring attention ({priority.value} priority)."

        warnings: List[str] = []
        if not loc_name:
            warnings.append("Specific landmark or street location could not be determined automatically. Please verify your location.")
        if category == "Other":
            warnings.append("Complaint could not be categorized automatically with high confidence. Please verify the category.")

        requires_review = len(warnings) > 0 or cat_confidence < 0.7

        return AnalysisResponse(
            original_text=raw_text,
            transcription=transcription,
            detected_language=detected_lang,
            normalized_text=normalized,
            category=category,
            suggested_department=suggested_dept,
            extracted_location=loc_name,
            latitude=lat,
            longitude=lon,
            priority=priority,
            summary=summary,
            analysis_method=method,
            requires_review=requires_review,
            warnings=warnings,
            metadata={
                "language_confidence": lang_confidence,
                "category_confidence": cat_confidence,
                "location_confidence": loc_confidence,
                "priority_confidence": priority_confidence
            }
        )


ai_provider = AIProvider()
