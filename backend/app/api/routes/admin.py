from typing import List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

from app.database.session import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.complaint import Complaint, ComplaintStatus, ComplaintPriority
from app.models.escalation import Escalation
from app.models.complaint_history import ComplaintHistory
from app.schemas.dashboard import (
    AdminDashboardStats,
    CategoryStatItem,
    DepartmentStatItem,
    PriorityStatItem
)
from app.services.escalation_service import escalation_service

router = APIRouter(prefix="/admin", tags=["Admin Operations"])


@router.get("/stats", response_model=AdminDashboardStats)
def get_admin_dashboard_stats(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OFFICER)),
    db: Session = Depends(get_db)
):
    """
    Returns real live aggregated statistics computed directly from the database.
    Never outputs fabricated or hardcoded sample numbers.
    """
    total = db.query(func.count(Complaint.id)).scalar() or 0
    
    # Status counts
    submitted = db.query(func.count(Complaint.id)).filter(Complaint.status == ComplaintStatus.SUBMITTED).scalar() or 0
    under_review = db.query(func.count(Complaint.id)).filter(Complaint.status == ComplaintStatus.UNDER_REVIEW).scalar() or 0
    assigned = db.query(func.count(Complaint.id)).filter(Complaint.status == ComplaintStatus.ASSIGNED).scalar() or 0
    in_progress = db.query(func.count(Complaint.id)).filter(Complaint.status == ComplaintStatus.IN_PROGRESS).scalar() or 0
    resolved = db.query(func.count(Complaint.id)).filter(Complaint.status == ComplaintStatus.RESOLVED).scalar() or 0
    rejected = db.query(func.count(Complaint.id)).filter(Complaint.status == ComplaintStatus.REJECTED).scalar() or 0
    reopened = db.query(func.count(Complaint.id)).filter(Complaint.status == ComplaintStatus.REOPENED).scalar() or 0
    overdue = db.query(func.count(Complaint.id)).filter(Complaint.status == ComplaintStatus.OVERDUE).scalar() or 0
    critical = db.query(func.count(Complaint.id)).filter(Complaint.priority == ComplaintPriority.CRITICAL).scalar() or 0

    # Category breakdown
    cat_rows = (
        db.query(Complaint.category, func.count(Complaint.id))
        .group_by(Complaint.category)
        .all()
    )
    categories = [CategoryStatItem(category=r[0] or "Other", count=r[1]) for r in cat_rows]

    # Priority breakdown
    pri_rows = (
        db.query(Complaint.priority, func.count(Complaint.id))
        .group_by(Complaint.priority)
        .all()
    )
    priorities = [PriorityStatItem(priority=r[0].value if hasattr(r[0], 'value') else str(r[0]), count=r[1]) for r in pri_rows]

    # Department breakdown
    all_depts = db.query(Department).all()
    departments: List[DepartmentStatItem] = []
    for d in all_depts:
        d_total = db.query(func.count(Complaint.id)).filter(Complaint.department_id == d.id).scalar() or 0
        d_pending = db.query(func.count(Complaint.id)).filter(
            Complaint.department_id == d.id,
            Complaint.status.in_([ComplaintStatus.SUBMITTED, ComplaintStatus.UNDER_REVIEW, ComplaintStatus.ASSIGNED])
        ).scalar() or 0
        d_in_prog = db.query(func.count(Complaint.id)).filter(
            Complaint.department_id == d.id,
            Complaint.status == ComplaintStatus.IN_PROGRESS
        ).scalar() or 0
        d_res = db.query(func.count(Complaint.id)).filter(
            Complaint.department_id == d.id,
            Complaint.status == ComplaintStatus.RESOLVED
        ).scalar() or 0

        departments.append(
            DepartmentStatItem(
                department_id=d.id,
                department_name=d.name,
                total=d_total,
                pending=d_pending,
                in_progress=d_in_prog,
                resolved=d_res
            )
        )

    # Recent history activity
    recent_history = (
        db.query(ComplaintHistory)
        .order_by(desc(ComplaintHistory.created_at))
        .limit(10)
        .all()
    )
    activity = [
        {
            "id": h.id,
            "complaint_id": h.complaint_id,
            "complaint_number": h.complaint.complaint_number if h.complaint else "N/A",
            "new_status": h.new_status,
            "note": h.note,
            "changed_by": h.changed_by.full_name if h.changed_by else "System",
            "created_at": h.created_at.isoformat()
        }
        for h in recent_history
    ]

    return AdminDashboardStats(
        total_complaints=total,
        submitted=submitted,
        under_review=under_review,
        assigned=assigned,
        in_progress=in_progress,
        resolved=resolved,
        rejected=rejected,
        reopened=reopened,
        overdue=overdue,
        emergency_critical=critical,
        categories=categories,
        departments=departments,
        priorities=priorities,
        recent_activity=activity
    )


@router.get("/escalations")
def list_escalations(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Lists all active and resolved complaint escalations."""
    return db.query(Escalation).order_by(desc(Escalation.created_at)).all()


@router.post("/escalations/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Resolves an open escalation."""
    return escalation_service.resolve_escalation(db, escalation_id)
