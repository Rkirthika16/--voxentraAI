"""Dynamic Conversational Question Manager for VoxentraAI Conversational IVR.
Handles dynamic human-like conversational questioning, slot evaluation,
natural follow-ups, and empathetic multilingual spoken replies in Tamil, English, and Tanglish.
"""
import re
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
    "street_road_name": {
        "Tamil": "உங்கள் தெரு அல்லது சாலை பெயர் என்ன?",
        "English": "What is your street name or road name?",
        "Tanglish": "Unga street name enna?"
    },
    "duration": {
        "Tamil": "இந்த பிரச்சினை எப்போது ஆரம்பித்தது? எத்தனை நாட்களாக உள்ளது?",
        "English": "When did this problem start and how long has it continued?",
        "Tanglish": "Indha problem eppo lendhu irukku? Evvalavu naala aagudhu?"
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
        },
        "impact": {
            "Tamil": "குடிநீர் விநியோகம் எத்தனை வீடுகளுக்கு பாதிக்கப்பட்டுள்ளது?",
            "English": "How many houses or families are impacted by this drinking water shortage?",
            "Tanglish": "Drinking water supply ethanai veedugalukku affect aayirukku?"
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
            "English": "Is there a deep pothole, road damage, or traffic blockage?",
            "Tanglish": "Road-la periya pallam irukkaa, traffic block aagudhaa?"
        },
        "safety_hazard": {
            "Tamil": "இந்த சாலை சேதத்தால் விபத்து ஏற்படும் ஆபத்து உள்ளதா?",
            "English": "Is there an immediate risk of vehicular accidents on this damaged road?",
            "Tanglish": "Indha road damage naala accident aaga risk irukkaa?"
        }
    },
    "Sanitation": {
        "severity": {
            "Tamil": "குப்பை பல நாட்களாக அள்ளப்படாமல் தேங்கியுள்ளதா?",
            "English": "Has garbage been left uncollected for days causing severe foul smell?",
            "Tanglish": "Kuppai pala naala edukama overflow aagi bad smell varudhaa?"
        },
        "impact": {
            "Tamil": "குப்பைத் தொட்டி நிரம்பி தெருவில் சிதறியுள்ளதா?",
            "English": "Is the municipal waste bin overflowing onto the public street?",
            "Tanglish": "Dustbin overflow aagi theru full-ah kuppai kedaika?"
        }
    },
    "Garbage": {
        "severity": {
            "Tamil": "குப்பை பல நாட்களாக அள்ளப்படாமல் தேங்கியுள்ளதா?",
            "English": "Has garbage been left uncollected for days causing severe foul smell?",
            "Tanglish": "Kuppai pala naala edukama overflow aagi bad smell varudhaa?"
        }
    },
    "Drainage": {
        "severity": {
            "Tamil": "சாக்கடை அடைப்பு ஏற்பட்டு கழிவுநீர் சாலையில் தேங்கி நிற்கிறதா?",
            "English": "Is drainage blocked and overflowing with sewage stagnating on the street?",
            "Tanglish": "Drainage block aagi therula saakkadai thanni thenki nikkudha?"
        },
        "impact": {
            "Tamil": "கழிவுநீர் தேக்கத்தால் கொசு மற்றும் சுகாதார சீர்கேடு ஏற்பட்டுள்ளதா?",
            "English": "Is sewage stagnation creating health hazards and mosquito breeding?",
            "Tanglish": "Sewage thanni thenkura naala health hazard and kosu thollai irukkaa?"
        }
    },
    "Sewage": {
        "severity": {
            "Tamil": "கழிவுநீர் குழாய் உடைந்து துர்நாற்றத்துடன் சாக்கடை நீர் தெருவில் ஓடுகிறதா?",
            "English": "Is there a sewage pipe burst causing overflow on the public pathway?",
            "Tanglish": "Sewage pipe udanju saakkadai thanni therula odundha?"
        }
    },
    "Street Light": {
        "severity": {
            "Tamil": "தெரு விளக்கு முற்றிலும் எரியவில்லையா அல்லது விட்டு விட்டு எரிகிறதா?",
            "English": "Is the street light completely non-functional or flickering?",
            "Tanglish": "Street light full-ah eriyalaiya illa vittu vittu eriyudha?"
        },
        "exact_location": {
            "Tamil": "தெரு விளக்கு கம்பத்தின் எண் அல்லது கதவு எண் தெரியுமா?",
            "English": "Do you know the electric pole number or adjacent door number?",
            "Tanglish": "Street light lamp post number illa nearby door number theriyuma?"
        }
    },
    "Streetlights": {
        "severity": {
            "Tamil": "தெரு விளக்கு முற்றிலும் எரியவில்லையா அல்லது விட்டு விட்டு எரிகிறதா?",
            "English": "Is the street light completely non-functional or flickering?",
            "Tanglish": "Street light full-ah eriyalaiya illa vittu vittu eriyudha?"
        }
    },
    "Public Transport": {
        "severity": {
            "Tamil": "பேருந்து சரியான நேரத்திற்கு வருவதில்லையா அல்லது நிறுத்தம் சேதமடைந்துள்ளதா?",
            "English": "Are government buses skipping stops, delayed, or is the bus shelter damaged?",
            "Tanglish": "Bus correct time-ku varalaya illa bus stop shelter damage aayirukka?"
        }
    }
}

