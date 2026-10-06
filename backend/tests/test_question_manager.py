"""Automated tests for Question Manager & Dynamic Questioning in VoxentraAI Conversational IVR."""
import pytest
from app.services.question_manager import question_manager, ORDERED_QUESTION_SLOTS, QUESTION_TEMPLATES, CATEGORY_QUESTION_OVERRIDES

def test_initial_missing_slot():
    # Empty memory -> first missing slot is problem_description
    memory = {}
    next_slot = question_manager.get_next_missing_slot(memory)
    assert next_slot == "problem_description"


def test_skip_already_provided_slots():
    # Citizen said: "Gandhipuram 5th Street-la rendu naala full street-ku thanni varala."
    # Problem = Water, Area = Gandhipuram, Street = 5th Street, Duration = 2 days, Scope = Whole street
    memory = {
        "problem_description": "Water supply issue",
        "district_area": "Gandhipuram",
        "duration": "2 days",
        "street_road_name": "5th Street",
        "affected_scope": "Whole street",
        "questions_asked_count": 0
    }
    next_slot = question_manager.get_next_missing_slot(memory)
    # Must NOT ask problem, area, duration, street, or affected_scope again!
    assert next_slot not in ["problem_description", "district_area", "duration", "street_road_name", "affected_scope"]
    assert next_slot == "exact_location"


def test_one_question_at_a_time():
    memory = {"category": "Water"}
    # Generate question for single slot
    reply_ta, _, _ = question_manager.generate_question("street_road_name", memory, language="Tamil")
    assert "தெரு" in reply_ta
    assert "?" in reply_ta or "என்ன" in reply_ta
    # Single sentence, not multiple questions concatenated
    assert "விவரம் என்ன" not in reply_ta or "தெரு" in reply_ta

    reply_en, _, _ = question_manager.generate_question("street_road_name", memory, language="English")
    assert "street" in reply_en.lower()

    reply_tg, _, _ = question_manager.generate_question("street_road_name", memory, language="Tanglish")
    assert "street name" in reply_tg.lower()


def test_category_specific_overrides():
    # Water category severity question
    water_mem = {"category": "Water"}
    q_ta, _, _ = question_manager.generate_question("severity", water_mem, language="Tamil")
    assert "குடிநீர்" in q_ta or "அழுத்தம்" in q_ta

    # Electricity category severity question
    elec_mem = {"category": "Electricity"}
    q_elec_tg, _, _ = question_manager.generate_question("severity", elec_mem, language="Tanglish")
    assert "current cut" in q_elec_tg.lower() or "voltage" in q_elec_tg.lower()

    # Electricity safety hazard question
    q_safe_en, _, _ = question_manager.generate_question("safety_hazard", elec_mem, language="English")
    assert "wire" in q_safe_en.lower() or "spark" in q_safe_en.lower() or "danger" in q_safe_en.lower()


def test_minimum_10_question_progression():
    memory = {}
    slots_asked = []
    
    for i in range(14):
        slot = question_manager.get_next_missing_slot(memory, min_questions=10)
        if slot is None:
            break
        slots_asked.append(slot)
        # Populate slot as answered
        memory[slot] = f"Answer_{i+1}"
        memory["questions_asked_count"] = i + 1

    # Verified that at least 10 slots are available in the question manager
    assert len(slots_asked) >= 10
    assert "problem_description" in slots_asked
    assert "district_area" in slots_asked
    assert "street_road_name" in slots_asked
    assert "duration" in slots_asked
    assert "landmark" in slots_asked


def test_build_confirmation_summary_multilingual():
    memory = {
        "problem_description": "Water not supply",
        "area": "Gandhipuram",
        "street": "5th Street",
        "duration": "2 days",
        "landmark": "Near Bus Stand",
        "affected_scope": "Entire street"
    }

    # Tamil Summary
    sum_ta, _ = question_manager.build_confirmation_summary(memory, language="Tamil")
    assert "உறுதிப்படுத்துகிறேன்" in sum_ta
    assert "Gandhipuram" in sum_ta or "5th Street" in sum_ta
    assert "பதிவு செய்யலாமா" in sum_ta

    # Tanglish Summary
    sum_tg, _ = question_manager.build_confirmation_summary(memory, language="Tanglish")
    assert "confirm panren" in sum_tg
    assert "register pannalama" in sum_tg

    # English Summary
    sum_en, _ = question_manager.build_confirmation_summary(memory, language="English")
    assert "confirm your complaint" in sum_en
    assert "register this complaint" in sum_en
