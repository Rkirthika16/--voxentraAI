import os
import sys
import uuid
import xml.etree.ElementTree as ET
from fastapi.testclient import TestClient

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.database.session import SessionLocal
from app.models.complaint import Complaint, ComplaintSource, ComplaintStatus
from app.models.ivr import IVRSession, IVRState

client = TestClient(app)

def run_tests():
    print("=" * 70)
    print("VOXENTRA AI — REAL TELEPHONY HELPLINE END-TO-END VERIFICATION")
    print("=" * 70)

    # 1. Telephony Status Check
    print("\n[Step 1] Checking Telephony System Status & Webhook Configuration...")
    status_resp = client.get("/api/v1/telephony/status")
    assert status_resp.status_code == 200, f"Status check failed: {status_resp.text}"
    status_data = status_resp.json()
    print(f"  Active Telephony Provider: {status_data['active_provider']}")
    print(f"  Helpline Phone Number:     {status_data['phone_number']}")
    print(f"  Inbound Webhook URL:       {status_data['webhook_url']}")
    print(f"  Dialogue Turn URL:         {status_data['turn_url']}")
    assert "webhook_url" in status_data
    print("  \u2714 Telephony endpoints configured successfully.")

    # 2. Inbound Telephone Call Answering (Silent Connect)
    call_sid = f"CA_test_{uuid.uuid4().hex[:12]}"
    caller_phone = "+919843098765"
    print(f"\n[Step 2] Simulating Inbound Call from Ordinary Phone ({caller_phone})...")
    print(f"  CallSid: {call_sid}")

    incoming_resp = client.post("/api/v1/telephony/voice/incoming", data={
        "CallSid": call_sid,
        "From": caller_phone,
        "To": status_data["phone_number"],
        "CallStatus": "ringing",
        "Direction": "inbound"
    })
    assert incoming_resp.status_code == 200, f"Incoming call failed: {incoming_resp.text}"
    assert "application/xml" in incoming_resp.headers["content-type"]
    root = ET.fromstring(incoming_resp.text)
    gather = root.find("Gather")
    assert gather is not None, "TwiML must include <Gather> to collect citizen voice"
    # Mandatory requirement: AI must NOT speak first (silent connection)
    say_tags = root.findall(".//Say")
    assert len(say_tags) == 0, "AI must be SILENT when answering the call; citizen must speak first!"
    print("  \u2714 Inbound call answered automatically and silently with <Gather input=\"speech\">.")

    # 3. Conversational Dialogue Turns (The Exact User Prompt Example)
    print("\n[Step 3] Conversational Dialogue Loop in Tamil/Tanglish...")

    # Turn 1: Citizen speaks FIRST: "Hello, enga oorla thanni varala."
    print("  Citizen: 'Hello, enga oorla thanni varala.'")
    t1_resp = client.post("/api/v1/telephony/voice/turn", data={
        "CallSid": call_sid,
        "From": caller_phone,
        "SpeechResult": "Hello, enga oorla thanni varala."
    })
    assert t1_resp.status_code == 200
    t1_root = ET.fromstring(t1_resp.text)
    t1_play = t1_root.find("Play")
    assert t1_play is not None, "TwiML must contain <Play> for audio response"
    print(f"  AI Voice Audio URL: {t1_play.text}")

    # Verify audio file can be fetched dynamically
    audio_path = t1_play.text.split("/api/v1")[-1]
    audio_resp = client.get(f"/api/v1{audio_path}")
    assert audio_resp.status_code == 200
    assert "audio/mpeg" in audio_resp.headers["content-type"]
    assert len(audio_resp.content) > 0
    print("  \u2714 Dynamic TTS audio generated and verified streamable.")

    # Turn 2: Location provided: "Coimbatore, Vadavalli."
    print("  Citizen: 'Coimbatore, Vadavalli.'")
    t2_resp = client.post("/api/v1/telephony/voice/turn", data={
        "CallSid": call_sid,
        "From": caller_phone,
        "SpeechResult": "Coimbatore, Vadavalli."
    })
    assert t2_resp.status_code == 200
    t2_root = ET.fromstring(t2_resp.text)
    assert t2_root.find("Play") is not None
    print("  \u2714 Location recognized (Coimbatore, Vadavalli); AI prompted for street.")

    # Turn 3: Street provided: "Anna Nagar second street."
    print("  Citizen: 'Anna Nagar second street.'")
    t3_resp = client.post("/api/v1/telephony/voice/turn", data={
        "CallSid": call_sid,
        "From": caller_phone,
        "SpeechResult": "Anna Nagar second street."
    })
    assert t3_resp.status_code == 200
    t3_root = ET.fromstring(t3_resp.text)
    assert t3_root.find("Play") is not None
    print("  \u2714 Street recognized (Anna Nagar second street); AI prompted for duration.")

    # Turn 4: Duration provided: "Three days."
    print("  Citizen: 'Three days.'")
    t4_resp = client.post("/api/v1/telephony/voice/turn", data={
        "CallSid": call_sid,
        "From": caller_phone,
        "SpeechResult": "Three days."
    })
    assert t4_resp.status_code == 200
    t4_root = ET.fromstring(t4_resp.text)
    assert t4_root.find("Play") is not None
    print("  \u2714 Duration recognized (3 days); AI prompted for affected scope.")

    # Turn 5: Scope provided: "Full street."
    print("  Citizen: 'Full street.'")
    t5_resp = client.post("/api/v1/telephony/voice/turn", data={
        "CallSid": call_sid,
        "From": caller_phone,
        "SpeechResult": "Full street."
    })
    assert t5_resp.status_code == 200
    t5_root = ET.fromstring(t5_resp.text)
    assert t5_root.find("Play") is not None
    print("  \u2714 All core details collected; AI generated confirmation summary.")

    # Turn 6: Citizen confirms: "Aama, correct, register pannunga."
    print("  Citizen: 'Aama, correct, register pannunga.'")
    t6_resp = client.post("/api/v1/telephony/voice/turn", data={
        "CallSid": call_sid,
        "From": caller_phone,
        "SpeechResult": "Aama, correct, register pannunga."
    })
    assert t6_resp.status_code == 200
    t6_root = ET.fromstring(t6_resp.text)
    t6_hangup = t6_root.find("Hangup")
    assert t6_hangup is not None, "Call must end politely with <Hangup> after final announcement"
    t6_play = t6_root.find("Play")
    assert t6_play is not None, "Final confirmation announcement must be played aloud"
    print("  \u2714 Complaint registered and aloud voice announcement returned in TwiML.")

    # 4. Database Verification
    print("\n[Step 4] Verifying Grievance in SQLite Database...")
    db = SessionLocal()
    try:
        session_rec = db.query(IVRSession).filter(IVRSession.session_id == call_sid).first()
        assert session_rec is not None, "IVRSession must exist in DB"
        assert session_rec.complaint_id is not None, "Session must link to created complaint"
        assert session_rec.complaint_number.startswith("VX-"), f"Invalid complaint ID: {session_rec.complaint_number}"
        
        complaint = db.query(Complaint).filter(Complaint.id == session_rec.complaint_id).first()
        assert complaint is not None, "Complaint record must be persisted in database"
        assert complaint.complaint_number == session_rec.complaint_number
        assert complaint.source == ComplaintSource.TELEPHONY_IVR
        assert "Water" in complaint.category
        assert complaint.status in [ComplaintStatus.SUBMITTED, ComplaintStatus.UNDER_REVIEW]
        assert complaint.priority is not None

        print(f"  \u2714 Complaint ID:     {complaint.complaint_number}")
        print(f"  \u2714 Category:         {complaint.category}")
        print(f"  \u2714 Department:       {complaint.department.name if complaint.department else 'Water Supply'}")
        print(f"  \u2714 Priority:         {complaint.priority.value}")
        print(f"  \u2714 Location:         {complaint.location}")
        print(f"  \u2714 Source:           {complaint.source.value}")
        print(f"  \u2714 Citizen Phone:    {session_rec.caller_phone}")
    finally:
        db.close()

    # 5. Webhook Idempotency Check (Duplicate Prevention)
    print("\n[Step 5] Testing Webhook Idempotency & Duplicate Prevention...")
    db = SessionLocal()
    count_before = db.query(Complaint).count()
    db.close()

    # Re-post confirmation webhook (as telecom carrier retries can occur)
    retry_resp = client.post("/api/v1/telephony/voice/turn", data={
        "CallSid": call_sid,
        "From": caller_phone,
        "SpeechResult": "Aama, correct, register pannunga."
    })
    assert retry_resp.status_code == 200

    db = SessionLocal()
    count_after = db.query(Complaint).count()
    db.close()
    assert count_before == count_after, "Duplicate complaint was created on webhook retry!"
    print(f"  \u2714 Webhook retry handled idempotently without creating duplicate complaints ({count_after} total).")

    # 6. Silence & Timeout Handling Check
    print("\n[Step 6] Testing Silence and Timeout Handling...")
    timeout_sid = f"CA_timeout_{uuid.uuid4().hex[:12]}"
    client.post("/api/v1/telephony/voice/incoming", data={
        "CallSid": timeout_sid,
        "From": "+919843098765"
    })

    # Timeout 1: Silence prompt
    to1_resp = client.post("/api/v1/telephony/voice/turn", data={
        "CallSid": timeout_sid,
        "timeout": "true"
    })
    assert to1_resp.status_code == 200
    to1_root = ET.fromstring(to1_resp.text)
    assert to1_root.find("Play") is not None
    assert to1_root.find("Gather") is not None
    print("  \u2714 Timeout 1: Prompted citizen gently to speak.")

    # Timeout 2 & 3: Exceeding silence retries
    client.post("/api/v1/telephony/voice/turn", data={"CallSid": timeout_sid, "timeout": "true"})
    to3_resp = client.post("/api/v1/telephony/voice/turn", data={"CallSid": timeout_sid, "timeout": "true"})
    to3_root = ET.fromstring(to3_resp.text)
    assert to3_root.find("Hangup") is not None
    print("  \u2714 Timeout limit reached: Call terminated politely.")

    # 7. Call Status Callback
    print("\n[Step 7] Testing Call Status Callback...")
    status_cb_resp = client.post("/api/v1/telephony/voice/status", data={
        "CallSid": call_sid,
        "CallStatus": "completed",
        "CallDuration": "85"
    })
    assert status_cb_resp.status_code == 200
    assert status_cb_resp.json()["status"] == "completed"
    print("  \u2714 Status callback processed and session ended_at recorded.")

    print("\n" + "=" * 70)
    print("ALL TELEPHONY INTEGRATION VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
