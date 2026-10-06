"""Automated tests for Language Detection & Dynamic Switching in VoxentraAI Conversational IVR."""
import pytest
from app.services.language_detector import language_detector, detect_language
from app.ai.language_service import detect_language as ai_detect_language

def test_tamil_detection():
    # Pure Tamil script sentences
    lang1, conf1 = language_detector.detect("எங்க தெருவில் தண்ணீர் வரவில்லை.")
    assert lang1 == "Tamil"
    assert conf1 >= 0.95

    lang2, conf2 = language_detector.detect("தெரு விளக்கு எரியவில்லை, இருட்டாக உள்ளது")
    assert lang2 == "Tamil"
    assert conf2 >= 0.95

    lang3, conf3 = language_detector.detect("குப்பையை அள்ள வேண்டும்")
    assert lang3 == "Tamil"
    assert conf3 >= 0.95


def test_english_detection():
    # Pure English sentences
    lang1, conf1 = language_detector.detect("There is no water supply in my street.")
    assert lang1 == "English"
    assert conf1 >= 0.90

    lang2, conf2 = language_detector.detect("The streetlight is broken and not working since two days.")
    assert lang2 == "English"
    assert conf2 >= 0.90

    lang3, conf3 = language_detector.detect("Severe road damage and deep potholes on cross cut road.")
    assert lang3 == "English"
    assert conf3 >= 0.90


def test_tanglish_detection():
    # Tanglish (Tamil in Latin/Roman script with particles & suffixes)
    lang1, conf1 = language_detector.detect("Gandhipuram-la thanni varala.")
    assert lang1 == "Tanglish"
    assert conf1 >= 0.90

    lang2, conf2 = language_detector.detect("Peelamedu area-la current cut aaiduchu.")
    assert lang2 == "Tanglish"
    assert conf2 >= 0.90

    lang3, conf3 = language_detector.detect("RS Puram DB Road pakkathula garbage overflow aagudhu.")
    assert lang3 == "Tanglish"
    assert conf3 >= 0.90

    lang4, conf4 = language_detector.detect("5th street full-ah rendu naala water varala.")
    assert lang4 == "Tanglish"
    assert conf4 >= 0.90


def test_mid_conversation_language_switching():
    # Tamil -> English switch
    switched, new_lang = language_detector.should_switch_language(
        "Could you please speak in English?", current_lang="Tamil"
    )
    assert switched is True
    assert new_lang == "English"

    # English -> Tamil switch
    switched, new_lang = language_detector.should_switch_language(
        "தெருவில் உள்ள மின் கம்பத்தில் தீப்பொறி பறக்கிறது", current_lang="English"
    )
    assert switched is True
    assert new_lang == "Tamil"

    # Tanglish -> Tamil switch
    switched, new_lang = language_detector.should_switch_language(
        "காந்திபுரத்தில் தண்ணீர் வரவில்லை", current_lang="Tanglish"
    )
    assert switched is True
    assert new_lang == "Tamil"

    # Tamil -> Tanglish switch
    switched, new_lang = language_detector.should_switch_language(
        "Gandhipuram bus stand pakkathula irukken", current_lang="Tamil"
    )
    assert switched is True
    assert new_lang == "Tanglish"


def test_short_response_session_stickiness():
    # Short slot answers like numbers or landmarks should retain ongoing session language
    lang1, _ = language_detector.detect("5th street", current_session_lang="Tamil")
    assert lang1 == "Tamil"

    lang2, _ = language_detector.detect("Two days", current_session_lang="Tanglish")
    assert lang2 == "Tanglish"

    lang3, _ = language_detector.detect("Aama", current_session_lang="Tanglish")
    assert lang3 == "Tanglish"

    lang4, _ = language_detector.detect("சரி", current_session_lang="Tamil")
    assert lang4 == "Tamil"
