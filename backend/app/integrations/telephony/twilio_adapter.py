import logging
import uuid
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.config import settings

logger = logging.getLogger("voxentra.telephony.twilio")


class TwilioAdapter:
    """
    Adapter for Twilio Voice, IVR Webhooks & SMS integration.
    Supports TwiML response generation for multilingual Tamil/English telephony,
    inbound speech recording, and automated SMS callbacks.
    """

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self.is_configured = bool(self.account_sid and self.auth_token)
        # Ring buffer for recent telephony interactions (Calls & SMS)
        self.telephony_logs: List[Dict[str, Any]] = []

    def _log_event(self, event_type: str, direction: str, phone: str, details: Dict[str, Any], status: str = "SUCCESS"):
        log_entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": "TWILIO",
            "event_type": event_type,  # 'SMS_OUTBOUND', 'SMS_INBOUND', 'CALL_INBOUND', 'CALL_RECORDING'
            "direction": direction,    # 'INBOUND', 'OUTBOUND'
            "phone": phone,
            "status": status,
            "details": details
        }
        self.telephony_logs.insert(0, log_entry)
        if len(self.telephony_logs) > 100:
            self.telephony_logs.pop()

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.telephony_logs[:limit]

    def handle_incoming_call(self, payload: Dict[str, Any]) -> str:
        """
        Processes inbound call webhook from Twilio phone number.
        Returns TwiML XML instruction to play greeting and record citizen's voice grievance.
        """
        call_sid = payload.get("CallSid", f"CA_{uuid.uuid4().hex[:16]}")
        from_number = payload.get("From", "+919843098765")
        to_number = payload.get("To", self.phone_number or "+1913000000")

        logger.info(f"[Twilio] Inbound call from {from_number} -> {to_number} (CallSid: {call_sid})")

        prompt_ta = "வணக்கம். வாக்ஸென்ட்ரா தமிழ்நாடு அரசு ஊரக மற்றும் நகராட்சி பொது குறைதீர்ப்பு சேவைக்கு நல்வரவு. உங்கள் கிராம புகார் அல்லது பிரச்சனையை பீப் ஒலிக்கு பின் தெளிவாக கூறவும்."
        prompt_en = "Welcome to Voxentra Citizen Grievance Helpline. Please state your village problem or grievance clearly after the beep."

        # Generate standard TwiML XML
        twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="ta-IN">{prompt_ta}</Say>
    <Pause length="1"/>
    <Say voice="Polly.Aditi" language="en-IN">{prompt_en}</Say>
    <Record 
        action="/api/v1/webhooks/twilio/voice/recording" 
        method="POST" 
        maxLength="60" 
        finishOnKey="#" 
        playBeep="true" 
        transcribe="true"
    />
    <Say voice="Polly.Aditi" language="en-IN">We did not receive any recording. Goodbye.</Say>
</Response>"""

        self._log_event(
            event_type="CALL_INBOUND",
            direction="INBOUND",
            phone=from_number,
            details={
                "call_sid": call_sid,
                "to_number": to_number,
                "action": "twiml_play_and_record"
            }
        )

        return twiml_response

    def handle_recording_callback(self, payload: Dict[str, Any]) -> str:
        """
        Processes Twilio recording callback once citizen finishes speaking.
        Returns TwiML XML confirmation.
        """
        call_sid = payload.get("CallSid", f"CA_{uuid.uuid4().hex[:16]}")
        recording_url = payload.get("RecordingUrl", "")
        from_number = payload.get("From", "+919843098765")
        duration = payload.get("RecordingDuration", "0")

        logger.info(f"[Twilio] Recording completed for call {call_sid} ({duration}s): {recording_url}")

        self._log_event(
            event_type="CALL_RECORDING",
            direction="INBOUND",
            phone=from_number,
            details={
                "call_sid": call_sid,
                "recording_url": recording_url,
                "duration_seconds": duration
            }
        )

        reply_ta = "நன்றி! உங்கள் கிராம புகார் பெறப்பட்டது. சம்பந்தப்பட்ட துறைக்கு அனுப்பி புகார் எண் எஸ்.எம்.எஸ் மூலம் அனுப்பப்படும்."
        reply_en = "Thank you! Your grievance has been registered and forwarded to the designated department. Your tracking ID is being sent via SMS."

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="ta-IN">{reply_ta}</Say>
    <Pause length="1"/>
    <Say voice="Polly.Aditi" language="en-IN">{reply_en}</Say>
    <Hangup/>
</Response>"""

    def send_sms(self, to_phone: str, message: str) -> bool:
        """
        Sends SMS confirmation via Twilio REST API.
        Falls back gracefully to simulated logging if API credentials are not set.
        """
        if not to_phone:
            return False

        if self.is_configured:
            try:
                url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
                auth = (self.account_sid, self.auth_token)
                data = {
                    "From": self.phone_number,
                    "To": to_phone,
                    "Body": message
                }

                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(url, data=data, auth=auth)
                    if resp.status_code in [200, 201]:
                        sid = resp.json().get("sid", "SM_SUCCESS")
                        logger.info(f"[Twilio] Live SMS dispatched to {to_phone} (SID: {sid})")
                        self._log_event("SMS_OUTBOUND", "OUTBOUND", to_phone, {"message": message, "twilio_sid": sid}, "SUCCESS")
                        return True
                    else:
                        logger.warning(f"[Twilio] API error sending SMS to {to_phone}: {resp.status_code} - {resp.text}")
                        self._log_event("SMS_OUTBOUND", "OUTBOUND", to_phone, {"error": resp.text}, "FAILED")
                        return False
            except Exception as e:
                logger.error(f"[Twilio] Exception dispatching SMS to {to_phone}: {e}")
                self._log_event("SMS_OUTBOUND", "OUTBOUND", to_phone, {"error": str(e)}, "FAILED")
                return False

        # Simulation Mode
        logger.info(f"[Twilio Simulation] SMS delivered to {to_phone}: '{message}'")
        self._log_event(
            event_type="SMS_OUTBOUND",
            direction="OUTBOUND",
            phone=to_phone,
            details={
                "message": message,
                "simulation": True,
                "note": "Twilio live SMS simulator active. Credentials not configured in .env."
            },
            status="SUCCESS"
        )
        return True


twilio_adapter = TwilioAdapter()
