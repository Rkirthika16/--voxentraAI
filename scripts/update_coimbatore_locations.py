"""Differential update and refresh script for Coimbatore Location Intelligence."""
import sys
import json
import csv
from datetime import datetime
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database.session import SessionLocal
from app.models.location import Area, Street, Landmark, LocationSource

def update_locations():
    db = SessionLocal()
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "additions": [],
        "modifications": [],
        "preserved_records": 0,
        "errors": []
    }
    
    try:
        # Check for diffs in streets
        streets_csv = Path(__file__).resolve().parent.parent / "data" / "location" / "coimbatore_streets.csv"
        if streets_csv.exists():
            with open(streets_csv, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing = db.query(Street).filter(Street.id == row["id"]).first()
                    if not existing:
                        new_st = Street(
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
                        db.add(new_st)
                        report["additions"].append(f"Street: {row['id']} ({row['name_en']})")
                    else:
                        report["preserved_records"] += 1
                        
        db.commit()
        print(f"Differential update completed. Additions: {len(report['additions'])}, Preserved: {report['preserved_records']}")
        
        # Save differential report
        report_file = Path(__file__).resolve().parent.parent / "location_update_report.json"
        with open(report_file, "w", encoding="utf-8") as rf:
            json.dump(report, rf, indent=2)
    except Exception as e:
        db.rollback()
        print(f"Error during differential update: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    update_locations()
