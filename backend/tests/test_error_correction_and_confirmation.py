import uuid
from fastapi.testclient import TestClient
from app.ai.complaint_collector import complaint_collector
from app.models.complaint import Complaint


def test_unclear_misheard_input_reprompt_english(client: TestClient):
    session_id = f"test_unclear_en_{uuid.uuid4().hex[:8]}"

    # Send garbled / mumble noise
    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "umm...", "session_id": session_id, "language_hint": "English"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "UNCLEAR_INPUT"
    assert "understood that correctly" in data["reply_text"]
    assert "spelling" in data["reply_text"]


def test_unclear_misheard_input_reprompt_tamil(client: TestClient):
    session_id = f"test_unclear_ta_{uuid.uuid4().hex[:8]}"

    # Send filler noise with Tamil hint
    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "???...", "session_id": session_id, "language_hint": "Tamil"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "UNCLEAR_INPUT"
    assert "மன்னிக்கவும்" in data["reply_text"]
    assert "எழுத்துக் கூட்டலை" in data["reply_text"] or "மீண்டும்" in data["reply_text"]


def test_spelling_variation_candidate_confirmation_flow(client: TestClient):
    session_id = f"test_spell_conf_{uuid.uuid4().hex[:8]}"

    # Turn 1: State the problem
    res1 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Water pipe is broken and leaking severely", "session_id": session_id}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["collection_state"]["current_field_prompted"] == "district_area"

    # Turn 2: Citizen inputs a misspelled / STT variation location: "Kandhipuram"
    res2 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Kandhipuram", "session_id": session_id}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    # Should NOT silently store or assume; must prompt for confirmation
    assert data2["intent"] == "SLOT_CONFIRMATION_PENDING"
    assert "I understood it as Gandhipuram" in data2["reply_text"] or "Gandhipuram" in data2["reply_text"]
    assert "correct spelling" in data2["reply_text"]

    # Turn 3: Citizen confirms "Yes, that's correct"
    res3 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Yes, that is correct", "session_id": session_id}
    )
    assert res3.status_code == 200
    data3 = res3.json()
    # Now it is confirmed and stored! Moves to the next field (street_road_name)
    assert data3["collection_state"]["fields"]["district_area"] == "Gandhipuram"
    assert "Gandhipuram" in data3["reply_text"]
    assert data3["collection_state"]["current_field_prompted"] == "street_road_name"


def test_spelling_correction_with_spelled_out_letters(client: TestClient):
    session_id = f"test_spell_letters_{uuid.uuid4().hex[:8]}"

    # Turn 1: State the problem
    client.post(
        "/api/v1/assistant/chat",
        json={"message": "Streetlight not glowing", "session_id": session_id}
    )

    # Turn 2: Citizen enters slight spelling error: "Pilamedu"
    res2 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Pilamedu", "session_id": session_id}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"] == "SLOT_CONFIRMATION_PENDING"

    # Turn 3: Citizen spells it out letter-by-letter: "P E E L A M E D U"
    res3 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "No, it is P E E L A M E D U", "session_id": session_id}
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["collection_state"]["fields"]["district_area"] == "Peelamedu"


def test_tamil_spelling_confirmation(client: TestClient):
    session_id = f"test_ta_conf_{uuid.uuid4().hex[:8]}"

    # Turn 1: Tamil problem description
    client.post(
        "/api/v1/assistant/chat",
        json={"message": "சாக்கடை நீர் வழிகிறது", "session_id": session_id, "language_hint": "Tamil"}
    )

    # Turn 2: User provides location with slight variation
    res2 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Kandhipuram", "session_id": session_id, "language_hint": "Tamil"}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"] == "SLOT_CONFIRMATION_PENDING"
    assert "நான் இதை" in data2["reply_text"]
    assert "என்று புரிந்து கொண்டேன்" in data2["reply_text"]

    # Turn 3: Confirm with Tamil "சரி, ஆமாம்"
    res3 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "ஆமாம், சரி", "session_id": session_id, "language_hint": "Tamil"}
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["collection_state"]["fields"]["district_area"] == "Gandhipuram"
    assert "உறுதிப்படுத்தப்பட்டது" in data3["reply_text"]


def test_ivr_dialogue_turn_error_correction(client: TestClient):
    call_sid = f"CA_{uuid.uuid4().hex[:12]}"

    # Turn 1: Initial problem
    res1 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "Drinking water pipeline leakage",
            "dialogue_turn": 1,
            "language_preference": "English"
        }
    )
    assert res1.status_code == 200

    # Turn 2: User says misspelled location
    res2 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "Kandhipuram",
            "dialogue_turn": 2,
            "language_preference": "English"
        }
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"] == "SLOT_CONFIRMATION_PENDING"
    assert "Gandhipuram" in data2["ai_spoken_reply"]

    # Turn 3: User confirms over IVR
    res3 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "Yes, correct",
            "dialogue_turn": 3,
            "language_preference": "English"
        }
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["collection_state"]["district_area"] == "Gandhipuram"
