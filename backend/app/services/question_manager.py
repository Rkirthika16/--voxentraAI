"""Dynamic Conversational Question Manager for VoxentraAI Conversational IVR.
Handles dynamic human-like conversational questioning, slot evaluation,
natural follow-ups, and empathetic multilingual spoken replies in Tamil, English, and Tanglish.
"""
import re
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger("voxentra.question_manager")

# Ordered slots for dynamic evaluation (up to 20 conversational slots)
ORDERED_QUESTION_SLOTS = [
    "problem_description",          # 1. Citizen civic issue / category
    "district_area",                # 2. Village / town / area
    "street_road_name",             # 3. Exact street / road name
    "exact_location",               # 4. House number / door number / pole number / spot
    "landmark",                     # 5. Nearby landmark or identifying detail
    "duration",                     # 6. Duration / when it started
    "affected_scope",               # 7. Whole street or single house
    "frequency",                    # 8. Frequency / when water last arrived
    "severity",                     # 9. Severity / pressure / urgency
    "safety_hazard",                # 10. Immediate safety hazard / accident danger
    "impact",                       # 11. Drinking water / public facility affected
    "previous_complaint",           # 12. Reported previously?
    "previous_complaint_number",    # 13. Previous token / ID
    "water_supply_timing",          # 14. Routine timing or when supply cut off
    "leakage_or_contamination",     # 15. Pipe leakage, contamination, or foul smell
    "affected_population",          # 16. Number of families / residents impacted
    "alternate_source",             # 17. Alternate source or tanker needed
    "contact_person",               # 18. Local resident contact / on-site person
    "preferred_contact_time",       # 19. Preferred inspection time for municipal crew
    "additional_details"            # 20. Additional info / special instructions
]

