import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.complaint_collector import complaint_collector
from app.ai.language_service import detect_language
from app.ai.classification_service import classify_complaint
from app.integrations.telephony.twilio_adapter import twilio_adapter
from app.models.complaint import Complaint, ComplaintStatus, ComplaintSource


def test_language_detection_multilingual():
    """Requirement 1: Multilingual AI Conversation detection."""
    # Tamil speech
    ta_speech = "எங்க தெருவுல மூணு நாளா குடிநீர் வரவே இல்லை"
    lang, conf = detect_language(ta_speech)
    assert lang == "Tamil"
    assert conf > 0.8

    # English speech
    en_speech = "There is a severe water leakage on Cross Cut Road"
    lang_en, conf_en = detect_language(en_speech)
    assert lang_en == "English"
    assert conf_en > 0.8

    # Tanglish speech
    tanglish_speech = "Gandhipuram-la water pipe odanju romba thanni valiyuthu"
    lang_tg, conf_tg = detect_language(tanglish_speech)
    assert lang_tg in ["Tanglish", "Tamil"]


def test_department_and_complaint_understanding():
    """Requirement 3 & 4: Department detection and complaint understanding."""
    # Example from requirement: "எங்க தெருவுல மூணு நாளா குடிநீர் வரவே இல்லை."
    text = "எங்க தெருவுல மூணு நாளா குடிநீர் வரவே இல்லை"
    cat, dept, conf = classify_complaint(text)
    assert cat == "Water"
    assert "Water" in dept

    # Garbage issue
    cat_g, dept_g, _ = classify_complaint("குப்பை அள்ளாமல் துர்நாற்றம் வீசுகிறது")
    assert cat_g == "Sanitation/Garbage"
    assert "Sanitation" in dept_g

    # Road damage issue
    cat_r, dept_r, _ = classify_complaint("ரோட்டில் பெரிய பள்ளம் மற்றும் குழி உள்ளது")
    assert cat_r == "Roads"
    assert "Roads" in dept_r

    # Streetlight issue
    cat_s, dept_s, _ = classify_complaint("தெரு விளக்கு எரியவில்லை இருட்டாக உள்ளது")
    assert cat_s == "Streetlights"
    assert "Lighting" in dept_s or "Street" in dept_s


