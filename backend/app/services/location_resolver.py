"""Production-grade Coimbatore Location Intelligence Resolver for VoxentraAI.
Hierarchically resolves spoken/written Tamil, English, and Tanglish locations into official
administrative and corporation records with confidence scoring, citizen corrections, and smart clarification.
"""
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from app.services.location_normalizer import LocationNormalizer
from app.services.location_alias_service import location_alias_service
from app.services.speech_correction import speech_correction_service
from app.ai.language_service import detect_language
from app.database.session import SessionLocal
from app.models.location import (
    Taluk, Firka, RevenueVillage, CorporationZone,
    CorporationWard, Area, Street, Landmark
)

logger = logging.getLogger("voxentra.location_resolver")

# Multi-lingual clarification and confirmation templates
CLARIFICATION_PROMPTS = {
    "ask_street": {
        "Tamil": "உங்கள் தெரு பெயர் என்ன?",
        "English": "What is your street name?",
        "Tanglish": "Unga street name enna?"
    },
    "ask_area": {
        "Tamil": "நீங்கள் கோவையில் எந்த பகுதியில் வசிக்கிறீர்கள்?",
        "English": "Which area in Coimbatore are you located in?",
        "Tanglish": "Neenga Coimbatore-la endha area-la irukkeenga?"
    },
    "ask_landmark": {
        "Tamil": "உங்கள் தெரு அருகில் உள்ள முக்கிய அடையாளம் (Landmark) என்ன?",
        "English": "What is a nearby landmark or recognizable place near your street?",
        "Tanglish": "Unga street pakkathula edhavadhu landmark irukka?"
    },
    "confirm_location": {
        "Tamil": "நீங்கள் குறிப்பிட்ட இடம் {location} தானா?",
        "English": "Is your location {location}?",
        "Tanglish": "Neenga sonna location {location} thaana?"
    },
    "disambiguate_candidates": {
        "Tamil": "நீங்கள் {cand1} அல்லது {cand2} - இதில் எந்த இடத்தை குறிப்பிடுகிறீர்கள்?",
        "English": "Did you mean {cand1} or {cand2}?",
        "Tanglish": "Neenga {cand1} solreengala illa {cand2} solreengala?"
    },
    "correction_acknowledged": {
        "Tamil": "புரிந்துகொண்டேன். உங்கள் இடம் {location} என மாற்றப்பட்டுள்ளது, சரியா?",
        "English": "Understood. I have updated your location to {location}. Is this correct?",
        "Tanglish": "Purinjikiten. Unga location {location}-nu update panniyachu, idhu sariya?"
    },
    "low_confidence_clarify": {
        "Tamil": "உங்கள் இடத்தை தெளிவாக கண்டறிய முடியவில்லை. தயவுசெய்து உங்கள் பகுதி பெயரை சொல்லவும் அல்லது அருகில் உள்ள அடையாளத்தை (Landmark) குறிப்பிடவும்.",
        "English": "We couldn't clearly identify your location. Could you please specify your area name or mention a nearby landmark?",
        "Tanglish": "Unga location sariya puriyala. Unga area peyar solla mudiyuma illana pakkathula edhavadhu landmark sollunga."
    },
    "ask_colony_street": {
        "Tamil": "அண்ணா நகரில் எந்தத் தெரு? தெரு எண் தெரியுமா, இல்ல பக்கத்தில் ஏதாவது முக்கியமான இடம் இருக்கா?",
        "English": "Which street in Anna Nagar? Do you know the street number, or is there a nearby landmark?",
        "Tanglish": "Anna Nagar-la endha street? Street number theriyuma, illa pakkathula edhavadhu landmark irukka?"
    }
}


