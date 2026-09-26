"""Build and populate comprehensive location aliases for Coimbatore entities."""
import sys
from pathlib import Path
import re

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database.session import SessionLocal
from app.models.location import (
    Taluk, Firka, RevenueVillage, CorporationZone,
    CorporationWard, Area, Street, Landmark, LocationAlias
)

def generate_phonetic_variations(name: str):
    variants = set()
    n = name.lower()
    variants.add(n)
    
    # Common variations
    v = n.replace("th", "t").replace("dh", "d")
    variants.add(v)
    v2 = n.replace("t", "th").replace("d", "dh")
    variants.add(v2)
    v3 = n.replace("aa", "a").replace("ee", "i").replace("oo", "u")
    variants.add(v3)
    v4 = n.replace("patti", "patty").replace("palayam", "palaiyam")
    variants.add(v4)
    v5 = n.replace(" ", "")
    variants.add(v5)
    v6 = n.replace("-", " ")
    variants.add(v6)
    
    # Road / Street variations
    if "road" in n:
        variants.add(n.replace("road", "rd"))
        variants.add(n.replace("road", "salai"))
    if "street" in n:
        variants.add(n.replace("street", "st"))
        variants.add(n.replace("street", "theru"))
        
    return [x for x in variants if x and x != n]

def build_all_aliases():
    db = SessionLocal()
    count = 0
    try:
        entities = [
            ("taluk", db.query(Taluk).all()),
            ("firka", db.query(Firka).all()),
            ("revenue_village", db.query(RevenueVillage).all()),
            ("zone", db.query(CorporationZone).all()),
            ("ward", db.query(CorporationWard).all()),
            ("area", db.query(Area).all()),
            ("street", db.query(Street).all()),
            ("landmark", db.query(Landmark).all()),
        ]
        
        for entity_type, records in entities:
            for rec in records:
                name_en = getattr(rec, "name_en", None) or getattr(rec, "name", None)
                if not name_en:
                    continue
                
                # Check canonical alias
                alias_en = db.query(LocationAlias).filter(
                    LocationAlias.entity_type == entity_type,
                    LocationAlias.entity_id == rec.id,
                    LocationAlias.alias == name_en
                ).first()
                if not alias_en:
                    db.add(LocationAlias(
                        entity_type=entity_type,
                        entity_id=rec.id,
                        alias=name_en,
                        language="en",
                        alias_type="canonical",
                        normalized_value=name_en.lower()
                    ))
                    count += 1
                
                # Add Tamil alias if exists
                name_ta = getattr(rec, "name_ta", None)
                if name_ta:
                    alias_ta = db.query(LocationAlias).filter(
                        LocationAlias.entity_type == entity_type,
                        LocationAlias.entity_id == rec.id,
                        LocationAlias.alias == name_ta
                    ).first()
                    if not alias_ta:
                        db.add(LocationAlias(
                            entity_type=entity_type,
                            entity_id=rec.id,
                            alias=name_ta,
                            language="ta",
                            alias_type="tamil_script",
                            normalized_value=name_ta.strip()
                        ))
                        count += 1
                
                # Add Phonetic Variations
                variations = generate_phonetic_variations(name_en)
                for var in variations:
                    existing_var = db.query(LocationAlias).filter(
                        LocationAlias.entity_type == entity_type,
                        LocationAlias.entity_id == rec.id,
                        LocationAlias.alias == var
                    ).first()
                    if not existing_var:
                        db.add(LocationAlias(
                            entity_type=entity_type,
                            entity_id=rec.id,
                            alias=var,
                            language="tanglish",
                            alias_type="phonetic",
                            normalized_value=var.lower().replace(" ", "")
                        ))
                        count += 1

        db.commit()
        print(f"Successfully generated and synced {count} aliases into database.")
    except Exception as e:
        db.rollback()
        print(f"Error building aliases: {e}")
    finally:
        db.close()
    return count

if __name__ == "__main__":
    build_all_aliases()
