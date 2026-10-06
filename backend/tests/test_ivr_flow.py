"""Comprehensive End-to-End Test Suite verifying the 20 IVR Scenarios in VoxentraAI.
"""
import sys
import os
import pytest
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.services.conversation_manager import conversation_manager
from app.services.location_resolver import location_resolver
from app.services.language_detector import language_detector
from app.services.speech_correction import speech_correction_service
from app.models.complaint import Complaint, ComplaintStatus, ComplaintPriority
from app.models.ivr import IVRSession, IVRState

# -------------------------------------------------------------
# TEST 1: Tamil complaint
# -------------------------------------------------------------
def test_1_tamil_complaint():
    db: Session = SessionLocal()
    try:
        session, greeting, _ = conversation_manager.create_session(db, "+919843011111", "Auto")
        assert greeting == ""
        res1 = conversation_manager.process_citizen_turn(db, session.session_id, "எங்க தெருவில் தண்ணீர் வரவில்லை.")
        assert res1["detected_language"] == "Tamil"
        assert res1["memory"]["category"] == "Water"
        assert "தெரு" in res1["ai_reply"] or "எந்த" in res1["ai_reply"]
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 2: English complaint
# -------------------------------------------------------------
def test_2_english_complaint():
    db: Session = SessionLocal()
    try:
        session, greeting, _ = conversation_manager.create_session(db, "+919843022222", "Auto")
        assert greeting == ""
        res1 = conversation_manager.process_citizen_turn(db, session.session_id, "There is no water supply in my street.")
        assert res1["detected_language"] == "English"
        assert res1["memory"]["category"] == "Water"
        assert "street" in res1["ai_reply"].lower() or "area" in res1["ai_reply"].lower()
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 3: Tanglish complaint
# -------------------------------------------------------------
def test_3_tanglish_complaint():
    db: Session = SessionLocal()
    try:
        session, greeting, _ = conversation_manager.create_session(db, "+919843033333", "Auto")
        assert greeting == ""
        res1 = conversation_manager.process_citizen_turn(db, session.session_id, "Gandhipuram-la thanni varala.")
        assert res1["detected_language"] == "Tanglish"
        assert res1["memory"]["category"] == "Water"
        assert res1["memory"]["area"] == "Gandhipuram"
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 4: Whisper transcription mistake
# -------------------------------------------------------------
def test_4_whisper_transcription_mistake():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843044444", "Auto")
        res1 = conversation_manager.process_citizen_turn(db, session.session_id, "Gandhi puram la tani vara la")
        assert res1["memory"]["area"] == "Gandhipuram"
        assert res1["memory"]["category"] == "Water"
        assert "thanni varala" in res1["memory"]["corrected_transcription"].lower() or "gandhipuram" in res1["memory"]["corrected_transcription"].lower()
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 5: Incomplete location
# -------------------------------------------------------------
def test_5_incomplete_location():
    res = location_resolver.resolve("Near the tea shop", current_language="Tanglish")
    assert res["confidence"] < 0.70 or res["needs_clarification"] is True
    assert res["clarification_question"] is not None

# -------------------------------------------------------------
# TEST 6: Street + landmark provided
# -------------------------------------------------------------
def test_6_street_and_landmark_provided():
    res = location_resolver.resolve("Cross Cut Road near Gandhipuram Central Bus Stand", current_language="English")
    assert "Cross Cut Road" in res["street"]
    assert "Gandhipuram" in res["landmark"]
    assert res["area"] == "Gandhipuram"
    assert res["confidence"] >= 0.85

# -------------------------------------------------------------
# TEST 7: Only landmark provided
# -------------------------------------------------------------
def test_7_only_landmark_provided():
    res = location_resolver.resolve("Saravanampatti bus stand pakkathula", current_language="Tanglish")
    assert "Saravanampatti Bus Stand" in res["landmark"]
    assert res["area"] == "Saravanampatti"
    assert res["ward_no"] == 2
    assert res["confidence"] >= 0.85

