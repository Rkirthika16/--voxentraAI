"""Rebuild fast in-memory phonetic index and serialized lookup cache for Coimbatore locations."""
import sys
import json
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database.session import SessionLocal
from app.models.location import (
    Taluk, Firka, RevenueVillage, CorporationZone,
    CorporationWard, Area, Street, Landmark, LocationAlias
)

def rebuild_index():
    db = SessionLocal()
    index_data = {
        "taluks": {},
        "firkas": {},
        "villages": {},
        "zones": {},
        "wards": {},
        "areas": {},
        "streets": {},
        "landmarks": {},
        "alias_to_entity": {}
    }
    
    try:
        # Load Taluks
        for t in db.query(Taluk).all():
            index_data["taluks"][t.id] = {
                "id": t.id,
                "name_en": t.name_en,
                "name_ta": t.name_ta,
                "division_id": t.division_id,
                "confidence": t.confidence
            }
            
        # Load Zones
        for z in db.query(CorporationZone).all():
            index_data["zones"][z.id] = {
                "id": z.id,
                "name": z.name,
                "name_ta": z.name_ta
            }
            
        # Load Wards
        for w in db.query(CorporationWard).all():
            index_data["wards"][w.id] = {
                "id": w.id,
                "ward_no": w.ward_no,
                "name": w.name,
                "zone_id": w.zone_id
            }
            
        # Load Areas
        for a in db.query(Area).all():
            index_data["areas"][a.id] = {
                "id": a.id,
                "name_en": a.name_en,
                "name_ta": a.name_ta,
                "zone_id": a.zone_id,
                "ward_id": a.ward_id,
                "taluk_id": a.taluk_id,
                "village_id": a.village_id,
                "latitude": a.latitude,
                "longitude": a.longitude
            }
            
        # Load Streets
        for s in db.query(Street).all():
            index_data["streets"][s.id] = {
                "id": s.id,
                "name_en": s.name_en,
                "name_ta": s.name_ta,
                "area_id": s.area_id,
                "ward_id": s.ward_id,
                "zone_id": s.zone_id,
                "taluk_id": s.taluk_id,
                "village_id": s.village_id,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "confidence": s.confidence
            }
            
        # Load Landmarks
        for l in db.query(Landmark).all():
            index_data["landmarks"][l.id] = {
                "id": l.id,
                "name_en": l.name_en,
                "name_ta": l.name_ta,
                "landmark_type": l.landmark_type,
                "area_id": l.area_id,
                "street_id": l.street_id,
                "ward_id": l.ward_id,
                "zone_id": l.zone_id,
                "taluk_id": l.taluk_id,
                "village_id": l.village_id,
                "latitude": l.latitude,
                "longitude": l.longitude,
                "confidence": l.confidence
            }
            
        # Load Aliases
        for al in db.query(LocationAlias).all():
            key = al.alias.lower().strip()
            if key not in index_data["alias_to_entity"]:
                index_data["alias_to_entity"][key] = []
            index_data["alias_to_entity"][key].append({
                "entity_type": al.entity_type,
                "entity_id": al.entity_id,
                "language": al.language,
                "alias_type": al.alias_type
            })

        out_path = Path(__file__).resolve().parent.parent / "data" / "location" / "coimbatore_location_index.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        print(f"Rebuilt and saved location index to {out_path} ({len(index_data['alias_to_entity'])} alias index keys).")
    except Exception as e:
        print(f"Error rebuilding index: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    rebuild_index()
