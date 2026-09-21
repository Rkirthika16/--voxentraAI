from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.notification import Notification


class NotificationService:
    def create_notification(
        self,
        db: Session,
        user_id: int,
        title: str,
        message: str,
        complaint_id: Optional[int] = None
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            complaint_id=complaint_id,
            title=title,
            message=message,
            is_read=False
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    def get_user_notifications(
        self,
        db: Session,
        user_id: int,
        limit: int = 50
    ) -> List[Notification]:
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    def mark_as_read(
        self,
        db: Session,
        notification_id: int,
        user_id: int
    ) -> Optional[Notification]:
        notification = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if notification:
            notification.is_read = True
            db.commit()
            db.refresh(notification)
        return notification

    def mark_all_as_read(self, db: Session, user_id: int) -> int:
        count = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read == False)
            .update({"is_read": True})
        )
        db.commit()
        return count


notification_service = NotificationService()