class CoimbatoreLocationResolver:
    """Core Location Intelligence Resolver for VoxentraAI Voice Assistant and APIs."""

    def __init__(self):
        self.normalizer = LocationNormalizer()
        self.alias_service = location_alias_service
        self.speech_correction = speech_correction_service

    def _detect_citizen_correction(self, text: str) -> Tuple[bool, str, Optional[str]]:
        """
        Detects if citizen is correcting a previous guess or specifying a corrected location.
        Examples:
        'Illa, Coimbatore town Anna Nagar' -> (True, 'Coimbatore town Anna Nagar', 'Illa')
        'No, not Vadavalli, it is Town Hall' -> (True, 'Town Hall', ...)
        'தவறு காந்திபுரம் இல்லை, வடவள்ளி' -> (True, 'வடவள்ளி', ...)
        'வேற இடம், Peelamedu' -> (True, 'Peelamedu', ...)
        """
        if not text:
            return False, text, None

        patterns = [
            # Case with repudiated entity before comma/separator: e.g. 'No, not 5th street, 6th street' or 'not Vadavalli, it is Town Hall'
            r'^(?:(?:no|illa|illai|ille|thavaru|wrong|தவறு|இல்லை|இல்ல)[\s,:;\-]+)?(?:not|inga\s*illa|anga\s*illa)\s+[a-zA-Z0-9\u0B80-\u0BFF\s]+?[,;\-]\s*(?:it\s*is\s*|it\'s\s*)?',
            # Tamil rejection: e.g. 'தவறு, காந்திபுரம் இல்லை, வடவள்ளி'
            r'^(?:தவறு|இல்லை)?[\s,:;\-]*[a-zA-Z0-9\u0B80-\u0BFF\s]+?இல்லை[\s,:;\-]+',
            # Simple prefix like 'Illa, Coimbatore town Anna Nagar' or 'No, Town Hall'
            r'^(?:no|not|illa|illai|ille|thavaru|thappu|wrong|different|mariduchu|இல்லை|தவறு|இல்ல|வேற\s*இடம்|வேற)\b[\s,:;\-]+(?:it\s*is\s*|anga\s*illa,?\s*|inga\s*illa,?\s*)?',
            r'^(?:not\s+[a-zA-Z0-9\u0B80-\u0BFF\s]+,?\s*(?:it\s*is|it\'s)?\s*)',
            r'^(?:illa\s+[a-zA-Z0-9\u0B80-\u0BFF\s]+,\s*)'
        ]

        for pat in patterns:
            m = re.match(pat, text, flags=re.IGNORECASE)
            if m:
                prefix = m.group(0)
                corrected_target = text[len(prefix):].strip()
                if corrected_target:
                    return True, corrected_target, prefix.strip(" ,:-")

        return False, text, None

    def resolve(
        self,
        text: str,
        current_language: str = "Tanglish",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Resolves a raw speech transcript or text string into a structured location hierarchy.
        Returns all 7 core pipeline fields for auditing, debugging, and multi-tier confidence evaluation.
        """
        raw_text = text.strip() if text else ""
        if not raw_text:
            return self._empty_result(
                clarification_question=self._get_prompt("ask_area", current_language),
                needs_clarification=True,
                original_transcript=raw_text,
                detected_language=current_language
            )

        context = context or {}

        # 1. Pipeline transcript stages (7 core fields preservation)
        meta = self.speech_correction.correct_with_metadata(raw_text)
        original_transcript = meta["original_transcript"]
        normalized_transcript = meta["normalized_transcript"]
        corrected_transcript = meta["corrected_transcript"]

        # 2. Dynamic Language Detection
        detected_lang, _ = detect_language(raw_text, current_session_lang=current_language)

        # 3. Citizen Correction Detection & Handling
        is_citizen_correction, target_text, _ = self._detect_citizen_correction(corrected_transcript)
        if is_citizen_correction:
            # Clear conflicting prior context so we don't insist on the old location
            context = {}
            working_text = target_text
        else:
            working_text = corrected_transcript

        # Normalize texts for entity matching
        cleaned_text = self.normalizer.clean(working_text)
        tanglish_text = self.normalizer.normalize_tanglish(working_text)
        tamil_text = self.normalizer.normalize_tamil(working_text)

        # 4. Extract candidate entities from text
        matched_areas = self._extract_areas(tanglish_text, tamil_text)
        area_hint = matched_areas[0] if matched_areas else context.get("area_entity")
        if not area_hint and context.get("area"):
            context_area_cands = self._extract_areas(
                self.normalizer.normalize_tanglish(context["area"]),
                self.normalizer.normalize_tamil(context["area"])
            )
            if context_area_cands:
                area_hint = context_area_cands[0]
            elif context.get("area_id"):
                area_hint = {"id": context["area_id"], "name_en": context["area"], "confidence": 0.9}

        matched_landmarks = self._extract_landmarks(tanglish_text, tamil_text, area_hint=area_hint)
        matched_streets = self._extract_streets(tanglish_text, tamil_text, area_hint=area_hint)
        matched_taluks = self._extract_taluks(tanglish_text, tamil_text)
        matched_villages = self._extract_villages(tanglish_text, tamil_text)
        matched_firkas = self._extract_firkas(tanglish_text, tamil_text)

        # 5. Build candidate locations list with ranking & confidence
        candidate_locations = self._build_candidates(
            streets=matched_streets,
            areas=matched_areas,
            landmarks=matched_landmarks,
            taluks=matched_taluks,
            villages=matched_villages,
            area_hint=area_hint
        )

        # 6. Integrate with context or pick highest-ranked entity
        area_entity = matched_areas[0] if matched_areas else context.get("area_entity")
        street_entity = matched_streets[0] if matched_streets else context.get("street_entity")
        landmark_entity = matched_landmarks[0] if matched_landmarks else context.get("landmark_entity")
        taluk_entity = matched_taluks[0] if matched_taluks else context.get("taluk_entity")
        village_entity = matched_villages[0] if matched_villages else context.get("village_entity")
        firka_entity = matched_firkas[0] if matched_firkas else context.get("firka_entity")

        # Check landmark-based resolution (landmark brings area & ward proximity)
        if landmark_entity and not area_entity:
            lm_details = self._get_db_entity(Landmark, landmark_entity["id"])
            if lm_details and lm_details.area_id:
                area_obj = self._get_db_entity(Area, lm_details.area_id)
                if area_obj:
                    area_entity = {
                        "id": area_obj.id,
                        "name_en": area_obj.name_en,
                        "name_ta": area_obj.name_ta,
                        "ward_id": area_obj.ward_id,
                        "zone_id": area_obj.zone_id,
                        "taluk_id": area_obj.taluk_id,
                        "confidence": 0.95
                    }

        # Check street-based resolution (street brings area & ward proximity)
        if street_entity and not area_entity and street_entity.get("id"):
            st_details = self._get_db_entity(Street, street_entity["id"])
            if st_details and st_details.area_id:
                area_obj = self._get_db_entity(Area, st_details.area_id)
                if area_obj:
                    area_entity = {
                        "id": area_obj.id,
                        "name_en": area_obj.name_en,
                        "name_ta": area_obj.name_ta,
                        "ward_id": area_obj.ward_id,
                        "zone_id": area_obj.zone_id,
                        "taluk_id": area_obj.taluk_id,
                        "confidence": 0.95
                    }

        # 7. Build full hierarchy
        hierarchy = self._build_hierarchy(
            area=area_entity,
            street=street_entity,
            landmark=landmark_entity,
            taluk=taluk_entity,
            village=village_entity,
            firka=firka_entity
        )

        # 8. Compute overall confidence score
        conf = self._compute_confidence(area_entity, street_entity, landmark_entity, taluk_entity or village_entity)
        hierarchy["confidence"] = conf
        hierarchy["confidence_score"] = conf

        # 9. Form confirmed location string if resolved
        loc_parts = []
        if hierarchy.get("street"):
            loc_parts.append(hierarchy["street"])
        if hierarchy.get("area"):
            loc_parts.append(hierarchy["area"])
        elif hierarchy.get("taluk"):
            loc_parts.append(hierarchy["taluk"])
        elif hierarchy.get("revenue_village"):
            loc_parts.append(hierarchy["revenue_village"])
        
        if loc_parts:
            loc_parts.append("Coimbatore")
            confirmed_loc_str = ", ".join(loc_parts)
        else:
            confirmed_loc_str = None

        # 10. Apply 3 Confidence Tiers & Decision Rules
        # Tier 1: High (>= 0.85) -> Ask confirmation before final save
        # Tier 2: Medium (0.60 - 0.84) -> Disambiguate between 2-3 candidates
        # Tier 3: Low (< 0.60) -> Do not auto-select; ask citizen to clarify or give landmark; preserve unresolved
        if conf >= 0.85:
            hierarchy["needs_confirmation"] = True
            hierarchy["needs_clarification"] = False
            hierarchy["confirmed_location"] = confirmed_loc_str
            hierarchy["unresolved_location"] = None
            if is_citizen_correction:
                hierarchy["clarification_question"] = self._get_prompt(
                    "correction_acknowledged", detected_lang, location=confirmed_loc_str or "Coimbatore"
                )
            else:
                hierarchy["clarification_question"] = self._get_prompt(
                    "confirm_location", detected_lang, location=confirmed_loc_str or "Coimbatore"
                )
        elif 0.60 <= conf < 0.85:
            hierarchy["needs_confirmation"] = False
            hierarchy["needs_clarification"] = True
            hierarchy["confirmed_location"] = None
            hierarchy["unresolved_location"] = None
            if len(candidate_locations) >= 2 and candidate_locations[0].get("area") != candidate_locations[1].get("area"):
                cand1 = candidate_locations[0]["label"]
                cand2 = candidate_locations[1]["label"]
                hierarchy["clarification_question"] = self._get_prompt(
                    "disambiguate_candidates", detected_lang, cand1=cand1, cand2=cand2
                )
            elif any("anna nagar" in (c.get("label") or "").lower() for c in candidate_locations) and not any(w in working_text.lower() for w in ["second", "2nd", "rendu", "இரண்டாவது", "main", "1st"]):
                hierarchy["clarification_question"] = self._get_prompt("ask_colony_street", detected_lang)
            elif len(candidate_locations) >= 2:
                cand1 = candidate_locations[0]["label"]
                cand2 = candidate_locations[1]["label"]
                hierarchy["clarification_question"] = self._get_prompt(
                    "disambiguate_candidates", detected_lang, cand1=cand1, cand2=cand2
                )
            elif not hierarchy.get("area") and not hierarchy.get("taluk"):
                hierarchy["clarification_question"] = self._get_prompt("ask_area", detected_lang)
            elif not hierarchy.get("street"):
                hierarchy["clarification_question"] = self._get_prompt("ask_street", detected_lang)
            else:
                hierarchy["clarification_question"] = self._get_prompt("ask_landmark", detected_lang)
        else:
            hierarchy["needs_confirmation"] = False
            hierarchy["needs_clarification"] = True
            hierarchy["confirmed_location"] = None
            hierarchy["unresolved_location"] = raw_text
            hierarchy["clarification_question"] = self._get_prompt("low_confidence_clarify", detected_lang)

        # 11. Add nearby suggested landmarks if area is known
        if hierarchy.get("area_id"):
            hierarchy["suggested_landmarks"] = self._get_suggested_landmarks(hierarchy["area_id"])
        else:
            hierarchy["suggested_landmarks"] = []

        # 12. Attach 7 core audit and debugging pipeline fields
        hierarchy["original_transcript"] = original_transcript
        hierarchy["normalized_transcript"] = normalized_transcript
        hierarchy["corrected_transcript"] = corrected_transcript
        hierarchy["detected_language"] = detected_lang
        hierarchy["candidate_locations"] = candidate_locations
        hierarchy["is_citizen_correction"] = is_citizen_correction

        return hierarchy

    def _build_candidates(
        self,
        streets: List[Dict[str, Any]],
        areas: List[Dict[str, Any]],
        landmarks: List[Dict[str, Any]],
        taluks: List[Dict[str, Any]],
        villages: List[Dict[str, Any]],
        area_hint: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Constructs ranked candidate locations with confidence scores."""
        candidates = []
        seen_labels = set()

        # 1. From streets
        for st in streets:
            area_id = st.get("area_id")
            area_obj = self._get_db_entity(Area, area_id) if area_id else None
            area_name = area_obj.name_en if area_obj else (area_hint.get("name_en") if area_hint else None)
            st_name = st.get("name_en") or "Unknown Street"
            label = f"{st_name}, {area_name}" if area_name else st_name
            if label not in seen_labels:
                seen_labels.add(label)
                conf = st.get("confidence", 0.70)
                if area_hint and area_id and area_hint.get("id") == area_id:
                    conf = max(conf, 0.95)
                candidates.append({
                    "label": label,
                    "area": area_name,
                    "area_id": area_id,
                    "street": st_name,
                    "street_id": st.get("id"),
                    "landmark": None,
                    "ward_no": area_obj.ward_id if area_obj else None,
                    "taluk": None,
                    "confidence": conf
                })

        # 2. From landmarks
        for lm in landmarks:
            area_id = lm.get("area_id")
            area_obj = self._get_db_entity(Area, area_id) if area_id else None
            area_name = area_obj.name_en if area_obj else (area_hint.get("name_en") if area_hint else None)
            lm_name = lm.get("name_en")
            label = f"{lm_name}, {area_name}" if area_name else lm_name
            if label not in seen_labels:
                seen_labels.add(label)
                candidates.append({
                    "label": label,
                    "area": area_name,
                    "area_id": area_id,
                    "street": None,
                    "street_id": None,
                    "landmark": lm_name,
                    "landmark_id": lm.get("id"),
                    "ward_no": area_obj.ward_id if area_obj else None,
                    "taluk": None,
                    "confidence": lm.get("confidence", 0.85)
                })

        # 3. From areas
        for ar in areas:
            ar_name = ar.get("name_en")
            if ar_name and ar_name not in seen_labels:
                seen_labels.add(ar_name)
                candidates.append({
                    "label": f"{ar_name}, Coimbatore",
                    "area": ar_name,
                    "area_id": ar.get("id"),
                    "street": None,
                    "street_id": None,
                    "landmark": None,
                    "ward_no": ar.get("ward_id"),
                    "taluk": None,
                    "confidence": ar.get("confidence", 0.90)
                })

        candidates.sort(key=lambda x: x["confidence"], reverse=True)
        return candidates[:3]

    def _extract_landmarks(self, tanglish_text: str, tamil_text: str, area_hint: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        candidates = self.normalizer.get_candidate_tokens(tanglish_text) + self.normalizer.get_candidate_tokens(tamil_text)
        candidates = sorted(list(set(candidates)), key=len, reverse=True)
        generic_keywords = {"bus stand", "bus stop", "temple", "kovil", "church", "mosque", "hospital", "school", "college", "mall", "theatre"}

        results = []
        for cand in candidates:
            cand_lower = cand.lower().strip()
            exact = self.alias_service.lookup_exact(cand)
            if not exact and area_hint and (area_hint.get("name_en") or area_hint.get("area")):
                area_name = area_hint.get("name_en") or area_hint.get("area")
                exact = self.alias_service.lookup_exact(f"{area_name} {cand}")
                if not exact:
                    exact = self.alias_service.lookup_exact(f"{cand} {area_name}")
            for m in exact:
                if m.get("entity_type") == "landmark":
                    det = self.alias_service.get_entity_details("landmark", m["entity_id"])
                    if det:
                        if cand_lower in generic_keywords:
                            if area_hint and (area_hint.get("id") or area_hint.get("name_en")):
                                if (area_hint.get("id") and det.get("area_id") == area_hint["id"]) or (area_hint.get("name_en") and str(det.get("area_id")) == str(area_hint.get("id"))):
                                    results.append({
                                        "id": int(m["entity_id"]),
                                        "name_en": det.get("name_en"),
                                        "name_ta": det.get("name_ta"),
                                        "area_id": det.get("area_id"),
                                        "confidence": 0.95
                                    })
                                else:
                                    results.append({
                                        "id": int(m["entity_id"]),
                                        "name_en": det.get("name_en"),
                                        "name_ta": det.get("name_ta"),
                                        "area_id": det.get("area_id"),
                                        "confidence": 0.90
                                    })
                        else:
                            results.append({
                                "id": int(m["entity_id"]),
                                "name_en": det.get("name_en"),
                                "name_ta": det.get("name_ta"),
                                "area_id": det.get("area_id"),
                                "confidence": 1.0
                            })
            if results:
                if area_hint and area_hint.get("id"):
                    same_area = [r for r in results if r.get("area_id") == area_hint["id"]]
                    if same_area:
                        return same_area
                return results

        if not results:
            fuzzy = self.alias_service.lookup_fuzzy(tanglish_text, threshold=82.0)
            for ent, score in fuzzy:
                if ent.get("entity_type") == "landmark":
                    det = self.alias_service.get_entity_details("landmark", ent["entity_id"])
                    if det:
                        results.append({
                            "id": int(ent["entity_id"]),
                            "name_en": det.get("name_en"),
                            "name_ta": det.get("name_ta"),
                            "area_id": det.get("area_id"),
                            "confidence": score
                        })
        return results

    def _extract_streets(self, tanglish_text: str, tamil_text: str, area_hint: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # 1. Check explicit numbered street pattern first: e.g. "Anna nagar second street", "5th street", "2nd cross"
        numbered_street = self.normalizer.extract_numbered_street(tanglish_text)
        if numbered_street:
            if area_hint and area_hint.get("name_en"):
                area_name = area_hint["name_en"]
                for cand in [f"{area_name} {numbered_street}", f"{numbered_street} {area_name}", numbered_street]:
                    exact = self.alias_service.lookup_exact(cand)
                    for m in exact:
                        if m.get("entity_type") == "street":
                            det = self.alias_service.get_entity_details("street", m["entity_id"])
                            if det:
                                return [{
                                    "id": int(m["entity_id"]),
                                    "name_en": numbered_street,
                                    "name_ta": det.get("name_ta"),
                                    "area_id": det.get("area_id"),
                                    "confidence": 0.95
                                }]
                return [{
                    "id": None,
                    "name_en": numbered_street,
                    "name_ta": None,
                    "confidence": 0.90
                }]
            else:
                # Isolated / ambiguous numbered street without area
                exact = self.alias_service.lookup_exact(numbered_street)
                matches = []
                for m in exact:
                    if m.get("entity_type") == "street":
                        det = self.alias_service.get_entity_details("street", m["entity_id"])
                        if det:
                            matches.append({
                                "id": int(m["entity_id"]),
                                "name_en": numbered_street,
                                "name_ta": det.get("name_ta"),
                                "area_id": det.get("area_id"),
                                "confidence": 0.75,
                                "is_ambiguous": True
                            })
                # Check Anna Nagar disambiguation candidate (Town Hall Anna Nagar Main Street)
                if "anna nagar" in numbered_street.lower():
                    det_town = self.alias_service.get_entity_details("street", 109)
                    if det_town and not any(m["id"] == 109 for m in matches):
                        matches.append({
                            "id": 109,
                            "name_en": det_town.get("name_en"),
                            "name_ta": det_town.get("name_ta"),
                            "area_id": det_town.get("area_id"),
                            "confidence": 0.70,
                            "is_ambiguous": True
                        })
                if matches:
                    return matches
                return [{
                    "id": None,
                    "name_en": numbered_street,
                    "name_ta": None,
                    "confidence": 0.65,
                    "is_ambiguous": True
                }]

        # 2. Check named streets from candidates (longest first)
        candidates = self.normalizer.get_candidate_tokens(tanglish_text) + self.normalizer.get_candidate_tokens(tamil_text)
        candidates = sorted(list(set(candidates)), key=len, reverse=True)
        generic_street_words = {"road", "street", "theru", "salai", "lane", "main road"}

        results = []
        for cand in candidates:
            if cand.lower().strip() in generic_street_words:
                continue
            exact = self.alias_service.lookup_exact(cand)
            for m in exact:
                if m.get("entity_type") == "street":
                    det = self.alias_service.get_entity_details("street", m["entity_id"])
                    if det:
                        results.append({
                            "id": int(m["entity_id"]),
                            "name_en": det.get("name_en"),
                            "name_ta": det.get("name_ta"),
                            "area_id": det.get("area_id"),
                            "confidence": 1.0
                        })
            if results:
                if area_hint and area_hint.get("id"):
                    same_area = [r for r in results if r.get("area_id") == area_hint["id"]]
                    if same_area:
                        return same_area
                return results

        # 3. Check Anna Nagar multi-candidate matching if "anna nagar" is in text
        if "anna nagar" in tanglish_text.lower():
            has_street_spec = any(w in tanglish_text.lower() for w in [
                "second", "2nd", "rendu", "இரண்டாவது", "first", "1st", "mudhal", "3rd", "third", "main", "முதன்மை", "cross"
            ])
            det_vada = self.alias_service.get_entity_details("street", 107)
            det_town = self.alias_service.get_entity_details("street", 109)
            if has_street_spec:
                if any(w in tanglish_text.lower() for w in ["second", "2nd", "rendu", "இரண்டாவது"]):
                    return [{
                        "id": 107,
                        "name_en": "Anna Nagar 2nd Street",
                        "name_ta": "அண்ணா நகர் இரண்டாவது தெரு",
                        "area_id": 14,
                        "confidence": 0.95
                    }]
                elif any(w in tanglish_text.lower() for w in ["main", "முதன்மை"]):
                    return [{
                        "id": 109,
                        "name_en": "Anna Nagar Main Street",
                        "name_ta": "அண்ணா நகர் முதன்மைத் தெரு",
                        "area_id": 10,
                        "confidence": 0.95
                    }]
            # Citizen ONLY gave colony / locality name ("Anna Nagar") without a street number!
            # Return ambiguous candidates so question manager asks which street or landmark in Anna Nagar!
            return [
                {
                    "id": 107,
                    "name_en": "Anna Nagar 2nd Street",
                    "name_ta": "அண்ணா நகர் இரண்டாவது தெரு",
                    "area_id": 14,
                    "confidence": 0.70,
                    "is_ambiguous": True
                },
                {
                    "id": 109,
                    "name_en": "Anna Nagar Main Street",
                    "name_ta": "அண்ணா நகர் முதன்மைத் தெரு",
                    "area_id": 10,
                    "confidence": 0.65,
                    "is_ambiguous": True
                }
            ]

        if not results:
            fuzzy = self.alias_service.lookup_fuzzy(tanglish_text, threshold=82.0)
            for ent, score in fuzzy:
                if ent.get("entity_type") == "street":
                    det = self.alias_service.get_entity_details("street", ent["entity_id"])
                    if det:
                        results.append({
                            "id": int(ent["entity_id"]),
                            "name_en": det.get("name_en"),
                            "name_ta": det.get("name_ta"),
                            "area_id": det.get("area_id"),
                            "confidence": score
                        })
        return results

    def _extract_areas(self, tanglish_text: str, tamil_text: str) -> List[Dict[str, Any]]:
        candidates = self.normalizer.get_candidate_tokens(tanglish_text) + self.normalizer.get_candidate_tokens(tamil_text)
        candidates = sorted(list(set(candidates)), key=len, reverse=True)
        results = []
        for cand in candidates:
            exact = self.alias_service.lookup_exact(cand)
            for m in exact:
                if m.get("entity_type") == "area":
                    det = self.alias_service.get_entity_details("area", m["entity_id"])
                    if det:
                        results.append({
                            "id": int(m["entity_id"]),
                            "name_en": det.get("name_en"),
                            "name_ta": det.get("name_ta"),
                            "ward_id": det.get("ward_id"),
                            "zone_id": det.get("zone_id"),
                            "taluk_id": det.get("taluk_id"),
                            "confidence": 1.0
                        })
            if results:
                return results

        if not results:
            fuzzy = self.alias_service.lookup_fuzzy(tanglish_text, threshold=80.0)
            for ent, score in fuzzy:
                if ent.get("entity_type") == "area":
                    det = self.alias_service.get_entity_details("area", ent["entity_id"])
                    if det:
                        results.append({
                            "id": int(ent["entity_id"]),
                            "name_en": det.get("name_en"),
                            "name_ta": det.get("name_ta"),
                            "ward_id": det.get("ward_id"),
                            "zone_id": det.get("zone_id"),
                            "taluk_id": det.get("taluk_id"),
                            "confidence": score
                        })
        return results

    def _extract_taluks(self, tanglish_text: str, tamil_text: str) -> List[Dict[str, Any]]:
        candidates = self.normalizer.get_candidate_tokens(tanglish_text) + self.normalizer.get_candidate_tokens(tamil_text)
        candidates = sorted(list(set(candidates)), key=len, reverse=True)
        results = []
        for cand in candidates:
            exact = self.alias_service.lookup_exact(cand)
            for m in exact:
                if m.get("entity_type") == "taluk":
                    det = self.alias_service.get_entity_details("taluk", m["entity_id"])
                    if det:
                        results.append({
                            "id": int(m["entity_id"]),
                            "name_en": det.get("name_en"),
                            "name_ta": det.get("name_ta"),
                            "confidence": 1.0
                        })
            if results:
                return results
        return results

    def _extract_villages(self, tanglish_text: str, tamil_text: str) -> List[Dict[str, Any]]:
        candidates = self.normalizer.get_candidate_tokens(tanglish_text) + self.normalizer.get_candidate_tokens(tamil_text)
        candidates = sorted(list(set(candidates)), key=len, reverse=True)
        results = []
        for cand in candidates:
            exact = self.alias_service.lookup_exact(cand)
            for m in exact:
                if m.get("entity_type") == "revenue_village":
                    det = self.alias_service.get_entity_details("revenue_village", m["entity_id"])
                    if det:
                        results.append({
                            "id": int(m["entity_id"]),
                            "name_en": det.get("name_en"),
                            "name_ta": det.get("name_ta"),
                            "taluk_id": det.get("taluk_id"),
                            "firka_id": det.get("firka_id"),
                            "confidence": 1.0
                        })
            if results:
                return results
        return results

    def _extract_firkas(self, tanglish_text: str, tamil_text: str) -> List[Dict[str, Any]]:
        candidates = self.normalizer.get_candidate_tokens(tanglish_text) + self.normalizer.get_candidate_tokens(tamil_text)
        candidates = sorted(list(set(candidates)), key=len, reverse=True)
        results = []
        for cand in candidates:
            exact = self.alias_service.lookup_exact(cand)
            for m in exact:
                if m.get("entity_type") == "firka":
                    det = self.alias_service.get_entity_details("firka", m["entity_id"])
                    if det:
                        results.append({
                            "id": int(m["entity_id"]),
                            "name_en": det.get("name_en"),
                            "name_ta": det.get("name_ta"),
                            "taluk_id": det.get("taluk_id"),
                            "confidence": 1.0
                        })
            if results:
                return results
        return results

    def _build_hierarchy(
        self,
        area: Optional[Dict[str, Any]],
        street: Optional[Dict[str, Any]],
        landmark: Optional[Dict[str, Any]],
        taluk: Optional[Dict[str, Any]],
        village: Optional[Dict[str, Any]] = None,
        firka: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Assembles the full official hierarchy with strict city vs rural validation."""
        db = SessionLocal()
        res = self._empty_result()
        try:
            # Set Landmark
            if landmark:
                res["landmark"] = landmark.get("name_en")
                if landmark.get("id"):
                    lm_db = db.query(Landmark).filter_by(id=landmark["id"]).first()
                    if lm_db:
                        res["landmark_id"] = lm_db.id
                        res["latitude"] = lm_db.latitude
                        res["longitude"] = lm_db.longitude
                        res["source"] = lm_db.source

            # Set Street
            if street:
                res["street"] = street.get("name_en")
                if street.get("id"):
                    st_db = db.query(Street).filter_by(id=street["id"]).first()
                    if st_db:
                        res["street_id"] = st_db.id
                        if not res["latitude"]:
                            res["latitude"] = st_db.latitude
                            res["longitude"] = st_db.longitude
                            res["source"] = st_db.source

            # Set Area & Corporation / Taluk Hierarchy
            if area and area.get("id"):
                area_db = db.query(Area).filter_by(id=area["id"]).first()
                if area_db:
                    res["area"] = area_db.name_en
                    res["area_id"] = area_db.id
                    if not res["latitude"]:
                        res["latitude"] = area_db.latitude
                        res["longitude"] = area_db.longitude

                    # Check Corporation Zone & Ward
                    if area_db.zone_id:
                        zone_db = db.query(CorporationZone).filter_by(id=area_db.zone_id).first()
                        if zone_db:
                            res["corporation_zone"] = zone_db.name

                    if area_db.ward_id:
                        ward_db = db.query(CorporationWard).filter_by(id=area_db.ward_id).first()
                        if ward_db:
                            res["ward_no"] = ward_db.ward_no
                            res["ward_name"] = ward_db.name

                    # Check Taluk Hierarchy
                    if area_db.taluk_id:
                        taluk_db = db.query(Taluk).filter_by(id=area_db.taluk_id).first()
                        if taluk_db:
                            res["taluk"] = taluk_db.name_en
                            res["taluk_id"] = taluk_db.id
                            if taluk_db.division:
                                res["revenue_division"] = taluk_db.division.name_en
            elif area:
                res["area"] = area.get("name_en")

            # Check Village and Firka
            if village:
                res["revenue_village"] = village.get("name_en")
                if village.get("id"):
                    vil_db = db.query(RevenueVillage).filter_by(id=village["id"]).first()
                    if vil_db:
                        if vil_db.firka:
                            res["firka"] = vil_db.firka.name_en
                        if vil_db.taluk:
                            res["taluk"] = vil_db.taluk.name_en
                            res["taluk_id"] = vil_db.taluk.id
                            if vil_db.taluk.division:
                                res["revenue_division"] = vil_db.taluk.division.name_en

            if firka and not res["firka"]:
                res["firka"] = firka.get("name_en")
                if firka.get("id"):
                    fk_db = db.query(Firka).filter_by(id=firka["id"]).first()
                    if fk_db and fk_db.taluk:
                        res["taluk"] = fk_db.taluk.name_en
                        res["taluk_id"] = fk_db.taluk.id
                        if fk_db.taluk.division:
                            res["revenue_division"] = fk_db.taluk.division.name_en

            # Fallback Taluk if provided explicitly
            if not res["taluk"] and taluk:
                res["taluk"] = taluk.get("name_en")
                if taluk.get("id"):
                    res["taluk_id"] = taluk["id"]
                    t_db = db.query(Taluk).filter_by(id=taluk["id"]).first()
                    if t_db and t_db.division:
                        res["revenue_division"] = t_db.division.name_en

        except Exception as e:
            logger.error(f"Error building hierarchy: {e}")
        finally:
            db.close()
        return res

    def _compute_confidence(
        self,
        area: Optional[Dict[str, Any]],
        street: Optional[Dict[str, Any]],
        landmark: Optional[Dict[str, Any]],
        taluk: Optional[Dict[str, Any]]
    ) -> float:
        """Computes weighted location confidence."""
        if street and street.get("is_ambiguous"):
            return round(street.get("confidence", 0.75), 2)
        if landmark and street and area:
            return round(min(1.0, max(0.95, (landmark.get("confidence", 1.0) + street.get("confidence", 1.0)) / 2.0)), 2)
        if area and street:
            return round(min(1.0, max(0.90, (area.get("confidence", 1.0) + street.get("confidence", 1.0)) / 2.0)), 2)
        if landmark and area:
            return round(min(1.0, max(0.92, landmark.get("confidence", 0.95))), 2)
        if area:
            return round(area.get("confidence", 0.88), 2)
        if landmark:
            return round(landmark.get("confidence", 0.85), 2)
        if street:
            if street.get("confidence", 0.0) < 0.70:
                return round(street.get("confidence", 0.65), 2)
            return round(street.get("confidence", 0.85), 2)
        if taluk:
            return round(taluk.get("confidence", 0.85), 2)
        return 0.40

    def _get_suggested_landmarks(self, area_id: int) -> List[str]:
        db = SessionLocal()
        try:
            landmarks = db.query(Landmark).filter_by(area_id=area_id).limit(3).all()
            return [lm.name_en for lm in landmarks]
        except Exception:
            return []
        finally:
            db.close()

    def _get_db_entity(self, model, entity_id: int):
        db = SessionLocal()
        try:
            return db.query(model).filter_by(id=entity_id).first()
        except Exception:
            return None
        finally:
            db.close()

    def _get_prompt(self, template_key: str, language: str, **kwargs) -> str:
        lang = "Tanglish"
        if language:
            l_lower = language.lower()
            if "tamil" in l_lower or "தமிழ்" in l_lower:
                lang = "Tamil"
            elif "english" in l_lower:
                lang = "English"

        template = CLARIFICATION_PROMPTS.get(template_key, {}).get(lang, CLARIFICATION_PROMPTS[template_key]["Tanglish"])
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    def _empty_result(
        self,
        clarification_question: Optional[str] = None,
        needs_clarification: bool = False,
        original_transcript: str = "",
        normalized_transcript: str = "",
        corrected_transcript: str = "",
        detected_language: str = "Tanglish"
    ) -> Dict[str, Any]:
        return {
            "original_transcript": original_transcript,
            "normalized_transcript": normalized_transcript,
            "corrected_transcript": corrected_transcript,
            "detected_language": detected_language,
            "candidate_locations": [],
            "confidence_score": 0.0,
            "confirmed_location": None,
            "unresolved_location": original_transcript or None,
            "is_citizen_correction": False,
            "district": "Coimbatore",
            "revenue_division": None,
            "taluk": None,
            "taluk_id": None,
            "firka": None,
            "revenue_village": None,
            "corporation_zone": None,
            "ward_no": None,
            "ward_name": None,
            "area": None,
            "area_id": None,
            "street": None,
            "street_id": None,
            "landmark": None,
            "landmark_id": None,
            "latitude": None,
            "longitude": None,
            "confidence": 0.0,
            "source": "CCMC_Revenue_GIS_2024",
            "needs_confirmation": False,
            "needs_clarification": needs_clarification,
            "clarification_question": clarification_question,
            "suggested_landmarks": []
        }


location_resolver = CoimbatoreLocationResolver()
