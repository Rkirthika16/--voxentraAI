"""Import Coimbatore streets into the database."""
import csv
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database.session import SessionLocal
from app.models.location import Street

def import_streets():
    csv_path = Path(__file__).resolve().parent.parent / "data" / "location" / "coimbatore_streets.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist.")
        return 0

    db = SessionLocal()
    count = 0
    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing = db.query(Street).filter(Street.id == row["id"]).first()
                if not existing:
                    street = Street(
                        id=row["id"],
                        name_en=row["name_en"],
                        name_ta=row.get("name_ta"),
                        area_id=row.get("area_id") or None,
                        ward_id=row.get("ward_id") or None,
                        zone_id=row.get("zone_id") or None,
                        taluk_id=row.get("taluk_id") or None,
                        village_id=row.get("village_id") or None,
                        latitude=float(row["latitude"]) if row.get("latitude") else None,
                        longitude=float(row["longitude"]) if row.get("longitude") else None,
                        source=row.get("source", "CCMC_Ward_Delimitation_OSM"),
                        confidence=float(row.get("confidence", 0.95))
                    )
                    db.add(street)
                    count += 1
        db.commit()
        print(f"Successfully imported {count} streets.")
    except Exception as e:
        db.rollback()
        print(f"Error importing streets: {e}")
    finally:
        db.close()
    return count

if __name__ == "__main__":
    import_streets()
