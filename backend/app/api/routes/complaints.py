from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, cast, String

from app.database.session import get_db
from app.core.dependencies import get_current_user, get_optional_current_user, require_role
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.models.user import User, UserRole
from app.models.complaint import Complaint, ComplaintStatus, ComplaintPriority
from app.models.complaint_history import ComplaintHistory
from app.models.notification import Notification
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintResponse,
    ComplaintDetailResponse,
    ComplaintStatusUpdate,
    ComplaintHistoryResponse
)
from app.schemas.notification import NotificationResponse
from app.services.complaint_service import complaint_service

router = APIRouter(prefix="/complaints", tags=["Complaints"])


def _to_complaint_response(c: Complaint) -> ComplaintResponse:
    return ComplaintResponse(
        id=c.id,
        complaint_number=c.complaint_number,
        citizen_id=c.citizen_id,
        citizen_name=c.citizen.full_name if c.citizen else "Anonymous / Citizen",
        department_id=c.department_id,
        department_name=c.department.name if c.department else None,
        assigned_officer_id=c.assigned_officer_id,
        assigned_officer_name=c.assigned_officer.full_name if c.assigned_officer else None,
        title=c.title,
        description=c.description,
        language=c.language,
        category=c.category,
        location=c.location,
        latitude=c.latitude,
        longitude=c.longitude,
        priority=c.priority,
        status=c.status,
        source=c.source,
        ai_metadata=c.ai_metadata,
        citizen_confirmed=c.citizen_confirmed,
        audio_file_path=c.audio_file_path,
        created_at=c.created_at,
        updated_at=c.updated_at,
        resolved_at=c.resolved_at,
        due_at=c.due_at
    )


