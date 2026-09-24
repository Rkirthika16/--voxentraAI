import pytest
from fastapi.testclient import TestClient
from app.ai.normalization_service import clean_transcription, normalize_text
from app.ai.location_service import extract_location, is_valid_tamil_nadu_location, find_fuzzy_location_candidate
from app.ai.conversation_service import conversation_service


def test_clean_transcription_and_normalization():
    # 1. Speech-to-text acoustic misrecognitions cleaned
    cleaned1 = clean_transcription("Severe water leak on cross cutting near bus stand")
    assert "Cross Cut Road" in cleaned1

    cleaned2 = clean_transcription("Streetlight broken on 100 feet road")
    assert "100 Feet Road" in cleaned2

    # 2. Tanglish variations normalized
    norm1 = normalize_text("Gandhipuram-la thanni varla romba problem")
    assert "thanni" in norm1
    assert "varala" in norm1


def test_location_prefix_stripping_and_clean_extraction():
    # 1. "இந்த காந்திபுரம்ல தண்ணி வரல" -> Extracts Gandhipuram, NOT "இந்த"
    loc1, lat1, lon1, conf1 = extract_location("இந்த காந்திபுரம்ல தண்ணி வரல")
    assert loc1 is not None
    assert "Gandhipuram" in loc1
    assert "இந்த" not in loc1

    # 2. "In the Gandhipuram water pipeline broken" -> Extracts Gandhipuram, NOT "in the"
    loc2, lat2, lon2, conf2 = extract_location("In the Gandhipuram water pipeline broken")
    assert loc2 is not None
    assert "Gandhipuram" in loc2
    assert "in the" not in loc2.lower()

    # 3. "cross cut road" or "cross cutting" mapped to Gandhipuram
    loc3, lat3, lon3, conf3 = extract_location("cross cut road thanni leak")
    assert loc3 is not None
    assert "Gandhipuram" in loc3

    loc4, lat4, lon4, conf4 = extract_location("cross cutting la drainage overflow")
    assert loc4 is not None
    assert "Gandhipuram" in loc4


def test_generic_phrase_not_captured_as_location():
    # "in the street thanni varala" should NOT capture "in the street" or "the street" or "in the"
    loc, lat, lon, conf = extract_location("in the street thanni varala")
    assert loc is None or loc == "Tamil Nadu" or "the street" not in loc.lower()


def test_location_validation_and_fuzzy_match():
    # Valid location
    is_valid, loc_obj, conf = is_valid_tamil_nadu_location("Gandhipuram")
    assert is_valid is True
    assert loc_obj["district"] == "Coimbatore"

    is_valid2, _, _ = is_valid_tamil_nadu_location("Madurai Central")
    assert is_valid2 is True

    # Invalid / garbage location
    is_invalid, _, _ = is_valid_tamil_nadu_location("RandomUnknownPlaceXYZ")
    assert is_invalid is False

    # Fuzzy candidate detection
    fuzzy = find_fuzzy_location_candidate("Kandhipuram")
    assert fuzzy is not None
    assert "Gandhipuram" in fuzzy[0]


def test_voice_assistant_turn_with_inda_gandhipuram(client: TestClient):
    # Citizen says "இந்த காந்திபுரம்ல தண்ணி வரல"
    res = client.post(
        "/api/v1/voice/session/sess_test_inda_gp/message",
        json={"message": "இந்த காந்திபுரம்ல தண்ணி வரல"}
    )
    assert res.status_code == 200
    data = res.json()
    # Should extract Gandhipuram as location, NOT 'இந்த' or 'in the'
    assert "Gandhipuram" in data["context"]["location"]
    assert "இந்த" not in data["context"]["location"]


def test_voice_assistant_turn_with_cross_cutting(client: TestClient):
    # Citizen says "cross cutting-la drainage overflow aagudhu"
    res = client.post(
        "/api/v1/voice/session/sess_test_crosscut/message",
        json={"message": "cross cutting-la drainage overflow aagudhu"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "Gandhipuram" in data["context"]["location"] or "Cross Cut" in data["context"]["location"]
