import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.ai.conversation_service import conversation_service

client = TestClient(app)


def test_ivr_conversational_session_start():
    """Verify IVR session start returns welcome response and enters WAITING_FOR_CITIZEN state."""
    response = client.post("/api/v1/ivr/session")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["conversation_state"] == "WAITING_FOR_CITIZEN"
    assert data["should_continue"] is True
    assert "response_text" in data
    assert len(data["response_text"]) > 0


def test_ivr_two_way_continuous_conversation_multi_turn():
    """
    Test the complete 4-turn two-way conversational flow:
    Turn 1: Citizen: 'Gandhipuram-la thanni varala.'
    Turn 2: Citizen: 'Two days-ah.'
    Turn 3: Citizen: 'Area full-ah.'
    Turn 4: Citizen: 'Aama.' -> Confirmation & Complaint Registration
    """
    # 1. Start Session
    start_res = client.post("/api/v1/ivr/session")
    assert start_res.status_code == 200
    sid = start_res.json()["session_id"]

    # 2. Turn 1: Citizen states issue & location in Tanglish
    turn1_res = client.post(
        f"/api/v1/ivr/session/{sid}/message",
        data={"message": "Gandhipuram-la thanni varala.", "caller_phone": "+919843098765"}
    )
    assert turn1_res.status_code == 200
    turn1_data = turn1_res.json()
    assert turn1_data["analysis"]["category"] == "Water"
    assert "Gandhipuram" in turn1_data["analysis"]["location"]
    assert turn1_data["conversation_state"] == "WAITING_FOR_CITIZEN"
    assert turn1_data["should_continue"] is True
    # The response should ask for duration without re-asking location
    assert "location" not in turn1_data["response_text"].lower() or "gandhipuram" in turn1_data["response_text"].lower()

    # 3. Turn 2: Citizen provides duration
    turn2_res = client.post(
        f"/api/v1/ivr/session/{sid}/message",
        data={"message": "Two days-ah.", "caller_phone": "+919843098765"}
    )
    assert turn2_res.status_code == 200
    turn2_data = turn2_res.json()
    # Memory retained!
    assert turn2_data["analysis"]["category"] == "Water"
    assert "Gandhipuram" in turn2_data["analysis"]["location"]
    assert "2 days" in turn2_data["analysis"]["duration"]
    assert turn2_data["conversation_state"] == "WAITING_FOR_CITIZEN"

    # 4. Turn 3: Citizen provides affected scope
    turn3_res = client.post(
        f"/api/v1/ivr/session/{sid}/message",
        data={"message": "Area full-ah.", "caller_phone": "+919843098765"}
    )
    assert turn3_res.status_code == 200
    turn3_data = turn3_res.json()
    assert "Entire area" in turn3_data["analysis"]["affected_scope"]
    # All required slots collected -> AI requests confirmation
    assert turn3_data["confirmation_required"] is True

    # 5. Turn 4: Citizen confirms: 'Aama'
    turn4_res = client.post(
        f"/api/v1/ivr/session/{sid}/message",
        data={"message": "Aama.", "caller_phone": "+919843098765"}
    )
    assert turn4_res.status_code == 200
    turn4_data = turn4_res.json()
    assert turn4_data["conversation_state"] == "CONFIRMED"
    assert turn4_data["should_continue"] is False
    assert turn4_data["complaint_number"] is not None
    assert str(turn4_data["complaint_number"]).startswith("VX-")
    assert turn4_data["complaint_id"] is not None


def test_language_preservation_tamil_and_english():
    """Verify that Tamil input receives Tamil response and English receives English response."""
    # Tamil
    res_ta_start = client.post("/api/v1/ivr/session")
    sid_ta = res_ta_start.json()["session_id"]
    res_ta = client.post(
        f"/api/v1/ivr/session/{sid_ta}/message",
        data={"message": "பீளமேடு பகுதியில் இரண்டு நாட்களாக மின்சாரம் இல்லை."}
    )
    assert res_ta.status_code == 200
    data_ta = res_ta.json()
    assert data_ta["language"] == "Tamil"
    assert any("\u0B80" <= c <= "\u0BFF" for c in data_ta["response_text"])

    # English
    res_en_start = client.post("/api/v1/ivr/session")
    sid_en = res_en_start.json()["session_id"]
    res_en = client.post(
        f"/api/v1/ivr/session/{sid_en}/message",
        data={"message": "There is a severe water leakage in RS Puram since yesterday."}
    )
    assert res_en.status_code == 200
    data_en = res_en.json()
    assert data_en["language"] == "English"
    assert data_en["analysis"]["category"] == "Water"
