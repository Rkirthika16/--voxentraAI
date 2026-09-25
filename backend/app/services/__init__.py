from app.services.auth_service import auth_service, AuthService
from app.services.complaint_service import complaint_service, ComplaintService
from app.services.routing_service import routing_service, RoutingService
from app.services.notification_service import notification_service, NotificationService
from app.services.escalation_service import escalation_service, EscalationService

__all__ = [
    "auth_service",
    "AuthService",
    "complaint_service",
    "ComplaintService",
    "routing_service",
    "RoutingService",
    "notification_service",
    "NotificationService",
    "escalation_service",
    "EscalationService"
]


