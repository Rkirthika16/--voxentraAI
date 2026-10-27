"""Comprehensive test suite verifying Intelligent Multilingual Location Detection,
Speech Correction, 7 Pipeline Fields, Confidence Tiers, and Citizen Corrections.
"""
import sys
from pathlib import Path
import pytest

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.location_resolver import location_resolver
from app.services.conversation_manager import ConversationManager
from app.database.session import SessionLocal
from app.models.complaint import Complaint
from app.models.ivr import IVRSession


def test_1_pure_tamil_detection():
    """Test 1: Pure Tamil ('வடவள்ளில தண்ணி வரல') -> Vadavalli + Water problem."""
    res = location_resolver.resolve("வடவள்ளில தண்ணி வரல", current_language="Tamil")
    assert res["area"] == "Vadavalli"
    assert res["ward_no"] == 85
    assert res["corporation_zone"] == "West Zone"
    assert res["confidence_score"] >= 0.85
    assert res["detected_language"] == "Tamil"
    assert res["confirmed_location"] is not None
    assert "Vadavalli" in res["confirmed_location"]
    # Check 7 pipeline fields presence
    for field in [
        "original_transcript", "normalized_transcript", "corrected_transcript",
        "detected_language", "candidate_locations", "confidence_score", "confirmed_location"
    ]:
        assert field in res, f"Missing pipeline field: {field}"


def test_2_tanglish_detection():
    """Test 2: Tanglish ('Vadavalli la thanni varala') -> Vadavalli + Water."""
    res = location_resolver.resolve("Vadavalli la thanni varala", current_language="Tanglish")
    assert res["area"] == "Vadavalli"
    assert res["ward_no"] == 85
    assert res["confidence_score"] >= 0.85
    assert res["detected_language"] == "Tanglish"
    assert res["confirmed_location"] is not None


def test_3_whisper_spacing_error():
    """Test 3: Whisper error / spacing ('Vada valli water problem') -> Vadavalli."""
    res = location_resolver.resolve("Vada valli water problem", current_language="English")
    assert res["area"] == "Vadavalli"
    assert res["confidence_score"] >= 0.85
    assert res["confirmed_location"] is not None


def test_4_phonetic_mispronunciation():
    """Test 4: Phonetic mispronunciation ('Coimbatore vadaveli') -> Vadavalli."""
    res = location_resolver.resolve("Coimbatore vadaveli", current_language="Tanglish")
    assert res["area"] == "Vadavalli"
    assert res["ward_no"] == 85
    assert res["confidence_score"] >= 0.85


def test_5_ordinal_street_extraction():
    """Test 5: Ordinal street extraction across English, Tanglish, and Tamil."""
    # English ordinal
    res_en = location_resolver.resolve("Anna nagar second street Vadavalli", current_language="English")
    assert res_en["street"] == "Anna Nagar 2nd Street"
    assert res_en["area"] == "Vadavalli"

    # Tanglish ordinal word ('rendu')
    res_tg = location_resolver.resolve("Anna nagar rendu street Vadavalli", current_language="Tanglish")
    assert res_tg["street"] == "Anna Nagar 2nd Street"
    assert res_tg["area"] == "Vadavalli"

    # Tamil ordinal script
    res_ta = location_resolver.resolve("அண்ணா நகர் 2வது தெரு வடவள்ளி", current_language="Tamil")
    assert res_ta["street"] == "Anna Nagar 2nd Street"
    assert res_ta["area"] == "Vadavalli"


def test_6_landmark_clue_resolution():
    """Test 6: Landmark clue ('Government school pakkathula') -> Landmark + Vadavalli."""
    res = location_resolver.resolve("Government school pakkathula", current_language="Tanglish")
    assert res["landmark"] == "Government Higher Secondary School Vadavalli"
    assert res["area"] == "Vadavalli"
    assert res["ward_no"] == 85
    assert res["corporation_zone"] == "West Zone"
    assert res["confidence_score"] >= 0.85


def test_7_ambiguous_street_medium_confidence():
    """Test 7: Ambiguous street / Medium confidence -> candidate ranking & disambiguation prompt."""
    res = location_resolver.resolve("Anna Nagar", current_language="Tanglish")
    assert 0.60 <= res["confidence_score"] < 0.85
    assert res["needs_clarification"] is True
    assert res["needs_confirmation"] is False
    assert len(res["candidate_locations"]) >= 2
    # Verify ranked candidates include both Vadavalli and Town Hall
    candidate_labels = [c["label"] for c in res["candidate_locations"]]
    assert any("Vadavalli" in lbl for lbl in candidate_labels)
    assert any("Town Hall" in lbl for lbl in candidate_labels)
    # Verify clarification prompt offers options
    assert "solreengala" in res["clarification_question"] or "or" in res["clarification_question"]


def test_8_citizen_correction():
    """Test 8: Citizen correction ('Illa, Coimbatore town Anna Nagar') -> switches to Town Hall."""
    res = location_resolver.resolve("Illa, Coimbatore town Anna Nagar", current_language="Tanglish")
    assert res["is_citizen_correction"] is True
    assert res["area"] == "Town Hall"
    assert res["street"] == "Anna Nagar Main Street"
    assert res["confidence_score"] >= 0.85
    assert "Purinjikiten" in res["clarification_question"] or "update" in res["clarification_question"].lower()


def test_9_low_confidence_unresolved():
    """Test 9: Low confidence ('Near the tea shop') -> asks for landmark, preserves unresolved."""
    res = location_resolver.resolve("Near the tea shop", current_language="English")
    assert res["confidence_score"] < 0.60
    assert res["needs_clarification"] is True
    assert res["confirmed_location"] is None
    assert res["unresolved_location"] == "Near the tea shop"
    assert "landmark" in res["clarification_question"].lower() or "area" in res["clarification_question"].lower()


def test_10_database_persistence_of_7_fields():
    """Test 10: Full conversation manager turn and DB persistence with all 7 pipeline fields."""
    db = SessionLocal()
    cm = ConversationManager()
    try:
        session, _, _ = cm.create_session(db=db, caller_phone="+919876543210", language_preference="Tanglish")
        turn_res = cm.process_citizen_turn(
            db=db,
            session_id=session.session_id,
            speech_text="Vadavalli la Anna nagar second street la water supply illa rendu naala"
        )
        assert turn_res["success"] is True
        mem = turn_res["memory"]

        # Verify 7 pipeline fields in conversation memory
        assert mem.get("original_transcript") is not None
        assert mem.get("normalized_transcript") is not None
        assert mem.get("corrected_transcript") is not None
        assert mem.get("detected_language") in ["Tanglish", "Tamil", "English"]
        assert isinstance(mem.get("candidate_locations"), list)
        assert mem.get("confidence_score") is not None
        assert mem.get("area") == "Vadavalli"
        assert mem.get("street") == "Anna Nagar 2nd Street"

        # Finalize complaint registration
        complaint_res = cm.finalize_and_register_complaint(db, session)
        assert complaint_res["success"] is True
        assert complaint_res["complaint_created"] is True

        # Query complaint from DB
        complaint = db.query(Complaint).filter_by(id=complaint_res["complaint_id"]).first()
        assert complaint is not None
        assert "Vadavalli" in complaint.location
        assert "Anna Nagar 2nd Street" in complaint.location
        assert complaint.ai_metadata is not None
        assert "confidence_score" in complaint.ai_metadata
        assert "candidate_locations" in complaint.ai_metadata
        assert "original_transcript" in complaint.ai_metadata
        print("\nTest 10 Passed: Complaint created with full AI location intelligence metadata!")
    finally:
        db.close()
