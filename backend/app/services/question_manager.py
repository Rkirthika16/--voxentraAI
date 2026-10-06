"""Dynamic Question Manager for VoxentraAI Conversational IVR.
Handles dynamic questioning (minimum 10 meaningful questions/slots),
category-specific prompts, one-question-at-a-time enforcement,
and multilingual prompt generation for Tamil, English, and Tanglish.
"""
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger("voxentra.question_manager")

# Ordered slots for dynamic evaluation
ORDERED_QUESTION_SLOTS = [
    "problem_description",       # 1. Problem
    "district_area",             # 2. Area / locality
    "street_road_name",          # 3. Street / road name
    "exact_location",            # 4. Spot / house / pole number
    "landmark",                  # 5. Nearby landmark
    "duration",                  # 6. Duration / when it started
    "affected_scope",            # 7. Whole street or single house
    "severity",                  # 8. Severity / urgency
    "impact",                    # 9. Drinking water / public facility affected
    "safety_hazard",             # 10. Immediate safety hazard
    "previous_complaint",        # 11. Reported previously?
    "previous_complaint_number", # 12. Previous token / ID
    "frequency",                 # 13. Frequency of occurrence
    "additional_details"         # 14. Additional info
]

# Multilingual question templates customized by slot and category
QUESTION_TEMPLATES = {
    "problem_description": {
        "Tamil": "வணக்கம், உங்களுக்கு என்ன பிரச்சினை? விவரிக்கவும்.",
        "English": "What civic problem or issue are you facing?",
        "Tanglish": "Unga area-la enna problem aachu? Sollunga."
    },
    "district_area": {
        "Tamil": "நீங்கள் கோவையில் எந்த பகுதியில் வசிக்கிறீர்கள்?",
        "English": "Which area or locality in Coimbatore are you located in?",
        "Tanglish": "Neenga Coimbatore-la endha area-la irukkeenga?"
    },
    "duration": {
        "Tamil": "இந்த பிரச்சினை எப்போது ஆரம்பித்தது? எத்தனை நாட்களாக உள்ளது?",
        "English": "When did this problem start and how long has it continued?",
        "Tanglish": "Indha problem eppo lendhu irukku? Evvalavu naala aagudhu?"
    },
    "street_road_name": {
        "Tamil": "உங்கள் தெரு அல்லது சாலை பெயர் என்ன?",
        "English": "What is your street name or road name?",
        "Tanglish": "Unga street name enna?"
    },
    "affected_scope": {
        "Tamil": "இது உங்கள் வீட்டிற்கு மட்டுமா அல்லது தெரு முழுவதும் உள்ளதா?",
        "English": "Is this affecting only your house or the entire street?",
        "Tanglish": "Idhu unga veetuku mattumaa illa whole street-kum problem-aa?"
    },
    "severity": {
        "Tamil": "பிரச்சினை எந்த அளவுக்கு தீவிரமாக உள்ளது?",
        "English": "How severe is the issue?",
        "Tanglish": "Problem evvalavu serious-ah irukku?"
    },
    "impact": {
        "Tamil": "குடிநீர் அல்லது பொது வசதிகள் ஏதேனும் பாதிக்கப்பட்டுள்ளதா?",
        "English": "Are drinking water supplies or public facilities affected?",
        "Tanglish": "Drinking water illa public facilities edhavadhu affect aayirukkaa?"
    },
    "previous_complaint": {
        "Tamil": "இதற்கு முன்பு இந்த புகாரைப் பதிவு செய்துள்ளீர்களா?",
        "English": "Have you previously reported this complaint?",
        "Tanglish": "Idhuku munnadi indha complaint-a report pannirukeengala?"
    },
    "landmark": {
        "Tamil": "உங்கள் தெரு அருகில் உள்ள முக்கிய அடையாளம் (Landmark) என்ன?",
        "English": "What is a nearby recognizable landmark or bus stand?",
        "Tanglish": "Unga street pakkathula edhavadhu landmark irukka?"
    },
    "safety_hazard": {
        "Tamil": "ஏதேனும் உடனடி விபத்து அல்லது ஆபத்து உள்ளதா?",
        "English": "Is there any immediate safety hazard or emergency concern?",
        "Tanglish": "Edhavadhu danger illa emergency safety risk irukkaa?"
    },
    "exact_location": {
        "Tamil": "சரியான கதவு எண், மின் கம்ப எண் அல்லது இடத்தின் விவரம் என்ன?",
        "English": "What is the exact door number, pillar, or spot location?",
        "Tanglish": "Exact door number illa spot detail enna?"
    },
    "frequency": {
        "Tamil": "இந்த பிரச்சினை அடிக்கடி ஏற்படுகிறதா அல்லது முதல் முறையா?",
        "English": "Does this issue happen frequently or is it occasional?",
        "Tanglish": "Indha problem adikkadi varudhaa illa occasional-aa?"
    },
    "previous_complaint_number": {
        "Tamil": "முந்தைய புகார் எண் (Complaint ID) ஏதேனும் உள்ளதா?",
        "English": "Do you have the previous complaint reference number?",
        "Tanglish": "Pazhaya complaint number edhavadhu irukkaa?"
    },
    "additional_details": {
        "Tamil": "வேறு ஏதேனும் கூடுதல் தகவல் உள்ளதா?",
        "English": "Do you have any additional information to add?",
        "Tanglish": "Vera edhavadhu additional details sollalama?"
    }
}

