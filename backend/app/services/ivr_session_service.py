import time
import uuid
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("voxentra.ivr_session")


class IVRState(str, Enum):
    CALL_RECEIVED = "CALL_RECEIVED"
    WELCOME = "WELCOME"
    WAITING_FOR_CITIZEN = "WAITING_FOR_CITIZEN"
    RECORDING = "RECORDING"
    TRANSCRIBING = "TRANSCRIBING"
    LANGUAGE_DETECTION = "LANGUAGE_DETECTION"
    ANALYZING = "ANALYZING"
    ASKING_QUESTION = "ASKING_QUESTION"
    WAITING_FOR_RESPONSE = "WAITING_FOR_RESPONSE"
    CONFIRMING = "CONFIRMING"
    REGISTERING_COMPLAINT = "REGISTERING_COMPLAINT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    ENDED = "ENDED"


@dataclass
class IVRSession:
    call_session_id: str
    provider: str = "local_simulation"  # "local_simulation" | "exotel" | "twilio"
    caller_number: Optional[str] = "+919843098765"
    call_status: str = "connected"  # "ringing" | "connected" | "in-progress" | "completed" | "failed"
    current_state: IVRState = IVRState.WELCOME
    language: str = "Tamil"  # "Tamil" | "English" | "Tanglish" | "Mixed (Tamil/English)"
    conversation_context: Dict[str, Any] = field(default_factory=dict)
    turns: List[Dict[str, Any]] = field(default_factory=list)
    complaint_id: Optional[int] = None
    complaint_number: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at: Optional[str] = None
    duration_seconds: int = 0

    def transition_to(self, new_state: IVRState) -> None:
        """Transitions IVR state machine and updates timestamps."""
        logger.info(f"[IVRSession {self.call_session_id}] State transition: {self.current_state.value} -> {new_state.value}")
        self.current_state = new_state
        self.updated_at = datetime.utcnow().isoformat()

    def add_turn(self, speaker: str, text: str, audio_url: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Appends a dialogue turn to the session history."""
        turn_entry = {
            "turn_index": len(self.turns) + 1,
            "speaker": speaker,  # "ivr" | "citizen"
            "text": text,
            "audio_url": audio_url,
            "state": self.current_state.value,
            "language": self.language,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self.turns.append(turn_entry)
        self.updated_at = datetime.utcnow().isoformat()

    def end_call(self, final_state: IVRState = IVRState.ENDED) -> None:
        """Terminates IVR call session and records end duration."""
        self.current_state = final_state
        self.call_status = "completed" if final_state == IVRState.COMPLETED else "ended"
        self.ended_at = datetime.utcnow().isoformat()
        self.updated_at = self.ended_at
        try:
            start_dt = datetime.fromisoformat(self.started_at)
            end_dt = datetime.fromisoformat(self.ended_at)
            self.duration_seconds = int((end_dt - start_dt).total_seconds())
        except Exception:
            self.duration_seconds = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["current_state"] = self.current_state.value
        return data


class IVRSessionService:
    """
    In-memory and persistent manager for real-time IVR telephony sessions.
    Maintains active call state machines across local simulations and real Exotel / Twilio telephony calls.
    """
    def __init__(self):
        self._sessions: Dict[str, IVRSession] = {}

    def create_session(
        self,
        call_session_id: Optional[str] = None,
        caller_number: Optional[str] = None,
        provider: str = "local_simulation"
    ) -> IVRSession:
        sid = call_session_id or f"CALL_{uuid.uuid4().hex[:16]}"
        session = IVRSession(
            call_session_id=sid,
            caller_number=caller_number or "+919843098765",
            provider=provider,
            current_state=IVRState.WELCOME
        )
        self._sessions[sid] = session
        logger.info(f"[IVRSessionService] Created session {sid} for caller {caller_number} via {provider}")
        return session

    def get_session(self, call_session_id: str) -> Optional[IVRSession]:
        return self._sessions.get(call_session_id)

    def get_or_create_session(
        self,
        call_session_id: Optional[str] = None,
        caller_number: Optional[str] = None,
        provider: str = "local_simulation"
    ) -> IVRSession:
        if call_session_id and call_session_id in self._sessions:
            return self._sessions[call_session_id]
        return self.create_session(call_session_id, caller_number, provider)

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._sessions.values() if s.call_status in ["connected", "in-progress", "ringing"]]

    def list_all_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        sessions_list = [s.to_dict() for s in self._sessions.values()]
        sessions_list.sort(key=lambda x: x["started_at"], reverse=True)
        return sessions_list[:limit]

    def delete_session(self, call_session_id: str) -> bool:
        if call_session_id in self._sessions:
            del self._sessions[call_session_id]
            return True
        return False


ivr_session_service = IVRSessionService()
