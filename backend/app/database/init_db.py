import logging
from sqlalchemy.orm import Session
from app.database.base import Base
from app.database.session import engine, SessionLocal
from app.models.user import User, UserRole
from app.models.department import Department
from app.core.security import get_password_hash

logger = logging.getLogger("voxentra.db_init")

DEFAULT_DEPARTMENTS = [
    {
        "code": "WATER",
        "name": "Water Supply & Sewage Department",
        "description": "Drinking water supply, pipeline leak repairs, pressure regulation, and sewage maintenance."
    },
    {
        "code": "ELECTRICITY",
        "name": "Electricity & Power Department",
        "description": "Power cuts, transformer repair, high-voltage issues, and dangerous electrical wires."
    },
    {
        "code": "ROADS",
        "name": "Roads & Transport Department",
        "description": "Pothole repairs, road resurfacing, speed breakers, asphalt maintenance, and pavement safety."
    },
    {
        "code": "SANITATION",
        "name": "Sanitation & Solid Waste Department",
        "description": "Garbage clearance, waste segregation, overflowing dustbins, and municipal cleanliness."
    },
    {
        "code": "DRAINAGE",
        "name": "Drainage & Stormwater Department",
        "description": "Stormwater canals, clogged gutters, open drains, and monsoon water stagnation."
    },
    {
        "code": "STREETLIGHTS",
        "name": "Street Lighting Department",
        "description": "Street lamp maintenance, replacement of broken bulbs, dark road illumination."
    },
    {
        "code": "SAFETY",
        "name": "Public Safety & Emergency Department",
        "description": "Emergency hazards, fallen trees, stray dog control, and civic life-safety hazards."
    },
    {
        "code": "GENERAL",
        "name": "General Administration Department",
        "description": "General civic grievances, administrative requests, and miscellaneous municipal complaints."
    }
]