# Category-specific overrides
CATEGORY_QUESTION_OVERRIDES = {
    "Water": {
        "severity": {
            "Tamil": "குடிநீர் முற்றிலும் வரவில்லையா அல்லது குறைந்த அழுத்தத்தில் வருகிறதா?",
            "English": "Is water completely unavailable or coming at low pressure?",
            "Tanglish": "Thanni completely varalaya illa low pressure-la varudha?"
        }
    },
    "Electricity": {
        "severity": {
            "Tamil": "மின்சாரம் முற்றிலும் துண்டிக்கப்பட்டுள்ளதா அல்லது குறைந்த மின்னழுத்தமா?",
            "English": "Is there a complete power blackout or low voltage fluctuation?",
            "Tanglish": "Full-ah current cut aayiduchaa illa low voltage problem-aa?"
        },
        "safety_hazard": {
            "Tamil": "மின் கம்பம் அல்லது வயர் அறுந்து தீப்பொறி பறக்கும் ஆபத்து உள்ளதா?",
            "English": "Is there any broken live wire, damaged pole, or sparking danger?",
            "Tanglish": "Broken wire, transformer spark illa edhavadhu live current risk irukkaa?"
        }
    },
    "Roads": {
        "severity": {
            "Tamil": "சாலையில் பெரிய பள்ளம் உள்ளதா அல்லது போக்குவரத்து பாதிக்கப்பட்டுள்ளதா?",
            "English": "Is there a deep pothole, road blockage, or accident danger?",
            "Tanglish": "Road-la periya pallam irukkaa, traffic block aagudhaa?"
        }
    },
    "Sanitation": {
        "severity": {
            "Tamil": "குப்பை நிரம்பி வழிந்து துர்நாற்றம் வீசுகிறதா?",
            "English": "Is garbage overflowing with severe foul smell in the area?",
            "Tanglish": "Kuppai overflow aagi bad smell varudhaa?"
        }
    },
    "Drainage": {
        "severity": {
            "Tamil": "சாக்கடை நீர் சாலையில் தேங்கி வழிந்துள்ளதா?",
            "English": "Is drainage overflowing onto the road causing water stagnation?",
            "Tanglish": "Drainage overflow aagi therula thenki nikkudha?"
        }
    }
}


