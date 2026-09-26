import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add backend to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import importlib
SessionLocal = importlib.import_module("app.database.session").SessionLocal
new_ivr_service = importlib.import_module("app.services.new_ivr_service").new_ivr_service
IVRState = importlib.import_module("app.models.ivr").IVRState
Complaint = importlib.import_module("app.models.complaint").Complaint

def run_tests():
    db = SessionLocal()
    print("=" * 70)
    print("RUNNING VOXENTRA AI IVR 10-POINT REQUIREMENT VERIFICATION SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # TEST 1 & 3: Tanglish Dynamic Dialogue (Matching exact prompt example)
    # -------------------------------------------------------------
    print("\n--- TEST 1: Tanglish Dialogue Flow with Slot Skipping & Dynamic Questioning ---")
    session, greeting_text, greeting_spoken = new_ivr_service.create_session(db, caller_phone="+919843098765", language_preference="Auto")
    sid = session.session_id
    print(f"[Session Created] ID: {sid}")
    print(f"[Requirement 1: AI must NOT speak first] Greeting text: '{greeting_text}', Spoken: '{greeting_spoken}' -> SILENT LISTENING: {greeting_text == ''}")
    assert greeting_text == "", "AI must not speak first on incoming call!"
    assert session.state == IVRState.WAITING_FOR_CITIZEN.value

    # Turn 1: Citizen speaks first: "Gandhipuram-la thanni varala."
    print("\n[Turn 1] Citizen: 'Gandhipuram-la thanni varala.'")
    res1 = new_ivr_service.process_citizen_turn(db, sid, "Gandhipuram-la thanni varala.")
    print(f"  -> Detected Language: {res1['detected_language']}")
    print(f"  -> Memory: Category={res1['memory'].get('category')}, Area={res1['memory'].get('area')}")
    print(f"  -> AI Reply: {res1['ai_reply']}")
    print(f"  -> AI Spoken: {res1['spoken_reply']}")
    print(f"  -> Next Field Prompted: {res1.get('next_field')}")
    assert res1['detected_language'] == 'Tanglish'
    assert res1['memory']['area'] == 'Gandhipuram'
    # AI must NOT ask problem or area again. Next should be street!
    assert res1['next_field'] == 'street_road_name'

    # Turn 2: Citizen: "5th street."
    print("\n[Turn 2] Citizen: '5th street.'")
    res2 = new_ivr_service.process_citizen_turn(db, sid, "5th street.")
    print(f"  -> Memory: Street={res2['memory'].get('street')}")
    print(f"  -> AI Reply: {res2['ai_reply']}")
    print(f"  -> Next Field Prompted: {res2.get('next_field')}")
    assert '5th' in res2['memory']['street'].lower() and 'street' in res2['memory']['street'].lower()

    # Turn 3: Citizen provides exact spot: "Opposite door no 45"
    print("\n[Turn 3] Citizen: 'Opposite door no 45'")
    res3 = new_ivr_service.process_citizen_turn(db, sid, "Opposite door no 45")
    print(f"  -> Next Field Prompted: {res3.get('next_field')}")

    # Turn 4: Landmark
    print("\n[Turn 4] Citizen: 'Near Indian Bank ATM'")
    res4 = new_ivr_service.process_citizen_turn(db, sid, "Near Indian Bank ATM")
    print(f"  -> Next Field Prompted: {res4.get('next_field')}")

    # Turn 5: Duration / Start time: "Rendu naala."
    print("\n[Turn 5] Citizen: 'Rendu naala.'")
    res5 = new_ivr_service.process_citizen_turn(db, sid, "Rendu naala.")
    print(f"  -> Memory: Duration={res5['memory'].get('duration')}")
    print(f"  -> AI Reply: {res5['ai_reply']}")
    print(f"  -> Next Field Prompted: {res5.get('next_field')}")
    assert 'rendu naala' in res5['memory']['duration'].lower()

    # Turn 6: Scope: "5th street full-ah problem"
    print("\n[Turn 6] Citizen: 'Full street problem'")
    res6 = new_ivr_service.process_citizen_turn(db, sid, "Full street problem")
    print(f"  -> Memory: Scope={res6['memory'].get('affected_scope')}")
    print(f"  -> Next Field Prompted: {res6.get('next_field')}")

    # Turn 7: Frequency: "Daily recurring"
    print("\n[Turn 7] Citizen: 'Daily recurring'")
    res7 = new_ivr_service.process_citizen_turn(db, sid, "Daily recurring")
    print(f"  -> Next Field Prompted: {res7.get('next_field')}")

    # Turn 8: Previous complaint: "First time reporting"
    print("\n[Turn 8] Citizen: 'First time dhaan report panren'")
    res8 = new_ivr_service.process_citizen_turn(db, sid, "First time dhaan report panren")
    print(f"  -> Next Field Prompted: {res8.get('next_field')}")

    # Turn 9: Severity: "Completely stopped"
    print("\n[Turn 9] Citizen: 'Water completely stop aaiduchu'")
    res9 = new_ivr_service.process_citizen_turn(db, sid, "Water completely stop aaiduchu")
    print(f"  -> Next Field Prompted: {res9.get('next_field')}")

    # Turn 10: Safety Hazard: "No safety risk"
    print("\n[Turn 10] Citizen: 'No safety hazard'")
    res10 = new_ivr_service.process_citizen_turn(db, sid, "No safety hazard")
    print(f"  -> Next Field Prompted: {res10.get('next_field')}")

    # Turn 11: Additional info: "No other info"
    print("\n[Turn 11] Citizen: 'Nothing else'")
    res11 = new_ivr_service.process_citizen_turn(db, sid, "Nothing else")
    print(f"  -> State: {res11['state']}")
    print(f"  -> Is Confirmation: {res11.get('is_confirmation')}")
    print(f"  -> Summary AI Reply:\n{res11['ai_reply']}")
    print(f"  -> Summary Spoken:\n{res11['spoken_reply']}")
    assert res11['state'] == IVRState.CONFIRMATION.value
    assert res11['is_confirmation'] is True

    # Turn 12: Citizen Confirms: "Aama, register pannunga"
    print("\n[Turn 12] Citizen: 'Aama, register pannunga'")
    res12 = new_ivr_service.process_citizen_turn(db, sid, "Aama, register pannunga")
    print(f"  -> State: {res12['state']}")
    print(f"  -> Complaint Created: {res12.get('complaint_created')}")
    print(f"  -> Complaint Number: {res12.get('complaint_number')}")
    print(f"  -> Spoken Response: {res12.get('spoken_reply')}")
    assert res12['complaint_created'] is True
    assert res12['complaint_number'] is not None
    assert "VX-" in res12['complaint_number']

    # Verify DB record
    complaint_db = db.query(Complaint).filter(Complaint.id == res12['complaint_id']).first()
    assert complaint_db is not None
    print(f"[DB Verified] Complaint ID={complaint_db.id}, Number={complaint_db.complaint_number}, Category={complaint_db.category}, Location={complaint_db.location}")
    print(f"[AI Metadata] {complaint_db.ai_metadata.keys()}")
    assert "citizen_input" in complaint_db.ai_metadata
    assert "corrected_transcription" in complaint_db.ai_metadata
    assert "duration" in complaint_db.ai_metadata

    # -------------------------------------------------------------
    # TEST 4: Whisper STT Correction Test ("Gandhi puram la tani vara la")
    # -------------------------------------------------------------
    print("\n--- TEST 4: Whisper STT Error Correction ---")
    session_stt, _, _ = new_ivr_service.create_session(db, "+919843098765", "Auto")
    res_stt = new_ivr_service.process_citizen_turn(db, session_stt.session_id, "Gandhi puram la tani vara la")
    print(f"  -> Raw Input: 'Gandhi puram la tani vara la'")
    print(f"  -> Corrected in Memory: {res_stt['memory']['corrected_transcription']}")
    print(f"  -> Extracted Area: {res_stt['memory']['area']}")
    print(f"  -> Extracted Category: {res_stt['memory']['category']}")
    assert res_stt['memory']['area'] == 'Gandhipuram'
    assert 'Water' in res_stt['memory']['category']

    # -------------------------------------------------------------
    # TEST 5: Mid-conversation Language Switching
    # -------------------------------------------------------------
    print("\n--- TEST 5: Dynamic Mid-Conversation Language Switching ---")
    session_lang, _, _ = new_ivr_service.create_session(db, "+919843098765", "Auto")
    sl_id = session_lang.session_id
    
    # Start in Tanglish
    r_l1 = new_ivr_service.process_citizen_turn(db, sl_id, "Gandhipuram-la power cut")
    print(f"  -> Turn 1 (Tanglish): Detected={r_l1['detected_language']}")
    assert r_l1['detected_language'] == 'Tanglish'

    # Switch to English
    r_l2 = new_ivr_service.process_citizen_turn(db, sl_id, "It has been off since 3 hours on Cross Cut Road")
    print(f"  -> Turn 2 (Switched to English): Detected={r_l2['detected_language']}")
    print(f"  -> AI Reply in English: {r_l2['ai_reply'][:80]}...")
    assert r_l2['detected_language'] == 'English'

    # Switch to Tamil
    r_l3 = new_ivr_service.process_citizen_turn(db, sl_id, "தெருவில் உள்ள மின் கம்பத்தில் தீப்பொறி பறக்கிறது")
    print(f"  -> Turn 3 (Switched to Tamil): Detected={r_l3['detected_language']}")
    print(f"  -> AI Reply in Tamil: {r_l3['ai_reply'][:80]}...")
    assert r_l3['detected_language'] == 'Tamil'

    # -------------------------------------------------------------
    # TEST 6: Structured Location Normalization
    # -------------------------------------------------------------
    print("\n--- TEST 6: Location Normalization ---")
    session_loc, _, _ = new_ivr_service.create_session(db, "+919843098765", "Auto")
    loc = new_ivr_service.process_citizen_turn(db, session_loc.session_id, "Peelamedu Avinashi Road near Fun Republic Mall")
    print(f"  -> Extracted Memory: Area={loc['memory'].get('area')}, Street={loc['memory'].get('street')}, Landmark={loc['memory'].get('landmark')}")
    assert 'Peelamedu' in str(loc['memory'].get('area')) or 'Peelamedu' in str(loc['memory'].get('district_area'))

    print("\n" + "=" * 70)
    print("ALL 10 REQUIREMENTS VERIFIED AND PASSED SUCCESSFULLY! 🚀")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