def test_voice_register_start_and_turn_flow(client: TestClient, db_session: Session):
    """Requirement 13 & 14: Complete dialogue flow through /voice-register endpoints."""
    call_sid = f"EXO_CALL_{uuid.uuid4().hex[:12]}"
    caller_phone = "+919843098765"

    # Step 1: Citizen calls Exotel toll-free number
    start_res = client.post(
        "/api/v1/voice-register/start",
        json={"exotel_call_sid": call_sid, "caller_phone": caller_phone, "language_hint": "Tamil"}
    )
    assert start_res.status_code == 200
    start_data = start_res.json()
    assert start_data["call_sid"] == call_sid
    assert "வணக்கம்" in start_data["greeting_text_tamil"]
    assert start_data["first_question"] is not None

    # Step 2: Citizen describes problem in Tamil
    turn1_res = client.post(
        "/api/v1/voice-register/turn",
        json={
            "call_sid": call_sid,
            "user_speech": "எங்க தெருவுல மூணு நாளா குடிநீர் வரவே இல்லை",
            "caller_phone": caller_phone
        }
    )
    assert turn1_res.status_code == 200
    turn1_data = turn1_res.json()
    assert turn1_data["detected_language"] == "Tamil"
    assert turn1_data["collection_state"]["problem_description"] is not None

    # Step 3: Citizen provides Area/District
    turn2_res = client.post(
        "/api/v1/voice-register/turn",
        json={
            "call_sid": call_sid,
            "user_speech": "கோயம்புத்தூர் காந்திபுரம்",
            "caller_phone": caller_phone
        }
    )
    assert turn2_res.status_code == 200
    turn2_data = turn2_res.json()
    assert turn2_data["collection_state"]["district_area"] is not None

    # Step 4: Citizen provides Street name
    turn3_res = client.post(
        "/api/v1/voice-register/turn",
        json={
            "call_sid": call_sid,
            "user_speech": "5வது தெரு",
            "caller_phone": caller_phone
        }
    )
    assert turn3_res.status_code == 200
    turn3_data = turn3_res.json()
    assert turn3_data["collection_state"]["street_road_name"] is not None

    # Step 5: Citizen provides Landmark
    turn4_res = client.post(
        "/api/v1/voice-register/turn",
        json={
            "call_sid": call_sid,
            "user_speech": "பேருந்து நிலையம் அருகில்",
            "caller_phone": caller_phone
        }
    )
    assert turn4_res.status_code == 200
    turn4_data = turn4_res.json()
    assert turn4_data["collection_state"]["landmark"] is not None

    # Step 6: Citizen provides remaining details and name (Ramesh)
    turn5_res = client.post(
        "/api/v1/voice-register/turn",
        json={
            "call_sid": call_sid,
            "user_speech": "Door No 45, தொடர்ந்து பிரச்சனை உள்ளது, என் பெயர் ரமேஷ் 9843098765",
            "caller_phone": caller_phone
        }
    )
    assert turn5_res.status_code == 200
    turn5_data = turn5_res.json()

    # Step 7: Check confirmation pending summary
    assert turn5_data["is_confirmation_pending"] is True
    assert "உறுதிப்படுத்துகிறேன்" in turn5_data["ai_reply_tamil"]
    assert "குடிநீர்" in turn5_data["ai_reply_tamil"]
    assert "ரமேஷ்" in turn5_data["ai_reply_tamil"] or "Ramesh" in turn5_data["ai_reply_tamil"] or "9843098765" in turn5_data["ai_reply_tamil"]

    # Step 8: Citizen confirms
    confirm_res = client.post(
        "/api/v1/voice-register/turn",
        json={
            "call_sid": call_sid,
            "user_speech": "ஆமாம், பதிவு செய்க",
            "caller_phone": caller_phone
        }
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["is_completed"] is True
    assert confirm_data["complaint_number"] is not None
    assert confirm_data["complaint_number"].startswith("VX-")

    # Verify complaint in database
    comp = db_session.query(Complaint).filter(Complaint.complaint_number == confirm_data["complaint_number"]).first()
    assert comp is not None
    assert comp.source == ComplaintSource.TELEPHONY_IVR
    assert comp.ai_metadata["call_sid"] == call_sid
    assert comp.ai_metadata["caller_phone"] == caller_phone


def test_location_clarification_no_assumptions():
    """Requirement 5 & 6: Location accuracy and no missing assumption."""
    session = complaint_collector.get_or_create_session(f"loc_test_{uuid.uuid4().hex[:8]}")
    session["fields"]["problem_description"] = "Water leak"
    
    # Check accuracy before details
    acc_initial = complaint_collector.evaluate_location_accuracy(session)
    assert acc_initial == "Unclear"

    # Only Area provided
    session["fields"]["district_area"] = "Gandhipuram"
    acc_partial = complaint_collector.evaluate_location_accuracy(session)
    assert acc_partial == "Partially Complete"

    # Street and landmark provided
    session["fields"]["street_road_name"] = "5th Street"
    session["fields"]["landmark"] = "Near Bus Stand"
    acc_complete = complaint_collector.evaluate_location_accuracy(session)
    assert acc_complete == "Complete"


def test_twilio_sms_templates_and_failure_handling():
    """Requirement 11 & 12: Twilio SMS formatting and honest failure handling."""
    complaint_no = "VX-20260923-000123"
    desc = "மூன்று நாட்களாக குடிநீர் வரவில்லை"
    dept = "Water Supply & Sewage Department"
    loc = "காந்திபுரம், 5வது தெரு"

    # Tamil SMS format
    sms_ta = twilio_adapter.build_complaint_sms(
        complaint_number=complaint_no,
        description=desc,
        department=dept,
        location=loc,
        lang="Tamil"
    )
    assert "VoxentraAI" in sms_ta
    assert complaint_no in sms_ta
    assert "குடிநீர்" in sms_ta
    assert "பதிவு செய்யப்பட்டது" in sms_ta

    # English SMS format
    sms_en = twilio_adapter.build_complaint_sms(
        complaint_number=complaint_no,
        description="No water supply for 3 days",
        department=dept,
        location="Gandhipuram, 5th Street",
        lang="English"
    )
    assert "VoxentraAI Complaint Registered" in sms_en
    assert complaint_no in sms_en
    assert "REGISTERED" in sms_en


def test_exotel_dialogue_webhook(client: TestClient):
    """Requirement 13: Exotel Live Passthru dialogue webhook."""
    call_sid = f"EXO_WH_{uuid.uuid4().hex[:12]}"
    from_num = "+919843098765"

    webhook_res = client.post(
        "/api/v1/webhooks/exotel/voice/dialogue",
        json={
            "CallSid": call_sid,
            "From": from_num,
            "SpeechResult": "ரோடு டேமேஜ் ஆகி பெரிய பள்ளம் இருக்கு, காந்திபுரம் 5வது தெரு"
        }
    )
    assert webhook_res.status_code == 200
    wh_data = webhook_res.json()
    assert wh_data["status"] == "ok"
    assert wh_data["call_sid"] == call_sid
    assert wh_data["prompt"] is not None
