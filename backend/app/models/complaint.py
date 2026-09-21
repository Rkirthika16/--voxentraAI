import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from app.database.base import Base


class ComplaintPriority(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ComplaintStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    REOPENED = "REOPENED"
    OVERDUE = "OVERDUE"


class ComplaintSource(str, enum.Enum):
    WEB_TEXT = "WEB_TEXT"
    WEB_VOICE = "WEB_VOICE"
    AUDIO_UPLOAD = "AUDIO_UPLOAD"
    TELEPHONY_IVR = "TELEPHONY_IVR"


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    complaint_number = Column(String(30), unique=True, index=True, nullable=False)
    
    citizen_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_officer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    original_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    
    language = Column(String(50), default="English", nullable=False)
    category = Column(String(100), default="Other", nullable=False, index=True)
    location = Column(String(255), nullable=True, index=True)
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)
    
    priority = Column(Enum(ComplaintPriority), default=ComplaintPriority.MEDIUM, nullable=False, index=True)
    status = Column(Enum(ComplaintStatus), default=ComplaintStatus.SUBMITTED, nullable=False, index=True)
    source = Column(Enum(ComplaintSource), default=ComplaintSource.WEB_TEXT, nullable=False)
    
    ai_metadata = Column(JSON, nullable=True)
    citizen_confirmed = Column(Boolean, default=True, nullable=False)
    audio_file_path = Column(String(255), nullable=True)
    
    due_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    citizen = relationship("User", back_populates="submitted_complaints", foreign_keys=[citizen_id])
    assigned_officer = relationship("User", back_populates="assigned_complaints", foreign_keys=[assigned_officer_id])
    department = relationship("Department", back_populates="complaints")
    history = relationship("ComplaintHistory", back_populates="complaint", cascade="all, delete-orphan", order_by="ComplaintHistory.created_at.desc()")
    assignments = relationship("Assignment", back_populates="complaint", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="complaint", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="complaint", cascade="all, delete-orphan")
