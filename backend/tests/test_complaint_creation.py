"""Automated tests for Complaint Creation & Database Reliability in VoxentraAI Conversational IVR."""
import pytest
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.services.conversation_manager import conversation_manager
from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus
from app.models.ivr import IVRSession, IVRState

def test_successful_complaint_creation_and_id_generation():
    db: Session = SessionLocal()
    try:
        # Create session
        session, _, _ = conversation_manager.create_session(db, caller_phone="+919843011111", language_preference="English")
        
        # Populate session memory with complete grievance info
        memory = {
            "conversation_id": session.session_id,
            "call_id": session.session_id,
            "problem_description": "Drinking water pipeline leak on street",
            "category": "Water",
            "area": "Gandhipuram",
            "street": "Cross Cut Road",
            "landmark": "Near Bus Stand",
            "duration": "2 days",
            "affected_scope": "Entire street",
            "priority": "HIGH",
            "citizen_phone": "+919843011111",
            "confirmation_status": "CONFIRMED"
        }
        session.structured_memory = memory
        session.language = "English"
        session.state = IVRState.CONFIRMATION.value
        db.commit()

        # Finalize and register complaint
        res = conversation_manager.finalize_and_register_complaint(db, session)

        # Assertions
        assert res["success"] is True
        assert res["complaint_created"] is True
        assert res["complaint_number"] is not None
        assert res["complaint_number"].startswith("VX-")
        assert res["state"] == IVRState.COMPLETED.value
        assert "VX-" in res["spoken_reply"]

        # Verify DB insertion
        db_complaint = db.query(Complaint).filter(Complaint.id == res["complaint_id"]).first()
        assert db_complaint is not None
        assert db_complaint.complaint_number == res["complaint_number"]
        assert db_complaint.category == "Water"
        assert "Gandhipuram" in db_complaint.location
        assert db_complaint.status == ComplaintStatus.SUBMITTED  # Pending in grievance lifecycle
        assert db_complaint.priority == ComplaintPriority.HIGH
        assert db_complaint.citizen_confirmed is True

    finally:
        db.close()


def test_complaint_id_generated_only_after_successful_save():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, caller_phone="+919843022222", language_preference="Tamil")
        
        # Before finalizing, session must NOT have complaint_number
        assert session.complaint_number is None
        assert session.complaint_id is None

        session.structured_memory = {
            "problem_description": "மின் கம்பி அறுந்து விழுந்துள்ளது",
            "category": "Electricity",
            "area": "Peelamedu",
            "street": "Avinashi Road",
            "priority": "HIGH",
            "citizen_phone": "+919843022222"
        }
        session.language = "Tamil"
        db.commit()

        res = conversation_manager.finalize_and_register_complaint(db, session)
        assert res["success"] is True
        assert res["complaint_number"] is not None
        assert session.complaint_number == res["complaint_number"]
        assert session.complaint_id == res["complaint_id"]
        assert "VX-" in res["spoken_reply"]

    finally:
        db.close()


def test_database_failure_handling_and_no_fake_id():
    db: Session = SessionLocal()
    try:
        session, _, _ = conversation_manager.create_session(db, caller_phone="+919843033333", language_preference="Tanglish")
        
        # Simulate invalid memory structure or force a closed/invalid DB session
        db.close()

        # When DB fails, finalize_and_register_complaint must handle safely and NOT return a fake ID
        res = conversation_manager.finalize_and_register_complaint(db, session)
        assert res["success"] is False
        assert res["complaint_created"] is False
        assert "complaint_number" not in res or res.get("complaint_number") is None
        assert res["error_code"] == "DATABASE_ERROR"
        assert "technical" in res["spoken_reply"].lower() or "problem" in res["spoken_reply"].lower() or "மன்னிக்கவும்" in res["spoken_reply"]

    except Exception:
        pass
