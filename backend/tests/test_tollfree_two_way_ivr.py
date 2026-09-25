import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.tollfree import TollFreeCallSession, TollFreeState
from app.models.complaint import Complaint, ComplaintStatus

client = TestClient(app)


def test_tollfree_session_creation():
    """Verify Toll-Free call session initializes greeting and sets WAITING_FOR_CITIZEN state."""
    response = client.post("/api/v1/tollfree/session", json={
        "caller_phone": "+919876543210",
        "toll_free_number": "1800-425-8693"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "session_id" in data
    assert data["session_id"].startswith("tf_sess_")
    assert data["state"] == "WAITING_FOR_CITIZEN"
    assert "greeting" in data
    assert "spoken_greeting" in data


def test_tollfree_session_retrieval():
    """Verify retrieving session state, transcript, and message history."""
    init_res = client.post("/api/v1/tollfree/session")
    session_id = init_res.json()["session_id"]

    get_res = client.get(f"/api/v1/tollfree/session/{session_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["session_id"] == session_id
    assert data["state"] == "WAITING_FOR_CITIZEN"
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["role"] == "ai"


def test_tollfree_exact_multiturn_conversational_flow_with_memory():
    """
    Test exact required Toll-Free turn-by-turn conversation:
    1. AI Greeting -> Citizen speaks first
    2. Citizen: 'Gandhipuram-la thanni varala'
    3. AI detects Tanglish + Water + Gandhipuram, asks duration: 'Idhu eppo lendhu varala?'
    4. Citizen: 'Two days-ah'
    5. AI remembers Water & Gandhipuram, updates duration, asks scope: 'Area full-ah problem-aa?'
    6. Citizen: 'Aama, full area affected'
    7. AI summarizes all details and asks confirmation: 'Naan sonna details ellam correct-aa?'
    8. Citizen: 'Aama, correct'
    9. Real DB Complaint created with status SUBMITTED, unique ID generated, routed to Water Department!
    """
    init_res = client.post("/api/v1/tollfree/session", json={"caller_phone": "+919843098765"})
    session_id = init_res.json()["session_id"]

    # Turn 1: Problem + Location
    turn1 = client.post(f"/api/v1/tollfree/session/{session_id}/message", json={
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
    turn2 = client.post(f"/api/v1/tollfree/session/{session_id}/message", json={
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
    turn3 = client.post(f"/api/v1/tollfree/session/{session_id}/message", json={
        "message": "Aama, full area affected"
    })
    assert turn3.status_code == 200
    d3 = turn3.json()
    assert d3["success"] is True
    assert d3["state"] == "CONFIRMATION"
    assert d3["is_confirmation"] is True
    assert "Gandhipuram" in d3["ai_reply"] or "Gandhipuram" in d3["spoken_reply"]

    # Turn 4: Confirmation -> Creates Real Complaint
    turn4 = client.post(f"/api/v1/tollfree/session/{session_id}/message", json={
        "message": "Aama, correct"
    })
    assert turn4.status_code == 200
    d4 = turn4.json()
    assert d4["success"] is True
    assert d4["state"] == "COMPLETED"
    assert d4["complaint_created"] is True
    assert "complaint_number" in d4
    assert d4["complaint_number"].startswith("VX-")
    assert "Water" in d4["department"]


def test_tollfree_tamil_speech_adaptation():
    """Verify Tamil citizen speech triggers responses in Tamil."""
    init_res = client.post("/api/v1/tollfree/session")
    session_id = init_res.json()["session_id"]

    turn1 = client.post(f"/api/v1/tollfree/session/{session_id}/message", json={
        "message": "எங்கள் பகுதியில் மின்வெட்டு ஏற்பட்டுள்ளது"
    })
    assert turn1.status_code == 200
    d1 = turn1.json()
    assert d1["success"] is True
    assert d1["detected_language"] in ["Tamil", "Tanglish"]


def test_tollfree_english_speech_adaptation():
    """Verify English citizen speech triggers responses in English."""
    init_res = client.post("/api/v1/tollfree/session")
    session_id = init_res.json()["session_id"]

    turn1 = client.post(f"/api/v1/tollfree/session/{session_id}/message", json={
        "message": "There is a severe drainage overflow in Cross Cut Road"
    })
    assert turn1.status_code == 200
    d1 = turn1.json()
    assert d1["success"] is True
    assert d1["detected_language"] == "English"
    assert "Drainage" in d1["memory"]["category"]


def test_tollfree_citizen_explicit_correction():
    """Verify citizen can explicitly correct location or category mid-conversation."""
    init_res = client.post("/api/v1/tollfree/session")
    session_id = init_res.json()["session_id"]

    # Initial turn: mentions Saibaba Colony
    client.post(f"/api/v1/tollfree/session/{session_id}/message", json={"message": "Saibaba Colony thanni varala"})

    # Correction turn: citizen clarifies location is Peelamedu
    turn_corr = client.post(f"/api/v1/tollfree/session/{session_id}/message", json={"message": "No, actually Peelamedu"})
    assert turn_corr.status_code == 200
    d_corr = turn_corr.json()
    assert "Peelamedu" in d_corr["memory"]["location"]


def test_tollfree_audio_upload_validation():
    """Verify empty audio upload returns EMPTY_AUDIO."""
    init_res = client.post("/api/v1/tollfree/session")
    session_id = init_res.json()["session_id"]

    empty_audio = io.BytesIO(b"short")
    files = {"audio": ("test.webm", empty_audio, "audio/webm;codecs=opus")}

    res = client.post(f"/api/v1/tollfree/session/{session_id}/audio", files=files)
    assert res.status_code == 200
    assert res.json()["success"] is False
    assert res.json()["error_code"] == "EMPTY_AUDIO"


def test_tollfree_telephony_webhooks():
    """Verify Telephony Provider webhook endpoints (Exotel/Twilio/SIP)."""
    # 1. Inbound webhook
    res_inbound = client.post("/api/v1/tollfree/webhook/incoming", data={
        "From": "+919843098765",
        "CallSid": "CA_test_call_123"
    })
    assert res_inbound.status_code == 200
    assert "Response" in res_inbound.text

    # 2. Audio recording callback webhook
    res_audio = client.post("/api/v1/tollfree/webhook/audio", data={
        "CallSid": "CA_test_call_123",
        "SpeechResult": "Gandhipuram-la thanni varala"
    })
    assert res_audio.status_code == 200
    assert "Response" in res_audio.text

    # 3. Status webhook
    res_status = client.get("/api/v1/tollfree/webhook/status")
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "active"
