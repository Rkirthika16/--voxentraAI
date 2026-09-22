import uuid
from fastapi.testclient import TestClient
from app.ai.complaint_collector import complaint_collector, FIELD_KEYS
from app.models.complaint import Complaint
from app.models.user import User


def test_complaint_collector_slot_extraction():
    text = (
        "Drainage is overflowing on 100 Feet Road, Gandhipuram, Coimbatore near Murugan Temple. "
        "It started yesterday morning, happening daily and still active. I am Ramesh, 9842112345."
    )
    slots = complaint_collector.extract_slots(text)

    assert "drainage" in (slots.get("problem_description") or "").lower()
    assert "Gandhipuram" in (slots.get("district_area") or "") or "Coimbatore" in (slots.get("district_area") or "")
    assert "Road" in (slots.get("street_road_name") or "") or "100" in (slots.get("street_road_name") or "")
    assert "Murugan" in (slots.get("landmark") or "") or "Temple" in (slots.get("landmark") or "")
    assert "yesterday" in (slots.get("date_and_time") or "").lower()
    assert "daily" in (slots.get("frequency") or "").lower()
    assert "active" in (slots.get("current_status") or "").lower() or "still" in (slots.get("current_status") or "").lower()
    assert "9842112345" in (slots.get("citizen_details") or "")


def test_turn_by_turn_intake_workflow(client: TestClient):
    session_id = f"test_sess_{uuid.uuid4().hex[:8]}"

    # Turn 1: Citizen states the problem
    res1 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Water pipe is broken and leaking", "session_id": session_id}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["intent"] == "COLLECTING_FIELD"
    assert data1["collection_state"]["fields"]["problem_description"] is not None
    assert data1["collection_state"]["completed_fields_count"] >= 1
    assert data1["collection_state"]["current_field_prompted"] is not None

    # Turn 2: Citizen provides location details
    res2 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Near central bus stand, Ward 5", "session_id": session_id}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["collection_state"]["completed_fields_count"] >= 2

    # Turn 3: Citizen provides street name
    res3 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Cross Cut Road", "session_id": session_id}
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["collection_state"]["fields"]["street_road_name"] is not None


def test_bulk_all_fields_and_confirmation(client: TestClient, db_session):
    session_id = f"test_full_{uuid.uuid4().hex[:8]}"

    # All details in message
    full_msg = (
        "Severe water pipeline leak on Main Bazaar Road, Gandhipuram, Coimbatore opposite City Hospital. "
        "Started today 8 AM, first time, still leaking severely right now. No other hazard. Citizen Murugan, 9840112345"
    )
    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": full_msg, "session_id": session_id}
    )
    assert res.status_code == 200
    data = res.json()

    # Should ask for confirmation
    assert data["intent"] == "CONFIRMATION_PENDING"
    assert data["collection_state"]["completion_percentage"] == 100
    assert "Water" in data["reply_text"] or "Grievance" in data["reply_text"]

    # Citizen confirms
    confirm_res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Yes, confirm and register complaint", "session_id": session_id}
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["intent"] == "COMPLAINT_REGISTERED"
    assert "VOX-" in confirm_data["reply_text"]

    # Verify complaint exists in DB
    tracking = confirm_data["collection_state"]["created_complaint_number"]
    assert tracking is not None
    complaint = db_session.query(Complaint).filter(Complaint.complaint_number == tracking).first()
    assert complaint is not None
    assert complaint.category == "Water"
    assert "Coimbatore" in complaint.location or "Gandhipuram" in complaint.location


def test_tamil_dialogue_flow(client: TestClient):
    session_id = f"test_ta_{uuid.uuid4().hex[:8]}"

    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "குடிநீர் குழாய் உடைந்துள்ளது", "session_id": session_id}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["detected_language"] == "Tamil"
    assert data["intent"] == "COLLECTING_FIELD"
    assert "இடம்" in data["reply_text"] or "விவரம்" in data["reply_text"]


def test_reset_collection_endpoint(client: TestClient):
    session_id = f"test_reset_{uuid.uuid4().hex[:8]}"
    client.post(
        "/api/v1/assistant/chat",
        json={"message": "Streetlight broken", "session_id": session_id}
    )

    reset_res = client.post(
        "/api/v1/assistant/reset-collection",
        data={"session_id": session_id}
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["success"] is True


def test_tanglish_multilingual_flow(client: TestClient):
    session_id = f"test_tanglish_{uuid.uuid4().hex[:8]}"

    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Gandhipuram-la water pipe odanjuruchu romba leak aagudhu", "session_id": session_id}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["detected_language"] in ["Tanglish", "Tamil", "English"]
    assert data["intent"] == "COLLECTING_FIELD"
    assert data["collection_state"]["fields"]["problem_description"] is not None


def test_location_no_assumption_clarification(client: TestClient):
    session_id = f"test_no_assume_{uuid.uuid4().hex[:8]}"

    # Citizen says only the area name
    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "I want to report sewage overflow in Peelamedu, Coimbatore", "session_id": session_id}
    )
    assert res.status_code == 200
    data = res.json()

    # AI should have captured district_area but NOT assumed street or landmark
    assert data["collection_state"]["fields"]["district_area"] is not None
    assert data["collection_state"]["fields"]["street_road_name"] is None
    assert data["collection_state"]["current_field_prompted"] == "street_road_name"
    assert "street" in data["reply_text"].lower() or "road" in data["reply_text"].lower() or "தெரு" in data["reply_text"]


def test_vague_location_clarification(client: TestClient):
    session_id = f"test_vague_{uuid.uuid4().hex[:8]}"

    # Citizen states problem
    client.post(
        "/api/v1/assistant/chat",
        json={"message": "Streetlight not working", "session_id": session_id}
    )

    # Citizen provides vague location
    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "near my house", "session_id": session_id}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "COLLECTING_FIELD"

