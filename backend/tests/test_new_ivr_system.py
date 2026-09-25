import os
import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.ivr import IVRSession, IVRState
from app.models.complaint import Complaint

client = TestClient(app)


def test_new_ivr_session_creation():
    """Verify IVR session creation initializes greeting and WAITING_FOR_CITIZEN state."""
    response = client.post("/api/v1/new-ivr/session", json={
        "caller_phone": "+919876543210",
        "language_preference": "Tanglish"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "session_id" in data
    assert data["session_id"].startswith("ivr_sess_")
    assert data["caller_phone"] == "+919876543210"
    assert data["state"] == "WAITING_FOR_CITIZEN"
    assert "greeting" in data
    assert "spoken_greeting" in data


def test_new_ivr_session_retrieval():
    """Verify retrieving session state and message history."""
    init_res = client.post("/api/v1/new-ivr/session")
    session_id = init_res.json()["session_id"]

    get_res = client.get(f"/api/v1/new-ivr/session/{session_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["session_id"] == session_id
    assert data["state"] == "WAITING_FOR_CITIZEN"
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["role"] == "ai"


def test_new_ivr_multiturn_conversational_flow_with_memory():
    """
    Test turn-by-turn live voice IVR conversation:
    1. Citizen: 'Gandhipuram-la thanni varala'
    2. AI detects Water + Gandhipuram, asks duration: 'Idhu eppo lendhu varala?'
    3. Citizen: 'Two days-ah'
    4. AI remembers Water & Gandhipuram, updates duration, asks scope: 'Area full-ah problem-aa?'
    5. Citizen: 'Aama, area full-ah problem'
    6. AI summarizes and asks confirmation: 'Indha complaint-a register pannava?'
    7. Citizen: 'Aama'
    8. Complaint is created in DB with unique ID, routed to Water Department, and confirmed!
    """
    # Create session
    init_res = client.post("/api/v1/new-ivr/session", json={"caller_phone": "+919843012345"})
    session_id = init_res.json()["session_id"]

    # Turn 1: Problem + Location
    turn1 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Gandhipuram-la thanni varala"
    })
    assert turn1.status_code == 200
    d1 = turn1.json()
    assert d1["success"] is True
    assert d1["state"] == "WAITING_FOR_CITIZEN"
    assert "Gandhipuram" in d1["memory"]["location"]
    assert "Water" in d1["memory"]["category"]
    assert d1["next_field"] == "duration"

    # Turn 2: Duration
    turn2 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Two days-ah"
    })
    assert turn2.status_code == 200
    d2 = turn2.json()
    assert d2["success"] is True
    # Verify memory retained Category and Location!
    assert "Gandhipuram" in d2["memory"]["location"]
    assert "Water" in d2["memory"]["category"]
    assert "two days" in d2["memory"]["duration"].lower()
    assert d2["next_field"] == "affected_scope"

    # Turn 3: Scope -> Leads to Confirmation
    turn3 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Area full-ah problem"
    })
    assert turn3.status_code == 200
    d3 = turn3.json()
    assert d3["success"] is True
    assert d3["state"] == "CONFIRMATION"
    assert d3["is_confirmation"] is True
    assert "Gandhipuram" in d3["ai_reply"] or "Gandhipuram" in d3["spoken_reply"]

    # Turn 4: Confirmation -> Creates Real Complaint
    turn4 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Aama"
    })
    assert turn4.status_code == 200
    d4 = turn4.json()
    assert d4["success"] is True
    assert d4["state"] == "COMPLETED"
    assert d4["complaint_created"] is True
    assert "complaint_number" in d4
    assert d4["complaint_number"].startswith("VX-")
    assert "Water" in d4["department"]


