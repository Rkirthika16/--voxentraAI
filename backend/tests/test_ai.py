from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text
from app.ai.classification_service import classify_complaint
from app.ai.location_service import extract_location
from app.ai.priority_service import assess_priority
from app.ai.provider import ai_provider


def test_language_detection():
    # Tamil script
    lang, _ = detect_language("காந்திபுரம் அருகில் குடிநீர் குழாய் உடைப்பு")
    assert lang == "Tamil"

    # Tanglish
    lang, _ = detect_language("Gandhipuram-la thanni pipe odanju pochu romba mosam")
    assert lang == "Tanglish"

    # English
    lang, _ = detect_language("Major road pothole in RS Puram causing traffic congestion")
    assert lang == "English"


def test_text_normalization():
    raw = "  Thani pipe   odanju  kuppe alli podala  "
    normalized = normalize_text(raw)
    assert "thanni" in normalized
    assert "kuppai" in normalized
    assert "  " not in normalized


def test_category_classification():
    # Water
    cat, dept, _ = classify_complaint("thanni pipe leak aaguthu kudikka thanni varala")
    assert cat == "Water"
    assert "Water" in dept

    # Roads
    cat, dept, _ = classify_complaint("road la periya pallam irukku accident aaguthu")
    assert cat == "Roads"

    # Streetlights
    cat, dept, _ = classify_complaint("street light eriyala romba irutta irukku")
    assert cat == "Streetlights"

    # Sanitation
    cat, dept, _ = classify_complaint("kuppai thotti romba naaththam adikuthu")
    assert cat == "Sanitation/Garbage"

    # Electricity
    cat, dept, _ = classify_complaint("live wire arunthu vizhunthuduchu current cut")
    assert cat == "Electricity"


def test_location_extraction():
    loc, lat, lon, _ = extract_location("There is a water leak near Gandhipuram Central Bus Stand")
    assert loc is not None
    assert "Gandhipuram" in loc
    assert lat is not None
    assert lon is not None

    loc2, lat2, lon2, _ = extract_location("Anna Nagar Chennai road pothole")
    assert loc2 is not None
    assert "Anna Nagar" in loc2


def test_priority_assessment():
    pri_crit, _ = assess_priority("live wire dangling danger fire emergency", "Electricity")
    assert pri_crit.value == "CRITICAL"

    pri_med, _ = assess_priority("water pipeline maintenance needed for street", "Water")
    assert pri_med.value == "MEDIUM"

    pri_low, _ = assess_priority("minor aesthetic suggestion for park bench", "Other")
    assert pri_low.value == "LOW"


def test_ai_provider_full_pipeline(client):
    payload = {
        "text": "Gandhipuram-la thanni pipe odanju pochu urgent ah fix pannunga"
    }
    response = client.post("/api/v1/analysis/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Water"
    assert "Gandhipuram" in (data["extracted_location"] or "")
    assert data["detected_language"] == "Tanglish"
    assert data["priority"] in ["HIGH", "CRITICAL"]
    assert data["analysis_method"] == "deterministic_fallback"
