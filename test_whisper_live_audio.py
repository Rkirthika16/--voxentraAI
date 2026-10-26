import os
import sys
import tempfile
import asyncio

# Setup paths
if sys.platform == "win32":
    reconfig = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig):
        try:
            reconfig(encoding="utf-8")
        except Exception:
            pass

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.ai.speech_service import speech_service
from app.ai.tts_service import synthesize_speech
from app.services.speech_correction import speech_correction_service
from app.services.language_detector import language_detector

def test_whisper_multilingual_audio():
    print("=" * 70)
    print("STEP 3 VERIFICATION: WHISPER LIVE AUDIO TRANSCRIPTION (TAMIL, ENGLISH, TANGLISH)")
    print("=" * 70)

    avail = speech_service.check_availability()
    print(f"Speech Service Availability: {avail}")
    assert avail["available"] is True, f"Whisper engine not available: {avail}"

    test_cases = [
        {
            "name": "English Test",
            "lang": "English",
            "text": "There is no water in my street",
            "lang_hint": "en"
        },
        {
            "name": "Tamil Test",
            "lang": "Tamil",
            "text": "எங்க தெருவில் தண்ணீர் வரவில்லை",
            "lang_hint": "ta"
        },
        {
            "name": "Tanglish Test",
            "lang": "Tanglish",
            "text": "Gandhipuram-la thanni varala",
            "lang_hint": "ta"
        }
    ]

    temp_dir = tempfile.mkdtemp(prefix="whisper_test_")

    for tc in test_cases:
        print(f"\n--- Testing {tc['name']} ---")
        print(f"Original Text: '{tc['text']}'")
        
        # Synthesize real audio bytes
        audio_data = synthesize_speech(tc["text"], lang=tc["lang"])
        assert len(audio_data) > 0, "Failed to generate test audio data"
        
        audio_path = os.path.join(temp_dir, f"{tc['lang'].lower()}_sample.mp3")
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        
        print(f"Generated Audio File: {audio_path} ({len(audio_data)} bytes)")

        # Run Whisper Transcription
        res = speech_service.transcribe(audio_path, language_hint=tc["lang_hint"])
        print(f"Whisper Output: {res}")
        assert res["success"] is True, f"Transcription failed: {res.get('message')}"
        assert len(res["transcription"]) > 0, "Whisper returned empty transcription"
        print(f"-> Raw Whisper: '{res.get('raw_transcription')}'")
        print(f"-> Normalized/Cleaned: '{res.get('transcription')}'")
        
        # Test Language Detection on transcribed output
        det_lang, conf = language_detector.detect(res["transcription"])
        print(f"-> Detected Language: {det_lang} (confidence: {conf})")

    print("\n" + "=" * 70)
    print("WHISPER LIVE AUDIO TESTS COMPLETED SUCCESSFULLY! ✅")
    print("=" * 70)

if __name__ == "__main__":
    test_whisper_multilingual_audio()
