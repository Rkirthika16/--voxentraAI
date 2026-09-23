from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintSource
from app.models.complaint_history import ComplaintHistory
from app.models.assignment import Assignment
from app.models.user import User, UserRole
from app.schemas.complaint import ComplaintCreate, ComplaintStatusUpdate
from app.services.routing_service import routing_service
from app.services.notification_service import notification_service
from app.core.exceptions import BadRequestException, NotFoundException, ForbiddenException

# Allowed status transitions dictionary
VALID_TRANSITIONS: Dict[ComplaintStatus, List[ComplaintStatus]] = {
    ComplaintStatus.SUBMITTED: [
        ComplaintStatus.UNDER_REVIEW,
        ComplaintStatus.ASSIGNED,
        ComplaintStatus.REJECTED
    ],
    ComplaintStatus.UNDER_REVIEW: [
        ComplaintStatus.ASSIGNED,
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.REJECTED
    ],
    ComplaintStatus.ASSIGNED: [
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.REJECTED
    ],
    ComplaintStatus.IN_PROGRESS: [
        ComplaintStatus.RESOLVED,
        ComplaintStatus.REJECTED,
        ComplaintStatus.OVERDUE
    ],
    ComplaintStatus.RESOLVED: [
        ComplaintStatus.REOPENED
    ],
    ComplaintStatus.REJECTED: [
        ComplaintStatus.REOPENED
    ],
    ComplaintStatus.REOPENED: [
        ComplaintStatus.UNDER_REVIEW,
        ComplaintStatus.ASSIGNED,
        ComplaintStatus.IN_PROGRESS
    ],
    ComplaintStatus.OVERDUE: [
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.RESOLVED,
        ComplaintStatus.REJECTED
    ]
}


