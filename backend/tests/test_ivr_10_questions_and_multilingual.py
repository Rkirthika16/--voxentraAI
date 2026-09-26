import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ivr_tamil_detection_and_speaking():
    """Verify Tamil citizen input is detected as Tamil and AI responds with Tamil text and speech."""
    init_res = client.post("/api/v1/new-ivr/session", json={"caller_phone": "+919876543210"})
    assert init_res.status_code == 201
    session_id = init_res.json()["session_id"]

    # Citizen speaks in pure Tamil
    turn1 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "எங்கள் பகுதியில் குடிநீர் வரவில்லை"
    })
    assert turn1.status_code == 200
    d1 = turn1.json()
    assert d1["success"] is True
    assert d1["detected_language"] == "Tamil"
    assert "குடிநீர்" in d1["ai_reply"] or "பிரச்சினை" in d1["ai_reply"] or "எந்த" in d1["ai_reply"] or "பகுதி" in d1["ai_reply"]
    assert d1["question_count"] >= 1
    assert d1["max_questions"] == 10


def test_ivr_tanglish_detection_and_speaking():
    """Verify Tanglish citizen input is detected as Tanglish and AI responds with natural Tanglish."""
    init_res = client.post("/api/v1/new-ivr/session", json={"caller_phone": "+919876543210"})
    session_id = init_res.json()["session_id"]

    # Citizen speaks in Tanglish
    turn1 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "Street light work aagala, full-ah iruttu irukku"
    })
    assert turn1.status_code == 200
    d1 = turn1.json()
    assert d1["success"] is True
    assert d1["detected_language"] == "Tanglish"
    assert "location" in d1["next_field"] or "district" in d1["ai_reply"].lower() or "street" in d1["ai_reply"].lower()
    assert d1["question_count"] >= 1


def test_ivr_english_detection_and_speaking():
    """Verify English citizen input is detected as English and AI responds with English."""
    init_res = client.post("/api/v1/new-ivr/session", json={"caller_phone": "+919876543210"})
    session_id = init_res.json()["session_id"]

    # Citizen speaks in English
    turn1 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "There is a severe drainage overflow on Main Road since yesterday"
    })
    assert turn1.status_code == 200
    d1 = turn1.json()
    assert d1["success"] is True
    assert d1["detected_language"] == "English"
    assert "Drainage" in d1["memory"]["category"]


def test_ivr_maximum_10_questions_and_confirmation():
    """
    Verify multi-turn question gathering up to 10 questions maximum,
    and automatic transition to confirmation summary.
    """
    init_res = client.post("/api/v1/new-ivr/session", json={"caller_phone": "+919843098765"})
    session_id = init_res.json()["session_id"]

    # Turn 1: Problem only
    t1 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "குடிநீர் விநியோகத்தில் பிரச்சினை"
    }).json()
    assert t1["state"] == "WAITING_FOR_CITIZEN"
    assert t1["question_count"] == 1
    assert t1["next_field"] == "location"

    # Turn 2: Location
    t2 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "கோயம்புத்தூர் காந்திபுரம்"
    }).json()
    assert t2["state"] == "WAITING_FOR_CITIZEN"
    assert t2["question_count"] == 2
    assert t2["next_field"] == "duration"

    # Turn 3: Duration
    t3 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "மூன்று நாட்களாக"
    }).json()
    assert t3["state"] == "WAITING_FOR_CITIZEN"
    assert t3["question_count"] == 3
    assert t3["next_field"] == "affected_scope"

    # Turn 4: Scope -> transitions to CONFIRMATION
    t4 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "பகுதி முழுவதும்"
    }).json()
    assert t4["state"] == "CONFIRMATION"
    assert t4["is_confirmation"] is True
    assert "உறுதி" in t4["ai_reply"] or "பதிவு" in t4["ai_reply"] or "காந்திபுரம்" in t4["ai_reply"]

    # Turn 5: Citizen confirms
    t5 = client.post(f"/api/v1/new-ivr/session/{session_id}/message", json={
        "message": "ஆமாம், பதிவு செய்யவும்"
    }).json()
    assert t5["state"] == "COMPLETED"
    assert t5["complaint_created"] is True
    assert t5["complaint_number"].startswith("VX-")


def test_ivr_tts_audio_synthesis_endpoints():
    """Verify TTS endpoints stream valid MP3 audio bytes for Tamil and English."""
    res_ta = client.get("/api/v1/new-ivr/tts?text=வணக்கம்&lang=ta")
    assert res_ta.status_code == 200
    assert len(res_ta.content) > 0
    assert res_ta.headers["content-type"] == "audio/mpeg"

    res_en = client.get("/api/v1/audio/tts?text=Welcome+to+VoxentraAI&lang=en")
    assert res_en.status_code == 200
    assert len(res_en.content) > 0
    assert res_en.headers["content-type"] == "audio/mpeg"
