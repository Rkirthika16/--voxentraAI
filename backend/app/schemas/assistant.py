from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.complaint import ComplaintPriority


class ActionSuggestion(BaseModel):
    label: str
    action_type: str = Field(..., description="Action type: SUBMIT_DRAFT, TRACK_COMPLAINT, CALL_HELPLINE, QUICK_PROMPT")
    payload: Dict[str, Any] = Field(default_factory=dict)
    icon: Optional[str] = "sparkles"


class ComplaintDraft(BaseModel):
    title: str
    description: str
    category: str
    suggested_department: str
    extracted_location: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    priority: ComplaintPriority = ComplaintPriority.MEDIUM
    summary: str


class ComplaintCollectionStateSchema(BaseModel):
    session_id: str
    stage: str = Field(..., description="GREETING, COLLECTING, CONFIRMATION_PENDING, REGISTERED")
    language: str
    fields: Dict[str, Optional[str]]
    current_field_prompted: Optional[str] = None
    completed_fields_count: int = 0
    total_fields: int = 10
    completion_percentage: int = 0
    created_complaint_number: Optional[str] = None
    created_complaint_id: Optional[int] = None


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    language_hint: Optional[str] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    reply_text: str
    spoken_text: str
    detected_language: str
    intent: str
    draft_complaint: Optional[ComplaintDraft] = None
    status_info: Optional[Dict[str, Any]] = None
    collection_state: Optional[ComplaintCollectionStateSchema] = None
    suggested_actions: List[ActionSuggestion] = Field(default_factory=list)
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssistantVoiceChatResponse(AssistantResponse):
    transcription: str
    speech_status: str
    duration_seconds: Optional[float] = None


class SuggestionsResponse(BaseModel):
    sample_questions: List[Dict[str, str]]
    emergency_helplines: List[Dict[str, str]]
    quick_categories: List[Dict[str, str]]

