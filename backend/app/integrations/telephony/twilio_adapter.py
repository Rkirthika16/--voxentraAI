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

    def build_complaint_sms(
        self,
        complaint_number: str,
        description: str,
        department: str,
        location: str,
        lang: str,
        created_at: Optional[datetime] = None
    ) -> str:
        """
        Builds a bilingual SMS body for complaint registration confirmation.
        lang: 'Tamil' | 'English' | 'Tanglish'
        Tanglish defaults to English SMS policy.
        """
        dt = created_at or datetime.now(timezone.utc)
        date_str = dt.strftime("%d-%m-%Y %H:%M")

        # Truncate description for SMS character limits
        desc_short = description[:100].strip()
        loc_short = location[:80].strip() if location else "\u2014"

        if lang == "Tamil":
            return (
                "VoxentraAI \u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1 "
                "\u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba4\u0bc1.\n\n"
                f"\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0b8e\u0ba3\u0bcd: {complaint_number}\n"
                f"\u0baa\u0bbf\u0bb0\u0b9a\u0bcd\u0b9a\u0bbf\u0ba9\u0bc8: {desc_short}\n"
                f"\u0ba4\u0bc1\u0bb1\u0bc8: {department}\n"
                f"\u0b87\u0b9f\u0bae\u0bcd: {loc_short}\n"
                "\u0ba8\u0bbf\u0bb2\u0bc8: \u0baa\u0ba4\u0bbf\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1\n"
                f"\u0ba4\u0bc7\u0ba4\u0bbf: {date_str}\n\n"
                "\u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0b8e\u0ba3\u0bcd\u0ba3\u0bc8\u0baa\u0bcd "
                "\u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bc8 "
                "\u0b95\u0ba3\u0bcd\u0b95\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0bb2\u0bbe\u0bae\u0bcd."
            )
        else:
            # English and Tanglish use English SMS policy
            return (
                f"VoxentraAI Complaint Registered.\n\n"
                f"Complaint ID: {complaint_number}\n"
                f"Issue: {desc_short}\n"
                f"Department: {department}\n"
                f"Location: {loc_short}\n"
                f"Status: REGISTERED\n"
                f"Date: {date_str}\n\n"
                f"Track your complaint using the above ID."
            )

    def handle_incoming_call(self, payload: Dict[str, Any]) -> str:
        """
        Processes inbound call webhook from Twilio phone number.
        Returns TwiML XML instruction to play greeting and record citizen's voice grievance.
        """
        call_sid = payload.get("CallSid", f"CA_{uuid.uuid4().hex[:16]}")
        from_number = payload.get("From", "+919843098765")
        to_number = payload.get("To", self.phone_number or "+1913000000")

        logger.info(f"[Twilio] Inbound call from {from_number} -> {to_number} (CallSid: {call_sid})")

        prompt_ta = (
            "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd. \u0bb5\u0bbe\u0b95\u0bcd\u0b9a\u0bc6\u0ba9\u0bcd"
            "\u0b9f\u0bcd\u0bb0\u0bbe \u0ba4\u0bae\u0bbf\u0bb4\u0bcd\u0ba8\u0bbe\u0b9f\u0bc1 \u0b85\u0bb0\u0b9a\u0bc1 "
            "\u0b8a\u0bb0\u0b95 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0b95\u0bb0\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf "
            "\u0baa\u0bcb\u0ba4\u0bc1 \u0b95\u0bc1\u0bb1\u0bc8\u0ba4\u0bc0\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 "
            "\u0b9a\u0bc7\u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bb2\u0bcd\u0bb5\u0bb0\u0bb5\u0bc1."
        )
        prompt_en = "Welcome to Voxentra Citizen Grievance Helpline. Please state your village problem or grievance clearly after the beep."

        # Generate standard TwiML XML
        twiml_response = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'    <Say voice="Polly.Aditi" language="ta-IN">{prompt_ta}</Say>\n'
            '    <Pause length="1"/>\n'
            f'    <Say voice="Polly.Aditi" language="en-IN">{prompt_en}</Say>\n'
            "    <Record \n"
            '        action="/api/v1/webhooks/twilio/voice/recording" \n'
            '        method="POST" \n'
            '        maxLength="60" \n'
            '        finishOnKey="#" \n'
            '        playBeep="true" \n'
            '        transcribe="true"\n'
            "    />\n"
            '    <Say voice="Polly.Aditi" language="en-IN">We did not receive any recording. Goodbye.</Say>\n'
            "</Response>"
        )

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

        reply_ta = (
            "\u0ba8\u0ba9\u0bcd\u0bb1\u0bbf! \u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bbf\u0bb0\u0bbe\u0bae "
            "\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0baa\u0bc6\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1. "
            "\u0b9a\u0bae\u0bcd\u0baa\u0ba8\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0bc1\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bc1 "
            "\u0b85\u0ba9\u0bc1\u0baa\u0bcd\u0baa\u0bbf \u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0b8e\u0ba3\u0bcd "
            "\u0b8e\u0bb8\u0bcd.\u0b8e\u0bae\u0bcd.\u0b8e\u0bb8\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b85\u0ba9\u0bc1\u0baa\u0bcd\u0baa\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd."
        )
        reply_en = "Thank you! Your grievance has been registered and forwarded to the designated department. Your tracking ID is being sent via SMS."

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'    <Say voice="Polly.Aditi" language="ta-IN">{reply_ta}</Say>\n'
            '    <Pause length="1"/>\n'
            f'    <Say voice="Polly.Aditi" language="en-IN">{reply_en}</Say>\n'
            "    <Hangup/>\n"
            "</Response>"
        )

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        """
        Sends SMS confirmation via Twilio REST API.
        Returns a dict: {"success": bool, "sid": str, "mode": str, "error": str|None}
        Falls back gracefully to simulated logging if API credentials are not set.
        """
        if not to_phone:
            return {"success": False, "sid": "", "mode": "SKIPPED", "error": "No recipient phone provided"}

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
                        return {"success": True, "sid": sid, "mode": "LIVE", "error": None}
                    else:
                        err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        logger.warning(f"[Twilio] API error sending SMS to {to_phone}: {err}")
                        self._log_event("SMS_OUTBOUND", "OUTBOUND", to_phone, {"error": err}, "FAILED")
                        return {"success": False, "sid": "", "mode": "LIVE", "error": err}
            except Exception as e:
                err = str(e)
                logger.error(f"[Twilio] Exception dispatching SMS to {to_phone}: {err}")
                self._log_event("SMS_OUTBOUND", "OUTBOUND", to_phone, {"error": err}, "FAILED")
                return {"success": False, "sid": "", "mode": "LIVE", "error": err}

        # Simulation Mode
        sim_sid = f"SM_SIM_{uuid.uuid4().hex[:12]}"
        logger.info(f"[Twilio Simulation] SMS delivered to {to_phone}: '{message[:80]}...'")
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
        return {"success": True, "sid": sim_sid, "mode": "SIMULATED", "error": None}


twilio_adapter = TwilioAdapter()
