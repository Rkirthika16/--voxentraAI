import uuid
from fastapi.testclient import TestClient
from app.ai.conversation_service import conversation_service
from app.models.complaint import Complaint


def test_conversation_service_tanglish_water_flow(client: TestClient):
    session_id = f"test_tanglish_water_{uuid.uuid4().hex[:8]}"

    # Turn 1: Citizen speaks FIRST with problem & location: "Gandhipuram-la thanni varala."
    res1 = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_speech": "Gandhipuram-la thanni varala."}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["detected_language"] in ["Tanglish", "Tamil"]
    assert data1["context"]["category"] == "Water"
    assert "Gandhipuram" in data1["context"]["location"]
    # AI must NOT ask location again; should ask duration or category specific detail
    assert "Gandhipuram" in data1["ai_text"] or "Gandhipuram" in data1["ai_spoken"]
    assert data1["confirmation_required"] is False
    assert data1["conversation_complete"] is False

    # Turn 2: Citizen answers duration: "Two days-ah."
    res2 = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_speech": "Two days-ah."}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["context"]["duration"] == "2 days"
    # Category question for water: area full-ah vs individual house
    assert "area full-ah" in data2["ai_text"] or "area" in data2["ai_text"].lower() or data2["confirmation_required"] is True

    # Turn 3: Citizen answers scope: "Area full-ah."
    res3 = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_speech": "Area full-ah."}
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["context"]["affected_scope"] == "Entire area"
    # Now all critical info is gathered -> Must be in CONFIRMING state
    assert data3["confirmation_required"] is True
    assert "summary" in data3["ai_text"].lower() or "confirm" in data3["ai_text"].lower() or "register" in data3["ai_text"].lower()

    # Turn 4: Citizen confirms: "Aama, register pannunga."
    res4 = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_speech": "Aama, register pannunga."}
    )
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["state"] == "COMPLETED"
    assert data4["conversation_complete"] is True
    assert data4["complaint_number"] is not None
    assert data4["complaint_number"].startswith("VX-")


def test_conversation_service_tamil_electricity_urgent_hazard(client: TestClient):
    session_id = f"test_ta_elec_{uuid.uuid4().hex[:8]}"

    # Turn 1: Tamil speech with live wire hazard
    res1 = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_speech": "அண்ணா நகரில் மின்சார கம்பி அறுந்து விழுந்து தீப்பொறி பறக்கிறது."}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["detected_language"] in ["Tamil", "Mixed (Tamil/English)"]
    assert data1["context"]["category"] == "Electricity"
    assert data1["context"]["priority"] == "CRITICAL"


def test_conversation_unclear_speech_handling(client: TestClient):
    session_id = f"test_unclear_{uuid.uuid4().hex[:8]}"

    res = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_speech": "umm... uhhh..."}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "WAITING_FOR_USER"
    assert "understood that correctly" in data["ai_text"].lower() or "spelling" in data["ai_text"].lower() or "clear" in data["ai_text"].lower() or "மீண்டும்" in data["ai_text"]


def test_conversation_service_annur_tanglish_water_flow(client: TestClient):
    session_id = f"test_annur_{uuid.uuid4().hex[:8]}"

    # Turn 1: Citizen speaks "annur la thanniye vara matingithu"
    res1 = client.post(
        "/api/v1/conversation/turn",
        json={"session_id": session_id, "user_speech": "annur la thanniye vara matingithu"}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["detected_language"] == "Tanglish"
    assert data1["context"]["category"] == "Water"
    assert "Annur" in data1["context"]["location"]
    # AI must respond in Tanglish mentioning Annur cleanly
    assert "Annur" in data1["ai_text"]
    assert "eppo lendhu" in data1["ai_text"] or "irukku" in data1["ai_text"]

