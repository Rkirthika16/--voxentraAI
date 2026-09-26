import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database.session import SessionLocal
from app.models.location import CorporationZone, CorporationWard
from scripts.build_coimbatore_location_database import read_csv

def import_wards():
    db = SessionLocal()
    zone_rows = read_csv("corporation_zones.csv")
    for r in zone_rows:
        existing = db.query(CorporationZone).filter_by(id=int(r["id"])).first()
        if not existing:
            z = CorporationZone(
                id=int(r["id"]),
                name=r["name"],
                name_ta=r.get("name_ta"),
                office_address=r.get("office_address"),
                source="CCMC"
            )
            db.add(z)
    db.commit()

    ward_rows = read_csv("corporation_wards.csv")
    count = 0
    for r in ward_rows:
        existing = db.query(CorporationWard).filter_by(id=int(r["id"])).first()
        if not existing:
            w = CorporationWard(
                id=int(r["id"]),
                zone_id=int(r["zone_id"]),
                ward_no=int(r["ward_no"]),
                name=r["name"],
                name_ta=r.get("name_ta"),
                major_localities=r.get("major_localities"),
                boundary_description=r.get("boundary_description"),
                source="CCMC Ward Delimitation"
            )
            db.add(w)
            count += 1
    db.commit()
    db.close()
    print(f"Imported/Verified {len(ward_rows)} Wards across 5 Zones (added {count}).")

if __name__ == "__main__":
    import_wards()
