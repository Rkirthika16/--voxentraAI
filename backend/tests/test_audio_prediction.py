import io
import uuid
import wave
import struct
import pytest
from app.ai.audio_prediction_service import audio_prediction_service


def create_mock_wav_bytes(duration_sec: float = 1.0, freq: float = 440.0, sample_rate: int = 16000) -> bytes:
    """Generates a synthetic 16-bit PCM WAV in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        nframes = int(duration_sec * sample_rate)
        # Generate simple sine-like amplitude
        raw_samples = bytearray()
        for i in range(nframes):
            val = int(10000 * (1 if (i % 40) < 20 else -1))
            raw_samples.extend(struct.pack("<h", val))
        wf.writeframes(raw_samples)
    return buf.getvalue()


def test_audio_prediction_service_wav(tmp_path):
    wav_path = str(tmp_path / "test_sample.wav")
    wav_bytes = create_mock_wav_bytes(duration_sec=1.5)
    with open(wav_path, "wb") as f:
        f.write(wav_bytes)

    result = audio_prediction_service.analyze_audio_file(
        wav_path,
        transcription_override="Gandhipuram-la thanni pipe odanju water romba waste aaguthu, urgent-ah sari pannunga."
    )

    assert result["success"] is True
    assert "Water" in result["predicted_category"]
    assert "Water" in result["suggested_department"]
    assert result["predicted_language"] == "Tanglish"
    assert result["urgency_score"] > 50.0
    assert "acoustic_metrics" in result
    assert result["acoustic_metrics"]["duration_seconds"] >= 1.0
    assert result["acoustic_metrics"]["peak_amplitude"] > 0.0


def test_audio_prediction_endpoint(client):
    wav_bytes = create_mock_wav_bytes(duration_sec=2.0)
    files = {"file": ("citizen_call.wav", io.BytesIO(wav_bytes), "audio/wav")}
    data = {
        "transcription_override": "பீளமேடு பகுதியில் மின் கம்பி அறுந்து விழுந்து தீப்பொறி பறக்கிறது.",
        "language_hint": "ta"
    }
    response = client.post("/api/v1/analysis/audio-prediction", files=files, data=data)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert "Electricity" in res_json["predicted_category"]
    assert res_json["predicted_language"] == "Tamil"
    assert res_json["urgency_score"] >= 70.0
    assert "acoustic_metrics" in res_json
    assert res_json["acoustic_metrics"]["duration_seconds"] >= 1.5


def test_ivr_dialogue_turn_clarification(client):
    """Test AI asking clarifying location question on turn 1 when location is unspecified."""
    req_payload = {
        "call_sid": "CA_test12345",
        "caller_phone": "+919843011223",
        "dialogue_turn": 1,
        "user_speech": "குடிநீர் குழாய் உடைந்து தண்ணீர் வீணாகிறது.",
        "language_preference": "ta"
    }
    response = client.post("/api/v1/ivr/dialogue-turn", json=req_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] in ["GATHER_MORE_INFO", "CONFIRMED"]
    assert data["ai_spoken_reply"] != ""


def test_ivr_dialogue_turn_registration(client):
    """Test AI handling dialogue turns, location clarification, and registering upon confirmation."""
    call_sid = f"CA_test_{uuid.uuid4().hex[:8]}"

    # Turn 1: Caller states full problem & location details
    req_payload = {
        "call_sid": call_sid,
        "caller_phone": "+919843011223",
        "dialogue_turn": 1,
        "user_speech": "Severe water pipe leak on Cross Cut Road, Gandhipuram, Coimbatore opp City Hospital. Started today, still active.",
        "language_preference": "English"
    }
    response = client.post("/api/v1/ivr/dialogue-turn", json=req_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] in ["GATHER_MORE_INFO", "CONFIRMATION_PENDING"]

    # Turn 2: Caller confirms registration
    confirm_payload = {
        "call_sid": call_sid,
        "caller_phone": "+919843011223",
        "dialogue_turn": 2,
        "user_speech": "Yes, confirm and register complaint",
        "language_preference": "English"
    }
    confirm_res = client.post("/api/v1/ivr/dialogue-turn", json=confirm_payload)
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    if confirm_data["is_completed"]:
        assert confirm_data["intent"] == "CONFIRMED"
        assert confirm_data["complaint_number"] is not None
