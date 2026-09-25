from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.models.department import Department

CATEGORY_CODE_MAP: Dict[str, str] = {
    "Water": "WATER",
    "Water Supply": "WATER",
    "Electricity": "ELECTRICITY",
    "Power": "ELECTRICITY",
    "Roads": "ROADS",
    "Roads & Infrastructure": "ROADS",
    "Sanitation/Garbage": "SANITATION",
    "Sanitation": "SANITATION",
    "Garbage": "SANITATION",
    "Sanitation / Solid Waste Management": "SANITATION",
    "Drainage": "DRAINAGE",
    "Drainage / Sewerage": "DRAINAGE",
    "Streetlights": "STREETLIGHTS",
    "Street Lighting": "STREETLIGHTS",
    "Public Safety": "SAFETY",
    "Public Health": "SAFETY",
    "Animal Control": "SAFETY",
    "Revenue / Property Tax": "GENERAL",
    "Civil Registration": "GENERAL",
    "Other": "GENERAL"
}



class RoutingService:
    def route_category_to_department(self, db: Session, category: str) -> Optional[Department]:
        """
        Dynamically finds the appropriate active department based on category.
        """
        code = CATEGORY_CODE_MAP.get(category, "GENERAL")
        
        # Look up by department code first
        dept = db.query(Department).filter(Department.code == code, Department.is_active == True).first()
        if dept:
            return dept

        # Secondary search by partial name match
        keyword = category.split("/")[0].lower()
        dept = db.query(Department).filter(
            Department.name.ilike(f"%{keyword}%"),
            Department.is_active == True
        ).first()
        if dept:
            return dept

        # Fallback to general admin department
        general = db.query(Department).filter(Department.code == "GENERAL", Department.is_active == True).first()
        if general:
            return general

        # Last resort: return any active department
        return db.query(Department).filter(Department.is_active == True).first()


routing_service = RoutingService()
