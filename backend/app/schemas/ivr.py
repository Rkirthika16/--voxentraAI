from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class IVRCallInitiateRequest(BaseModel):
    caller_phone: str = Field(default="+919843098765", description="Village caller mobile number")
    toll_free_number: str = Field(default="1800-425-1913", description="Toll-free helpline number dialed")


class IVRCallInitiateResponse(BaseModel):
    call_sid: str
    caller_phone: str
    toll_free_number: str
    greeting_tamil: str
    greeting_english: str
    prompt_tamil: str
    prompt_english: str
    combined_spoken_prompt: str


class IVRProcessSpeechRequest(BaseModel):
    call_sid: Optional[str] = None
    caller_phone: Optional[str] = "+919843098765"
    speech_text: Optional[str] = None
    language_hint: Optional[str] = None


class IVRProcessSpeechResponse(BaseModel):
    call_sid: str
    caller_phone: str
    transcription: str
    detected_language: str
    category: str
    suggested_department: str
    department_id: Optional[int] = None
    extracted_location: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    priority: str
    complaint_number: str
    complaint_id: int
    confirmation_spoken_tamil: str
    confirmation_spoken_english: str
    combined_spoken_confirmation: str
    sms_text: str
    status: str
    audio_prediction: Optional[Dict[str, Any]] = None


class IVRCallDialogueRequest(BaseModel):
    call_sid: str
    caller_phone: Optional[str] = "+919843098765"
    dialogue_turn: int = Field(default=1, description="Current turn in conversation")
    user_speech: str = Field(..., description="What the village citizen said")
    conversation_history: Optional[list] = []
    language_preference: Optional[str] = "Auto"


class IVRCallDialogueResponse(BaseModel):
    call_sid: str
    dialogue_turn: int
    ai_spoken_reply: str
    ai_spoken_reply_tamil: str
    ai_spoken_reply_english: str
    detected_language: str
    language_confidence: Optional[float] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    osm_location_name: Optional[str] = None
    intent: str  # 'GATHER_MORE_INFO' | 'CONFIRMATION_PENDING' | 'CONFIRMED' | 'GENERAL_HELP'
    extracted_category: Optional[str] = None
    extracted_location: Optional[str] = None
    suggested_department: Optional[str] = None
    is_confirmation_pending: bool = False
    is_completed: bool = False
    collection_state: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    complaint_id: Optional[int] = None
    complaint_number: Optional[str] = None
    sms_sent: bool = False
    sms_failure_reason: Optional[str] = None


# Inbound Village SMS Schemas
class InboundSMSRequest(BaseModel):
    from_phone: str = Field(default="+919843098765", description="Sender mobile number from village")
    to_phone: Optional[str] = Field(default="1800-425-1913", description="Helpline or Exotel virtual number")
    message_body: str = Field(..., description="Grievance message content in Tamil, Tanglish, or English")
    sms_sid: Optional[str] = None


class InboundSMSResponse(BaseModel):
    sms_sid: str
    sender_phone: str
    raw_message: str
    detected_language: str
    extracted_category: str
    extracted_location: Optional[str] = None
    assigned_department: str
    complaint_id: int
    complaint_number: str
    reply_sms_tamil: str
    reply_sms_english: str
    reply_sms_dispatched: str
    status: str


# Manual SMS Dispatch by Officers
class ManualSMSRequest(BaseModel):
    to_phone: str = Field(..., description="Citizen recipient mobile number")
    message: str = Field(..., description="SMS message text")
    complaint_number: Optional[str] = None


class ManualSMSResponse(BaseModel):
    success: bool
    sms_sid: str
    to_phone: str
    message: str
    mode: str
    status: str


class TelephonyLogItem(BaseModel):
    id: str
    timestamp: str
    event_type: str
    direction: str
    phone: str
    status: str
    details: Dict[str, Any]


class TelephonyLogsResponse(BaseModel):
    total: int
    logs: List[TelephonyLogItem]


# ─── Voice Register Dedicated API Schemas ────────────────────────────────────

class VoiceRegisterStartRequest(BaseModel):
    caller_phone: Optional[str] = Field(default="+919843098765", description="Citizen mobile number (from Exotel caller ID or manual input)")
    language_hint: Optional[str] = Field(default="Auto", description="Preferred language: 'Tamil', 'English', 'Tanglish', or 'Auto'")
    exotel_call_sid: Optional[str] = Field(default=None, description="Exotel CallSid if triggered from live inbound call")


class VoiceRegisterStartResponse(BaseModel):
    session_id: str
    call_sid: str
    greeting_text: str
    greeting_text_tamil: str
    greeting_text_english: str
    detected_language: str
    first_question: str


class VoiceRegisterTurnRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="Dialogue session ID")
    call_sid: Optional[str] = Field(default=None, description="Exotel / telephony call SID")
    dialogue_turn: int = Field(default=1)
    user_speech: str = Field(..., description="What the citizen said in this turn")
    caller_phone: Optional[str] = "+919843098765"
    language_preference: Optional[str] = "Auto"


class VoiceRegisterTurnResponse(BaseModel):
    session_id: str
    call_sid: str
    dialogue_turn: int
    ai_reply: str
    ai_reply_tamil: str
    ai_reply_english: str
    detected_language: str
    language_confidence: Optional[float] = None
    intent: str
    fields_collected: int
    fields_total: int
    next_field: Optional[str] = None
    is_confirmation_pending: bool = False
    is_completed: bool = False
    collection_state: Optional[Dict[str, Any]] = None
    complaint_id: Optional[int] = None
    complaint_number: Optional[str] = None
    sms_sent: bool = False
    sms_failure_reason: Optional[str] = None


class VoiceRegisterSessionResponse(BaseModel):
    session_id: str
    call_sid: str
    state: str
    language: str
    dialogue_turn: int
    fields: Dict[str, Any]
    fields_collected: int
    fields_total: int
    complaint_number: Optional[str] = None
    complaint_id: Optional[int] = None
