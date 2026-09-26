"""Production-grade Coimbatore Location Intelligence Resolver for VoxentraAI.
Hierarchically resolves spoken/written Tamil, English, and Tanglish locations into official
administrative and corporation records with confidence scoring and smart clarification.
"""
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from app.services.location_normalizer import LocationNormalizer
from app.services.location_alias_service import location_alias_service
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
    }
}

class CoimbatoreLocationResolver:
    """Core Location Intelligence Resolver for VoxentraAI Voice Assistant and APIs."""

    def __init__(self):
        self.normalizer = LocationNormalizer()
        self.alias_service = location_alias_service

    def resolve(
        self,
        text: str,
        current_language: str = "Tanglish",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Resolves a raw speech transcript or text string into a structured location hierarchy."""
        if not text or not text.strip():
            return self._empty_result(
                clarification_question=self._get_prompt("ask_area", current_language),
                needs_clarification=True
            )

        context = context or {}
        cleaned_text = self.normalizer.clean(text)
        tanglish_text = self.normalizer.normalize_tanglish(text)
        tamil_text = self.normalizer.normalize_tamil(text)

        # 1. Extract candidate entities from text
        matched_areas = self._extract_areas(tanglish_text, tamil_text)
        area_hint = matched_areas[0] if matched_areas else context.get("area_entity")

        matched_landmarks = self._extract_landmarks(tanglish_text, tamil_text, area_hint=area_hint)
        matched_streets = self._extract_streets(tanglish_text, tamil_text, area_hint=area_hint)
        matched_taluks = self._extract_taluks(tanglish_text, tamil_text)

        # 2. Integrate with previous conversation context if available
        area_entity = matched_areas[0] if matched_areas else context.get("area_entity")
        street_entity = matched_streets[0] if matched_streets else context.get("street_entity")
        landmark_entity = matched_landmarks[0] if matched_landmarks else context.get("landmark_entity")
        taluk_entity = matched_taluks[0] if matched_taluks else context.get("taluk_entity")

        # 3. Check landmark-based resolution (landmark brings area & ward proximity)
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

        # 4. Check street-based resolution (street brings area & ward proximity)
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

        # 5. Build full hierarchy
        hierarchy = self._build_hierarchy(
            area=area_entity,
            street=street_entity,
            landmark=landmark_entity,
            taluk=taluk_entity
        )

        # 6. Compute overall confidence score
        conf = self._compute_confidence(area_entity, street_entity, landmark_entity, taluk_entity)
        hierarchy["confidence"] = conf

        # 7. Apply Decision Rules:
        # >= 0.85: accept automatically
        # 0.70 - 0.84: ask confirmation question
        # < 0.70: ask for clarification
        if conf >= 0.85:
            hierarchy["needs_confirmation"] = False
            hierarchy["needs_clarification"] = False
            hierarchy["clarification_question"] = None
        elif 0.70 <= conf < 0.85:
            hierarchy["needs_confirmation"] = True
            hierarchy["needs_clarification"] = False
            loc_label = hierarchy.get("area") or hierarchy.get("taluk") or "Coimbatore"
            hierarchy["clarification_question"] = self._get_prompt(
                "confirm_location", current_language, location=loc_label
            )
        else:
            hierarchy["needs_confirmation"] = False
            hierarchy["needs_clarification"] = True
            # Smart single question follow up based on what's missing
            if not hierarchy.get("area") and not hierarchy.get("taluk"):
                hierarchy["clarification_question"] = self._get_prompt("ask_area", current_language)
            elif not hierarchy.get("street"):
                hierarchy["clarification_question"] = self._get_prompt("ask_street", current_language)
            elif not hierarchy.get("landmark"):
                hierarchy["clarification_question"] = self._get_prompt("ask_landmark", current_language)

        # 8. Add nearby suggested landmarks if area is known
        if hierarchy.get("area_id"):
            hierarchy["suggested_landmarks"] = self._get_suggested_landmarks(hierarchy["area_id"])
        else:
            hierarchy["suggested_landmarks"] = []

        return hierarchy

    def _extract_landmarks(self, tanglish_text: str, tamil_text: str, area_hint: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        candidates = self.normalizer.get_candidate_tokens(tanglish_text) + self.normalizer.get_candidate_tokens(tamil_text)
        candidates = sorted(list(set(candidates)), key=len, reverse=True)
        generic_keywords = {"bus stand", "bus stop", "temple", "kovil", "church", "mosque", "hospital", "school", "college", "mall", "theatre"}

        results = []
        for cand in candidates:
            cand_lower = cand.lower().strip()
            exact = self.alias_service.lookup_exact(cand)
            for m in exact:
                if m.get("entity_type") == "landmark":
                    det = self.alias_service.get_entity_details("landmark", m["entity_id"])
                    if det:
                        # If candidate is a generic word, only match if it belongs to area_hint
                        if cand_lower in generic_keywords:
                            if area_hint and area_hint.get("id") and det.get("area_id") == area_hint["id"]:
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
                                "confidence": 1.0
                            })
            if results:
                # If area_hint is available, prioritize landmark in the same area
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
        # 1. Check explicit numbered street pattern first: e.g. "5th street", "3rd cross", "5th theru"
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

    def _build_hierarchy(
        self,
        area: Optional[Dict[str, Any]],
        street: Optional[Dict[str, Any]],
        landmark: Optional[Dict[str, Any]],
        taluk: Optional[Dict[str, Any]]
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
            elif area:
                res["area"] = area.get("name_en")

            # Fallback Taluk if provided explicitly
            if not res["taluk"] and taluk:
                res["taluk"] = taluk.get("name_en")
                if taluk.get("id"):
                    res["taluk_id"] = taluk["id"]

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
            if street.get("is_ambiguous") or street.get("confidence", 0.0) < 0.70:
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
        return template.format(**kwargs)

    def _empty_result(
        self,
        clarification_question: Optional[str] = None,
        needs_clarification: bool = False
    ) -> Dict[str, Any]:
        return {
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