TAMIL_AREA_MAP = {
    "Vadavalli": "வடவள்ளி",
    "Gandhipuram": "காந்திபுரம்",
    "RS Puram": "ஆர் எஸ் புரம்",
    "Peelamedu": "பீளமேடு",
    "Singanallur": "சிங்கநல்லூர்",
    "Saravanampatti": "சரவணம்பட்டி",
    "Town Hall": "டவுன் ஹால்",
    "Ukkadam": "உக்கடம்",
    "Saibaba Colony": "சாயிபாபா காலனி",
    "Ramanathapuram": "இராமநாதபுரம்",
    "Thudiyalur": "துடியலூர்",
    "Ganapathy": "கணபதி",
    "Kovaipudur": "கோவைப்புதூர்",
    "Kuniyamuthur": "குனியமுத்தூர்",
    "Ondipudur": "ஒண்டிப்புதூர்",
    "Sowripalayam": "சௌரிபாளையம்",
    "Race Course": "ரேஸ் கோர்ஸ்",
    "Annur": "அன்னூர்"
}

def tamil_locative(area_name_ta: str) -> str:
    """Forms natural locative in Tamil (e.g. காந்திபுரம் -> காந்திபுரத்தில், வடவள்ளி -> வடவள்ளியில்)."""
    if not area_name_ta:
        return ""
    if area_name_ta.endswith("புரம்"):
        return area_name_ta[:-len("புரம்")] + "புரத்தில்"
    elif area_name_ta.endswith("மேடு"):
        return area_name_ta[:-len("மேடு")] + "மேட்டில்"
    elif area_name_ta.endswith("பட்டி") or area_name_ta.endswith("வள்ளி") or area_name_ta.endswith("காலனி"):
        return area_name_ta + "யில்"
    elif area_name_ta.endswith("நல்லூர்") or area_name_ta.endswith("ஊர்") or area_name_ta.endswith("ஹால்") or area_name_ta.endswith("கோர்ஸ்"):
        return area_name_ta + "ில்"
    else:
        return area_name_ta + "ில்"

TAMIL_STREET_MAP = {
    "Anna Nagar 2nd Street": "அண்ணா நகர் இரண்டாவது தெரு",
    "Anna Nagar Second Street": "அண்ணா நகர் இரண்டாவது தெரு",
    "Anna Nagar Main Street": "அண்ணா நகர் முதன்மைத் தெரு",
    "Cross Cut Road": "கிராஸ் கட் ரோடு",
    "DB Road": "டி பி ரோடு",
    "100 Feet Road": "100 அடி ரோடு",
    "Avinashi Road": "அவினாசி ரோடு",
    "Trichy Road": "திருச்சி ரோடு",
    "Mettupalayam Road": "மேட்டுப்பாளையம் ரோடு",
    "Pollachi Road": "பொள்ளாச்சி ரோடு",
    "Sathy Road": "சத்தி ரோடு",
    "Marudamalai Road": "மருதமலை ரோடு",
    "5th Street": "5வது தெரு",
    "Gandhipuram 5th Street": "காந்திபுரம் 5வது தெரு",
    "6th Street": "6வது தெரு"
}


