from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
import enum

from app.database.base import Base


class TollFreeState(str, enum.Enum):
    CONNECTED = "CONNECTED"
    GREETING = "GREETING"
    WAITING_FOR_CITIZEN = "WAITING_FOR_CITIZEN"
    RECORDING = "RECORDING"
    TRANSCRIBING = "TRANSCRIBING"
    UNDERSTANDING = "UNDERSTANDING"
    AI_SPEAKING = "AI_SPEAKING"
    CONFIRMATION = "CONFIRMATION"
    REGISTERING_COMPLAINT = "REGISTERING_COMPLAINT"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class TollFreeCallSession(Base):
    __tablename__ = "tollfree_sessions"

    id = Column(Integer, primary_key=True, index=True)
    call_session_id = Column(String(64), unique=True, index=True, nullable=False)
    provider_call_id = Column(String(128), nullable=True, index=True)
    caller_phone = Column(String(32), nullable=True, default="+919843098765")
    toll_free_number = Column(String(32), nullable=False, default="1800-425-8693")
    
    language = Column(String(32), default="Auto", nullable=False)  # Tamil, English, Tanglish, Auto
    language_confidence = Column(Float, default=0.0)
    
    state = Column(String(64), default=TollFreeState.CONNECTED.value, nullable=False)
    current_field_prompted = Column(String(64), nullable=True)

    # Structured Conversation Memory Slots
    category = Column(String(64), nullable=True)
    problem = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    duration = Column(String(128), nullable=True)
    affected_scope = Column(String(128), nullable=True)
    frequency = Column(String(128), nullable=True)
    severity = Column(String(64), nullable=True)
    priority = Column(String(32), nullable=True, default="MEDIUM")
    department = Column(String(128), nullable=True)
    citizen_name = Column(String(128), nullable=True)

    # Complete snapshot of memory dictionary
    structured_memory = Column(JSON, default=dict, nullable=False)

    # Full Transcript Record
    raw_transcript = Column(Text, nullable=True, default="")
    normalized_transcript = Column(Text, nullable=True, default="")

    # Real Database Complaint Linkage
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="SET NULL"), nullable=True)
    complaint_number = Column(String(64), nullable=True)

    # Error Tracking
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    messages = relationship("TollFreeMessage", back_populates="session", cascade="all, delete-orphan", order_by="TollFreeMessage.created_at")
    complaint = relationship("Complaint", foreign_keys=[complaint_id])


class TollFreeMessage(Base):
    __tablename__ = "tollfree_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("tollfree_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # "citizen", "ai", "system"
    content = Column(Text, nullable=False)
    normalized_content = Column(Text, nullable=True)
    language = Column(String(32), nullable=True)
    audio_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("TollFreeCallSession", back_populates="messages")