def test_new_ivr_tamil_conversation_flow():
    """Verify Tamil citizen input is understood and responded to in Tamil."""
    init_res = client.post("/api/v1/new-ivr/session")
    session_id = init_res.json()["session_id"]

    turn1 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "கோயம்புத்தூர் அண்ணா நகரில் மின்வெட்டு ஏற்பட்டுள்ளது"
    })
    assert turn1.status_code == 200
    d1 = turn1.json()
    assert d1["success"] is True
    assert d1["detected_language"] in ["Tamil", "Tanglish"]
    assert "மின்" in d1["ai_reply"] or "பிரச்சினை" in d1["ai_reply"] or "கால" in d1["ai_reply"] or "எப்போது" in d1["ai_reply"] or "Electricity" in d1["memory"]["category"]


def test_new_ivr_english_conversation_flow():
    """Verify English citizen input is understood and responded to in English."""
    init_res = client.post("/api/v1/new-ivr/session")
    session_id = init_res.json()["session_id"]

    turn1 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "There is heavy garbage overflow in Gandhi Street"
    })
    assert turn1.status_code == 200
    d1 = turn1.json()
    assert d1["success"] is True
    assert d1["detected_language"] == "English"
    assert "Sanitation" in d1["memory"]["category"] or "Garbage" in d1["memory"]["category"]


def test_new_ivr_audio_upload_empty_validation():
    """Verify empty audio uploads return clean error code EMPTY_AUDIO."""
    init_res = client.post("/api/v1/new-ivr/session")
    session_id = init_res.json()["session_id"]

    empty_wav = io.BytesIO(b"RIFF....WAVEfmt ....data")  # Very small dummy bytes
    files = {"audio": ("empty.wav", empty_wav, "audio/wav")}

    res = client.post(f"/api/v1/new-ivr/session/{session_id}/audio", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["error_code"] == "EMPTY_AUDIO"


def test_new_ivr_audio_upload_invalid_format():
    """Verify invalid file extensions return INVALID_AUDIO."""
    init_res = client.post("/api/v1/new-ivr/session")
    session_id = init_res.json()["session_id"]

    bad_file = io.BytesIO(b"not an audio file content at all")
    files = {"audio": ("test.exe", bad_file, "application/octet-stream")}

    res = client.post(f"/api/v1/new-ivr/session/{session_id}/audio", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["error_code"] == "INVALID_AUDIO"


def test_new_ivr_unclear_speech_handling():
    """Verify unintelligible mumbling triggers polite re-prompt without guessing."""
    init_res = client.post("/api/v1/new-ivr/session")
    session_id = init_res.json()["session_id"]

    res = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "umm uhh hmm"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["unclear"] is True
    assert "clear" in data["ai_reply"].lower() or "மீண்டும்" in data["ai_reply"] or "sorry" in data["ai_reply"].lower()


def test_new_ivr_explicit_confirm_and_cancel_endpoints():
    """Verify explicit /confirm and /cancel endpoints."""
    init_res = client.post("/api/v1/new-ivr/session")
    session_id = init_res.json()["session_id"]

    # Pre-populate memory
    client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={"message": "Gandhipuram thanni varala"})
    client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={"message": "3 days"})
    client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={"message": "entire area"})

    # Test /cancel
    cancel_res = client.post(f"/api/v1/new-ivr/session/{session_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["state"] == "WAITING_FOR_CITIZEN"

    # Test /confirm
    confirm_res = client.post(f"/api/v1/new-ivr/session/{session_id}/confirm")
    assert confirm_res.status_code == 200
    data = confirm_res.json()
    assert data["complaint_created"] is True
    assert data["complaint_number"].startswith("VX-")
    assert data["state"] == "COMPLETED"


def test_new_ivr_end_session_endpoint():
    """Verify /end endpoint completes session cleanly."""
    init_res = client.post("/api/v1/new-ivr/session")
    session_id = init_res.json()["session_id"]

    end_res = client.post(f"/api/v1/new-ivr/session/{session_id}/end")
    assert end_res.status_code == 200
    assert end_res.json()["state"] == "COMPLETED"
