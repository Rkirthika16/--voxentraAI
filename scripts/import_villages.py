import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database.session import SessionLocal
from app.models.location import RevenueVillage
from scripts.build_coimbatore_location_database import read_csv, parse_json_or_list

def import_villages():
    db = SessionLocal()
    rows = read_csv("coimbatore_revenue_villages.csv")
    count = 0
    for r in rows:
        existing = db.query(RevenueVillage).filter_by(id=int(r["id"])).first()
        aliases = parse_json_or_list(r.get("aliases"))
        lat = float(r["latitude"]) if r.get("latitude") else None
        lon = float(r["longitude"]) if r.get("longitude") else None
        if not existing:
            v = RevenueVillage(
                id=int(r["id"]),
                taluk_id=int(r["taluk_id"]),
                firka_id=int(r["firka_id"]) if r.get("firka_id") else None,
                name_en=r["name_en"],
                name_ta=r.get("name_ta"),
                village_code=r.get("village_code"),
                aliases=aliases,
                latitude=lat,
                longitude=lon,
                source=r.get("source", "TN Revenue Administration"),
                confidence=float(r.get("confidence", 1.0))
            )
            db.add(v)
            count += 1
    db.commit()
    db.close()
    print(f"Imported/Verified {len(rows)} Revenue Villages (added {count}).")

if __name__ == "__main__":
    import_villages()
