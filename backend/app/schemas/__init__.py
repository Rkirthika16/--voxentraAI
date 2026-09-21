from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse, UserUpdate, UserCreateOfficer
from app.schemas.department import DepartmentResponse, DepartmentCreate, DepartmentUpdate
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintResponse,
    ComplaintDetailResponse,
    ComplaintStatusUpdate,
    ComplaintAssignRequest,
    ComplaintHistoryResponse
)
from app.schemas.analysis import TextAnalysisRequest, AnalysisResponse, AudioTranscriptionResponse, ExtractedLocation
from app.schemas.dashboard import AdminDashboardStats, CitizenDashboardStats
from app.schemas.notification import NotificationResponse

__all__ = [
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    "UserUpdate",
    "UserCreateOfficer",
    "DepartmentResponse",
    "DepartmentCreate",
    "DepartmentUpdate",
    "ComplaintCreate",
    "ComplaintResponse",
    "ComplaintDetailResponse",
    "ComplaintStatusUpdate",
    "ComplaintAssignRequest",
    "ComplaintHistoryResponse",
    "TextAnalysisRequest",
    "AnalysisResponse",
    "AudioTranscriptionResponse",
    "ExtractedLocation",
    "AdminDashboardStats",
    "CitizenDashboardStats",
    "NotificationResponse"
]