def init_db(db: Session = None) -> None:
    # 1. Create all tables
    Base.metadata.create_all(bind=engine)

    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        # 2. Seed default departments
        dept_map = {}
        for dept_data in DEFAULT_DEPARTMENTS:
            existing = db.query(Department).filter(Department.code == dept_data["code"]).first()
            if not existing:
                dept = Department(
                    code=dept_data["code"],
                    name=dept_data["name"],
                    description=dept_data["description"],
                    is_active=True
                )
                db.add(dept)
                db.flush()
                dept_map[dept_data["code"]] = dept
            else:
                dept_map[dept_data["code"]] = existing
        db.commit()

        # 3. Seed Admin user if not exists
        admin_email = "admin@voxentra.tn.gov.in"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                full_name="Municipal Admin Officer",
                email=admin_email,
                phone="9876543210",
                password_hash=get_password_hash("Admin@123"),
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin)

        # 4. Seed Department Officers
        water_officer_email = "officer.water@voxentra.tn.gov.in"
        water_officer = db.query(User).filter(User.email == water_officer_email).first()
        if not water_officer:
            water_dept = dept_map.get("WATER")
            water_officer = User(
                full_name="Selvam (AE Water Supply)",
                email=water_officer_email,
                phone="9843012345",
                password_hash=get_password_hash("Officer@123"),
                role=UserRole.OFFICER,
                department_id=water_dept.id if water_dept else None,
                is_active=True
            )
            db.add(water_officer)

        roads_officer_email = "officer.roads@voxentra.tn.gov.in"
        roads_officer = db.query(User).filter(User.email == roads_officer_email).first()
        if not roads_officer:
            roads_dept = dept_map.get("ROADS")
            roads_officer = User(
                full_name="Kavitha (AE Highways & Roads)",
                email=roads_officer_email,
                phone="9843054321",
                password_hash=get_password_hash("Officer@123"),
                role=UserRole.OFFICER,
                department_id=roads_dept.id if roads_dept else None,
                is_active=True
            )
            db.add(roads_officer)

        # 5. Seed Test Citizen
        citizen_email = "citizen@voxentra.tn.gov.in"
        citizen = db.query(User).filter(User.email == citizen_email).first()
        if not citizen:
            citizen = User(
                full_name="Murugan Citizen",
                email=citizen_email,
                phone="9443212345",
                password_hash=get_password_hash("Citizen@123"),
                role=UserRole.CITIZEN,
                is_active=True
            )
            db.add(citizen)

        # 6. Seed Sample Geolocated Complaints for Live Map & Analytics
        from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintSource
        from app.models.complaint_history import ComplaintHistory
        from datetime import datetime, timezone, timedelta

        if db.query(Complaint).count() == 0:
            water_dept = dept_map.get("WATER")
            elec_dept = dept_map.get("ELECTRICITY")
            roads_dept = dept_map.get("ROADS")
            sanitation_dept = dept_map.get("SANITATION")
            drainage_dept = dept_map.get("DRAINAGE")
            lights_dept = dept_map.get("STREETLIGHTS")

            sample_complaints = [
                {
                    "number": "VOX-2026-0001",
                    "title": "Water pipeline burst near Gandhipuram bus stand",
                    "desc": "Drinking water pipeline has broken near Gandhipuram central bus stand, Coimbatore. Severe water leakage flooding the road.",
                    "category": "Water",
                    "dept": water_dept,
                    "location": "Gandhipuram Central Bus Stand, Coimbatore",
                    "lat": "11.014092",
                    "lng": "76.966940",
                    "priority": ComplaintPriority.HIGH,
                    "status": ComplaintStatus.IN_PROGRESS,
                    "lang": "Tamil",
                    "source": ComplaintSource.TELEPHONY_IVR
                },
                {
                    "number": "VOX-2026-0002",
                    "title": "Sparking transformer & broken live wire in Peelamedu",
                    "desc": "Peelamedu junction la current cut aachu, transformer spark aaguthu, danger wire hanging near pedestrian path.",
                    "category": "Electricity",
                    "dept": elec_dept,
                    "location": "Peelamedu, Coimbatore",
                    "lat": "11.026110",
                    "lng": "77.008240",
                    "priority": ComplaintPriority.CRITICAL,
                    "status": ComplaintStatus.ASSIGNED,
                    "lang": "Tanglish",
                    "source": ComplaintSource.TELEPHONY_IVR
                },
                {
                    "number": "VOX-2026-0003",
                    "title": "Deep potholes causing accidents near RS Puram",
                    "desc": "Severe road damage and deep potholes on RS Puram main road junction causing heavy bike skids.",
                    "category": "Roads",
                    "dept": roads_dept,
                    "location": "RS Puram, Coimbatore",
                    "lat": "11.008321",
                    "lng": "76.949056",
                    "priority": ComplaintPriority.HIGH,
                    "status": ComplaintStatus.SUBMITTED,
                    "lang": "English",
                    "source": ComplaintSource.WEB_TEXT
                },
                {
                    "number": "VOX-2026-0004",
                    "title": "Garbage dump not cleared for 4 days in T Nagar",
                    "desc": "தி நகர் பகுதியில் குப்பைத் தொட்டி நிரம்பி வழிந்து துர்நாற்றம் வீசுகிறது. உடனடியாக அள்ள வேண்டும்.",
                    "category": "Sanitation/Garbage",
                    "dept": sanitation_dept,
                    "location": "T Nagar, Chennai",
                    "lat": "13.041800",
                    "lng": "80.234100",
                    "priority": ComplaintPriority.MEDIUM,
                    "status": ComplaintStatus.SUBMITTED,
                    "lang": "Tamil",
                    "source": ComplaintSource.TELEPHONY_IVR
                },
                {
                    "number": "VOX-2026-0005",
                    "title": "Choked stormwater canal and sewage overflow in Velachery",
                    "desc": "Velachery 100 feet road-la drainage adaippu aagi road full-ah sakkadai thanni thenki nikkuthu.",
                    "category": "Drainage",
                    "dept": drainage_dept,
                    "location": "Velachery, Chennai",
                    "lat": "12.981500",
                    "lng": "80.218000",
                    "priority": ComplaintPriority.HIGH,
                    "status": ComplaintStatus.IN_PROGRESS,
                    "lang": "Tanglish",
                    "source": ComplaintSource.WEB_VOICE
                },
                {
                    "number": "VOX-2026-0006",
                    "title": "Non-functional streetlights on Madurai Goripalayam bridge",
                    "desc": "கோரிப்பாளையம் மேம்பாலத்தில் அனைத்து தெரு விளக்குகளும் எரியாமல் இருட்டாக உள்ளது. விபத்து அபாயம்.",
                    "category": "Streetlights",
                    "dept": lights_dept,
                    "location": "Goripalayam, Madurai",
                    "lat": "9.932800",
                    "lng": "78.130200",
                    "priority": ComplaintPriority.MEDIUM,
                    "status": ComplaintStatus.RESOLVED,
                    "lang": "Tamil",
                    "source": ComplaintSource.TELEPHONY_IVR
                }
            ]

            now = datetime.now(timezone.utc)
            for sc in sample_complaints:
                comp = Complaint(
                    complaint_number=sc["number"],
                    citizen_id=citizen.id if citizen else None,
                    department_id=sc["dept"].id if sc["dept"] else None,
                    title=sc["title"],
                    description=sc["desc"],
                    original_text=sc["desc"],
                    language=sc["lang"],
                    category=sc["category"],
                    location=sc["location"],
                    latitude=sc["lat"],
                    longitude=sc["lng"],
                    priority=sc["priority"],
                    status=sc["status"],
                    source=sc["source"],
                    citizen_confirmed=True,
                    due_at=now + timedelta(days=3)
                )
                db.add(comp)
                db.flush()

                hist = ComplaintHistory(
                    complaint_id=comp.id,
                    previous_status=None,
                    new_status=comp.status.value,
                    note="Complaint logged via " + comp.source.value,
                    changed_by_id=None
                )
                db.add(hist)

        db.commit()
        logger.info("Database initialized and seeded successfully.")
    finally:
        if close_session:
            db.close()


if __name__ == "__main__":
    init_db()
    print("VoxentraAI Database initialized and seeded successfully.")