class ComplaintService:
    def _generate_complaint_number(self, db: Session) -> str:
        today = datetime.now(timezone.utc).date()
        date_str = today.strftime("%Y%m%d")
        prefix = f"VX-{date_str}-"

        # Query all existing complaint numbers with today's prefix to find highest sequence
        existing = db.query(Complaint.complaint_number).filter(
            Complaint.complaint_number.like(f"{prefix}%")
        ).all()

        max_seq = 0
        for (c_num,) in existing:
            if c_num and c_num.startswith(prefix):
                suffix = c_num[len(prefix):]
                if suffix.isdigit():
                    max_seq = max(max_seq, int(suffix))

        candidate_seq = max_seq + 1
        while True:
            candidate = f"{prefix}{str(candidate_seq).zfill(6)}"
            exists = db.query(Complaint.id).filter(Complaint.complaint_number == candidate).first()
            if not exists:
                return candidate
            candidate_seq += 1

    def _calculate_due_date(self, priority: ComplaintPriority) -> datetime:
        now = datetime.now(timezone.utc)
        if priority == ComplaintPriority.CRITICAL:
            return now + timedelta(hours=24)
        elif priority == ComplaintPriority.HIGH:
            return now + timedelta(hours=48)
        elif priority == ComplaintPriority.MEDIUM:
            return now + timedelta(hours=72)
        else:
            return now + timedelta(hours=120)

    def create_complaint(
        self,
        db: Session,
        complaint_in: ComplaintCreate,
        citizen_id: Optional[int] = None
    ) -> Complaint:
        complaint_number = self._generate_complaint_number(db)
        
        # Route to appropriate department
        dept = routing_service.route_category_to_department(db, complaint_in.category or "Other")
        dept_id = dept.id if dept else None

        priority = complaint_in.priority or ComplaintPriority.MEDIUM
        due_at = self._calculate_due_date(priority)

        # Generate meaningful title if omitted
        title = complaint_in.title
        if not title:
            loc_str = f" at {complaint_in.location}" if complaint_in.location else ""
            title = f"{complaint_in.category or 'Civic'} issue{loc_str}"

        complaint = Complaint(
            complaint_number=complaint_number,
            citizen_id=citizen_id,
            department_id=dept_id,
            title=title[:200],
            description=complaint_in.description,
            original_text=complaint_in.description,
            language=complaint_in.language or "English",
            category=complaint_in.category or "Other",
            location=complaint_in.location,
            latitude=complaint_in.latitude,
            longitude=complaint_in.longitude,
            priority=priority,
            status=ComplaintStatus.SUBMITTED,
            source=complaint_in.source or ComplaintSource.WEB_TEXT,
            ai_metadata=complaint_in.ai_metadata,
            citizen_confirmed=complaint_in.citizen_confirmed if complaint_in.citizen_confirmed is not None else True,
            audio_file_path=complaint_in.audio_file_path,
            due_at=due_at
        )

        db.add(complaint)
        db.commit()
        db.refresh(complaint)

        # Initial history record
        history = ComplaintHistory(
            complaint_id=complaint.id,
            previous_status=None,
            new_status=ComplaintStatus.SUBMITTED.value,
            note="Complaint registered in system via " + complaint.source.value,
            changed_by_id=citizen_id
        )
        db.add(history)
        db.commit()

        # In-app notification for citizen
        if citizen_id:
            dept_name = dept.name if dept else "General Department"
            notification_service.create_notification(
                db=db,
                user_id=citizen_id,
                title="Complaint Submitted",
                message=f"Your complaint #{complaint.complaint_number} has been registered and routed to {dept_name}.",
                complaint_id=complaint.id
            )

        return complaint

    def update_status(
        self,
        db: Session,
        complaint: Complaint,
        status_in: ComplaintStatusUpdate,
        current_user: User
    ) -> Complaint:
        current_status = complaint.status
        new_status = status_in.status

        # Check if transition is valid
        if new_status != current_status:
            allowed = VALID_TRANSITIONS.get(current_status, [])
            if new_status not in allowed and current_user.role != UserRole.ADMIN:
                raise BadRequestException(
                    f"Invalid status transition from '{current_status.value}' to '{new_status.value}'. Allowed: {[s.value for s in allowed]}"
                )

        prev_status_str = current_status.value
        complaint.status = new_status
        complaint.updated_at = datetime.now(timezone.utc)

        if new_status == ComplaintStatus.RESOLVED:
            complaint.resolved_at = datetime.now(timezone.utc)

        # Create history record
        history = ComplaintHistory(
            complaint_id=complaint.id,
            previous_status=prev_status_str,
            new_status=new_status.value,
            note=status_in.note or f"Status changed to {new_status.value}",
            changed_by_id=current_user.id
        )
        db.add(history)
        db.commit()
        db.refresh(complaint)

        # Notify citizen
        if complaint.citizen_id:
            notification_service.create_notification(
                db=db,
                user_id=complaint.citizen_id,
                title=f"Complaint Status: {new_status.value}",
                message=f"Your complaint #{complaint.complaint_number} status updated to {new_status.value}. Note: {status_in.note or 'No additional notes'}",
                complaint_id=complaint.id
            )

        return complaint

    def assign_officer(
        self,
        db: Session,
        complaint: Complaint,
        officer: User,
        assigned_by: User,
        notes: Optional[str] = None
    ) -> Complaint:
        if officer.role != UserRole.OFFICER and officer.role != UserRole.ADMIN:
            raise BadRequestException("Target user is not an officer or administrator")

        prev_officer_id = complaint.assigned_officer_id
        complaint.assigned_officer_id = officer.id
        
        # If status was SUBMITTED or UNDER_REVIEW, transition to ASSIGNED
        if complaint.status in [ComplaintStatus.SUBMITTED, ComplaintStatus.UNDER_REVIEW]:
            complaint.status = ComplaintStatus.ASSIGNED

        # Record assignment
        assignment = Assignment(
            complaint_id=complaint.id,
            officer_id=officer.id,
            assigned_by_id=assigned_by.id,
            notes=notes
        )
        db.add(assignment)

        # Record history
        history = ComplaintHistory(
            complaint_id=complaint.id,
            previous_status=complaint.status.value,
            new_status=complaint.status.value,
            note=f"Assigned to Officer {officer.full_name}. Notes: {notes or 'N/A'}",
            changed_by_id=assigned_by.id
        )
        db.add(history)
        db.commit()
        db.refresh(complaint)

        # Notify assigned officer
        notification_service.create_notification(
            db=db,
            user_id=officer.id,
            title="New Grievance Assigned",
            message=f"Complaint #{complaint.complaint_number} ({complaint.category}) has been assigned to you.",
            complaint_id=complaint.id
        )

        # Notify citizen
        if complaint.citizen_id:
            notification_service.create_notification(
                db=db,
                user_id=complaint.citizen_id,
                title="Officer Assigned",
                message=f"Officer {officer.full_name} has been assigned to investigate your complaint #{complaint.complaint_number}.",
                complaint_id=complaint.id
            )

        return complaint


complaint_service = ComplaintService()
