"""Database and API operations service for Coimbatore Location Intelligence."""
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.models.location import (
    AdministrativeDivision, Taluk, Firka, RevenueVillage,
    CorporationZone, CorporationWard, Area, Street, Landmark,
    LocationAlias, LocationSource
)
from app.services.location_resolver import location_resolver

logger = logging.getLogger("voxentra.location_db_service")

class LocationService:

    @staticmethod
    def resolve_location(query: str, language: str = "Tanglish", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return location_resolver.resolve(query, current_language=language, context=context)

    @staticmethod
    def search_locations(db: Session, query: str, limit: int = 10) -> Dict[str, Any]:
        q = f"%{query}%"
        areas = db.query(Area).filter(or_(Area.name_en.ilike(q), Area.name_ta.ilike(q))).limit(limit).all()
        streets = db.query(Street).filter(or_(Street.name_en.ilike(q), Street.name_ta.ilike(q))).limit(limit).all()
        landmarks = db.query(Landmark).filter(or_(Landmark.name_en.ilike(q), Landmark.name_ta.ilike(q))).limit(limit).all()
        taluks = db.query(Taluk).filter(or_(Taluk.name_en.ilike(q), Taluk.name_ta.ilike(q))).limit(limit).all()

        return {
            "query": query,
            "areas": [{"id": a.id, "name_en": a.name_en, "name_ta": a.name_ta, "ward_id": a.ward_id, "zone_id": a.zone_id} for a in areas],
            "streets": [{"id": s.id, "name_en": s.name_en, "name_ta": s.name_ta, "area_id": s.area_id} for s in streets],
            "landmarks": [{"id": l.id, "name_en": l.name_en, "name_ta": l.name_ta, "type": l.landmark_type} for l in landmarks],
            "taluks": [{"id": t.id, "name_en": t.name_en, "name_ta": t.name_ta} for t in taluks]
        }

    @staticmethod
    def get_taluk_by_name(db: Session, name: str) -> Optional[Dict[str, Any]]:
        t = db.query(Taluk).filter(or_(Taluk.name_en.ilike(name), Taluk.name_ta.ilike(name))).first()
        if not t:
            return None
        firkas = db.query(Firka).filter(Firka.taluk_id == t.id).all()
        villages = db.query(RevenueVillage).filter(RevenueVillage.taluk_id == t.id).all()
        return {
            "id": t.id,
            "name_en": t.name_en,
            "name_ta": t.name_ta,
            "division_id": t.division_id,
            "headquarters": t.headquarters,
            "total_firkas": len(firkas),
            "firkas": [{"id": f.id, "name_en": f.name_en, "name_ta": f.name_ta} for f in firkas],
            "total_villages": len(villages)
        }

    @staticmethod
    def get_ward_by_number(db: Session, ward_no: int) -> Optional[Dict[str, Any]]:
        w = db.query(CorporationWard).filter(CorporationWard.ward_no == ward_no).first()
        if not w:
            return None
        zone = db.query(CorporationZone).filter(CorporationZone.id == w.zone_id).first() if w.zone_id else None
        areas = db.query(Area).filter(Area.ward_id == w.id).all()
        streets = db.query(Street).filter(Street.ward_id == w.id).all()
        return {
            "id": w.id,
            "ward_no": w.ward_no,
            "name": w.name,
            "name_ta": w.name_ta,
            "zone_id": w.zone_id,
            "zone_name": zone.name if zone else None,
            "major_localities": w.major_localities,
            "total_areas": len(areas),
            "areas": [a.name_en for a in areas],
            "total_streets": len(streets)
        }

    @staticmethod
    def get_admin_stats(db: Session) -> Dict[str, Any]:
        return {
            "total_divisions": db.query(AdministrativeDivision).count(),
            "total_taluks": db.query(Taluk).count(),
            "total_firkas": db.query(Firka).count(),
            "total_revenue_villages": db.query(RevenueVillage).count(),
            "total_zones": db.query(CorporationZone).count(),
            "total_wards": db.query(CorporationWard).count(),
            "total_areas": db.query(Area).count(),
            "total_streets": db.query(Street).count(),
            "total_landmarks": db.query(Landmark).count(),
            "total_aliases": db.query(LocationAlias).count(),
            "data_sources": [
                "Government of Tamil Nadu - Revenue Administration",
                "Coimbatore City Municipal Corporation (CCMC)",
                "CCMC Delimitation Report & Ward Map 2022-2024",
                "OpenStreetMap Geographic Street Dataset"
            ],
            "integrity_status": "Valid",
            "offline_mode_ready": True
        }

location_service = LocationService()
