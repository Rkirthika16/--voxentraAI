from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.database.session import get_db
from app.core.dependencies import require_role, get_current_user
from app.core.exceptions import NotFoundException
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.schemas.complaint import ComplaintResponse, ComplaintAssignRequest
from app.schemas.user import UserResponse
from app.services.complaint_service import complaint_service
from app.api.routes.complaints import _to_complaint_response

router = APIRouter(prefix="/officers", tags=["Officer Operations"])


@router.get("/complaints", response_model=List[ComplaintResponse])
def get_officer_queue(
    assigned_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Returns complaints assigned to the officer or available in their department.
    """
    query = db.query(Complaint)

    if assigned_only or not current_user.department_id:
        query = query.filter(Complaint.assigned_officer_id == current_user.id)
    else:
        query = query.filter(
            or_(
                Complaint.assigned_officer_id == current_user.id,
                Complaint.department_id == current_user.department_id
            )
        )

    offset = (page - 1) * page_size
    complaints = query.order_by(desc(Complaint.created_at)).offset(offset).limit(page_size).all()
    return [_to_complaint_response(c) for c in complaints]


@router.post("/assign", response_model=ComplaintResponse)
def assign_complaint_to_officer(
    complaint_id: int,
    assign_in: ComplaintAssignRequest,
    current_user: User = Depends(require_role(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Assigns an officer to investigate a complaint.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise NotFoundException("Complaint not found")

    officer = db.query(User).filter(User.id == assign_in.officer_id).first()
    if not officer:
        raise NotFoundException("Officer not found")

    updated = complaint_service.assign_officer(
        db=db,
        complaint=complaint,
        officer=officer,
        assigned_by=current_user,
        notes=assign_in.notes
    )
    return _to_complaint_response(updated)


@router.get("/list", response_model=List[UserResponse])
def list_available_officers(
    department_id: Optional[int] = None,
    current_user: User = Depends(require_role(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Lists available officers for assignment."""
    query = db.query(User).filter(User.role == UserRole.OFFICER, User.is_active == True)
    if department_id:
        query = query.filter(User.department_id == department_id)
    return query.order_by(User.full_name.asc()).all()