class QuestionManager:
    """Manages conversational question selection, natural human turn-taking, and formatting."""

    def is_essential_info_complete(self, memory: Dict[str, Any]) -> bool:
        """
        Checks whether sufficient core civic details have been gathered
        to register an actionable complaint without putting the citizen through
        a rigid 10-question questionnaire.
        """
        has_problem = bool(memory.get("problem_description") or memory.get("problem") or memory.get("category"))
        has_area = bool(memory.get("area") or memory.get("district_area") or memory.get("location"))
        has_street = bool(memory.get("street") or memory.get("street_road_name") or memory.get("exact_location"))

        category = (memory.get("category") or "").lower()
        if "water" in category:
            has_dur = bool(memory.get("duration") or memory.get("start_time"))
            has_scope = bool(memory.get("affected_scope") or memory.get("affected_area"))
            return has_problem and has_area and has_street and has_dur and has_scope

        return has_problem and has_area and has_street

    def get_next_missing_slot(self, memory: Dict[str, Any], min_questions: int = 10) -> Optional[str]:
        """
        Determines the next missing information slot to prompt.
        Skips already provided information.
        Continues until all slots are addressed or minimum requested turns are satisfied.
        """
        target_min = memory.get("min_questions", min_questions)
        questions_asked = memory.get("questions_asked_count", 0)

        # If citizen explicitly signaled ready to confirm or end
        if memory.get("is_citizen_confirmed_ready"):
            return None

        # Natural conversational completion for concise/short mode (e.g. min_questions <= 5)
        if target_min <= 5 and questions_asked >= 4 and self.is_essential_info_complete(memory):
            return None

        for slot in ORDERED_QUESTION_SLOTS:
            val = self._get_slot_value(memory, slot)
            if not val:
                return slot

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
        language: str = "Tanglish",
        last_raw_text: str = "",
        prompted_slot: Optional[str] = None
    ) -> Tuple[str, str, List[Dict[str, str]]]:
        """
        Generates natural, conversational human replies for the telephone call.
        Acknowledges what the caller just said, speaks politely like a helpful
        helpline representative, and asks ONE relevant question.
        """
        category = memory.get("category") or "General"
        area = memory.get("area") or memory.get("district_area") or ""
        street = memory.get("street") or memory.get("street_road_name") or ""
        duration = memory.get("duration") or ""
        lang = language if language in ["Tamil", "English", "Tanglish"] else "Tanglish"
        raw_lowered = (last_raw_text or "").lower().strip()

        area_ta = TAMIL_AREA_MAP.get(area, area)
        street_ta = TAMIL_STREET_MAP.get(street, street)
        loc_locative = tamil_locative(area_ta) if area_ta else ""

        # 1. Citizen just gave an area (e.g. 'Coimbatore Vadavalli', 'Vadavalli', 'RS Puram')
        if any(a.lower() in raw_lowered for a in ["vadavalli", "gandhipuram", "rs puram", "peelamedu", "singanallur", "saravanampatti", "town hall"]):
            if slot == "problem_description" or not memory.get("problem_description"):
                if lang in ["Tamil", "Tanglish"]:
                    reply = f"{area_ta}யா? சரி. அங்க என்ன பிரச்சினை?"
                else:
                    reply = f"{area}? Understood. What is the problem there?"
                return reply, reply, []
            elif slot in ["street_road_name", "exact_location"]:
                if any(w in category.lower() for w in ["road", "சாலை", "damage"]):
                    reply = f"சரி, {loc_locative or area_ta} சாலை சேதமடைந்திருக்கிறதா? எந்த இடத்துக்கு அருகில்?" if lang in ["Tamil", "Tanglish"] else f"Alright, road damage in {area}. Near which spot or landmark is this located?"
                else:
                    reply = f"சரி, {loc_locative or area_ta} எந்தத் தெருவில் இந்தப் பிரச்சினை இருக்கு?" if lang in ["Tamil", "Tanglish"] else f"Alright, which street in {area} is having this issue?"
                return reply, reply, []

        # 2. Road damage specific follow-up (Section 6 example: 'Gandhipuram la road damage' -> 'Bus stand pakkam')
        if any(w in raw_lowered for w in ["road damage", "road romba damage", "road sari illa", "சாலை சேதம்", "பள்ளம்"]):
            if slot in ["exact_location", "landmark", "street_road_name"]:
                reply = f"சரி, {loc_locative or area_ta or 'இங்கு'} சாலை சேதமடைந்திருக்கிறதா? எந்த இடத்துக்கு அருகில்?" if lang in ["Tamil", "Tanglish"] else f"Alright, road damage in {area or 'this area'}. Near which location or landmark?"
                return reply, reply, []

        if any(w in raw_lowered for w in ["bus stand", "bus stop", "பேருந்து"]) and any(w in category.lower() for w in ["road", "traffic"]):
            if slot in ["severity", "exact_location", "safety_hazard"]:
                reply = f"சரி, பேருந்து நிலையம் அருகில் சாலை சேதமடைந்திருக்கிறதா? போக்குவரத்துக்கு விபத்து ஆபத்து உள்ளதா?" if lang in ["Tamil", "Tanglish"] else f"Understood, near the bus stand. Is there accident risk or severe traffic blockage?"
                return reply, reply, []

        # 3. Citizen just gave duration (e.g. 'Three days ah water varala', '3 naala thanni varala')
        if any(d in raw_lowered for d in ["three days", "3 days", "moonu", "rendu", "2 days", "naala", "நாட்களாக", "நாளா"]):
            dur_ta = "மூணு நாளா" if any(w in raw_lowered for w in ["three", "3", "moonu", "மூணு"]) else (
                "ரெண்டு நாளா" if any(w in raw_lowered for w in ["two", "2", "rendu", "ரெண்டு"]) else (duration or "சில நாட்களாக")
            )
            dur_tang = "3 naala" if any(w in raw_lowered for w in ["three", "3", "moonu"]) else (
                "2 naala" if any(w in raw_lowered for w in ["two", "2", "rendu"]) else (duration or "pala naala")
            )
            if slot in ["street_road_name", "exact_location"]:
                if "water" in category.lower():
                    if lang in ["Tamil", "Tanglish"]:
                        reply = f"அச்சச்சோ, {dur_ta} தண்ணி வரலையா? எந்தத் தெருவில் இந்தப் பிரச்சினை இருக்கு?"
                    else:
                        reply = f"Oh, no water for {dur_tang}? Which street is facing this issue?"
                else:
                    if lang in ["Tamil", "Tanglish"]:
                        reply = f"அச்சச்சோ, {dur_ta} இந்தப் பிரச்சினையா? எந்தத் தெருவில் இந்தப் பிரச்சினை இருக்கு?"
                    else:
                        reply = f"Oh, {duration or 'several days'} ongoing? Which street is facing this problem?"
                return reply, reply, []

        # 4. Citizen just gave street name (e.g. 'Anna nagar second street', '5th street')
        is_scope_resp = any(w in raw_lowered for w in ["full street", "entire street", "whole street", "முழு தெரு", "fulla", "full-ah"])
        if not is_scope_resp and any(s in raw_lowered for s in ["anna nagar", "second street", "2nd street", "5th street", "street", "road", "theru", "salai"]):
            if slot in ["affected_scope", "severity", "exact_location", "landmark"] and "water" in category.lower():
                loc_disp_ta = f"{area_ta} {street_ta}".strip() if area_ta else street_ta
                loc_disp = f"{area} {street}".strip() if area else street
                if lang in ["Tamil", "Tanglish"]:
                    reply = f"சரி, {loc_disp_ta}. அந்தத் தெரு முழுக்க தண்ணி வரலையா, இல்ல உங்க வீட்டுக்கு மட்டும் வரலையா?"
                else:
                    reply = f"Alright, {loc_disp}. Is the whole street affected or only your house?"
                return reply, reply, []

        # 5. Caller initiated with greeting or general grievance (e.g. 'Hello, enga oorla thanni varala')
        if any(w in raw_lowered for w in ["hello", "vanakkam", "வணக்கம்"]) or (slot == "district_area" and memory.get("problem_description")):
            if lang in ["Tamil", "Tanglish"]:
                reply = "சரி, உதவி செய்கிறேன். எந்த ஊர்ல இருந்து பேசுறீங்க?"
            else:
                reply = "Sure, I am here to help you. Which area or town are you calling from?"
            return reply, reply, []

        # 6. Check category-specific question overrides
        cat_key = next((k for k in CATEGORY_QUESTION_OVERRIDES if k.lower() in category.lower()), None)
        if cat_key and slot in CATEGORY_QUESTION_OVERRIDES[cat_key]:
            override_dict = CATEGORY_QUESTION_OVERRIDES[cat_key][slot]
            if lang in override_dict:
                text = override_dict[lang]
                return text, text, []

        # 7. Fallback to standard multilingual templates
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
        Constructs a complete, natural confirmation summary in the citizen's language.
        Matches authentic government representative tone before DB insertion.
        """
        lang = language if language in ["Tamil", "English", "Tanglish"] else "Tanglish"
        area = memory.get("area") or memory.get("district_area") or memory.get("location") or "Coimbatore"
        street = memory.get("street") or memory.get("street_road_name") or ""
        problem = memory.get("problem_description") or memory.get("problem") or "Civic issue"
        duration = memory.get("duration") or ""
        landmark = memory.get("landmark") or ""
        scope = memory.get("affected_scope") or ""
        category = memory.get("category") or "General"

        area_ta = TAMIL_AREA_MAP.get(area, area)
        street_ta = TAMIL_STREET_MAP.get(street, street)
        dur_ta = "மூணு நாளா" if any(w in duration.lower() for w in ["3", "three", "moonu"]) else (
            "ரெண்டு நாளா" if any(w in duration.lower() for w in ["2", "two", "rendu"]) else (
                f"{duration} நாட்களாக" if duration else ""
            )
        )

        loc_str_ta = f"{area_ta} {street_ta}".strip() if (area_ta and street_ta) else (street_ta or area_ta or "கோயம்புத்தூர்")
        loc_str = f"{street}, {area}".strip(", ") if street else area

        if lang == "Tamil":
            cat_label = "குடிநீர் விநியோகப்" if "water" in category.lower() else (
                "மின்சாரப்" if any(k in category.lower() for k in ["electric", "power"]) else (
                    "சாலைப் பராமரிப்புப்" if "road" in category.lower() else (
                        "துப்புரவுப்" if any(k in category.lower() for k in ["sanitation", "garbage"]) else "பொது"
                    )
                )
            )
            prob_label = "தண்ணீர் வரல" if "water" in category.lower() else (
                "மின்சாரம் இல்லை" if any(k in category.lower() for k in ["electric", "power"]) else problem
            )
            dur_phrase = f"{dur_ta} " if dur_ta else ""
            summary = f"சரி, உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன். {loc_str} பகுதியில் {dur_phrase}{prob_label} ஏற்பட்டுள்ளது. இந்தப் புகாரை பதிவு செய்யலாமா? இந்த விவரம் சரிதானே?"
            return summary, summary

        elif lang == "Tanglish":
            summary = f"Seri, naan confirm panren. {loc_str}-la"
            if duration:
                summary += f" {duration}-ah"
            summary += f" {problem} problem irukku."
            if landmark:
                summary += f" {landmark} pakkathula."
            summary += " Indha complaint-a register pannalama? Indha vivaram saridhane?"
            return summary, summary

        else:
            summary = f"Let me confirm your complaint details. In {loc_str},"
            if duration:
                summary += f" for {duration},"
            summary += f" {problem} is reported."
            if landmark:
                summary += f" Near landmark: {landmark}."
            summary += " Should I register this complaint now? Are these details correct?"
            return summary, summary


question_manager = QuestionManager()