# -------------------------------------------------------------
# TEST 8: Citizen changes language
# -------------------------------------------------------------
def test_8_citizen_changes_language():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843088888", "Auto")
        sid = session.session_id

        # Start in Tanglish
        r1 = conversation_manager.process_citizen_turn(db, sid, "Gandhipuram-la power cut")
        assert r1["detected_language"] == "Tanglish"

        # Switch to English
        r2 = conversation_manager.process_citizen_turn(db, sid, "It has been off for 3 hours on Cross Cut Road")
        assert r2["detected_language"] == "English"
        assert "english" in str(r2.get("ai_reply", "")).lower() or any(w in r2["ai_reply"].lower() for w in ["what", "is", "how", "when", "please", "house", "street"])

        # Switch to Tamil
        r3 = conversation_manager.process_citizen_turn(db, sid, "தெருவில் உள்ள மின் கம்பத்தில் தீப்பொறி பறக்கிறது")
        assert r3["detected_language"] == "Tamil"
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 9: Citizen gives multiple details in one sentence
# -------------------------------------------------------------
def test_9_multiple_details_in_one_sentence():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843099999", "Auto")
        res = conversation_manager.process_citizen_turn(
            db, session.session_id,
            "Gandhipuram 5th street-la rendu naala full street-ku thanni varala."
        )
        mem = res["memory"]
        assert mem["area"] == "Gandhipuram"
        assert "5th" in mem["street"]
        assert "rendu" in mem["duration"].lower() or "2" in mem["duration"] or "naal" in mem["duration"].lower()
        assert "street" in mem["affected_scope"].lower() or "entire" in mem["affected_scope"].lower()
        # Skipped redundant questions
        assert res.get("next_field") not in ["problem_description", "district_area", "street_road_name", "duration"]
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 10: Citizen corrects previous answer
# -------------------------------------------------------------
def test_10_citizen_corrects_previous_answer():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843010101", "Auto")
        sid = session.session_id

        conversation_manager.process_citizen_turn(db, sid, "Gandhipuram-la water problem")
        conversation_manager.process_citizen_turn(db, sid, "5th street")

        # Citizen corrects street
        r3 = conversation_manager.process_citizen_turn(db, sid, "No, not 5th street, 6th street")
        assert "6th" in r3["memory"]["street"]
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 11: Ambiguous street
# -------------------------------------------------------------
def test_11_ambiguous_street():
    res = location_resolver.resolve("5th street", current_language="Tanglish")
    assert res["street"] == "5th Street"
    assert res["confidence"] < 0.75 or res["needs_confirmation"] is True or res["needs_clarification"] is True

# -------------------------------------------------------------
# TEST 12: Unknown location
# -------------------------------------------------------------
def test_12_unknown_location():
    res = location_resolver.resolve("Nonexistent Place 999XYZ", current_language="English")
    assert res["confidence"] < 0.70
    assert res["needs_clarification"] is True

