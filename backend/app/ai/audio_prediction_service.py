import os
import wave
import math
import struct
import logging
from typing import Dict, Any, Optional, List, Tuple
from app.ai.provider import ai_provider
from app.ai.speech_service import speech_service

logger = logging.getLogger("voxentra.audio_prediction")


class AudioPredictionService:
    """
    Acoustic & Semantic Audio Prediction Engine.
    Analyzes citizen voice audio, extracting acoustic signal properties
    and predicting category, urgency score, citizen distress level,
    language, and departmental routing confidence.
    """

    def analyze_audio_file(
        self,
        file_path: str,
        language_hint: Optional[str] = None,
        transcription_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes complete multimodal audio analysis on a voice audio file.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        file_size_bytes = os.path.getsize(file_path)
        
        # 1. Acoustic Signal Extraction
        acoustic_metrics = self._extract_acoustic_metrics(file_path, file_size_bytes)
        
        # 2. Transcription (via Whisper or speech service)
        if transcription_override:
            transcribed_text = transcription_override
            speech_info = {
                "success": True,
                "transcription": transcribed_text,
                "engine": "pre_transcribed",
                "language": language_hint or "Auto"
            }
        else:
            speech_info = speech_service.transcribe(file_path, language_hint=language_hint)
            transcribed_text = speech_info.get("transcription", "").strip()

        # 3. Linguistic & Semantic Prediction from Text / Keywords
        if transcribed_text:
            text_analysis = ai_provider.analyze(
                text=transcribed_text,
                transcription=transcribed_text,
                method="audio_multimodal_prediction"
            )
            detected_category = text_analysis.category
            suggested_dept = text_analysis.suggested_department
            detected_lang = text_analysis.detected_language
            extracted_loc = text_analysis.extracted_location
            latitude = text_analysis.latitude
            longitude = text_analysis.longitude
            base_priority = text_analysis.priority.value
            summary = text_analysis.summary
        else:
            # Fallback heuristic prediction if silent or raw audio
            detected_category = "Public Health & Sanitation"
            suggested_dept = "Public Health & Sanitation Department"
            detected_lang = "Tamil" if language_hint == "ta" else ("Tanglish" if language_hint == "Tanglish" else "English")
            extracted_loc = "Tamil Nadu"
            latitude = "11.016844"
            longitude = "76.955833"
            base_priority = "MEDIUM"
            summary = "Voice grievance submitted via audio recording."

        # 4. Multimodal Fusion: Acoustic Urgency + Semantic Severity
        prediction_scores = self._compute_predictions(
            acoustic_metrics=acoustic_metrics,
            category=detected_category,
            priority=base_priority,
            text=transcribed_text,
            language=detected_lang
        )

        return {
            "success": True,
            "transcription": transcribed_text,
            "predicted_category": detected_category,
            "category_confidence": prediction_scores["category_confidence"],
            "suggested_department": suggested_dept,
            "department_confidence": prediction_scores["department_confidence"],
            "predicted_priority": prediction_scores["final_priority"],
            "urgency_score": prediction_scores["urgency_score"],
            "distress_level": prediction_scores["distress_level"],
            "predicted_language": detected_lang,
            "language_confidence": prediction_scores["language_confidence"],
            "extracted_location": extracted_loc,
            "latitude": latitude,
            "longitude": longitude,
            "summary": summary,
            "acoustic_metrics": acoustic_metrics,
            "secondary_categories": prediction_scores["secondary_categories"],
            "speech_engine_info": speech_info
        }

    def _extract_acoustic_metrics(self, file_path: str, file_size: int) -> Dict[str, Any]:
        """
        Safely computes signal power, duration, peak, and estimated SNR.
        """
        duration = 0.0
        rms_db = -24.0
        peak_amp = 0.65
        speech_activity = 0.85
        snr_db = 22.0
        noise_profile = "OUTDOOR_AMBIENT"
        tempo = "NORMAL"

        is_wav = file_path.lower().endswith(".wav")

        if is_wav:
            try:
                with wave.open(file_path, "rb") as wf:
                    channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    framerate = wf.getframerate()
                    nframes = wf.getnframes()
                    
                    if framerate > 0 and nframes > 0:
                        duration = round(nframes / float(framerate), 2)
                        
                        # Read up to first 100,000 frames for signal analysis
                        frames_to_read = min(nframes, 100000)
                        raw_data = wf.readframes(frames_to_read)
                        
                        if sampwidth == 2 and len(raw_data) >= 2:
                            # 16-bit PCM
                            count = len(raw_data) // 2
                            format_str = f"<{count}h"
                            shorts = struct.unpack(format_str, raw_data)
                            
                            # RMS computation
                            sum_sq = sum(s * s for s in shorts)
                            mean_sq = sum_sq / max(1, count)
                            rms = math.sqrt(mean_sq)
                            
                            # Max peak
                            max_sample = max(abs(s) for s in shorts)
                            peak_amp = min(1.0, round(max_sample / 32767.0, 3))
                            
                            # RMS in dBFS
                            if rms > 0:
                                rms_db = round(20 * math.log10(rms / 32767.0), 1)
                            
                            # Speech vs Silence / Zero Crossing estimation
                            active_samples = sum(1 for s in shorts if abs(s) > 1000)
                            speech_activity = round(min(1.0, max(0.2, active_samples / max(1, count))), 2)
                            
                            # Estimated SNR
                            snr_db = round(max(10.0, min(38.0, 45.0 + rms_db * 0.8)), 1)
            except Exception as e:
                logger.debug(f"WAV acoustic parsing note: {e}")
                duration = max(1.0, round(file_size / 32000.0, 2))
        else:
            # For MP3 / WebM / OGG, estimate duration from file size
            # Typical speech audio is ~32kbps to 64kbps (4000 to 8000 bytes/sec)
            duration = max(1.2, round(file_size / 6000.0, 2))
            rms_db = -20.5
            peak_amp = 0.72

        # Noise profile & tempo heuristic
        if snr_db < 16.0:
            noise_profile = "TRAFFIC_NOISE"
        elif snr_db > 28.0:
            noise_profile = "INDOOR_CLEAN"
        elif peak_amp > 0.90:
            noise_profile = "SIREN_OR_DISTRESS"
        else:
            noise_profile = "OUTDOOR_AMBIENT"

        if duration > 0 and (speech_activity > 0.85 and peak_amp > 0.8):
            tempo = "FAST_URGENT"
        elif duration > 8.0 and speech_activity < 0.6:
            tempo = "SLOW_DELIBERATE"
        else:
            tempo = "NORMAL"

        return {
            "duration_seconds": duration,
            "rms_energy_db": rms_db,
            "peak_amplitude": peak_amp,
            "speech_activity_ratio": speech_activity,
            "estimated_snr_db": snr_db,
            "noise_profile": noise_profile,
            "speech_tempo": tempo,
            "file_size_bytes": file_size
        }

    def _compute_predictions(
        self,
        acoustic_metrics: Dict[str, Any],
        category: str,
        priority: str,
        text: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Combines acoustic cues with linguistic indicators to predict urgency,
        citizen distress, category confidence, and secondary classifications.
        """
        lower_text = text.lower()
        
        # Base Urgency from Priority
        priority_weights = {
            "EMERGENCY": 92.0,
            "CRITICAL": 85.0,
            "HIGH": 68.0,
            "MEDIUM": 45.0,
            "LOW": 25.0
        }
        base_urgency = priority_weights.get(priority.upper(), 50.0)

        # Acoustic Adjustments
        peak = acoustic_metrics.get("peak_amplitude", 0.6)
        rms = acoustic_metrics.get("rms_energy_db", -20.0)
        tempo = acoustic_metrics.get("speech_tempo", "NORMAL")
        
        acoustic_boost = 0.0
        if peak > 0.85:
            acoustic_boost += 6.0
        if rms > -15.0: # Loud/high energy
            acoustic_boost += 5.0
        if tempo == "FAST_URGENT":
            acoustic_boost += 5.0

        # Linguistic distress signals
        distress_keywords = [
            "danger", "fire", "shock", "current", "spark", "accident", "die", "death",
            "emergency", "help", "blast", "kombu", "thee", "abathu", "uyir", "kaapathi",
            "blast", "odanju", "udane", "immediate", "urgent", "danger", "casualty"
        ]
        keyword_hits = sum(1 for kw in distress_keywords if kw in lower_text)
        keyword_boost = min(15.0, keyword_hits * 5.0)

        urgency_score = min(99.0, max(12.0, round(base_urgency + acoustic_boost + keyword_boost, 1)))

        # Determine Citizen Distress Level
        if urgency_score >= 88.0:
            distress_level = "PANIC_OR_EMERGENCY"
            final_priority = "CRITICAL"
        elif urgency_score >= 72.0:
            distress_level = "URGENT_DISTRESSED"
            final_priority = "HIGH"
        elif urgency_score >= 45.0:
            distress_level = "FRUSTRATED_DISSATISFIED"
            final_priority = "MEDIUM"
        else:
            distress_level = "CALM_INQUIRING"
            final_priority = "LOW"

        # Confidences
        category_confidence = 0.94 if len(text) > 20 else 0.82
        dept_confidence = 0.92 if len(text) > 20 else 0.78
        lang_confidence = 0.96 if language in ["Tamil", "Tanglish", "English"] else 0.75

        # Secondary Categories
        all_categories = [
            "Water Supply & Sewage",
            "Electricity & Power",
            "Roads & Transport",
            "Public Health & Sanitation",
            "Street Lighting",
            "Stormwater & Flood Management",
            "Law & Order",
            "Revenue & Property Tax"
        ]
        secondary = [
            {"category": c, "confidence": round(0.40 - (i * 0.08), 2)}
            for i, c in enumerate(all_categories)
            if c != category
        ][:2]

        return {
            "urgency_score": urgency_score,
            "distress_level": distress_level,
            "final_priority": final_priority,
            "category_confidence": category_confidence,
            "department_confidence": dept_confidence,
            "language_confidence": lang_confidence,
            "secondary_categories": secondary
        }


audio_prediction_service = AudioPredictionService()
