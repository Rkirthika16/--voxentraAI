from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ivr_initiate_call():
    response = client.post("/api/v1/ivr/initiate-call", json={
        "caller_phone": "+919843098765",
        "toll_free_number": "1800-425-1913"
    })
    assert response.status_code == 200
    data = response.json()
    assert "call_sid" in data
    assert data["caller_phone"] == "+919843098765"
    assert "வணக்கம்" in data["greeting_tamil"]
    assert "Welcome" in data["greeting_english"]


def test_ivr_process_speech_rural_water():
    response = client.post("/api/v1/ivr/process-call", json={
        "caller_phone": "+919843098765",
        "speech_text": "மேட்டுப்பாளையம் ஊராட்சியில் கை பம்பு மோட்டார் பழுதாகி குடிநீர் வரவில்லை.",
        "language_hint": "ta"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Water"
    assert "Water Supply" in data["suggested_department"]
    assert data["complaint_number"].startswith("VOX-")
    assert "sms_text" in data
    assert "வணக்கம்" in data["confirmation_spoken_tamil"]


def test_ivr_process_speech_agricultural_electricity():
    response = client.post("/api/v1/ivr/process-call", json={
        "caller_phone": "+919843098765",
        "speech_text": "Athoor village transformer spark and agricultural power cut since morning.",
        "language_hint": "en"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Electricity"
    assert "Electricity" in data["suggested_department"]
    assert data["complaint_number"].startswith("VOX-")


def test_ivr_dialogue_turn_flow():
    # Turn 1: missing location
    turn1_resp = client.post("/api/v1/ivr/dialogue-turn", json={
        "call_sid": "CA_test123",
        "caller_phone": "+919843098765",
        "dialogue_turn": 1,
        "user_speech": "குடிநீர் குழாய் உடைந்துவிட்டது"
    })
    assert turn1_resp.status_code == 200
    turn1_data = turn1_resp.json()
    assert turn1_data["intent"] == "GATHER_MORE_INFO"
    assert turn1_data["is_completed"] is False

    # Turn 2: with location details
    turn2_resp = client.post("/api/v1/ivr/dialogue-turn", json={
        "call_sid": "CA_test123",
        "caller_phone": "+919843098765",
        "dialogue_turn": 2,
        "user_speech": "மேட்டுப்பாளையம் ஊராட்சி 3வது தெருவில் கோவில் அருகில் குடிநீர் குழாய் உடைந்துவிட்டது"
    })
    assert turn2_resp.status_code == 200
    turn2_data = turn2_resp.json()
    assert turn2_data["intent"] in ["GATHER_MORE_INFO", "CONFIRMATION_PENDING"]

    # Turn 3: caller confirms registration
    turn3_resp = client.post("/api/v1/ivr/dialogue-turn", json={
        "call_sid": "CA_test123",
        "caller_phone": "+919843098765",
        "dialogue_turn": 3,
        "user_speech": "ஆமாம், பதிவு செய்க"
    })
    assert turn3_resp.status_code == 200
    turn3_data = turn3_resp.json()
    if turn3_data["is_completed"]:
        assert turn3_data["intent"] == "CONFIRMED"
        assert turn3_data["complaint_number"].startswith("VOX-")
        assert turn3_data["sms_sent"] is True


def test_simulate_inbound_sms():
    response = client.post("/api/v1/ivr/simulate-inbound-sms", json={
        "from_phone": "+919843098765",
        "message_body": "திருப்புவனம் கிராம ரேஷன் கடையில் அரிசி வழங்கவில்லை."
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PROCESSED_AND_SMS_REPLIED"
    assert data["complaint_number"].startswith("VOX-")
    assert "தமிழ்நாடு அரசு" in data["reply_sms_tamil"]


def test_telephony_logs():
    response = client.get("/api/v1/ivr/telephony-logs?limit=20")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "logs" in data
    assert isinstance(data["logs"], list)


def test_exotel_incoming_call_webhook():
    response = client.post("/api/v1/webhooks/exotel/voice/incoming", json={
        "CallSid": "CA_exotel_webhook_test",
        "From": "+919843098765",
        "To": "1800-425-1913"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["action"] == "play_and_record"
    assert "prompt_text_ta" in data


def test_exotel_sms_incoming_webhook():
    response = client.post("/api/v1/webhooks/exotel/sms/incoming", json={
        "SmsSid": "SM_exotel_test",
        "From": "+919843098765",
        "Body": "Athoor village road damaged heavily with potholes."
    })
    assert response.status_code == 200
    data = response.json()
    assert data["complaint_number"].startswith("VOX-")
    assert data["extracted_category"] == "Roads"
