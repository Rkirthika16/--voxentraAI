"""Validation and relationship integrity auditor for Coimbatore Location Intelligence."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database.session import SessionLocal
from app.models.location import (
    Taluk, Firka, RevenueVillage, CorporationZone,
    CorporationWard, Area, Street, Landmark
)

def validate_all_locations():
    db = SessionLocal()
    issues = []
    try:
        taluks = {t.id: t for t in db.query(Taluk).all()}
        firkas = {f.id: f for f in db.query(Firka).all()}
        villages = {v.id: v for v in db.query(RevenueVillage).all()}
        zones = {z.id: z for z in db.query(CorporationZone).all()}
        wards = {w.id: w for w in db.query(CorporationWard).all()}
        areas = {a.id: a for a in db.query(Area).all()}
        streets = {s.id: s for s in db.query(Street).all()}
        landmarks = {l.id: l for l in db.query(Landmark).all()}
        
        print(f"--- Location Database Integrity Audit ---")
        print(f"Taluks: {len(taluks)}, Firkas: {len(firkas)}, Villages: {len(villages)}")
        print(f"Zones: {len(zones)}, Wards: {len(wards)}, Areas: {len(areas)}")
        print(f"Streets: {len(streets)}, Landmarks: {len(landmarks)}")
        
        # 1. Validate Firka -> Taluk
        for fid, f in firkas.items():
            if f.taluk_id and f.taluk_id not in taluks:
                issues.append(f"Firka '{f.name_en}' ({fid}) references non-existent Taluk {f.taluk_id}")
                
        # 2. Validate Village -> Taluk & Firka
        for vid, v in villages.items():
            if v.taluk_id and v.taluk_id not in taluks:
                issues.append(f"Village '{v.name_en}' ({vid}) references non-existent Taluk {v.taluk_id}")
            if v.firka_id and v.firka_id not in firkas:
                issues.append(f"Village '{v.name_en}' ({vid}) references non-existent Firka {v.firka_id}")
                
        # 3. Validate Ward -> Zone
        for wid, w in wards.items():
            if w.zone_id and w.zone_id not in zones:
                issues.append(f"Ward {w.ward_no} ({wid}) references non-existent Zone {w.zone_id}")
                
        # 4. Validate Area -> Zone / Ward / Taluk
        for aid, a in areas.items():
            if a.zone_id and a.zone_id not in zones:
                issues.append(f"Area '{a.name_en}' ({aid}) references non-existent Zone {a.zone_id}")
            if a.ward_id and a.ward_id not in wards:
                issues.append(f"Area '{a.name_en}' ({aid}) references non-existent Ward {a.ward_id}")
            if a.taluk_id and a.taluk_id not in taluks:
                issues.append(f"Area '{a.name_en}' ({aid}) references non-existent Taluk {a.taluk_id}")
                
        # 5. Validate Street -> Area / Ward / Zone
        for sid, s in streets.items():
            if s.area_id and s.area_id not in areas:
                issues.append(f"Street '{s.name_en}' ({sid}) references non-existent Area {s.area_id}")
            if s.ward_id and s.ward_id not in wards:
                issues.append(f"Street '{s.name_en}' ({sid}) references non-existent Ward {s.ward_id}")
            if s.zone_id and s.zone_id not in zones:
                issues.append(f"Street '{s.name_en}' ({sid}) references non-existent Zone {s.zone_id}")
                
        # 6. Validate Landmark -> Street / Area / Ward
        for lid, l in landmarks.items():
            if l.street_id and l.street_id not in streets:
                issues.append(f"Landmark '{l.name_en}' ({lid}) references non-existent Street {l.street_id}")
            if l.area_id and l.area_id not in areas:
                issues.append(f"Landmark '{l.name_en}' ({lid}) references non-existent Area {l.area_id}")
            if l.ward_id and l.ward_id not in wards:
                issues.append(f"Landmark '{l.name_en}' ({lid}) references non-existent Ward {l.ward_id}")

        if not issues:
            print("[PASS] All relationships and foreign key mappings are 100% valid! No orphan records.")
        else:
            print(f"[FAIL] Found {len(issues)} relationship issues:")
            for iss in issues[:10]:
                print(f" - {iss}")
    except Exception as e:
        print(f"Error during validation: {e}")
    finally:
        db.close()
    return len(issues) == 0

if __name__ == "__main__":
    validate_all_locations()
