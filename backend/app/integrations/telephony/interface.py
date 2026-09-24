from typing import Protocol, Dict, Any, Optional, List
from enum import Enum


class TelephonyProviderType(str, Enum):
    LOCAL_SIMULATION = "local_simulation"
    EXOTEL = "exotel"
    TWILIO = "twilio"


class TelephonyProvider(Protocol):
    """Abstract protocol for Telephony and IVR service integrations."""

    def incoming_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Processes incoming voice call webhook."""
        ...

    def play_audio(self, call_session_id: str, audio_url_or_text: str, language: str = "Tamil") -> Dict[str, Any]:
        """Plays audio or speaks text over the phone call."""
        ...

    def collect_speech(self, call_session_id: str, prompt_text: str, language: str = "Tamil") -> Dict[str, Any]:
        """Prompts citizen and captures speech recording/stream."""
        ...

    def collect_digits(self, call_session_id: str, prompt_text: str, max_digits: int = 1) -> Dict[str, Any]:
        """Collects DTMF keypad digits from caller."""
        ...

    def record_audio(self, call_session_id: str, max_duration_seconds: int = 30) -> Dict[str, Any]:
        """Initiates recording of caller's grievance description."""
        ...

    def hangup(self, call_session_id: str) -> bool:
        """Terminates active call session."""
        ...

    def transfer_call(self, call_session_id: str, target_number: str) -> Dict[str, Any]:
        """Transfers call to a live department field officer."""
        ...

    def get_call_status(self, call_session_id: str) -> Dict[str, Any]:
        """Retrieves real-time status of call session."""
        ...

    def send_sms(self, to_phone: str, message: str) -> bool:
        """Sends SMS confirmation to citizen."""
        ...
