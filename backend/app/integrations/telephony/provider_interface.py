import abc
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("voxentra.telephony.provider")


class TelephonyProvider(abc.ABC):
    """
    Abstract Telephony Provider Interface.
    Enables pluggable integration with Exotel, Twilio, or generic SIP/VoIP webhooks.
    """

    @abc.abstractmethod
    def generate_incoming_call_response(
        self,
        call_session_id: str,
        greeting_text: str,
        speech_action_url: str,
        lang: str = "Tanglish"
    ) -> str:
        """Generates XML/TwiML/Passthru payload to play greeting and listen for citizen speech."""
        pass

    @abc.abstractmethod
    def generate_speech_gather_response(
        self,
        call_session_id: str,
        prompt_text: str,
        speech_action_url: str,
        lang: str = "Tanglish"
    ) -> str:
        """Generates payload to speak prompt and listen for citizen answer."""
        pass

    @abc.abstractmethod
    def generate_hangup_response(
        self,
        call_session_id: str,
        final_message: str,
        lang: str = "Tanglish"
    ) -> str:
        """Generates payload to speak final confirmation and disconnect call."""
        pass

    @abc.abstractmethod
    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        """Dispatches complaint confirmation SMS."""
        pass


class GenericTelephonyProvider(TelephonyProvider):
    """
    Standard XML/TwiML Telephony Provider for Toll-Free telephony gateways.
    """

    def generate_incoming_call_response(
        self,
        call_session_id: str,
        greeting_text: str,
        speech_action_url: str,
        lang: str = "Tanglish"
    ) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'    <Say language="en-IN">{greeting_text}</Say>\n'
            f'    <Record action="{speech_action_url}" method="POST" maxLength="60" finishOnKey="#" playBeep="true" transcribe="true"/>\n'
            "</Response>"
        )

    def generate_speech_gather_response(
        self,
        call_session_id: str,
        prompt_text: str,
        speech_action_url: str,
        lang: str = "Tanglish"
    ) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'    <Say language="en-IN">{prompt_text}</Say>\n'
            f'    <Record action="{speech_action_url}" method="POST" maxLength="60" finishOnKey="#" playBeep="true" transcribe="true"/>\n'
            "</Response>"
        )

    def generate_hangup_response(
        self,
        call_session_id: str,
        final_message: str,
        lang: str = "Tanglish"
    ) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'    <Say language="en-IN">{final_message}</Say>\n'
            "    <Hangup/>\n"
            "</Response>"
        )

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        from app.integrations.telephony.twilio_adapter import twilio_adapter
        return twilio_adapter.send_sms(to_phone, message)


generic_telephony_provider = GenericTelephonyProvider()
