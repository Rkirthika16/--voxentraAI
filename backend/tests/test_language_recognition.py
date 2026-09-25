import pytest
from app.ai.language_service import detect_language


def test_tamil_script_detection():
    text = "எங்கள் தெருவில் குப்பை எடுக்கவில்லை"
    lang, conf = detect_language(text)
    assert lang == "Tamil"
    assert conf >= 0.9


def test_tanglish_detection_various_phrases():
    # Tanglish with English loan words and Tamil verb/grammar suffixes
    for phrase in [
        "Street light work aagala",
        "Enga street la garbage full-ah iruku",
        "Water supply 3 days-ah varala",
        "Ennoda area la drainage overflow aagudhu",
        "Two days-ah",
        "Kuppai romba naala iruku"
    ]:
        lang, conf = detect_language(phrase)
        assert lang == "Tanglish", f"Failed for phrase: {phrase}, got: {lang}"
        assert conf >= 0.8


def test_english_detection_with_indian_locations():
    for phrase in [
        "There is a water supply issue in Gandhipuram",
        "The street lights on the main road are not functioning properly",
        "Garbage collection is delayed in our neighborhood"
    ]:
        lang, conf = detect_language(phrase)
        assert lang == "English", f"Failed for phrase: {phrase}, got: {lang}"
        assert conf >= 0.8


def test_session_stickiness_for_short_slot_answers():
    # In an ongoing Tanglish session, short answers stay Tanglish
    lang, conf = detect_language("Two days", current_session_lang="Tanglish")
    assert lang == "Tanglish"
    assert conf >= 0.8

    lang, conf = detect_language("RS Puram", current_session_lang="Tanglish")
    assert lang == "Tanglish"
    assert conf >= 0.8

    lang, conf = detect_language("Near bus stop", current_session_lang="Tanglish")
    assert lang == "Tanglish"
    assert conf >= 0.8

    # In an ongoing Tamil session, short answers stay Tamil
    lang, conf = detect_language("2 days", current_session_lang="Tamil")
    assert lang == "Tamil"
    assert conf >= 0.8

    # Without session, short English answers default cleanly
    lang, conf = detect_language("Two days")
    assert lang == "English"