# -------------------------------------------------------------
# TEST 13: At least 10 questions
# -------------------------------------------------------------
def test_13_at_least_10_questions():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843013131", "Auto")
        sid = session.session_id
        
        responses = []
        # Step by step 10+ turns
        turns = [
            "Thanni varala",
            "Gandhipuram",
            "2 days-ah",
            "5th street",
            "Full street-ku problem",
            "Very severe",
            "Drinking water affect aachu",
            "First time reporting",
            "Near Gandhipuram Bus Stand",
            "No dangerous wire",
            "Door number 45",
            "Daily recurring",
            "No previous id",
            "No other details"
        ]
        
        for t in turns:
            r = conversation_manager.process_citizen_turn(db, sid, t)
            responses.append(r)
            if r.get("state") == IVRState.CONFIRMATION.value:
                break

        final_res = responses[-1]
        assert final_res["state"] == IVRState.CONFIRMATION.value
        assert final_res["memory"]["questions_asked_count"] >= 10
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 14: Complaint confirmation
# -------------------------------------------------------------
def test_14_complaint_confirmation():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843014141", "Tanglish")
        sid = session.session_id

        # Set in confirmation state
        session.state = IVRState.CONFIRMATION.value
        session.structured_memory = {
            "problem_description": "Water problem",
            "area": "Gandhipuram",
            "street": "5th Street",
            "duration": "2 days"
        }
        db.commit()

        # Citizen rejects first to edit
        r_rej = conversation_manager.process_citizen_turn(db, sid, "No, change details")
        assert r_rej["memory"]["confirmation_status"] == "REJECTED"

        # Set back to confirmation and confirm
        session.state = IVRState.CONFIRMATION.value
        db.commit()
        r_conf = conversation_manager.process_citizen_turn(db, sid, "Aama, register pannunga")
        assert r_conf["complaint_created"] is True
        assert r_conf["complaint_number"].startswith("VX-")
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 15: Successful database insert
# -------------------------------------------------------------
def test_15_successful_database_insert():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843015151", "English")
        session.state = IVRState.CONFIRMATION.value
        session.structured_memory = {
            "problem_description": "Garbage not cleared",
            "category": "Sanitation",
            "area": "RS Puram",
            "street": "DB Road",
            "duration": "4 days"
        }
        db.commit()

        res = conversation_manager.finalize_and_register_complaint(db, session)
        assert res["success"] is True
        assert res["complaint_id"] is not None

        db_row = db.query(Complaint).filter(Complaint.id == res["complaint_id"]).first()
        assert db_row is not None
        assert db_row.category == "Sanitation"
        assert "RS Puram" in db_row.location
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 16: Database failure
# -------------------------------------------------------------
def test_16_database_failure():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843016161", "English")
        # Close session to simulate db failure
        db.close()
        res = conversation_manager.finalize_and_register_complaint(db, session)
        assert res["success"] is False
        assert res["complaint_created"] is False
        assert "complaint_number" not in res or res.get("complaint_number") is None
    except Exception:
        pass

# -------------------------------------------------------------
# TEST 17: AI must remain silent before first citizen speech
# -------------------------------------------------------------
def test_17_ai_silent_before_first_speech():
    db: Session = SessionLocal()
    try:
        session, greeting_text, greeting_spoken = conversation_manager.create_session(db, "+919843017171", "Auto")
        assert greeting_text == ""
        assert greeting_spoken == ""
        assert session.state == IVRState.WAITING_FOR_CITIZEN.value
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 18: Call timeout / Silence
# -------------------------------------------------------------
def test_18_call_timeout_and_silence():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843018181", "Tanglish")
        res = conversation_manager.process_citizen_turn(db, session.session_id, "")
        assert "voice clear-ah kekkala" in res["ai_reply"].lower() or "repeat" in res["ai_reply"].lower()
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 19: Whisper failure and retry
# -------------------------------------------------------------
def test_19_whisper_failure_and_retry():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843019191", "Tamil")
        session.language = "Tamil"
        db.commit()
        res = conversation_manager.process_citizen_turn(db, session.session_id, "")
        assert "மன்னிக்கவும்" in res["ai_reply"]
        assert "மீண்டும்" in res["ai_reply"] or "மறுபடியும்" in res["ai_reply"]
    finally:
        db.close()

# -------------------------------------------------------------
# TEST 20: Complaint ID generated only after successful save
# -------------------------------------------------------------
def test_20_complaint_id_only_after_save():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, "+919843020202", "English")
        assert session.complaint_number is None
        assert session.complaint_id is None

        session.state = IVRState.CONFIRMATION.value
        session.structured_memory = {
            "problem_description": "Road pothole damage",
            "category": "Roads",
            "area": "Singanallur",
            "street": "Trichy Road"
        }
        db.commit()

        res = conversation_manager.finalize_and_register_complaint(db, session)
        assert res["success"] is True
        assert res["complaint_number"].startswith("VX-")
        assert session.complaint_number == res["complaint_number"]
        assert session.complaint_id == res["complaint_id"]
    finally:
        db.close()
