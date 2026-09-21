import logging
import time
import uuid
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.config import settings

logger = logging.getLogger("voxentra.telephony")


class ExotelAdapter:
    """
    Adapter for Exotel IVR Webhooks & Telephony integration.
    Operates safely with live Exotel REST APIs when configured,
    and falls back to realistic simulation and logging in development/offline mode.
    """

    def __init__(self):
        self.account_sid = settings.EXOTEL_ACCOUNT_SID
        self.api_key = settings.EXOTEL_API_KEY
        self.api_token = settings.EXOTEL_API_TOKEN
        self.caller_id = settings.EXOTEL_CALLER_ID
        self.is_configured = bool(self.account_sid and self.api_key and self.api_token)
        # Ring buffer for recent telephony interactions (Calls & SMS)
        self.telephony_logs: List[Dict[str, Any]] = []

    def _log_event(self, event_type: str, direction: str, phone: str, details: Dict[str, Any], status: str = "SUCCESS"):
        log_entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

    def handle_incoming_call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes inbound call webhook from Exotel virtual number.
        Returns Exotel Passthru XML/JSON instructions to play Tamil/English prompt and record.
        """
        call_sid = payload.get("CallSid", f"CA_{uuid.uuid4().hex[:16]}")
        from_number = payload.get("From", "+919843098765")
        to_number = payload.get("To", self.caller_id or "1800-425-1913")
        logger.info(f"Received inbound call from {from_number} -> {to_number} (CallSid: {call_sid})")

        prompt_ta = "வணக்கம். வாக்ஸென்ட்ரா தமிழ்நாடு அரசு கிராமப்புற மற்றும் நகராட்சி பொது குறைதீர்ப்பு சேவைக்கு நல்வரவு. உங்கள் கிராம புகார் அல்லது பிரச்சனையை பீப் ஒலிக்கு பின் தெளிவாக கூறவும்."
        prompt_en = "Welcome to Voxentra Citizen Grievance Helpline. Please state your village problem or grievance clearly after the tone."

        response_data = {
            "status": "success",
            "call_sid": call_sid,
            "action": "play_and_record",
            "prompt_text_ta": prompt_ta,
            "prompt_text_en": prompt_en,
            "combined_prompt": f"{prompt_ta} {prompt_en}",
            "record_time_limit_sec": 60,
            "finish_on_key": "#",
            "transcription_requested": True,
            "callback_url": "/api/v1/webhooks/exotel/voice/recording"
        }

        self._log_event(
            event_type="CALL_INBOUND",
            direction="INBOUND",
            phone=from_number,
            details={
                "call_sid": call_sid,
                "to_number": to_number,
                "prompt": prompt_ta,
                "action": "play_and_record"
            }
        )

        return response_data

    def handle_recording_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes recording callback webhook from Exotel once the citizen finishes recording.
        """
        call_sid = payload.get("CallSid", f"CA_{uuid.uuid4().hex[:16]}")
        recording_url = payload.get("RecordingUrl", "")
        from_number = payload.get("From", "+919843098765")
        recording_duration = payload.get("RecordingDuration", 0)

        logger.info(f"Received recording callback for call {call_sid} ({recording_duration}s): {recording_url}")

        self._log_event(
            event_type="CALL_RECORDING",
            direction="INBOUND",
            phone=from_number,
            details={
                "call_sid": call_sid,
                "recording_url": recording_url,
                "recording_duration": recording_duration,
                "step": "speech_to_complaint_pipeline"
            }
        )

        return {
            "status": "received",
            "call_sid": call_sid,
            "recording_url": recording_url,
            "caller_phone": from_number,
            "recording_duration": recording_duration,
            "next_step": "speech_analysis_and_dispatch"
        }

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        """
        Sends an SMS message to a citizen's mobile number via Exotel REST API.
        Falls back to local simulated delivery if credentials are not set.
        """
        clean_phone = to_phone.strip()
        if not clean_phone.startswith("+") and not clean_phone.startswith("0") and len(clean_phone) == 10:
            clean_phone = f"+91{clean_phone}"

        sms_sid = f"SM_{uuid.uuid4().hex[:16]}"

        if not self.is_configured:
            logger.info(f"[TELEPHONY SIMULATOR] SMS dispatched to {clean_phone}: '{message}' (Sid: {sms_sid})")
            result = {
                "success": True,
                "sms_sid": sms_sid,
                "to": clean_phone,
                "message": message,
                "mode": "SIMULATED_LOCAL",
                "status": "DELIVERED",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self._log_event(
                event_type="SMS_OUTBOUND",
                direction="OUTBOUND",
                phone=clean_phone,
                details={"message": message, "sms_sid": sms_sid, "mode": "SIMULATED"},
                status="DELIVERED"
            )
            return result

        # Live Exotel API Integration
        try:
            url = f"https://api.exotel.com/v1/Accounts/{self.account_sid}/Sms/send.json"
            data = {
                "From": self.caller_id or "EXOTEL",
                "To": clean_phone,
                "Body": message
            }
            auth = (self.api_key, self.api_token)

            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, data=data, auth=auth)
                
            if response.status_code in [200, 201]:
                res_json = response.json()
                exotel_sms = res_json.get("SMSMessage", {})
                live_sid = exotel_sms.get("Sid", sms_sid)
                logger.info(f"Live Exotel SMS successfully sent to {clean_phone} (Sid: {live_sid})")
                
                result = {
                    "success": True,
                    "sms_sid": live_sid,
                    "to": clean_phone,
                    "message": message,
                    "mode": "LIVE_EXOTEL",
                    "status": "SENT",
                    "raw_response": res_json
                }
                self._log_event(
                    event_type="SMS_OUTBOUND",
                    direction="OUTBOUND",
                    phone=clean_phone,
                    details={"message": message, "sms_sid": live_sid, "mode": "LIVE_EXOTEL"},
                    status="SENT"
                )
                return result
            else:
                logger.error(f"Exotel SMS API Error: {response.status_code} - {response.text}")
                result = {
                    "success": False,
                    "sms_sid": sms_sid,
                    "to": clean_phone,
                    "error": response.text,
                    "status_code": response.status_code,
                    "mode": "LIVE_EXOTEL_FAILED"
                }
                self._log_event(
                    event_type="SMS_OUTBOUND",
                    direction="OUTBOUND",
                    phone=clean_phone,
                    details={"message": message, "error": response.text},
                    status="FAILED"
                )
                return result

        except Exception as e:
            logger.exception(f"Exception sending Exotel SMS to {clean_phone}: {str(e)}")
            result = {
                "success": False,
                "sms_sid": sms_sid,
                "to": clean_phone,
                "error": str(e),
                "mode": "EXCEPTION"
            }
            self._log_event(
                event_type="SMS_OUTBOUND",
                direction="OUTBOUND",
                phone=clean_phone,
                details={"message": message, "error": str(e)},
                status="EXCEPTION"
            )
            return result

    def initiate_outbound_call(self, to_phone: str, agent_or_caller_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Initiates a call connecting a citizen to a department officer or an IVR voice flow.
        """
        clean_phone = to_phone.strip()
        call_sid = f"CA_{uuid.uuid4().hex[:16]}"

        if not self.is_configured:
            logger.info(f"[TELEPHONY SIMULATOR] Outbound call to {clean_phone} initiated (Sid: {call_sid})")
            result = {
                "success": True,
                "call_sid": call_sid,
                "to": clean_phone,
                "mode": "SIMULATED_LOCAL",
                "status": "IN_PROGRESS"
            }
            self._log_event(
                event_type="CALL_OUTBOUND",
                direction="OUTBOUND",
                phone=clean_phone,
                details={"call_sid": call_sid, "mode": "SIMULATED"},
                status="IN_PROGRESS"
            )
            return result

        try:
            url = f"https://api.exotel.com/v1/Accounts/{self.account_sid}/Calls/connect.json"
            data = {
                "From": clean_phone,
                "To": agent_or_caller_id or self.caller_id,
                "CallerId": self.caller_id
            }
            auth = (self.api_key, self.api_token)

            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, data=data, auth=auth)

            if response.status_code in [200, 201]:
                res_json = response.json()
                live_sid = res_json.get("Call", {}).get("Sid", call_sid)
                result = {
                    "success": True,
                    "call_sid": live_sid,
                    "to": clean_phone,
                    "mode": "LIVE_EXOTEL",
                    "status": "INITIATED"
                }
                self._log_event(
                    event_type="CALL_OUTBOUND",
                    direction="OUTBOUND",
                    phone=clean_phone,
                    details={"call_sid": live_sid, "mode": "LIVE_EXOTEL"},
                    status="INITIATED"
                )
                return result
            else:
                logger.error(f"Exotel Outbound Call API Error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code
                }
        except Exception as e:
            logger.exception(f"Exception in Exotel outbound call: {str(e)}")
            return {"success": False, "error": str(e)}


exotel_adapter = ExotelAdapter()
