from app.services.auth_service import auth_service, AuthService
from app.services.complaint_service import complaint_service, ComplaintService
from app.services.routing_service import routing_service, RoutingService
from app.services.notification_service import notification_service, NotificationService
from app.services.escalation_service import escalation_service, EscalationService
from app.services.conversation_manager import conversation_manager, ConversationManager
from app.services.voice_assistant import voice_assistant, VoiceAssistantService
from app.services.location_resolver import location_resolver, CoimbatoreLocationResolver
from app.services.speech_correction import speech_correction_service, SpeechCorrectionService
from app.services.language_detector import language_detector, LanguageDetector
from app.services.question_manager import question_manager, QuestionManager
from app.services.new_ivr_service import new_ivr_service, NewIVRService

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
    "EscalationService",
    "conversation_manager",
    "ConversationManager",
    "voice_assistant",
    "VoiceAssistantService",
    "location_resolver",
    "CoimbatoreLocationResolver",
    "speech_correction_service",
    "SpeechCorrectionService",
    "language_detector",
    "LanguageDetector",
    "question_manager",
    "QuestionManager",
    "new_ivr_service",
    "NewIVRService"
]



