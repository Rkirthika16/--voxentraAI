from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.escalation import Escalation, EscalationStatus
from app.models.complaint import Complaint
from app.core.exceptions import NotFoundException


class EscalationService:
    def create_escalation(
        self,
        db: Session,
        complaint_id: int,
        reason: str,
        triggered_by_id: Optional[int] = None
    ) -> Escalation:
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            raise NotFoundException("Complaint not found")

        escalation = Escalation(
            complaint_id=complaint_id,
            triggered_by_id=triggered_by_id,
            reason=reason,
            status=EscalationStatus.OPEN
        )
        db.add(escalation)
        db.commit()
        db.refresh(escalation)
        return escalation

    def resolve_escalation(
        self,
        db: Session,
        escalation_id: int
    ) -> Escalation:
        escalation = db.query(Escalation).filter(Escalation.id == escalation_id).first()
        if not escalation:
            raise NotFoundException("Escalation record not found")

        escalation.status = EscalationStatus.RESOLVED
        escalation.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(escalation)
        return escalation


escalation_service = EscalationService()
