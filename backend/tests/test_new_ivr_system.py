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

    # Turn 2: Duration -> Next is street_road_name
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
    assert d2["next_field"] == "street_road_name"

    # Turn 3: Street -> Next is affected_scope
    turn3 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "12th Cross Street"
    })
    assert turn3.status_code == 200
    d3 = turn3.json()
    assert d3["success"] is True
    assert d3["next_field"] == "affected_scope"

    # Turn 4: Scope -> Next is severity
    turn4 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Area full-ah problem"
    })
    assert turn4.status_code == 200
    d4 = turn4.json()
    assert d4["success"] is True
    assert d4["next_field"] == "severity"

    # Turn 5: Severity -> Next is impact
    turn5 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Completely varala"
    })
    assert turn5.status_code == 200
    d5 = turn5.json()
    assert d5["success"] is True
    assert d5["next_field"] == "impact"

    # Turn 6: Impact -> Next is previous_complaint
    turn6 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Drinking water-kooda illa"
    })
    assert turn6.status_code == 200
    d6 = turn6.json()
    assert d6["success"] is True
    assert d6["next_field"] == "previous_complaint"

    # Turn 7: Previous complaint -> Next is landmark
    turn7 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "First time complaint"
    })
    assert turn7.status_code == 200
    d7 = turn7.json()
    assert d7["success"] is True
    assert d7["next_field"] == "landmark"

    # Turn 8: Landmark -> Transitions to CONFIRMATION
    turn8 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Near Bus Stand"
    })
    assert turn8.status_code == 200
    d8 = turn8.json()
    assert d8["success"] is True
    assert d8["state"] == "CONFIRMATION"
    assert d8["is_confirmation"] is True
    assert "Gandhipuram" in d8["ai_reply"] or "Gandhipuram" in d8["spoken_reply"]

    # Turn 9: Confirmation -> Creates Real Complaint
    turn9 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Aama correct"
    })
    assert turn9.status_code == 200
    d9 = turn9.json()
    assert d9["success"] is True
    assert d9["state"] == "COMPLETED"
    assert d9["complaint_created"] is True
    assert "complaint_number" in d9
    assert d9["complaint_number"].startswith("VX-")
    assert "Water" in d9["department"]


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


def test_new_ivr_no_repeating_questions_with_casual_speech():
    """Verify that casual responses ('nethula irundhu', 'aama') fill slots and never repeat questions."""
    init_res = client.post("/api/v1/new-ivr/session", json={"caller_phone": "+919876500001"})
    session_id = init_res.json()["session_id"]

    # Turn 1: Problem + Location
    t1 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Saravanampatti-la current cut aaiduchu"
    }).json()
    assert t1["next_field"] == "duration"

    # Turn 2: Casual duration in Tanglish ("nethu lendhu")
    t2 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "nethu lendhu"
    }).json()
    # Must NOT ask duration again! Must advance to street_road_name
    assert t2["next_field"] == "street_road_name"
    assert t2["memory"]["duration"] is not None

    # Turn 3: Street name provided
    t3 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Main Road"
    }).json()
    assert t3["next_field"] == "affected_scope"

