import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.ivr_session_service import ivr_session_service, IVRState
from app.models.complaint import Complaint


def test_voice_assistant_complete_conversation_flow(client: TestClient, db_session: Session):
    """
    Acceptance Test:
    Turn 1: Citizen speaks "Gandhipuram-la thanni varala." -> Tanglish, Water, Gandhipuram
    Turn 2: Citizen answers "Two days-ah." -> Duration = 2 days
    Turn 3: Citizen answers "Area full-ah." -> Scope = Entire area -> Confirmation summary
    Turn 4: Citizen confirms -> Database complaint created with unique tracking ID
    """
    # 1. Start session
    start_res = client.post("/api/v1/voice/session", json={"caller_phone": "+919843098765"})
    assert start_res.status_code == 200
    start_data = start_res.json()
    sid = start_data["session_id"]
    assert start_data["state"] == "WAITING_FOR_USER"
    assert "வணக்கம்" in start_data["greeting_text"]

    # 2. Turn 1: Citizen speaks FIRST
    turn1_res = client.post(
        f"/api/v1/voice/session/{sid}/message",
        json={"message": "Gandhipuram-la thanni varala."}
    )
    assert turn1_res.status_code == 200
    t1_data = turn1_res.json()
    assert t1_data["detected_language"] in ["Tanglish", "Tamil"]
    assert t1_data["context"]["category"] == "Water"
    assert "Gandhipuram" in t1_data["context"]["location"]
    # Must NOT re-ask location
    assert "Gandhipuram" in t1_data["ai_text"] or "Gandhipuram" in t1_data["ai_spoken"]
    assert t1_data["confirmation_required"] is False

    # 3. Turn 2: Duration answer
    turn2_res = client.post(
        f"/api/v1/voice/session/{sid}/message",
        json={"message": "Two days-ah."}
    )
    assert turn2_res.status_code == 200
    t2_data = turn2_res.json()
    assert t2_data["context"]["duration"] == "2 days"
    assert "area full-ah" in t2_data["ai_text"] or "area" in t2_data["ai_text"].lower() or "பகுதி" in t2_data["ai_text"] or "வீட்டில்" in t2_data["ai_text"]

    # 4. Turn 3: Scope answer
    turn3_res = client.post(
        f"/api/v1/voice/session/{sid}/message",
        json={"message": "Area full-ah."}
    )
    assert turn3_res.status_code == 200
    t3_data = turn3_res.json()
    assert t3_data["context"]["affected_scope"] == "Entire area"
    assert t3_data["confirmation_required"] is True
    assert t3_data["state"] in ["CONFIRMING", "CONFIRMATION"]

    # 5. Confirm session
    confirm_res = client.post(
        f"/api/v1/voice/session/{sid}/confirm",
        json={"citizen_name": "Kirthika", "caller_phone": "+919843098765"}
    )
    assert confirm_res.status_code == 200
    c_data = confirm_res.json()
    assert c_data["state"] == "COMPLETED"
    assert c_data["complaint_number"] is not None
    assert c_data["complaint_number"].startswith("VX-") or c_data["complaint_number"].startswith("VOX-")

    # Verify created in SQLite database
    comp = db_session.query(Complaint).filter(Complaint.id == c_data["complaint_id"]).first()
    assert comp is not None
    assert comp.category == "Water"
    assert "Gandhipuram" in comp.location


def test_voice_session_citizen_correction_and_cancel(client: TestClient):
    """Verifies citizen correction handling and session cancellation."""
    start_res = client.post("/api/v1/voice/session")
    sid = start_res.json()["session_id"]

    # Turn 1: Streetlight
    client.post(
        f"/api/v1/voice/session/{sid}/message",
        json={"message": "Streetlight broken in Peelamedu"}
    )

    # Turn 2: Citizen corrects location
    corr_res = client.post(
        f"/api/v1/voice/session/{sid}/message",
        json={"message": "Change location to Gandhipuram"}
    )
    assert corr_res.status_code == 200
    corr_data = corr_res.json()
    assert "Gandhipuram" in corr_data["context"]["location"]

    # Get session state
    get_res = client.get(f"/api/v1/voice/session/{sid}")
    assert get_res.status_code == 200
    assert get_res.json()["context"]["location"] == "Gandhipuram"

    # Cancel session
    cancel_res = client.post(f"/api/v1/voice/session/{sid}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["state"] == "CANCELLED"


def test_ivr_session_service_state_machine():
    """Unit test for IVRSessionService state machine transitions."""
    sid = f"ivr_test_{uuid.uuid4().hex[:8]}"
    session = ivr_session_service.create_session(call_session_id=sid, caller_number="+919843098765")
    assert session.current_state == IVRState.WELCOME

    session.transition_to(IVRState.RECORDING)
    assert session.current_state == IVRState.RECORDING

    session.add_turn("citizen", "No water in Gandhipuram")
    assert len(session.turns) == 1
    assert session.turns[0]["speaker"] == "citizen"

    session.transition_to(IVRState.ANALYZING)
    session.transition_to(IVRState.ASKING_QUESTION)
    session.add_turn("ivr", "How many days has this issue existed?")

    session.transition_to(IVRState.CONFIRMING)
    session.end_call(IVRState.COMPLETED)
    assert session.current_state == IVRState.COMPLETED
    assert session.call_status == "completed"
    assert session.ended_at is not None
