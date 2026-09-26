"""Import Coimbatore landmarks into the database."""
import csv
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database.session import SessionLocal
from app.models.location import Landmark

def import_landmarks():
    csv_path = Path(__file__).resolve().parent.parent / "data" / "location" / "coimbatore_landmarks.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist.")
        return 0

    db = SessionLocal()
    count = 0
    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing = db.query(Landmark).filter(Landmark.id == row["id"]).first()
                if not existing:
                    landmark = Landmark(
                        id=row["id"],
                        name_en=row["name_en"],
                        name_ta=row.get("name_ta"),
                        landmark_type=row.get("landmark_type", "civic"),
                        address=row.get("address"),
                        area_id=row.get("area_id") or None,
                        street_id=row.get("street_id") or None,
                        ward_id=row.get("ward_id") or None,
                        zone_id=row.get("zone_id") or None,
                        taluk_id=row.get("taluk_id") or None,
                        village_id=row.get("village_id") or None,
                        latitude=float(row["latitude"]) if row.get("latitude") else None,
                        longitude=float(row["longitude"]) if row.get("longitude") else None,
                        source=row.get("source", "Coimbatore_Landmark_Registry_2024"),
                        confidence=float(row.get("confidence", 0.95))
                    )
                    db.add(landmark)
                    count += 1
        db.commit()
        print(f"Successfully imported {count} landmarks.")
    except Exception as e:
        db.rollback()
        print(f"Error importing landmarks: {e}")
    finally:
        db.close()
    return count

if __name__ == "__main__":
    import_landmarks()
