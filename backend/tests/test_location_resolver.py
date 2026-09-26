"""Automated test suite verifying the 18 specific test scenarios for Coimbatore Location Intelligence."""
import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.location_resolver import location_resolver
from app.services.location_normalizer import LocationNormalizer

def test_1_gandhipuram_tanglish_speech():
    """Test 1: 'Gandhipuram-la thanni varala'"""
    res = location_resolver.resolve("Gandhipuram-la thanni varala", current_language="Tanglish")
    assert res["area"] == "Gandhipuram"
    assert "Central" in res["corporation_zone"]
    assert res["ward_no"] == 45
    assert res["confidence"] >= 0.85
    print("Test 1 Passed: Gandhipuram Tanglish speech resolved to Central Zone, Ward 45")

def test_2_gandhipuram_5th_street():
    """Test 2: 'Gandhipuram 5th street'"""
    res = location_resolver.resolve("Gandhipuram 5th street", current_language="Tanglish")
    assert res["area"] == "Gandhipuram"
    assert "5th" in res["street"]
    assert res["confidence"] >= 0.85
    print("Test 2 Passed: Gandhipuram 5th street resolved.")

def test_3_rs_puram_db_road():
    """Test 3: 'RS Puram DB Road'"""
    res = location_resolver.resolve("RS Puram DB Road", current_language="English")
    assert "RS Puram" in res["area"] or "R.S. Puram" in res["area"]
    assert "DB Road" in res["street"] or "Diwan Bahadur" in res["street"] or "D.B. Road" in res["street"]
    assert "West" in res["corporation_zone"]
    assert res["ward_no"] == 92
    assert res["confidence"] >= 0.85
    print("Test 3 Passed: RS Puram DB Road resolved to West Zone, Ward 92.")

def test_4_saravanampatti_bus_stand():
    """Test 4: 'Saravanampatti bus stand pakkathula'"""
    res = location_resolver.resolve("Saravanampatti bus stand pakkathula", current_language="Tanglish")
    assert res["area"] == "Saravanampatti"
    assert "Saravanampatti Bus Stand" in res["landmark"]
    assert "North" in res["corporation_zone"]
    assert res["ward_no"] == 2
    assert res["confidence"] >= 0.85
    print("Test 4 Passed: Saravanampatti Bus Stand resolved.")

def test_5_tamil_script_resolution():
    """Test 5: 'காந்திபுரத்தில் தண்ணீர் வரவில்லை'"""
    res = location_resolver.resolve("காந்திபுரத்தில் தண்ணீர் வரவில்லை", current_language="Tamil")
    assert res["area"] == "Gandhipuram"
    assert res["confidence"] >= 0.85
    print("Test 5 Passed: Pure Tamil script locative resolved.")

def test_6_coimbatore_north_area():
    """Test 6: 'Coimbatore north area'"""
    res = location_resolver.resolve("Coimbatore north area", current_language="English")
    assert res["taluk"] == "Coimbatore North" or res["corporation_zone"] == "North"
    assert res["confidence"] >= 0.80
    print("Test 6 Passed: Coimbatore North area resolved.")

def test_7_marudamalai_road():
    """Test 7: 'Marudamalai road pakkathula'"""
    res = location_resolver.resolve("Marudamalai road pakkathula", current_language="Tanglish")
    assert "Marudamalai Road" in res["street"]
    assert res["confidence"] >= 0.80
    print("Test 7 Passed: Marudamalai road resolved.")

def test_8_only_landmark_provided():
    """Test 8: Citizen provides only landmark: 'Gandhipuram Central Bus Stand'"""
    res = location_resolver.resolve("Gandhipuram Central Bus Stand", current_language="English")
    assert "Gandhipuram" in res["landmark"]
    assert res["area"] == "Gandhipuram"
    assert res["ward_no"] == 45
    assert res["confidence"] >= 0.85
    print("Test 8 Passed: Area inferred from landmark proximity.")

def test_9_only_street_provided():
    """Test 9: Citizen provides only street: 'Cross Cut Road'"""
    res = location_resolver.resolve("Cross Cut Road", current_language="English")
    assert "Cross Cut Road" in res["street"]
    assert res["area"] == "Gandhipuram"
    assert res["confidence"] >= 0.85
    print("Test 9 Passed: Area inferred from street database mapping.")

