import sys
import os
import io
import json
import base64
import pytest

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    reconfig = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig):
        try:
            reconfig(encoding="utf-8")
        except Exception:
            pass

# Add backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import importlib
SessionLocal = importlib.import_module("app.database.session").SessionLocal
conversation_manager = importlib.import_module("app.services.conversation_manager").conversation_manager
location_resolver = importlib.import_module("app.services.location_resolver").location_resolver
speech_correction_service = importlib.import_module("app.services.speech_correction").speech_correction_service
language_detector = importlib.import_module("app.services.language_detector").language_detector
question_manager = importlib.import_module("app.services.question_manager").question_manager
audio_converter = importlib.import_module("app.ai.audio_converter")
tts_service = importlib.import_module("app.ai.tts_service")
IVRSession = importlib.import_module("app.models.ivr").IVRSession
IVRState = importlib.import_module("app.models.ivr").IVRState
Complaint = importlib.import_module("app.models.complaint").Complaint
app = importlib.import_module("app.main").app

from fastapi.testclient import TestClient

def run_comprehensive_acceptance_suite():
    db = SessionLocal()
    client = TestClient(app)
    
    print("=" * 75)
    print("VOXENTRAAI REAL-PHONE CONVERSATIONAL AI IVR COMPREHENSIVE ACCEPTANCE SUITE")
    print("=" * 75)

    # =========================================================================
    # TEST 1: Tanglish Phone Call Scenario (Water Grievance with Slot Skipping)
    # =========================================================================
    print("\n--- TEST 1: Tanglish Phone Call Flow with AI Silent at Start & 10+ Points ---")
    session1, greeting_txt, greeting_spk = conversation_manager.create_session(
        db, caller_phone="+919843011111", language_preference="Auto"
    )
    sid1 = session1.session_id
    print(f"  [Call Connected] Session ID: {sid1}")
    print(f"  [Rule 1 Verification] AI Silent on connect: greeting='{greeting_txt}', spoken='{greeting_spk}'")
    assert greeting_txt == "" and greeting_spk == "", "AI must be silent at call start!"
    assert session1.state == IVRState.WAITING_FOR_CITIZEN.value

    # Turn 1: Citizen speaks first with multiple details
    print("\n  [Turn 1] Citizen: 'Gandhipuram 5th street-la rendu naala full street-ku thanni varala.'")
    t1 = conversation_manager.process_citizen_turn(db, sid1, "Gandhipuram 5th street-la rendu naala full street-ku thanni varala.")
    print(f"    -> Language Detected: {t1['detected_language']}")
    print(f"    -> Category Extracted: {t1['memory'].get('category')}")
    print(f"    -> Area Extracted: {t1['memory'].get('area')}")
    print(f"    -> Street Extracted: {t1['memory'].get('street')}")
    print(f"    -> Duration Extracted: {t1['memory'].get('duration')}")
    print(f"    -> Scope Extracted: {t1['memory'].get('affected_scope')}")
    print(f"    -> AI Question: {t1['ai_reply']}")
    print(f"    -> Next Slot Prompted: {t1.get('next_field')}")
    assert t1['detected_language'] == 'Tanglish'
    assert t1['memory']['category'] == 'Water'
    assert t1['memory']['area'] == 'Gandhipuram'
    assert '5th' in t1['memory']['street'].lower()
    # Problem, area, street, duration, affected_scope were provided -> AI must skip those!
    assert t1.get('next_field') not in ['problem_description', 'district_area', 'street_road_name', 'duration', 'affected_scope']

    # Turn 2: Exact location
    print("\n  [Turn 2] Citizen: 'Near door number 24'")
    t2 = conversation_manager.process_citizen_turn(db, sid1, "Near door number 24")
    print(f"    -> Next Slot Prompted: {t2.get('next_field')}")

    # Turn 3: Landmark
    print("\n  [Turn 3] Citizen: 'Gandhipuram bus stand pakkathula'")
    t3 = conversation_manager.process_citizen_turn(db, sid1, "Gandhipuram bus stand pakkathula")
    print(f"    -> Landmark: {t3['memory'].get('landmark')}")
    print(f"    -> Next Slot Prompted: {t3.get('next_field')}")
    assert 'bus stand' in t3['memory']['landmark'].lower()

    # Turn 4: Severity
    print("\n  [Turn 4] Citizen: 'Water completely stop aaiduchu'")
    t4 = conversation_manager.process_citizen_turn(db, sid1, "Water completely stop aaiduchu")
    print(f"    -> Severity: {t4['memory'].get('severity')}")
    print(f"    -> Next Slot Prompted: {t4.get('next_field')}")

    # Turn 5: Impact on drinking water
    print("\n  [Turn 5] Citizen: 'All houses drinking water supply affected'")
    t5 = conversation_manager.process_citizen_turn(db, sid1, "All houses drinking water supply affected")
    print(f"    -> Next Slot Prompted: {t5.get('next_field')}")

    # Turn 6: Safety hazard
    print("\n  [Turn 6] Citizen: 'No safety danger'")
    t6 = conversation_manager.process_citizen_turn(db, sid1, "No safety danger")
    print(f"    -> Next Slot Prompted: {t6.get('next_field')}")

    # Turn 7: Previous complaint
    print("\n  [Turn 7] Citizen: 'First time reporting'")
    t7 = conversation_manager.process_citizen_turn(db, sid1, "First time reporting")
    print(f"    -> Next Slot Prompted: {t7.get('next_field')}")

    # Turn 8: Frequency
    print("\n  [Turn 8] Citizen: 'Daily recurring issue'")
    t8 = conversation_manager.process_citizen_turn(db, sid1, "Daily recurring issue")
    print(f"    -> Next Slot Prompted: {t8.get('next_field')}")

    # Turn 9: Additional details
    print("\n  [Turn 9] Citizen: 'No other details'")
    t9 = conversation_manager.process_citizen_turn(db, sid1, "No other details")
    print(f"    -> State: {t9['state']}")
    print(f"    -> Is Confirmation: {t9.get('is_confirmation')}")
    print(f"    -> Summary AI Reply:\n      {t9['ai_reply']}")
    assert t9['state'] == IVRState.CONFIRMATION.value
    assert t9['is_confirmation'] is True

    # Turn 10: Citizen Confirms: "Aama, register pannunga"
    print("\n  [Turn 10] Citizen: 'Aama, register pannunga'")
    t10 = conversation_manager.process_citizen_turn(db, sid1, "Aama, register pannunga")
    print(f"    -> State: {t10['state']}")
    print(f"    -> Complaint Created: {t10.get('complaint_created')}")
    print(f"    -> Complaint Number: {t10.get('complaint_number')}")
    print(f"    -> Final AI Spoken Message:\n      {t10.get('spoken_reply')}")
    assert t10['complaint_created'] is True
    assert t10['complaint_number'] is not None
    assert "VX-" in t10['complaint_number']
    assert "Pending" in t10['spoken_reply']

    # Verify DB record
    c_db = db.query(Complaint).filter(Complaint.id == t10['complaint_id']).first()
    assert c_db is not None
    print(f"  [DB Verification] Complaint ID={c_db.id}, Number={c_db.complaint_number}, Category={c_db.category}, Location={c_db.location}")
    print("  [Result] TEST 1 PASSED! ✅")

    # =========================================================================
    # TEST 2: Pure Tamil Phone Call Scenario (Electricity Outage)
    # =========================================================================
    print("\n--- TEST 2: Pure Tamil Phone Call Flow ---")
    session2, g2_txt, _ = conversation_manager.create_session(db, "+919843022222", "Auto")
    sid2 = session2.session_id
    assert g2_txt == "", "AI must be silent at call start!"

    # Turn 1: Tamil citizen speaks
    print("\n  [Turn 1] Citizen: 'ஆர் எஸ் புரம் டி பி ரோட்டில் மின்சாரம் துண்டிக்கப்பட்டுள்ளது'")
    ta1 = conversation_manager.process_citizen_turn(db, sid2, "ஆர் எஸ் புரம் டி பி ரோட்டில் மின்சாரம் துண்டிக்கப்பட்டுள்ளது")
    print(f"    -> Detected Language: {ta1['detected_language']}")
    print(f"    -> Category: {ta1['memory'].get('category')}")
    print(f"    -> Area: {ta1['memory'].get('area')}")
    print(f"    -> Street: {ta1['memory'].get('street')}")
    print(f"    -> AI Question in Tamil: {ta1['ai_reply']}")
    assert ta1['detected_language'] == 'Tamil'
    assert 'Electricity' in ta1['memory']['category'] or 'Power' in ta1['memory']['category']
    assert 'RS Puram' in ta1['memory']['area'] or 'ஆர் எஸ் புரம்' in ta1['memory']['area'] or 'DB Road' in str(ta1['memory']['street'])

    # Tamil follow-ups
    ta2 = conversation_manager.process_citizen_turn(db, sid2, "கதவு எண் 12 அருகில்")
    ta3 = conversation_manager.process_citizen_turn(db, sid2, "ஆர் எஸ் புரம் தபால் நிலையம் அருகில்")
    ta4 = conversation_manager.process_citizen_turn(db, sid2, "மூன்று மணி நேரமாக")
    ta5 = conversation_manager.process_citizen_turn(db, sid2, "முழு தெருவும் மின்சாரம் இல்லை")
    ta6 = conversation_manager.process_citizen_turn(db, sid2, "முழுமையாக மின்சாரம் இல்லை")
    ta7 = conversation_manager.process_citizen_turn(db, sid2, "மின் கம்பத்தில் தீப்பொறி பறக்கிறது")
    ta8 = conversation_manager.process_citizen_turn(db, sid2, "முதல் முறை புகார் செய்கிறேன்")
    ta9 = conversation_manager.process_citizen_turn(db, sid2, "அடிக்கடி நடக்கிறது")
    ta10 = conversation_manager.process_citizen_turn(db, sid2, "கூடுதல் தகவல் இல்லை")
    assert ta10['state'] == IVRState.CONFIRMATION.value
    print(f"    -> Tamil Summary:\n      {ta10['ai_reply']}")

    # Confirm in Tamil
    ta_conf = conversation_manager.process_citizen_turn(db, sid2, "ஆம், புகாரை பதிவு செய்யுங்கள்")
    assert ta_conf['complaint_created'] is True
    assert "VX-" in ta_conf['complaint_number']
    print(f"    -> Tamil Spoken Response:\n      {ta_conf['spoken_reply']}")
    print("  [Result] TEST 2 PASSED! ✅")

    # =========================================================================
    # TEST 3: Pure English Phone Call Scenario (Road Grievance)
    # =========================================================================
    print("\n--- TEST 3: Pure English Phone Call Flow ---")
    session3, g3_txt, _ = conversation_manager.create_session(db, "+919843033333", "Auto")
    sid3 = session3.session_id

    en1 = conversation_manager.process_citizen_turn(db, sid3, "There is a massive deep pothole in Peelamedu Avinashi Road.")
    print(f"    -> Detected Language: {en1['detected_language']}")
    print(f"    -> Category: {en1['memory'].get('category')}")
    print(f"    -> Area: {en1['memory'].get('area')}")
    print(f"    -> Street: {en1['memory'].get('street')}")
    assert en1['detected_language'] == 'English'
    assert 'Road' in en1['memory']['category']

    en2 = conversation_manager.process_citizen_turn(db, sid3, "Near pillar number 45")
    en3 = conversation_manager.process_citizen_turn(db, sid3, "Near Fun Republic Mall")
    en4 = conversation_manager.process_citizen_turn(db, sid3, "Since 4 days")
    en5 = conversation_manager.process_citizen_turn(db, sid3, "Entire road section is broken")
    en6 = conversation_manager.process_citizen_turn(db, sid3, "Severe traffic blockage and risk of accidents")
    en7 = conversation_manager.process_citizen_turn(db, sid3, "High danger for two-wheelers")
    en8 = conversation_manager.process_citizen_turn(db, sid3, "No previous complaint")
    en9 = conversation_manager.process_citizen_turn(db, sid3, "Happens continuously after rains")
    en10 = conversation_manager.process_citizen_turn(db, sid3, "Nothing else to add")
    assert en10['state'] == IVRState.CONFIRMATION.value

    en_conf = conversation_manager.process_citizen_turn(db, sid3, "Yes, please register the complaint")
    assert en_conf['complaint_created'] is True
    assert "VX-" in en_conf['complaint_number']
    print(f"    -> English Spoken Confirmation:\n      {en_conf['spoken_reply']}")
    print("  [Result] TEST 3 PASSED! ✅")

    # =========================================================================
    # TEST 4: Whisper Mistakes & Phonetic Correction
    # =========================================================================
    print("\n--- TEST 4: Whisper STT Mistakes & Spelled Letters Normalization ---")
    raw_whisper_1 = "Gandhi puram la tani vara la"
    cleaned_1 = speech_correction_service.clean(raw_whisper_1)
    print(f"  Raw: '{raw_whisper_1}' -> Cleaned: '{cleaned_1}'")
    assert "Gandhipuram-la thanni varala" in cleaned_1

    raw_spelled = "My area is P E E L A M E D U"
    cleaned_spelled = speech_correction_service.clean(raw_spelled)
    print(f"  Raw: '{raw_spelled}' -> Cleaned: '{cleaned_spelled}'")
    assert "Peelamedu" in cleaned_spelled
    print("  [Result] TEST 4 PASSED! ✅")

    # =========================================================================
    # TEST 5: User Interruption & Slot Correction
    # =========================================================================
    print("\n--- TEST 5: Citizen Interruption & Slot Correction ---")
    session5, _, _ = conversation_manager.create_session(db, "+919843055555", "Auto")
    sid5 = session5.session_id
    conversation_manager.process_citizen_turn(db, sid5, "Gandhipuram-la sewage problem")
    conversation_manager.process_citizen_turn(db, sid5, "5th street")
    # Citizen interrupts/corrects street
    corr_turn = conversation_manager.process_citizen_turn(db, sid5, "No, not 5th street, 6th street")
    print(f"  Corrected Street in Memory: {corr_turn['memory'].get('street')}")
    assert "6th" in corr_turn['memory']['street'].lower()
    print("  [Result] TEST 5 PASSED! ✅")

    # =========================================================================
    # TEST 6: DTMF Keypress Fallbacks (1=Repeat, 2=Confirm, 9=End)
    # =========================================================================
    print("\n--- TEST 6: DTMF Keypress Fallback Tests ---")
    session6, _, _ = conversation_manager.create_session(db, "+919843066666", "Tanglish")
    sid6 = session6.session_id
    conversation_manager.process_citizen_turn(db, sid6, "Saravanampatti-la garbage problem")
    
    # DTMF 1: Repeat question
    dtmf1_res = conversation_manager.process_citizen_turn(db, sid6, "1")
    print(f"  DTMF 1 (Repeat): {dtmf1_res['spoken_reply']}")
    assert dtmf1_res['spoken_reply'] != ""

    # DTMF 9: End call
    dtmf9_res = conversation_manager.process_citizen_turn(db, sid6, "9")
    print(f"  DTMF 9 (End Call): state={dtmf9_res['state']}, reply={dtmf9_res['spoken_reply']}")
    assert dtmf9_res['state'] == IVRState.COMPLETED.value
    print("  [Result] TEST 6 PASSED! ✅")

    # =========================================================================
    # TEST 7: Telephony Endpoints via TestClient
    # =========================================================================
    print("\n--- TEST 7: Required IVR Telephony HTTP Endpoints ---")
    # 1. POST /api/v1/ivr/incoming (Rule 1: AI Silent)
    resp_inc = client.post("/api/v1/ivr/incoming", json={"caller_phone": "+919843077777"})
    assert resp_inc.status_code == 200
    inc_data = resp_inc.json()
    print(f"  POST /api/v1/ivr/incoming: state={inc_data.get('state')}, ai_silent={inc_data.get('ai_silent')}")
    assert inc_data.get("state") == "WAITING_FOR_CITIZEN"
    assert inc_data.get("ai_silent") is True
    assert inc_data.get("greeting") == ""

    # 2. POST /api/v1/ivr/status
    resp_stat = client.post("/api/v1/ivr/status", json={"CallSid": inc_data["session_id"], "CallStatus": "in-progress"})
    assert resp_stat.status_code == 200
    print(f"  POST /api/v1/ivr/status: {resp_stat.json()}")

    # 3. POST /api/v1/ivr/session/{id}/message
    resp_msg = client.post(f"/api/v1/ivr/session/{inc_data['session_id']}/message", json={"message": "Singanallur-la street light eriyala"})
    assert resp_msg.status_code == 200
    msg_data = resp_msg.json()
    print(f"  POST /api/v1/ivr/session/{{id}}/message: Category={msg_data['memory'].get('category')}, AI Reply={msg_data.get('ai_reply')}")
    assert "Street Light" in msg_data['memory']['category'] or "Streetlights" in msg_data['memory']['category']

    # 4. GET /api/v1/ivr/session/{id}
    resp_get = client.get(f"/api/v1/ivr/session/{inc_data['session_id']}")
    assert resp_get.status_code == 200
    print("  [Result] TEST 7 PASSED! ✅")

    # =========================================================================
    # TEST 8: WebSocket Telephony Audio Stream Integration
    # =========================================================================
    print("\n--- TEST 8: WebSocket Real-Time Telephony Audio Stream ---")
    with client.websocket_connect("/api/v1/ivr/stream") as ws:
        # Start event
        ws.send_json({
            "event": "start",
            "streamSid": "MZ_test_stream_001",
            "start": {
                "streamSid": "MZ_test_stream_001",
                "customParameters": {
                    "caller_phone": "+919843088888"
                }
            }
        })
        start_resp = ws.receive_json()
        print(f"  WS Event 'start' response: {start_resp}")
        assert start_resp.get("event") == "started"
        ws_sid = start_resp.get("session_id")

        # Send text message over websocket
        ws.send_json({
            "event": "message",
            "message": "Gandhipuram DB Road-la power cut"
        })
        resp1 = ws.receive_json()
        if resp1.get("event") == "media":
            print(f"  WS Audio Media Frame received: streamSid={resp1.get('streamSid')}, payload_len={len(resp1.get('media', {}).get('payload', ''))}")
            turn_resp = ws.receive_json()
        else:
            turn_resp = resp1
        print(f"  WS Event 'message' response: language={turn_resp.get('detected_language')}, AI={turn_resp.get('ai_reply')}")
        assert turn_resp.get("event") == "turn_complete"
        assert turn_resp.get("detected_language") in ["Tanglish", "English", "Tamil"]

        # Send DTMF 1 (Repeat)
        ws.send_json({
            "event": "dtmf",
            "digit": "1"
        })
        d_resp1 = ws.receive_json()
        if d_resp1.get("event") == "media":
            dtmf_resp = ws.receive_json()
        else:
            dtmf_resp = d_resp1
        print(f"  WS Event 'dtmf' response: {dtmf_resp.get('ai_reply')}")
        assert dtmf_resp.get("event") == "dtmf_processed"
    print("  [Result] TEST 8 PASSED! ✅")

    # =========================================================================
    # TEST 9: Audio Converter μ-law <-> PCM Conversion
    # =========================================================================
    print("\n--- TEST 9: Audio Converter μ-law Telephony Streaming Tests ---")
    # 100ms of synthetic 8kHz mu-law audio
    dummy_mulaw = b"\xFF" * 800
    wav_out = audio_converter.mulaw_to_wav_bytes(dummy_mulaw, in_rate=8000, out_rate=16000)
    assert len(wav_out) > 0
    assert wav_out.startswith(b"RIFF")
    
    mulaw_back = audio_converter.pcm_or_wav_to_mulaw(wav_out, in_rate=16000, out_rate=8000)
    assert len(mulaw_back) > 0
    print(f"  mu-law ({len(dummy_mulaw)} bytes) -> WAV ({len(wav_out)} bytes) -> mu-law ({len(mulaw_back)} bytes)")
    print("  [Result] TEST 9 PASSED! ✅")

    print("\n" + "=" * 75)
    print("ALL 9 COMPREHENSIVE ACCEPTANCE SCENARIOS PASSED WITH ZERO FAILURES! 🚀")
    print("=" * 75)


if __name__ == "__main__":
    run_comprehensive_acceptance_suite()
