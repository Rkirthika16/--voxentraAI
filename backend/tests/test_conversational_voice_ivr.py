import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus
from app.models.ivr import IVRSession
from app.ai.conversation_service import conversation_service

def test_conversational_ivr_e2e_tanglish_water_flow(client: TestClient, db_session: Session):
    """
    Complete Real-Time Conversational Voice IVR Flow:
    1. Citizen connects and speaks FIRST (no DTMF 'Press 1 for Tamil'): 'Gandhipuram-la thanni varala.'
    2. AI hears speech via Whisper, normalizes, detects Tanglish, extracts Water + Gandhipuram, prompts duration.
    3. Citizen answers: 'Two days-ah.'
    4. AI retains memory (Water + Gandhipuram), stores duration (2 days), prompts scope: 'Area full-ah problem-aa?'
    5. Citizen answers: 'Area full-ah.'
    6. AI generates natural spoken confirmation summary.
    7. Citizen confirms: 'Aama correct, register pannunga.'
    8. Real grievance created in SQLite DB with unique ID (VX-...), routed to Water Department, linked to IVR session!
    """
    # 1. Start session
    init_res = client.post("/api/v1/new-ivr/session", json={"caller_phone": "+919843012345"})
    assert init_res.status_code == 201
    init_data = init_res.json()
    session_id = init_data["session_id"]
    assert init_data["state"] == "WAITING_FOR_CITIZEN"
    assert init_data["caller_phone"] == "+919843012345"

    # 2. Turn 1: Citizen speaks FIRST
    turn1_res = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Gandhipuram-la thanni varala."
    })
    assert turn1_res.status_code == 200
    t1 = turn1_res.json()
    assert t1["success"] is True
    assert t1["state"] == "WAITING_FOR_CITIZEN"
    assert "Gandhipuram" in t1["memory"]["location"]
    assert "Water" in t1["memory"]["category"]
    assert t1["next_field"] == "duration"
    assert t1["detected_language"] in ["Tanglish", "Tamil"]
    # AI must NOT re-ask location; should ask duration
    assert "Gandhipuram" in t1["ai_reply"] or "Gandhipuram" in t1["spoken_reply"] or "தண்ணீர்" in t1["spoken_reply"] or "water" in t1["spoken_reply"].lower()

    # 3. Turn 2: Citizen provides duration
    turn2_res = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Two days-ah."
    })
    assert turn2_res.status_code == 200
    t2 = turn2_res.json()
    assert t2["success"] is True
    # Verify memory retained category & location
    assert "Gandhipuram" in t2["memory"]["location"]
    assert "Water" in t2["memory"]["category"]
    assert "2 days" in t2["memory"]["duration"].lower() or "two days" in t2["memory"]["duration"].lower()
    assert t2["next_field"] == "affected_scope"

    # 4. Turn 3: Citizen provides affected scope -> triggers confirmation summary
    turn3_res = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Area full-ah problem."
    })
    assert turn3_res.status_code == 200
    t3 = turn3_res.json()
    assert t3["success"] is True
    assert t3["state"] == "CONFIRMATION"
    assert t3["is_confirmation"] is True
    assert "Gandhipuram" in t3["ai_reply"] or "Gandhipuram" in t3["spoken_reply"]
    assert "water" in t3["ai_reply"].lower() or "தண்ணீர்" in t3["ai_reply"] or "complaint" in t3["ai_reply"].lower() or "புகார்" in t3["ai_reply"]

    # 5. Turn 4: Citizen confirms registration
    turn4_res = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Aama correct, register pannunga."
    })
    assert turn4_res.status_code == 200
    t4 = turn4_res.json()
    assert t4["success"] is True
    assert t4["state"] == "COMPLETED"
    assert t4["complaint_created"] is True
    assert "complaint_number" in t4
    complaint_no = t4["complaint_number"]
    assert complaint_no.startswith("VX-")
    assert "Water" in t4["department"]

    # 6. Verify real persistence in DB
    complaint = db_session.query(Complaint).filter(Complaint.complaint_number == complaint_no).first()
    assert complaint is not None
    assert complaint.category == "Water"
    assert "Gandhipuram" in complaint.location
    assert "IVR" in (complaint.source.value if hasattr(complaint.source, "value") else str(complaint.source))
    assert complaint.status in [ComplaintStatus.SUBMITTED, ComplaintStatus.IN_PROGRESS]


def test_conversational_ivr_tamil_electricity_flow(client: TestClient, db_session: Session):
    """Verify natural conversational flow in pure Tamil script."""
    init_res = client.post("/api/v1/new-ivr/session", json={"caller_phone": "+919843099999"})
    session_id = init_res.json()["session_id"]

    # Turn 1: Problem in pure Tamil
    turn1_res = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "பீளமேடு பகுதியில் இரண்டு நாட்களாக மின்சாரம் இல்லை"
    })
    assert turn1_res.status_code == 200
    t1 = turn1_res.json()
    assert t1["success"] is True
    assert t1["detected_language"] in ["Tamil", "Tanglish"]
    assert "Electricity" in t1["memory"]["category"] or "Power" in t1["memory"]["category"]
    assert "Peelamedu" in t1["memory"]["location"] or "பீளமேடு" in t1["memory"]["location"]


def test_conversational_ivr_english_sanitation_flow(client: TestClient, db_session: Session):
    """Verify natural conversational flow in English."""
    init_res = client.post("/api/v1/new-ivr/session", json={"caller_phone": "+919843088888"})
    session_id = init_res.json()["session_id"]

    # Turn 1: Problem in English
    turn1_res = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "There is a severe garbage overflow and bad smell on Cross Cut Road for 3 days"
    })
    assert turn1_res.status_code == 200
    t1 = turn1_res.json()
    assert t1["success"] is True
    assert t1["detected_language"] == "English"
    assert "Sanitation" in t1["memory"]["category"] or "Garbage" in t1["memory"]["category"]
    assert "Gandhipuram" in t1["memory"]["location"] or "Cross Cut" in t1["memory"]["location"] or "Coimbatore" in t1["memory"]["location"]