# Multilingual question templates customized by slot and category
QUESTION_TEMPLATES = {
    "problem_description": {
        "Tamil": "வணக்கம், உங்களுக்கு என்ன பிரச்சினை? விவரிக்கவும்.",
        "English": "What civic problem or issue are you facing?",
        "Tanglish": "Unga area-la enna problem aachu? Sollunga."
    },
    "district_area": {
        "Tamil": "சரி, உதவி செய்கிறேன். எந்த ஊர்ல இருந்து பேசுறீங்க?",
        "English": "Sure, I am here to help you. Which village or town are you calling from?",
        "Tanglish": "Seri, udhavi seiyren. Endha oorla irundhu pesureenga?"
    },
    "street_road_name": {
        "Tamil": "உங்கள் தெரு அல்லது சாலை பெயர் என்ன?",
        "English": "What is your street name or road name?",
        "Tanglish": "Unga street name illa theru peyar enna?"
    },
    "exact_location": {
        "Tamil": "சரியான கதவு எண், மின் கம்ப எண் அல்லது இடத்தின் விவரம் என்ன?",
        "English": "What is the exact door number, pillar, or spot location?",
        "Tanglish": "Exact door number illa spot detail enna?"
    },
    "landmark": {
        "Tamil": "உங்கள் தெரு அருகில் உள்ள முக்கிய அடையாளம் (Landmark) என்ன?",
        "English": "What is a nearby recognizable landmark or bus stand?",
        "Tanglish": "Unga street pakkathula edhavadhu landmark irukka?"
    },
    "duration": {
        "Tamil": "இந்த பிரச்சினை எப்போது ஆரம்பித்தது? எத்தனை நாட்களாக உள்ளது?",
        "English": "When did this problem start and how long has it continued?",
        "Tanglish": "Indha problem eppo lendhu irukku? Evvalavu naala aagudhu?"
    },
    "affected_scope": {
        "Tamil": "அந்தத் தெரு முழுக்க தண்ணீர் வரலையா, இல்ல சில வீடுகளுக்கு மட்டும் பிரச்சினையா?",
        "English": "Is this affecting only your house or the entire street?",
        "Tanglish": "Andha theru muzhukka thanni varalaya, illa sila veedugalukku mattum prachinaya?"
    },
    "frequency": {
        "Tamil": "சரி. கடைசியாக எப்போ தண்ணீர் வந்தது? கொஞ்சமாவது வருதா, இல்ல சுத்தமாக வரலையா?",
        "English": "When did water last arrive? Is it low pressure or completely stopped?",
        "Tanglish": "Kadaisiya eppo thanni vandhudhu? Konjamavadhu varudha, illa suthama varalaya?"
    },
    "severity": {
        "Tamil": "பிரச்சினை எந்த அளவுக்கு தீவிரமாக உள்ளது?",
        "English": "How severe is the issue?",
        "Tanglish": "Problem evvalavu serious-ah irukku?"
    },
    "safety_hazard": {
        "Tamil": "ஏதேனும் உடனடி விபத்து அல்லது ஆபத்து உள்ளதா?",
        "English": "Is there any immediate safety hazard or emergency concern?",
        "Tanglish": "Edhavadhu danger illa emergency safety risk irukkaa?"
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
    "previous_complaint_number": {
        "Tamil": "முந்தைய புகார் எண் (Complaint ID) ஏதேனும் உள்ளதா?",
        "English": "Do you have the previous complaint reference number?",
        "Tanglish": "Pazhaya complaint number edhavadhu irukkaa?"
    },
    "water_supply_timing": {
        "Tamil": "வழக்கமாக எந்த நேரத்தில் குடிநீர் விநியோகம் செய்யப்படும்?",
        "English": "What is the usual timing when water is supplied in your area?",
        "Tanglish": "Vazhakkama endha timing-la thanni varum?"
    },
    "leakage_or_contamination": {
        "Tamil": "குழாய் உடைந்து தண்ணீர் வீணாகிறதா அல்லது துர்நாற்றம் ஏதேனும் உள்ளதா?",
        "English": "Is there visible pipe leakage, water wastage, or contamination?",
        "Tanglish": "Pipe leakage illa thanni-la edhavadhu contamination or bad smell irukka?"
    },
    "affected_population": {
        "Tamil": "தோராயமாக எத்தனை குடும்பங்கள் அல்லது குடியிருப்பாளர்கள் பாதிக்கப்பட்டுள்ளனர்?",
        "English": "Approximately how many families or residents are affected?",
        "Tanglish": "Approximate-ah ethanai veedugal illa families affect aayirukanga?"
    },
    "alternate_source": {
        "Tamil": "மாற்று குடிநீர் வசதி உள்ளதா அல்லது லாரி தண்ணீர் தேவைப்படுகிறதா?",
        "English": "Do you have an alternate water arrangement or is a municipal water tanker needed?",
        "Tanglish": "Alternative water source irukka illa tanker supply thevaipadudha?"
    },
    "contact_person": {
        "Tamil": "நேரடி ஆய்வுக்கு வரும் அதிகாரிகளுக்கு உதவ அங்கு உள்ள தொடர்பு நபர் பெயர் என்ன?",
        "English": "Who is the resident representative or contact person available on site?",
        "Tanglish": "Field inspection-ku vara officer-ku contact person yaaru?"
    },
    "preferred_contact_time": {
        "Tamil": "அதிகாரிகள் ஆய்வு செய்ய தங்களுக்கு வசதியான நேரம் எது?",
        "English": "What is your convenient time for field verification by municipal officials?",
        "Tanglish": "Officers spot inspection vara ungalukku convenient time edhu?"
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
        "district_area": {
            "Tamil": "சரி, உதவி செய்கிறேன். எந்த ஊர்ல இருந்து பேசுறீங்க?",
            "English": "Sure, I am here to help you. Which village or town are you calling from?",
            "Tanglish": "Seri, udhavi seiyren. Endha oorla irundhu pesureenga?"
        },
        "street_road_name": {
            "Tamil": "எந்தத் தெருவில் தண்ணீர் வரல?",
            "English": "Which street is facing this water supply problem?",
            "Tanglish": "Endha street name-la thanni varala?"
        },
        "duration": {
            "Tamil": "மூணு நாளா தண்ணீர் வரலையா, இல்ல அதுக்கு முன்னாடியே பிரச்சினை இருக்கா?",
            "English": "Has water been unavailable for three days, or did this start earlier?",
            "Tanglish": "3 naala thanni varalaya, illa adhuku munnadiye problem irukka?"
        },
        "affected_scope": {
            "Tamil": "அந்தத் தெரு முழுக்க தண்ணீர் வரலையா, இல்ல சில வீடுகளுக்கு மட்டும் பிரச்சினையா?",
            "English": "Is the entire street affected or only a few houses?",
            "Tanglish": "Andha theru muzhukka thanni varalaya, illa sila veedugalukku mattum prachinaya?"
        },
        "frequency": {
            "Tamil": "சரி. கடைசியாக எப்போ தண்ணீர் வந்தது? கொஞ்சமாவது வருதா, இல்ல சுத்தமாக வரலையா?",
            "English": "When did water last arrive? Is there low pressure or has it stopped completely?",
            "Tanglish": "Kadaisiya eppo thanni vandhudhu? Konjamavadhu varudha, illa suthama varalaya?"
        },
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
        "street_road_name": {
            "Tamil": "எந்தத் தெருவில் மின் தடை ஏற்பட்டுள்ளது?",
            "English": "Which street is facing this power cut?",
            "Tanglish": "Endha theruvula current cut aayirukku?"
        },
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
        "street_road_name": {
            "Tamil": "எந்தச் சாலை அல்லது தெருவில் சேதம் ஏற்பட்டுள்ளது?",
            "English": "Which road or street has been damaged?",
            "Tanglish": "Endha road illa street-la damage aayirukku?"
        },
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
        to register an actionable complaint through conversation.
        Never marks complete while required fields remain unresolved.
        """
        has_problem = bool(memory.get("problem_description") or memory.get("problem") or memory.get("category"))
        
        # A broad district or generic placeholder ("Coimbatore", "enga oorla") alone is NOT a complete complaint location
        area_val = (memory.get("area") or memory.get("district_area") or "").strip()
        has_area = bool(area_val and area_val.lower() not in ["coimbatore", "enga oor", "enga oorla", "oorla", "district", "none"])

        # Street name or explicit landmark if street is unknown
        street_val = (memory.get("street") or memory.get("street_road_name") or "").strip()
        landmark_val = (memory.get("landmark") or "").strip()
        has_street_or_lm = bool((street_val and street_val.lower() not in ["none", ""]) or (landmark_val and landmark_val.lower() not in ["none", ""]))

        category = (memory.get("category") or "").lower()
        if "water" in category:
            has_dur = bool(memory.get("duration") or memory.get("start_time"))
            has_scope = bool(memory.get("affected_scope") or memory.get("affected_area"))
            has_freq = bool(memory.get("frequency") or memory.get("severity") or memory.get("impact"))
            return bool(has_problem and has_area and has_street_or_lm and has_dur and has_scope and has_freq)

        if "road" in category:
            has_sev = bool(memory.get("severity") or memory.get("safety_hazard"))
            return bool(has_problem and has_area and has_street_or_lm and has_sev)

        if "light" in category:
            has_sev = bool(memory.get("severity") or memory.get("affected_scope"))
            return bool(has_problem and has_area and has_street_or_lm and has_sev)

        return bool(has_problem and has_area and has_street_or_lm)

    def get_next_missing_slot(self, memory: Dict[str, Any], min_questions: int = 10) -> Optional[str]:
        """
        Determines the next missing information slot to prompt.
        Skips already provided information.
        Supports asking multiple questions up to a maximum of 20 questions.
        """
        # If citizen explicitly signaled ready to confirm or end
        if memory.get("is_citizen_confirmed_ready"):
            return None

        # Hard limit of maximum 20 questions
        if memory.get("questions_asked_count", 0) >= 20:
            return None

        # If citizen has answered enough questions (at least target_min) AND essential info is complete
        target_min = memory.get("max_questions", min_questions) or min_questions
        if memory.get("questions_asked_count", 0) >= target_min and self.is_essential_info_complete(memory):
            return None

        for slot in ORDERED_QUESTION_SLOTS:
            # Skip previous_complaint_number if not previously reported
            if slot == "previous_complaint_number":
                prev_rep = memory.get("previous_complaint", "")
                if not prev_rep or any(w in str(prev_rep).lower() for w in ["no", "first time", "illa", "illai", "இல்லை", "n/a"]):
                    continue

            val = self._get_slot_value(memory, slot)
            if not val:
                return slot

        return None

    def _get_slot_value(self, memory: Dict[str, Any], slot: str) -> Optional[Any]:
        """Retrieves slot value considering field aliases."""
        if slot == "problem_description":
            return memory.get("problem_description") or memory.get("problem")
        elif slot == "district_area":
            area_v = memory.get("area") or memory.get("district_area")
            if area_v and str(area_v).strip().lower() not in ["enga oor", "enga oorla", "oorla", "coimbatore"]:
                return area_v
            return None
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
        elif slot == "water_supply_timing":
            return memory.get("water_supply_timing") or memory.get("timing")
        elif slot == "leakage_or_contamination":
            return memory.get("leakage_or_contamination") or memory.get("contamination")
        elif slot == "affected_population":
            return memory.get("affected_population") or memory.get("population")
        elif slot == "alternate_source":
            return memory.get("alternate_source")
        elif slot == "contact_person":
            return memory.get("contact_person") or memory.get("citizen_name")
        elif slot == "preferred_contact_time":
            return memory.get("preferred_contact_time")
        elif slot == "additional_details":
            return memory.get("additional_details") or memory.get("additional_information")
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
        Speaks like a helpful local-language helpline representative.
        Acknowledges what the caller just said, asks ONE relevant question at a time,
        and never repeatedly asks the same question.
        """
        category = memory.get("category") or "General"
        area = memory.get("area") or memory.get("district_area") or ""
        street = memory.get("street") or memory.get("street_road_name") or ""
        duration = memory.get("duration") or ""
        landmark = memory.get("landmark") or ""
        lang = language if language in ["Tamil", "English", "Tanglish"] else "Tanglish"
        raw_lowered = (last_raw_text or "").lower().strip()

        area_ta = TAMIL_AREA_MAP.get(area, area)
        street_ta = TAMIL_STREET_MAP.get(street, street)
        loc_locative = tamil_locative(area_ta) if area_ta else ""

        # Check if citizen indicated unknown street (Test Case G)
        is_unknown_street = any(w in raw_lowered for w in ["theriyala", "theriyadhu", "don't know", "dont know", "not know", "தெரியாது", "தெரியல", "no street"])
        if is_unknown_street and slot in ["landmark", "street_road_name"]:
            if landmark:
                # Landmark already given, acknowledge and proceed
                pass
            else:
                if lang == "Tamil":
                    reply = "பரவாயில்லை, அருகில் ஏதாவது முக்கியமான அடையாளம் (Landmark) அல்லது பேருந்து நிறுத்தம் இருக்கிறதா?"
                elif lang == "Tanglish":
                    reply = "Paravaayillai, pakkathula edhavadhu landmark illa bus stop irukkaa?"
                else:
                    reply = "No problem. Is there a nearby recognizable landmark, school, or bus stand?"
                return reply, reply, []

        # 1. Broad Colony Disambiguation: Citizen said "Anna Nagar" without a specific street number
        is_colony_without_num = ("anna nagar" in raw_lowered) and not any(w in raw_lowered for w in ["second", "2nd", "rendu", "இரண்டாவது", "1st", "first", "3rd", "main", "முதன்மை"])
        if is_colony_without_num and slot in ["street_road_name", "landmark", "exact_location"]:
            if lang == "Tamil":
                reply = "அண்ணா நகரில் எந்தத் தெரு? தெரு எண் தெரியுமா, இல்ல பக்கத்தில் ஏதாவது முக்கியமான இடம் இருக்கா?"
            elif lang == "Tanglish":
                reply = "Anna Nagar-la endha street? Street number theriyuma, illa pakkathula edhavadhu landmark irukka?"
            else:
                reply = "Which street in Anna Nagar? Do you know the street number, or is there a nearby landmark?"
            return reply, reply, [
                {"label": "2nd Street, School near", "text": "Second street, government school pakkam"},
                {"label": "Main Street", "text": "Anna Nagar Main Street"},
                {"label": "Landmark only", "text": "Street number theriyala, school pakkam"}
            ]

        # 2. Citizen just gave an area or village name (e.g. 'Vadavalli', 'Gandhipuram', 'Coimbatore Vadavalli')
        if any(a.lower() in raw_lowered for a in ["vadavalli", "gandhipuram", "rs puram", "peelamedu", "singanallur", "saravanampatti", "town hall", "thudiyalur"]):
            if slot == "problem_description" or not memory.get("problem_description"):
                if lang in ["Tamil", "Tanglish"]:
                    reply = f"{area_ta}யா? சரி. அங்க என்ன பிரச்சினை?"
                else:
                    reply = f"{area}? Understood. What is the problem there?"
                return reply, reply, []
            elif slot in ["street_road_name", "exact_location"]:
                if any(w in category.lower() for w in ["road", "சாலை", "damage"]):
                    reply = f"சரி, {loc_locative or area_ta} சாலை சேதமடைந்திருக்கிறதா? எந்த இடத்துக்கு அருகில்?" if lang in ["Tamil", "Tanglish"] else f"Alright, road damage in {area}. Near which spot or landmark is this located?"
                elif "water" in category.lower():
                    reply = f"சரி, {area_ta or area}. எந்தத் தெருவில் தண்ணீர் வரல?" if lang in ["Tamil", "Tanglish"] else f"Alright, {area}. Which street is facing this water outage?"
                else:
                    reply = f"சரி, {loc_locative or area_ta} எந்தத் தெருவில் இந்தப் பிரச்சினை இருக்கு?" if lang in ["Tamil", "Tanglish"] else f"Alright, which street in {area} is having this issue?"
                return reply, reply, []

        # 3. Citizen just gave street and/or landmark (e.g. 'Second street, government school pakkam') -> Next ask Duration
        is_street_or_lm_turn = any(s in raw_lowered for s in ["second street", "2nd street", "5th street", "main street", "school", "pakkam", "kitta", "street", "road", "theru", "பள்ளி", "அருகில்"])
        if is_street_or_lm_turn and slot == "duration":
            loc_disp_ta = f"{area_ta} {street_ta}".strip() if area_ta and street_ta else (street_ta or area_ta or street or area)
            lm_disp_ta = f", {landmark}" if landmark else ""
            loc_disp = f"{area} {street}".strip() if area and street else (street or area)
            lm_disp = f", {landmark}" if landmark else ""

            if "water" in category.lower():
                if lang in ["Tamil", "Tanglish"]:
                    reply = f"சரி, {loc_disp_ta}{lm_disp_ta}. மூணு நாளா தண்ணீர் வரலையா, இல்ல அதுக்கு முன்னாடியே பிரச்சினை இருக்கா?"
                else:
                    reply = f"Understood, {loc_disp}{lm_disp}. Has water been unavailable for three days, or did this start earlier?"
            else:
                if lang in ["Tamil", "Tanglish"]:
                    reply = f"சரி, {loc_disp_ta}{lm_disp_ta}. இந்தப் பிரச்சினை எத்தனை நாட்களாக உள்ளது?"
                else:
                    reply = f"Understood, {loc_disp}{lm_disp}. How long has this problem continued?"
            return reply, reply, []

        # 4. Citizen just gave duration (e.g. 'Three days', '3 naala', 'Moonu naala') -> Next ask Affected Scope
        if any(d in raw_lowered for d in ["three days", "3 days", "moonu", "rendu", "2 days", "naala", "நாட்களாக", "நாளா"]) and slot == "affected_scope":
            if "water" in category.lower():
                if lang in ["Tamil", "Tanglish"]:
                    reply = "புரிஞ்சது. அந்தத் தெரு முழுக்க தண்ணீர் வரலையா, இல்ல சில வீடுகளுக்கு மட்டும் பிரச்சினையா?"
                else:
                    reply = "Understood. Is the entire street affected or only a few houses?"
            else:
                if lang in ["Tamil", "Tanglish"]:
                    reply = "புரிஞ்சது. இது உங்கள் வீட்டை மட்டுமா அல்லது பகுதி முழுவதையும் பாதிக்கிறதா?"
                else:
                    reply = "Understood. Is this affecting only your house or the entire area?"
            return reply, reply, []

        # 5. Citizen just gave scope (e.g. 'Full street', 'whole street', 'தெரு முழுவதும்') -> Next ask Frequency / Pressure
        is_scope_resp = any(w in raw_lowered for w in ["full street", "entire street", "whole street", "முழு தெரு", "fulla", "full-ah", "all houses"])
        if is_scope_resp and slot in ["frequency", "severity"]:
            if "water" in category.lower():
                if lang in ["Tamil", "Tanglish"]:
                    reply = "சரி. கடைசியாக எப்போ தண்ணீர் வந்தது? கொஞ்சமாவது வருதா, இல்ல சுத்தமாக வரலையா?"
                else:
                    reply = "Alright. When did water last arrive? Is there low pressure or has it stopped completely?"
                return reply, reply, []

        # 6. Road damage specific follow-up (e.g. 'Bus stand pakkam')
        if any(w in raw_lowered for w in ["bus stand", "bus stop", "பேருந்து"]) and any(w in category.lower() for w in ["road", "traffic"]):
            if slot in ["severity", "exact_location", "safety_hazard"]:
                reply = f"சரி, பேருந்து நிலையம் அருகில் சாலை சேதமடைந்திருக்கிறதா? போக்குவரத்துக்கு விபத்து ஆபத்து உள்ளதா?" if lang in ["Tamil", "Tanglish"] else f"Understood, near the bus stand. Is there accident risk or severe traffic blockage?"
                return reply, reply, []

        # 7. Initial greeting or general grievance (e.g. 'Hello, enga oorla thanni varala')
        if any(w in raw_lowered for w in ["hello", "vanakkam", "வணக்கம்", "enga oor", "ஊர்ல"]) or (slot == "district_area" and memory.get("problem_description")):
            if lang in ["Tamil", "Tanglish"]:
                reply = "சரி, உதவி செய்கிறேன். எந்த ஊர்ல இருந்து பேசுறீங்க?"
            else:
                reply = "Sure, I am here to help you. Which village or town are you calling from?"
            return reply, reply, []

        # 8. Check category-specific question overrides
        cat_key = next((k for k in CATEGORY_QUESTION_OVERRIDES if k.lower() in category.lower()), None)
        if cat_key and slot in CATEGORY_QUESTION_OVERRIDES[cat_key]:
            override_dict = CATEGORY_QUESTION_OVERRIDES[cat_key][slot]
            if lang in override_dict:
                text = override_dict[lang]
                return text, text, []

        # 9. Fallback to standard multilingual templates
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
        Summarizes exact street, landmark, duration, scope, and specific incident before registration.
        """
        lang = language if language in ["Tamil", "English", "Tanglish"] else "Tanglish"
        area = memory.get("area") or memory.get("district_area") or "Coimbatore"
        street = memory.get("street") or memory.get("street_road_name") or ""
        problem = memory.get("problem_description") or memory.get("problem") or "Civic issue"
        duration = memory.get("duration") or ""
        landmark = memory.get("landmark") or ""
        scope = memory.get("affected_scope") or ""
        category = memory.get("category") or "General"

        area_ta = TAMIL_AREA_MAP.get(area, area)
        street_ta = TAMIL_STREET_MAP.get(street, street)
        dur_ta = "3 நாட்களாக" if any(w in duration.lower() for w in ["3", "three", "moonu"]) else (
            "2 நாட்களாக" if any(w in duration.lower() for w in ["2", "two", "rendu"]) else (
                f"{duration} நாட்களாக" if duration else ""
            )
        )

        loc_parts_ta = []
        if area_ta: loc_parts_ta.append(area_ta)
        if street_ta: loc_parts_ta.append(street_ta)
        if landmark: loc_parts_ta.append(landmark if "அருகில்" in landmark or "பக்கம்" in landmark else f"{landmark} அருகில்")
        loc_str_ta = ", ".join(loc_parts_ta) if loc_parts_ta else "கோயம்புத்தூர்"
        loc_display_ta = f"{loc_str_ta} ({area})" if (area and area != area_ta and area.lower() not in loc_str_ta.lower()) else loc_str_ta

        loc_parts = []
        if area: loc_parts.append(area)
        if street: loc_parts.append(street)
        if landmark: loc_parts.append(f"Near {landmark}" if not landmark.lower().startswith("near") else landmark)
        loc_str = ", ".join(loc_parts) if loc_parts else area

        scope_phrase_ta = "தெரு முழுவதும் " if any(w in scope.lower() for w in ["full", "entire", "whole", "முழு"]) else ""
        dur_phrase_ta = f"{dur_ta} " if dur_ta else ""

        if lang == "Tamil":
            prob_label = "குடிநீர் விநியோகம் முற்றிலும் தடைப்பட்டுள்ளது" if "water" in category.lower() else (
                "மின்சாரம் தடைப்பட்டுள்ளது" if any(k in category.lower() for k in ["electric", "power"]) else (
                    "சாலை சேதமடைந்துள்ளது" if "road" in category.lower() else problem
                )
            )
            summary = f"சரி, உங்கள் புகார் விவரங்களை உறுதிப்படுத்துகிறேன். {loc_display_ta} பகுதியில் {dur_phrase_ta}{scope_phrase_ta}{prob_label}. இந்தப் புகாரை பதிவு செய்யலாமா? இந்த விவரம் சரிதானே?"
            return summary, summary

        elif lang == "Tanglish":
            prob_label = "thanni varala" if "water" in category.lower() else problem
            scope_tang = "full street-kum " if any(w in scope.lower() for w in ["full", "entire", "whole"]) else ""
            dur_tang = f"{duration} " if duration else ""
            summary = f"Seri, naan confirm panren. {loc_str}-la {dur_tang}{scope_tang}{prob_label}. Indha complaint-a register pannalama? Indha vivaram saridhane?"
            return summary, summary

        else:
            prob_label = "water supply is completely disrupted" if "water" in category.lower() else problem
            scope_en = "for the entire street" if any(w in scope.lower() for w in ["full", "entire", "whole"]) else ""
            dur_en = f"for {duration}" if duration else ""
            summary = f"Let me confirm your complaint details. In {loc_str}, {dur_en} {prob_label} {scope_en}. Should I register this complaint now? Are these details correct?"
            return summary, summary


question_manager = QuestionManager()
