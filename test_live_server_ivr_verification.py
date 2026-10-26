import os
import sys
import json
import base64
import httpx
import websockets
import asyncio

# Setup UTF-8 for Windows console
if sys.platform == "win32":
    reconfig = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfig):
        try:
            reconfig(encoding="utf-8")
        except Exception:
            pass

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/api/v1/ivr/stream"


def test_live_http_ivr_flow():
    print("=" * 75)
    print("LIVE SERVER HTTP IVR VERIFICATION")
    print("=" * 75)

    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        # 1. Health check
        h_resp = client.get("/health")
        assert h_resp.status_code == 200
        print(f"1. Health Check: {h_resp.json()}")

        # 2. Inbound call connected (AI Silent check)
        inc_resp = client.post("/api/v1/ivr/incoming", json={"caller_phone": "+919843055443"})
        assert inc_resp.status_code == 200
        call_data = inc_resp.json()
        print(f"2. Inbound Call: Session ID={call_data['session_id']}, State={call_data['state']}, AI Silent={call_data.get('ai_silent')}")
        assert call_data["state"] == "WAITING_FOR_CITIZEN"
        assert call_data.get("ai_silent") is True
        assert call_data.get("greeting") == ""
        session_id = call_data["session_id"]

        # 3. Turn 1 (Citizen speaks first with grievance)
        t1_resp = client.post(
            f"/api/v1/ivr/session/{session_id}/message",
            json={"message": "Gandhipuram 5th street-la rendu naala full street-ku thanni varala."}
        )
        assert t1_resp.status_code == 200
        t1_data = t1_resp.json()
        print(f"3. Turn 1 Processed: Lang={t1_data.get('detected_language')}, Category={t1_data['memory'].get('category')}, AI Reply='{t1_data.get('ai_reply')}'")
        assert t1_data["detected_language"] == "Tanglish"
        assert t1_data["memory"]["category"] == "Water"

        # 4. Turn 2: Exact Location / Spot
        t2_resp = client.post(
            f"/api/v1/ivr/session/{session_id}/message",
            json={"message": "Door number 45 near cross cut road"}
        )
        assert t2_resp.status_code == 200
        t2_data = t2_resp.json()
        print(f"4. Turn 2 Processed: Next Slot={t2_data.get('next_field')}, AI Reply='{t2_data.get('ai_reply')}'")

        # 5. Turn 3: Landmark
        t3_resp = client.post(
            f"/api/v1/ivr/session/{session_id}/message",
            json={"message": "Gandhipuram bus stand pakkathula"}
        )
        assert t3_resp.status_code == 200
        t3_data = t3_resp.json()
        print(f"5. Turn 3 Processed: Landmark={t3_data['memory'].get('landmark')}")
        assert "bus stand" in t3_data["memory"]["landmark"].lower()

        # 6. Complete remaining questions up to confirmation
        turns = [
            "Water completely cut aaiduchu",
            "Drinking water supplies affected for all houses",
            "No safety hazard",
            "First time reporting",
            "Daily recurring problem",
            "No other details"
        ]
        last_turn = None
        for i, utt in enumerate(turns, start=4):
            r = client.post(f"/api/v1/ivr/session/{session_id}/message", json={"message": utt})
            assert r.status_code == 200
            last_turn = r.json()
            print(f"   Turn {i}: Citizen='{utt}' -> AI='{last_turn.get('ai_reply')}'")

        assert last_turn["is_confirmation"] is True
        print(f"\n6. Reached Confirmation State! Summary:\n   {last_turn['ai_reply']}")

        # 7. Confirm registration: "Aama, register pannunga"
        conf_resp = client.post(f"/api/v1/ivr/session/{session_id}/message", json={"message": "Aama, register pannunga"})
        assert conf_resp.status_code == 200
        conf_data = conf_resp.json()
        print(f"7. Final Confirmation: Created={conf_data.get('complaint_created')}, Complaint ID={conf_data.get('complaint_number')}")
        assert conf_data["complaint_created"] is True
        assert conf_data["complaint_number"].startswith("VX-")
        print(f"   Final Spoken Message: {conf_data.get('spoken_reply')}")

    print("\n" + "=" * 75)
    print("LIVE SERVER HTTP IVR FLOW PASSED! ✅")
    print("=" * 75)


async def test_live_websocket_telephony_stream():
    print("\n" + "=" * 75)
    print("LIVE SERVER WEBSOCKET REAL-TIME AUDIO STREAM VERIFICATION")
    print("=" * 75)

    async with websockets.connect(WS_URL) as ws:
        # 1. Start event
        await ws.send(json.dumps({
            "event": "start",
            "streamSid": "STREAM_LIVE_001",
            "start": {
                "streamSid": "STREAM_LIVE_001",
                "customParameters": {
                    "caller_phone": "+919843077711"
                }
            }
        }))
        start_msg = json.loads(await ws.recv())
        print(f"1. WS Stream Started: {start_msg}")
        assert start_msg.get("event") == "started"
        assert start_msg.get("state") == "WAITING_FOR_CITIZEN"

        # 2. Send Citizen Speech
        await ws.send(json.dumps({
            "event": "message",
            "message": "Peelamedu Avinashi Road-la deep road pothole problem."
        }))

        # Read responses (may include audio media frames followed by turn_complete)
        received_media = False
        turn_complete = None
        while True:
            msg = json.loads(await ws.recv())
            evt = msg.get("event")
            if evt == "media":
                payload = msg.get("media", {}).get("payload", "")
                print(f"   -> Received Telephony Audio Frame: payload length={len(payload)} bytes")
                received_media = True
            elif evt == "turn_complete":
                turn_complete = msg
                break

        print(f"2. WS Turn Complete: Lang={turn_complete.get('detected_language')}, AI='{turn_complete.get('ai_reply')}'")
        assert turn_complete.get("detected_language") in ["Tanglish", "English"]
        assert turn_complete.get("memory", {}).get("category") in ["Roads", "Roads & Infrastructure", "Road"]

        # 3. Test DTMF digit 1 (Repeat prompt)
        await ws.send(json.dumps({
            "event": "dtmf",
            "digit": "1"
        }))
        dtmf_complete = None
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("event") == "dtmf_processed":
                dtmf_complete = msg
                break
        print(f"3. WS DTMF 1 Processed: AI Repeated='{dtmf_complete.get('ai_reply')}'")
        assert dtmf_complete.get("event") == "dtmf_processed"

    print("\n" + "=" * 75)
    print("LIVE SERVER WEBSOCKET STREAM PASSED! ✅")
    print("=" * 75)


def run_all():
    test_live_http_ivr_flow()
    asyncio.run(test_live_websocket_telephony_stream())


if __name__ == "__main__":
    run_all()
