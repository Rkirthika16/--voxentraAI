import io
from fastapi.testclient import TestClient
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus
from app.models.user import User, UserRole


def test_assistant_suggestions(client: TestClient):
    response = client.get("/api/v1/assistant/suggestions")
    assert response.status_code == 200
    data = response.json()
    assert "sample_questions" in data
    assert "emergency_helplines" in data
    assert "quick_categories" in data
    assert len(data["sample_questions"]) > 0
    assert len(data["emergency_helplines"]) > 0


def test_assistant_greeting_english(client: TestClient):
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Hello Voxentra AI"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "GREETING"
    assert "Voxentra AI" in data["reply_text"]
    assert len(data["spoken_text"]) > 0


def test_assistant_greeting_tamil(client: TestClient):
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "வணக்கம்"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "GREETING"
    assert "வணக்கம்" in data["reply_text"]


def test_assistant_emergency_helplines(client: TestClient):
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What is the emergency helpline number for municipal grievances?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "EMERGENCY_HELPLINE"
    assert "1913" in data["reply_text"]
    assert "112" in data["reply_text"]


def test_assistant_grievance_draft_generation(client: TestClient):
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Drinking water pipeline is broken and leaking severely near Gandhipuram bus stand Coimbatore"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "FILE_COMPLAINT"
    assert data["draft_complaint"] is not None
    assert data["draft_complaint"]["category"] == "Water"
    assert "Gandhipuram" in (data["draft_complaint"]["extracted_location"] or "")
    assert data["draft_complaint"]["latitude"] is not None
    assert len(data["suggested_actions"]) > 0
    assert data["suggested_actions"][0]["action_type"] == "SUBMIT_DRAFT"


def test_assistant_tanglish_power_grievance(client: TestClient):
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "current cut and fuse spark aaguthu in Peelamedu"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "FILE_COMPLAINT"
    assert data["draft_complaint"] is not None
    assert data["draft_complaint"]["category"] == "Electricity"
    assert "Peelamedu" in (data["draft_complaint"]["extracted_location"] or "")


def test_assistant_tracking_lookup(client: TestClient, db_session):
    # Create sample complaint
    citizen = db_session.query(User).filter(User.role == UserRole.CITIZEN).first()
    complaint = Complaint(
        complaint_number="VX-2026-9999",
        title="Sample Streetlight Issue",
        description="Streetlights are not working on 100 feet road",
        category="Streetlights",
        priority=ComplaintPriority.MEDIUM,
        status=ComplaintStatus.IN_PROGRESS,
        location="100 Feet Road, Coimbatore",
        citizen_id=citizen.id
    )
    db_session.add(complaint)
    db_session.commit()

    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What is the status of complaint VX-2026-9999?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "TRACK_STATUS"
    assert "VX-2026-9999" in data["reply_text"]
    assert "In Progress" in data["reply_text"]
    assert data["status_info"]["tracking_number"] == "VX-2026-9999"


def test_assistant_voice_chat_endpoint(client: TestClient):
    fake_audio = io.BytesIO(b"RIFF....WAVEfmt ....data....")
    fake_audio.name = "recording.wav"

    response = client.post(
        "/api/v1/assistant/voice-chat",
        files={"file": ("recording.wav", fake_audio, "audio/wav")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply_text" in data
    assert "spoken_text" in data
    assert "speech_status" in data
