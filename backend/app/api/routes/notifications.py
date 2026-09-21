from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse])
def get_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves all notifications for the authenticated user."""
    return notification_service.get_user_notifications(db, current_user.id)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marks a single notification as read."""
    notif = notification_service.mark_as_read(db, notification_id, current_user.id)
    if not notif:
        raise NotFoundException("Notification not found")
    return notif


@router.post("/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marks all notifications as read for current user."""
    count = notification_service.mark_all_as_read(db, current_user.id)
    return {"message": f"{count} notifications marked as read"}
