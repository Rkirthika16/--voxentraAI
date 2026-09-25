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
    assert "Gandhipuram" in data2["reply_text"]
    assert "spelling" in data2["reply_text"].lower() or "எழுத்துக் கூட்டலை" in data2["reply_text"]

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


def test_ivr_dialogue_explicit_slot_correction(client: TestClient):
    call_sid = f"CA_corr_{uuid.uuid4().hex[:12]}"

    # Turn 1: Problem
    res1 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "Streetlight is broken",
            "dialogue_turn": 1,
            "language_preference": "English"
        }
    )
    assert res1.status_code == 200

    # Turn 2: Location
    res2 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "Chennai",
            "dialogue_turn": 2,
            "language_preference": "English"
        }
    )
    assert res2.status_code == 200

    # Turn 3: Caller realizes mistake and corrects: "Wait, change district to Madurai"
    res3 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "Wait, change district to Madurai",
            "dialogue_turn": 3,
            "language_preference": "English"
        }
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["intent"] == "CORRECTION_APPLIED"
    assert "Madurai" in data3["ai_spoken_reply"]
    assert data3["collection_state"]["district_area"] == "Madurai"


def test_ivr_dialogue_spelled_out_speech_correction(client: TestClient):
    call_sid = f"CA_spell_{uuid.uuid4().hex[:12]}"

    # Turn 1: Problem
    client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "Garbage not cleared",
            "dialogue_turn": 1,
            "language_preference": "English"
        }
    )

    # Turn 2: User spells out location letter by letter
    res2 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "P E E L A M E D U",
            "dialogue_turn": 2,
            "language_preference": "English"
        }
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert "Peelamedu" in str(data2["collection_state"]["district_area"])


def test_tamil_ivr_speech_correction(client: TestClient):
    call_sid = f"CA_ta_corr_{uuid.uuid4().hex[:12]}"

    # Turn 1: Tamil problem
    client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "குடிநீர் குழாய் உடைந்து தண்ணீர் வீணாகிறது",
            "dialogue_turn": 1,
            "language_preference": "Tamil"
        }
    )

    # Turn 2: Tamil explicit location correction
    res2 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={
            "call_sid": call_sid,
            "user_speech": "மாவட்டம் மதுரை என மாற்றவும்",
            "dialogue_turn": 2,
            "language_preference": "Tamil"
        }
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"] == "CORRECTION_APPLIED"
    assert "மதுரை" in data2["collection_state"]["district_area"]
    assert "மாற்றப்பட்டது" in data2["ai_spoken_reply_tamil"]


def test_ivr_unclear_misheard_prompt_multilingual(client: TestClient):
    # 1. English IVR unclear
    call_en = f"CA_unclear_en_{uuid.uuid4().hex[:8]}"
    res_en = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={"call_sid": call_en, "user_speech": "umm uhh", "dialogue_turn": 1, "language_preference": "English"}
    )
    assert res_en.status_code == 200
    d_en = res_en.json()
    assert d_en["intent"] == "UNCLEAR_INPUT"
    assert "understood that correctly" in d_en["ai_spoken_reply"]
    assert "spelling" in d_en["ai_spoken_reply"]

    # 2. Tamil IVR unclear
    call_ta = f"CA_unclear_ta_{uuid.uuid4().hex[:8]}"
    res_ta = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={"call_sid": call_ta, "user_speech": "...", "dialogue_turn": 1, "language_preference": "Tamil"}
    )
    assert res_ta.status_code == 200
    d_ta = res_ta.json()
    assert d_ta["intent"] == "UNCLEAR_INPUT"
    assert "மன்னிக்கவும்" in d_ta["ai_spoken_reply_tamil"]

    # 3. Tanglish IVR unclear
    call_tg = f"CA_unclear_tg_{uuid.uuid4().hex[:8]}"
    res_tg = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={"call_sid": call_tg, "user_speech": "uhhhh...", "dialogue_turn": 1, "language_preference": "Tanglish"}
    )
    assert res_tg.status_code == 200
    d_tg = res_tg.json()
    assert d_tg["intent"] == "UNCLEAR_INPUT"
    assert "purinjikkala" in d_tg["ai_spoken_reply"]