class QuestionManager:
    """Manages conversational question selection, skipping answered items, and formatting."""

    def get_next_missing_slot(self, memory: Dict[str, Any], min_questions: int = 10) -> Optional[str]:
        """
        Determines the next missing information slot to prompt.
        Skips already provided information.
        Continues until at least min_questions (or all essential slots) are addressed.
        """
        questions_asked = memory.get("questions_asked_count", 0)

        for slot in ORDERED_QUESTION_SLOTS:
            val = self._get_slot_value(memory, slot)
            if not val:
                return slot

        # If all 14 slots answered or minimum questions satisfied
        return None

    def _get_slot_value(self, memory: Dict[str, Any], slot: str) -> Optional[Any]:
        """Retrieves slot value considering field aliases."""
        if slot == "problem_description":
            return memory.get("problem_description") or memory.get("problem")
        elif slot == "district_area":
            return memory.get("area") or memory.get("district_area") or memory.get("location")
        elif slot == "street_road_name":
            return memory.get("street") or memory.get("street_road_name")
        elif slot == "exact_location":
            return memory.get("exact_location")
        elif slot == "landmark":
            return memory.get("landmark")
        elif slot == "duration":
            return memory.get("duration") or memory.get("start_time")
        elif slot == "affected_scope":
            return memory.get("affected_scope") or memory.get("affected_area")
        elif slot == "severity":
            return memory.get("severity")
        elif slot == "impact":
            return memory.get("impact")
        elif slot == "previous_complaint":
            return memory.get("previous_complaint")
        elif slot == "previous_complaint_number":
            return memory.get("previous_complaint_number")
        elif slot == "safety_hazard":
            return memory.get("safety_hazard")
        elif slot == "frequency":
            return memory.get("frequency")
        elif slot == "additional_details":
            return memory.get("additional_details")
        return memory.get(slot)

    def generate_question(
        self,
        slot: str,
        memory: Dict[str, Any],
        language: str = "Tanglish"
    ) -> Tuple[str, str, List[Dict[str, str]]]:
        """
        Generates natural spoken and text question for the citizen in their detected language.
        Returns: (ai_reply_text, spoken_reply_text, quick_options)
        """
        category = memory.get("category", "General")
        lang = language if language in ["Tamil", "English", "Tanglish"] else "Tanglish"

        # Check category override first
        cat_key = next((k for k in CATEGORY_QUESTION_OVERRIDES if k.lower() in category.lower()), None)
        if cat_key and slot in CATEGORY_QUESTION_OVERRIDES[cat_key]:
            override_dict = CATEGORY_QUESTION_OVERRIDES[cat_key][slot]
            if lang in override_dict:
                text = override_dict[lang]
                return text, text, []

        template = QUESTION_TEMPLATES.get(slot, {}).get(lang)
        if not template:
            template = QUESTION_TEMPLATES.get(slot, {}).get("English", "Could you provide more details?")

        return template, template, []

    def build_confirmation_summary(
        self,
        memory: Dict[str, Any],
        language: str = "Tanglish"
    ) -> Tuple[str, str]:
        """
        Constructs a complete confirmation summary in the citizen's language before DB insertion.
        """
        lang = language if language in ["Tamil", "English", "Tanglish"] else "Tanglish"
        area = memory.get("area") or memory.get("district_area") or memory.get("location") or "Coimbatore"
        street = memory.get("street") or memory.get("street_road_name") or ""
        problem = memory.get("problem_description") or memory.get("problem") or "Civic issue"
        duration = memory.get("duration") or ""
        landmark = memory.get("landmark") or ""
        scope = memory.get("affected_scope") or ""

        loc_str = f"{street}, {area}".strip(", ") if street else area

        if lang == "Tamil":
            summary = f"சரி, உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன். {loc_str} பகுதியில்"
            if duration:
                summary += f" {duration} நாட்களாக"
            summary += f" {problem} ஏற்பட்டுள்ளது."
            if landmark:
                summary += f" அருகிலுள்ள அடையாளம்: {landmark}."
            summary += " இந்தப் புகாரை பதிவு செய்யலாமா?"
            return summary, summary

        elif lang == "Tanglish":
            summary = f"Seri, naan confirm panren. {loc_str}-la"
            if duration:
                summary += f" {duration}-ah"
            summary += f" {problem} problem irukku."
            if landmark:
                summary += f" {landmark} pakkathula."
            summary += " Indha complaint-a register pannalama?"
            return summary, summary

        else:
            summary = f"Let me confirm your complaint details. In {loc_str},"
            if duration:
                summary += f" for the past {duration},"
            summary += f" {problem} is reported."
            if landmark:
                summary += f" Near landmark: {landmark}."
            summary += " Should I register this complaint now?"
            return summary, summary


question_manager = QuestionManager()