def test_10_tanglish_phonetic_variations():
    """Test 10: 'kaandhipuram 5th theru'"""
    res = location_resolver.resolve("kaandhipuram 5th theru", current_language="Tanglish")
    assert res["area"] == "Gandhipuram"
    assert "5th" in res["street"]
    assert res["confidence"] >= 0.85
    print("Test 10 Passed: Phonetic Tanglish resolved.")

def test_11_tamil_to_english_switch():
    """Test 11: Switch Tamil -> English: 'Water issue at Cross Cut Road'"""
    res = location_resolver.resolve("Water issue at Cross Cut Road", current_language="English")
    assert "Cross Cut Road" in res["street"]
    assert res["area"] == "Gandhipuram"
    print("Test 11 Passed: Language switch resolved.")

def test_12_english_to_tanglish_switch():
    """Test 12: Switch English -> Tanglish: '5th street-la problem'"""
    res = location_resolver.resolve("5th street-la problem", current_language="Tanglish")
    assert "5th Street" in res["street"]
    print("Test 12 Passed: English to Tanglish switch resolved.")

def test_13_same_name_disambiguation():
    """Test 13: Contextual clarification when street is isolated"""
    res = location_resolver.resolve("5th street", current_language="Tanglish")
    assert res["street"] == "5th Street"
    # When area is unknown, resolver prompts for area/landmark
    assert res["needs_confirmation"] is True or res["needs_clarification"] is True
    print("Test 13 Passed: Ambiguous/isolated street flags clarification.")

def test_14_outside_corporation_boundary():
    """Test 14: Rural/Outside corporation boundaries: 'Siruvani Main Road'"""
    res = location_resolver.resolve("Siruvani Main Road", current_language="English")
    assert "Siruvani Main Road" in res["street"]
    # Rural addresses must have corporation_zone=None and ward_no=None
    assert res["corporation_zone"] is None
    assert res["ward_no"] is None
    print("Test 14 Passed: Outside corporation boundary preserves rural structure without forcing Ward.")

def test_15_unknown_street():
    """Test 15: Citizen provides unknown street"""
    res = location_resolver.resolve("Unregistered Fake Random Lane 999", current_language="English")
    assert res["confidence"] < 0.70
    assert res["needs_clarification"] is True
    assert res["clarification_question"] is not None
    print("Test 15 Passed: Unknown street prompts clarification without guessing.")

def test_16_unknown_landmark():
    """Test 16: Unknown landmark triggers landmark question"""
    res = location_resolver.resolve("Near Nonexistent Complex XYZ", current_language="Tanglish")
    assert res["confidence"] < 0.70
    assert res["needs_clarification"] is True
    print("Test 16 Passed: Unknown landmark handled gracefully.")

def test_17_whisper_transcription_error():
    """Test 17: Whisper transcription error: 'gandhi puram la tani vara la'"""
    res = location_resolver.resolve("gandhi puram la tani vara la", current_language="Tanglish")
    assert res["area"] == "Gandhipuram"
    assert "Central" in res["corporation_zone"]
    assert res["confidence"] >= 0.85
    print("Test 17 Passed: Whisper spacing and phonetic mishearings resolved.")

def test_18_multilingual_clarification_prompts():
    """Test 18: Generates clarification questions in requested citizen language"""
    res_ta = location_resolver.resolve("", current_language="Tamil")
    assert "கோவையில்" in res_ta["clarification_question"]

    res_en = location_resolver.resolve("", current_language="English")
    assert "Coimbatore" in res_en["clarification_question"]

    res_tg = location_resolver.resolve("", current_language="Tanglish")
    assert "Coimbatore-la" in res_tg["clarification_question"]
    print("Test 18 Passed: Dynamic multi-lingual clarification prompts verified.")

if __name__ == "__main__":
    test_1_gandhipuram_tanglish_speech()
    test_2_gandhipuram_5th_street()
    test_3_rs_puram_db_road()
    test_4_saravanampatti_bus_stand()
    test_5_tamil_script_resolution()
    test_6_coimbatore_north_area()
    test_7_marudamalai_road()
    test_8_only_landmark_provided()
    test_9_only_street_provided()
    test_10_tanglish_phonetic_variations()
    test_11_tamil_to_english_switch()
    test_12_english_to_tanglish_switch()
    test_13_same_name_disambiguation()
    test_14_outside_corporation_boundary()
    test_15_unknown_street()
    test_16_unknown_landmark()
    test_17_whisper_transcription_error()
    test_18_multilingual_clarification_prompts()
    print("\n--- ALL 18 COIMBATORE LOCATION INTELLIGENCE TEST CASES PASSED SUCCESSFULLY! ---")
