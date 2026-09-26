import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database.session import SessionLocal
from app.models.location import Firka
from scripts.build_coimbatore_location_database import read_csv, parse_json_or_list

def import_firkas():
    db = SessionLocal()
    rows = read_csv("coimbatore_firkas.csv")
    count = 0
    for r in rows:
        existing = db.query(Firka).filter_by(id=int(r["id"])).first()
        aliases = parse_json_or_list(r.get("aliases"))
        if not existing:
            f = Firka(
                id=int(r["id"]),
                taluk_id=int(r["taluk_id"]),
                name_en=r["name_en"],
                name_ta=r.get("name_ta"),
                aliases=aliases,
                source="TN Revenue Gazette - Coimbatore District",
                confidence=1.0
            )
            db.add(f)
            count += 1
    db.commit()
    db.close()
    print(f"Imported/Verified {len(rows)} Firkas (added {count}).")

if __name__ == "__main__":
    import_firkas()
