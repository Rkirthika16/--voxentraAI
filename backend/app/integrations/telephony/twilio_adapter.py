import hmac
import hashlib
import base64
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
        """
        dt = created_at or datetime.now(timezone.utc)
        date_str = dt.strftime("%d-%m-%Y %H:%M")

        desc_short = description[:100].strip()
        loc_short = location[:80].strip() if location else "—"

        if lang == "Tamil":
            return (
                "VoxentraAI புகார் பதிவு செய்யப்பட்டுள்ளது.\n\n"
                f"புகார் எண்: {complaint_number}\n"
                f"பிரச்சினை: {desc_short}\n"
                f"துறை: {department}\n"
                f"இடம்: {loc_short}\n"
                "நிலை: பதிவு செய்யப்பட்டது\n"
                f"தேதி: {date_str}\n\n"
                "உங்கள் புகார் எண்ணைப் பயன்படுத்தி புகாரைக் கண்காணிக்கலாம்."
            )
        else:
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

    def validate_signature(self, url: str, params: Dict[str, Any], signature: Optional[str]) -> bool:
        """
        Validates incoming webhook signature using HMAC-SHA1 with TWILIO_AUTH_TOKEN.
        If validation is disabled in settings or credentials not set, returns True.
        """
        if not settings.TELEPHONY_WEBHOOK_VALIDATE_SIGNATURE:
            return True
        if not self.auth_token or not signature:
            logger.warning("[Twilio] Signature validation requested but auth_token or signature missing")
            return False

        try:
            data_str = url
            for k in sorted(params.keys()):
                data_str += f"{k}{params[k]}"
            expected = base64.b64encode(
                hmac.new(self.auth_token.encode("utf-8"), data_str.encode("utf-8"), hashlib.sha1).digest()
            ).decode("utf-8")
            is_valid = hmac.compare_digest(expected, signature)
            if not is_valid:
                logger.warning(f"[Twilio] Webhook signature mismatch for URL: {url}")
            return is_valid
        except Exception as e:
            logger.error(f"[Twilio] Error validating signature: {e}")
            return False

    def build_silent_answer_twiml(self, turn_action_url: str, stream_url: Optional[str] = None) -> str:
        """
        TwiML instructing carrier to immediately answer call silently and gather citizen speech.
        Citizen speaks first. If silence occurs, redirects to turn_action_url with timeout=true.
        """
        connect_tag = ""
        if stream_url:
            connect_tag = (
                f'    <Connect>\n'
                f'        <Stream url="{stream_url}"/>\n'
                f'    </Connect>\n'
            )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'{connect_tag}'
            f'    <Gather input="speech" action="{turn_action_url}" method="POST" '
            f'speechTimeout="auto" timeout="6" language="ta-IN,en-IN">\n'
            f'        <Pause length="1"/>\n'
            f'    </Gather>\n'
            f'    <Redirect method="POST">{turn_action_url}?timeout=true</Redirect>\n'
            '</Response>'
        )

    def build_turn_twiml(self, play_audio_url: str, turn_action_url: str) -> str:
        """
        Plays AI response audio to the phone speaker, then listens for citizen reply.
        """
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'    <Play>{play_audio_url}</Play>\n'
            f'    <Gather input="speech" action="{turn_action_url}" method="POST" '
            f'speechTimeout="auto" timeout="6" language="ta-IN,en-IN"/>\n'
            f'    <Redirect method="POST">{turn_action_url}?timeout=true</Redirect>\n'
            '</Response>'
        )

    def build_completion_twiml(self, play_audio_url: str) -> str:
        """
        Plays final registration announcement (with Complaint ID aloud) and terminates call politely.
        """
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'    <Play>{play_audio_url}</Play>\n'
            f'    <Pause length="1"/>\n'
            f'    <Hangup/>\n'
            '</Response>'
        )

    def build_hangup_twiml(self, message: Optional[str] = None, play_audio_url: Optional[str] = None) -> str:
        """
        Politely ends the call due to repeated silence or caller disconnect.
        """
        play_tag = f'    <Play>{play_audio_url}</Play>\n' if play_audio_url else ""
        say_tag = f'    <Say voice="Polly.Aditi" language="ta-IN">{message}</Say>\n' if message and not play_audio_url else ""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            f'{play_tag}{say_tag}'
            f'    <Hangup/>\n'
            '</Response>'
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

        # Generate standard TwiML XML with bidirectional stream connecting directly with AI silent at start
        stream_url = settings.TELEPHONY_STREAM_URL or "/api/v1/ivr/stream"
        if not stream_url.startswith("ws"):
            stream_url = f"wss://voxentraai-prmy.onrender.com{stream_url if stream_url.startswith('/') else '/' + stream_url}"

        twiml_response = self.build_silent_answer_twiml(
            turn_action_url="/api/v1/telephony/voice/turn",
            stream_url=stream_url
        )

        self._log_event(
            event_type="CALL_INBOUND",
            direction="INBOUND",
            phone=from_number,
            details={
                "call_sid": call_sid,
                "to_number": to_number,
                "action": "twiml_silent_gather_and_stream"
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