def test_ivr_tanglish_spelling_variation_confirmation(client: TestClient):
    call_sid = f"CA_tg_spell_{uuid.uuid4().hex[:8]}"

    # Turn 1: Problem in Tanglish
    client.post(
        "/api/v1/ivr/dialogue-turn",
        json={"call_sid": call_sid, "user_speech": "Water pipe leak aagi thanni waste aagudhu", "dialogue_turn": 1, "language_preference": "Tanglish"}
    )

    # Turn 2: Tanglish speaker says location with spelling variation: "Kandhipuram"
    res2 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={"call_sid": call_sid, "user_speech": "Kandhipuram", "dialogue_turn": 2, "language_preference": "Tanglish"}
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["intent"] == "SLOT_CONFIRMATION_PENDING"
    assert "Gandhipuram" in d2["ai_spoken_reply"]
    assert "correct spelling" in d2["ai_spoken_reply"] or "spelling" in d2["ai_spoken_reply"]

    # Turn 3: Tanglish confirmation "Aama correct"
    res3 = client.post(
        "/api/v1/ivr/dialogue-turn",
        json={"call_sid": call_sid, "user_speech": "Aama, correct", "dialogue_turn": 3, "language_preference": "Tanglish"}
    )
    assert res3.status_code == 200
    d3 = res3.json()
    assert d3["collection_state"]["district_area"] == "Gandhipuram"
    assert "confirm panniyaachu" in d3["ai_spoken_reply"]


def test_voice_register_error_correction_and_confirmation(client: TestClient):
    sid = f"VR_err_{uuid.uuid4().hex[:8]}"

    # Start session
    client.post("/api/v1/voice-register/start", json={"session_id": sid, "language_hint": "English"})

    # Turn 1: Unclear input
    res1 = client.post(
        "/api/v1/voice-register/turn",
        json={"session_id": sid, "user_speech": "umm...", "language_preference": "English"}
    )
    assert res1.status_code == 200
    assert res1.json()["intent"] == "UNCLEAR_INPUT"
    assert "understood that correctly" in res1.json()["ai_reply"]

    # Turn 2: State problem
    res2 = client.post(
        "/api/v1/voice-register/turn",
        json={"session_id": sid, "user_speech": "Streetlight broken", "language_preference": "English"}
    )
    assert res2.status_code == 200

    # Turn 3: Misspelled location
    res3 = client.post(
        "/api/v1/voice-register/turn",
        json={"session_id": sid, "user_speech": "Pilamedu", "language_preference": "English"}
    )
    assert res3.status_code == 200
    assert res3.json()["intent"] == "SLOT_CONFIRMATION_PENDING"
    assert "Peelamedu" in res3.json()["ai_reply"]

    # Turn 4: Confirm
    res4 = client.post(
        "/api/v1/voice-register/turn",
        json={"session_id": sid, "user_speech": "Yes, correct", "language_preference": "English"}
    )
    assert res4.status_code == 200
    assert res4.json()["collection_state"]["district_area"] == "Peelamedu"


def test_conversation_service_spelling_variation_flow():
    from app.ai.conversation_service import conversation_service
    sid = f"conv_test_{uuid.uuid4().hex[:8]}"

    # Turn 1: Problem
    res1 = conversation_service.process_turn(sid, "Water pipe leakage in the street")
    assert res1["state"] == "WAITING_FOR_USER"

    # Turn 2: Misspelled location
    res2 = conversation_service.process_turn(sid, "Kandhipuram")
    assert res2["state"] == "SLOT_CONFIRMATION_PENDING"
    assert "Gandhipuram" in res2["ai_text"]
    assert "correct spelling" in res2["ai_text"] or "spelling" in res2["ai_text"]

    # Turn 3: User confirms
    res3 = conversation_service.process_turn(sid, "Yes, that is correct")
    assert res3["context"]["location"] == "Gandhipuram"
    assert "Gandhipuram" in res3["ai_text"]


