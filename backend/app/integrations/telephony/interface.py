from typing import Protocol, Dict, Any, Optional


class TelephonyProvider(Protocol):
    """Abstract protocol for Telephony and IVR service integrations."""

    def handle_incoming_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Processes incoming voice call webhook."""
        ...

    def handle_recording_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Processes completed audio recording webhook."""
        ...

    def send_sms(self, to_phone: str, message: str) -> bool:
        """Sends SMS confirmation to citizen."""
        ...