@router.get("/map/pins", response_model=List[ComplaintResponse])
def get_map_complaints(
    category: Optional[str] = None,
    status: Optional[ComplaintStatus] = None,
    priority: Optional[ComplaintPriority] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Public endpoint for the Live Complaint Map.
    Returns geolocated complaints across Tamil Nadu with department tags and coordinates.
    """
    query = db.query(Complaint).filter(Complaint.latitude.isnot(None), Complaint.longitude.isnot(None))

    if category:
        query = query.filter(Complaint.category == category)
    if status:
        query = query.filter(Complaint.status == status)
    if priority:
        query = query.filter(Complaint.priority == priority)

    complaints = query.order_by(desc(Complaint.created_at)).limit(limit).all()
    return [_to_complaint_response(c) for c in complaints]


@router.get("", response_model=List[ComplaintResponse])
def list_complaints(
    status: Optional[ComplaintStatus] = None,
    category: Optional[str] = None,
    priority: Optional[ComplaintPriority] = None,
    department_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists complaints with role-based filtering:
    - Citizens see only their own complaints.
    - Officers see complaints in their department or assigned to them.
    - Admins see all complaints across all departments.
    """
    query = db.query(Complaint)

    # Role-based access partition
    if current_user.role == UserRole.CITIZEN:
        conditions = [Complaint.citizen_id == current_user.id]
        if current_user.phone:
            clean_phone = current_user.phone.replace("+91", "").replace("-", "").strip()
            if len(clean_phone) >= 7:
                conditions.append(cast(Complaint.ai_metadata, String).like(f"%{clean_phone}%"))
        query = query.filter(or_(*conditions))
    elif current_user.role == UserRole.OFFICER:
        if current_user.department_id:
            query = query.filter(
                or_(
                    Complaint.department_id == current_user.department_id,
                    Complaint.assigned_officer_id == current_user.id
                )
            )
        else:
            query = query.filter(Complaint.assigned_officer_id == current_user.id)

    # Filters
    if status:
        query = query.filter(Complaint.status == status)
    if category:
        query = query.filter(Complaint.category == category)
    if priority:
        query = query.filter(Complaint.priority == priority)
    if department_id and current_user.role == UserRole.ADMIN:
        query = query.filter(Complaint.department_id == department_id)
    if search:
        s = f"%{search}%"
        query = query.filter(
            or_(
                Complaint.complaint_number.ilike(s),
                Complaint.title.ilike(s),
                Complaint.description.ilike(s),
                Complaint.location.ilike(s)
            )
        )

    offset = (page - 1) * page_size
    complaints = query.order_by(desc(Complaint.created_at)).offset(offset).limit(page_size).all()
    return [_to_complaint_response(c) for c in complaints]


@router.get("/my", response_model=List[ComplaintResponse])
def list_my_complaints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists complaints registered by the current citizen."""
    complaints = (
        db.query(Complaint)
        .filter(Complaint.citizen_id == current_user.id)
        .order_by(desc(Complaint.created_at))
        .all()
    )
    return [_to_complaint_response(c) for c in complaints]


@router.post("", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
def create_complaint(
    complaint_in: ComplaintCreate,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits a new citizen complaint.
    Automatically assigns tracking ID, executes department routing, and sends notifications.
    """
    citizen_id = current_user.id if current_user else None
    complaint = complaint_service.create_complaint(db, complaint_in, citizen_id=citizen_id)
    return _to_complaint_response(complaint)


@router.get("/{complaint_identifier}", response_model=ComplaintDetailResponse)
def get_complaint_details(
    complaint_identifier: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches detailed complaint record by ID or public tracking number (e.g. 'VOX-2026-0001').
    Validates ownership for citizens.
    """
    query = db.query(Complaint)
    if complaint_identifier.isdigit():
        complaint = query.filter(Complaint.id == int(complaint_identifier)).first()
    else:
        complaint = query.filter(Complaint.complaint_number == complaint_identifier.upper()).first()

    if not complaint:
        raise NotFoundException("Complaint not found")

    # Authorization check
    if current_user and current_user.role == UserRole.CITIZEN:
        if complaint.citizen_id and complaint.citizen_id != current_user.id:
            raise ForbiddenException("Access denied: you cannot view other citizens' complaints")

    base_resp = _to_complaint_response(complaint)

    history_list = [
        ComplaintHistoryResponse(
            id=h.id,
            complaint_id=h.complaint_id,
            previous_status=h.previous_status,
            new_status=h.new_status,
            note=h.note,
            changed_by_name=h.changed_by.full_name if h.changed_by else "System",
            created_at=h.created_at
        )
        for h in complaint.history
    ]

    return ComplaintDetailResponse(
        **base_resp.model_dump(),
        department=complaint.department,
        history=history_list
    )


@router.patch("/{complaint_id}/status", response_model=ComplaintResponse)
def update_complaint_status(
    complaint_id: int,
    status_in: ComplaintStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates the lifecycle status of a complaint with mandatory audit logging.
    Citizens may only reopen their own resolved/rejected complaints.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise NotFoundException("Complaint not found")

    # Authorization enforcement
    if current_user.role == UserRole.CITIZEN:
        if complaint.citizen_id != current_user.id:
            raise ForbiddenException("You cannot modify other citizens' complaints")
        if status_in.status != ComplaintStatus.REOPENED:
            raise ForbiddenException("Citizens can only request reopening of resolved or rejected complaints")
    elif current_user.role == UserRole.OFFICER:
        # Check if officer is assigned or in the same department
        if current_user.department_id and complaint.department_id != current_user.department_id and complaint.assigned_officer_id != current_user.id:
            raise ForbiddenException("You can only update complaints within your assigned department")

    updated = complaint_service.update_status(db, complaint, status_in, current_user)
    return _to_complaint_response(updated)


@router.get("/{complaint_id}/history", response_model=List[ComplaintHistoryResponse])
def get_complaint_history(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches complete status transition audit history."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise NotFoundException("Complaint not found")

    if current_user.role == UserRole.CITIZEN and complaint.citizen_id != current_user.id:
        raise ForbiddenException("You do not have permission to view this complaint's history")

    history = (
        db.query(ComplaintHistory)
        .filter(ComplaintHistory.complaint_id == complaint_id)
        .order_by(desc(ComplaintHistory.created_at))
        .all()
    )

    return [
        ComplaintHistoryResponse(
            id=h.id,
            complaint_id=h.complaint_id,
            previous_status=h.previous_status,
            new_status=h.new_status,
            note=h.note,
            changed_by_name=h.changed_by.full_name if h.changed_by else "System",
            created_at=h.created_at
        )
        for h in history
    ]


@router.get("/{complaint_id}/notifications", response_model=List[NotificationResponse])
def get_complaint_notifications(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches notifications associated with a specific complaint."""
    notifications = (
        db.query(Notification)
        .filter(Notification.complaint_id == complaint_id, Notification.user_id == current_user.id)
        .order_by(desc(Notification.created_at))
        .all()
    )
    return notifications
