"""Coimbatore Location Intelligence API routes."""
import json
import logging
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database.session import get_db
from app.services.location_service import location_service
from app.services.location_resolver import location_resolver
from app.models.location import (
    Taluk, Firka, RevenueVillage, CorporationZone,
    CorporationWard, Area, Street, Landmark, LocationAlias
)

logger = logging.getLogger("voxentra.location_api")

router = APIRouter(prefix="/location", tags=["Location Intelligence"])

@router.get("/resolve")
def resolve_location(
    q: str = Query(..., description="Spoken or written location text in Tamil, English, or Tanglish"),
    lang: str = Query("Tanglish", description="Language: Tamil, English, or Tanglish")
):
    """Hierarchically resolves a spoken/typed location with confidence scoring and smart clarification."""
    result = location_resolver.resolve(text=q, current_language=lang)
    return result

@router.get("/search")
def search_locations(
    q: str = Query(..., min_length=2, description="Search term for area, street, landmark, or taluk"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Searches across all Coimbatore areas, streets, landmarks, and taluks."""
    return location_service.search_locations(db=db, query=q, limit=limit)

@router.get("/taluk/{name}")
def get_taluk(name: str, db: Session = Depends(get_db)):
    """Retrieves official Coimbatore taluk data including firkas and village count."""
    taluk = location_service.get_taluk_by_name(db, name)
    if not taluk:
        raise HTTPException(status_code=404, detail=f"Taluk '{name}' not found in Coimbatore district registry.")
    return taluk

@router.get("/ward/{ward_no}")
def get_ward(ward_no: int, db: Session = Depends(get_db)):
    """Retrieves CCMC Corporation ward information, zone relationship, and associated streets."""
    ward = location_service.get_ward_by_number(db, ward_no)
    if not ward:
        raise HTTPException(status_code=404, detail=f"CCMC Corporation Ward {ward_no} not found.")
    return ward

@router.get("/street/search")
def search_streets(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Searches Coimbatore arterial roads, municipal streets, and residential lanes."""
    term = f"%{q}%"
    streets = db.query(Street).filter(or_(Street.name_en.ilike(term), Street.name_ta.ilike(term))).limit(limit).all()
    return [
        {
            "id": s.id,
            "name_en": s.name_en,
            "name_ta": s.name_ta,
            "street_type": s.street_type,
            "area_id": s.area_id,
            "ward_id": s.ward_id,
            "zone_id": s.zone_id,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "source": s.source,
            "confidence": s.confidence
        }
        for s in streets
    ]

@router.get("/landmark/search")
def search_landmarks(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Searches Coimbatore civic landmarks, hospitals, bus stands, stations, and temples."""
    term = f"%{q}%"
    landmarks = db.query(Landmark).filter(or_(Landmark.name_en.ilike(term), Landmark.name_ta.ilike(term))).limit(limit).all()
    return [
        {
            "id": l.id,
            "name_en": l.name_en,
            "name_ta": l.name_ta,
            "type": l.landmark_type,
            "address": l.address,
            "area_id": l.area_id,
            "ward_id": l.ward_id,
            "latitude": l.latitude,
            "longitude": l.longitude,
            "source": l.source,
            "confidence": l.confidence
        }
        for l in landmarks
    ]

@router.get("/nearby")
def get_nearby_landmarks(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(3.0, ge=0.5, le=20.0),
    db: Session = Depends(get_db)
):
    """Finds landmarks near given GPS coordinates using Euclidean distance approximation."""
    # 1 deg lat ~ 111 km, 1 deg lon ~ 111 * cos(11 deg) ~ 109 km
    delta_lat = radius_km / 111.0
    delta_lon = radius_km / 109.0
    
    nearby = db.query(Landmark).filter(
        Landmark.latitude.between(lat - delta_lat, lat + delta_lat),
        Landmark.longitude.between(lon - delta_lon, lon + delta_lon)
    ).limit(15).all()

    return [
        {
            "id": l.id,
            "name_en": l.name_en,
            "name_ta": l.name_ta,
            "type": l.landmark_type,
            "latitude": l.latitude,
            "longitude": l.longitude,
            "area_id": l.area_id
        }
        for l in nearby
    ]

@router.get("/hierarchy/{area_id}")
def get_area_hierarchy(area_id: int, db: Session = Depends(get_db)):
    """Returns complete administrative and corporation hierarchy tree for an area."""
    area = db.query(Area).filter_by(id=area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found.")
    
    zone = db.query(CorporationZone).filter_by(id=area.zone_id).first() if area.zone_id else None
    ward = db.query(CorporationWard).filter_by(id=area.ward_id).first() if area.ward_id else None
    taluk = db.query(Taluk).filter_by(id=area.taluk_id).first() if area.taluk_id else None
    streets = db.query(Street).filter_by(area_id=area.id).all()
    landmarks = db.query(Landmark).filter_by(area_id=area.id).all()

    return {
        "area": {
            "id": area.id,
            "name_en": area.name_en,
            "name_ta": area.name_ta,
            "pincode": area.pincode,
            "latitude": area.latitude,
            "longitude": area.longitude
        },
        "corporation": {
            "zone": zone.name if zone else None,
            "ward_no": ward.ward_no if ward else None,
            "ward_name": ward.name if ward else None
        } if area.is_corporation_area else None,
        "revenue_administration": {
            "district": "Coimbatore",
            "taluk": taluk.name_en if taluk else None,
            "taluk_headquarters": taluk.headquarters if taluk else None
        },
        "streets": [{"id": s.id, "name_en": s.name_en} for s in streets],
        "landmarks": [{"id": lm.id, "name_en": lm.name_en, "type": lm.landmark_type} for lm in landmarks]
    }

@router.get("/admin/stats")
def get_location_stats(db: Session = Depends(get_db)):
    """Returns administrative record counts, data coverage summary, and index status."""
    return location_service.get_admin_stats(db)

@router.get("/admin/report")
def get_import_report():
    """Returns official location ingestion audit report JSON."""
    report_path = Path(__file__).resolve().parent.parent.parent.parent / "location_import_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Location import report not found.")
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)
