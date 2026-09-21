from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict
from app.models.complaint import ComplaintPriority, ComplaintStatus, ComplaintSource
from app.schemas.department import DepartmentResponse


class ComplaintCreate(BaseModel):
    title: Optional[str] = None
    description: str = Field(..., min_length=5)
    category: Optional[str] = "Other"
    location: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    priority: Optional[ComplaintPriority] = ComplaintPriority.MEDIUM
    language: Optional[str] = "English"
    source: Optional[ComplaintSource] = ComplaintSource.WEB_TEXT
    ai_metadata: Optional[Dict[str, Any]] = None
    citizen_confirmed: Optional[bool] = True
    audio_file_path: Optional[str] = None


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    note: Optional[str] = Field(None, max_length=500)


class ComplaintAssignRequest(BaseModel):
    officer_id: int
    notes: Optional[str] = None


class ComplaintHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int
    previous_status: Optional[str] = None
    new_status: str
    note: Optional[str] = None
    changed_by_name: Optional[str] = None
    created_at: datetime


class ComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_number: str
    citizen_id: Optional[int] = None
    citizen_name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    assigned_officer_id: Optional[int] = None
    assigned_officer_name: Optional[str] = None
    title: str
    description: str
    language: str
    category: str
    location: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    priority: ComplaintPriority
    status: ComplaintStatus
    source: ComplaintSource
    ai_metadata: Optional[Dict[str, Any]] = None
    citizen_confirmed: bool
    audio_file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    due_at: Optional[datetime] = None


class ComplaintDetailResponse(ComplaintResponse):
    department: Optional[DepartmentResponse] = None
    history: List[ComplaintHistoryResponse] = []
