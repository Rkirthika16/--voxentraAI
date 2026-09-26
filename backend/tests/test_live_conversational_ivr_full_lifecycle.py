import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import get_db
from app.models.ivr import IVRSession, IVRState, IVRMessage
from app.models.complaint import Complaint, ComplaintStatus
from app.models.department import Department
from app.models.assignment import Assignment
from app.models.notification import Notification

client = TestClient(app)


def test_complete_live_conversational_ivr_flow():
    """
    Validates complete live 2-way conversational IVR lifecycle:
    1. Call connected -> AI is SILENT (waiting for citizen)
    2. Citizen speaks FIRST in Tanglish: 'Gandhipuram-la thanni varala.'
    3. AI detects Tanglish, problem (Water Supply), location (Gandhipuram)
    4. AI asks minimum 6 relevant follow-up questions one-by-one without asking for already known info
    5. Citizen answers each turn -> AI remembers all slot values
    6. AI provides final confirmation summary
    7. Citizen confirms -> Complaint created in DB with real record, department routing, and tracking
    """
    # 1. Start session - AI is SILENT
    resp = client.post("/api/v1/new-ivr/session", json={
        "caller_phone": "+919843098765",
        "language_preference": "Auto"
    })
    assert resp.status_code == 201
    sess_data = resp.json()
    assert sess_data["success"] is True
    session_id = sess_data["session_id"]
    assert sess_data["state"] == IVRState.WAITING_FOR_CITIZEN.value
    assert sess_data["greeting"] == ""  # AI MUST BE SILENT AT START

    # 2. Turn 1: Citizen speaks first
    t1 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Gandhipuram-la thanni varala."
    })
    assert t1.status_code == 200
    t1_data = t1.json()
    assert t1_data["detected_language"] == "Tanglish"
    assert "Gandhipuram" in t1_data["memory"]["location"]
    # AI should ask Question 1 (duration) since location and problem are already known
    assert t1_data["question_count"] == 1
    assert "duration" in str(t1_data.get("next_field", "")).lower() or "eppo" in t1_data.get("spoken_reply", "").lower()

    # 3. Turn 2: Citizen states duration
    t2 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Rendu naala varala."
    })
    assert t2.status_code == 200
    t2_data = t2.json()
    assert t2_data["question_count"] == 2
    assert "rendu" in str(t2_data["memory"]["duration"]).lower() or "2" in str(t2_data["memory"]["duration"]).lower()
    # AI asks Question 2 (street)
    assert "street" in t2_data["spoken_reply"].lower() or t2_data.get("next_field") == "street_road_name"

    # 4. Turn 3: Citizen states street
    t3 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "12th Street."
    })
    assert t3.status_code == 200
    t3_data = t3.json()
    assert t3_data["question_count"] == 3
    assert "12th street" in str(t3_data["memory"]["street_road_name"]).lower()

    # 5. Turn 4: Citizen states affected scope
    t4 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Full street-ku thanni varala."
    })
    assert t4.status_code == 200
    t4_data = t4.json()
    assert t4_data["question_count"] == 4

    # 6. Turn 5: Citizen states severity
    t5 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Completely varala."
    })
    assert t5.status_code == 200
    t5_data = t5.json()
    assert t5_data["question_count"] == 5

    # 7. Turn 6: Citizen states impact
    t6 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Aama, drinking water-kooda illa."
    })
    assert t6.status_code == 200
    t6_data = t6.json()
    assert t6_data["question_count"] == 6

    # 8. Turn 7: Citizen states previous complaint status
    t7 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Illai, first time dhaan."
    })
    assert t7.status_code == 200
    t7_data = t7.json()
    assert t7_data["question_count"] == 7
    assert t7_data["next_field"] == "landmark"

    # 9. Turn 8: Citizen states landmark
    t8 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Gandhipuram bus stand pakkam."
    })
    assert t8.status_code == 200
    t8_data = t8.json()
    assert "bus stand" in str(t8_data["memory"].get("landmark", "")).lower()

    # Continue until confirmation summary is presented
    current_data = t8_data
    while not current_data.get("is_confirmation") and current_data.get("state") != IVRState.CONFIRMATION.value:
        t_next = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
            "message": "Aama"
        })
        current_data = t_next.json()

    assert current_data["state"] == IVRState.CONFIRMATION.value
    assert current_data["is_confirmation"] is True

    # 9. Final Turn: Citizen confirms the complaint
    confirm_resp = client.post(f"/api/v1/new-ivr/session/{session_id}/confirm")
    assert confirm_resp.status_code == 200
    c_data = confirm_resp.json()
    assert c_data["success"] is True
    assert c_data["complaint_created"] is True
    complaint_num = c_data["complaint_number"]
    assert complaint_num.startswith("VX-")

    # 10. Database Verification: Query real DB to verify record exists
    comp_get = client.get(f"/api/v1/complaints/{c_data['complaint_id']}")
    assert comp_get.status_code == 200
    saved = comp_get.json()
    assert saved["complaint_number"] == complaint_num
    assert saved["status"] == ComplaintStatus.SUBMITTED.value
    assert "Water" in saved["category"]
    assert "Gandhipuram" in saved["location"]

    # 11. Verify tracking endpoint by complaint number
    track_resp = client.get(f"/api/v1/complaints/track/{complaint_num}")
    assert track_resp.status_code == 200
    assert track_resp.json()["complaint_number"] == complaint_num
