import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database.session import SessionLocal
from app.models.location import Taluk
from scripts.build_coimbatore_location_database import read_csv, parse_json_or_list

def import_taluks():
    db = SessionLocal()
    rows = read_csv("coimbatore_taluks.csv")
    count = 0
    for r in rows:
        existing = db.query(Taluk).filter_by(id=int(r["id"])).first()
        aliases = parse_json_or_list(r.get("aliases"))
        if not existing:
            t = Taluk(
                id=int(r["id"]),
                division_id=int(r["division_id"]) if r.get("division_id") else None,
                name_en=r["name_en"],
                name_ta=r.get("name_ta"),
                aliases=aliases,
                headquarters=r.get("headquarters"),
                source=r.get("source", "TN Revenue Gazette"),
                confidence=float(r.get("confidence", 1.0))
            )
            db.add(t)
            count += 1
    db.commit()
    db.close()
    print(f"Imported/Verified {len(rows)} Taluks (added {count}).")

if __name__ == "__main__":
    import_taluks()
