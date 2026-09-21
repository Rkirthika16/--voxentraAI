# VoxentraAI Telephony & Exotel IVR Integration Guide

## 1. Overview
VoxentraAI includes a modular telephony interface allowing citizens without internet access to dial a civic helpline number, record their grievance in Tamil or English, and have it automatically registered into the complaint lifecycle.

---

## 2. Telephony Architecture

```
Citizen Phone Call
       │
       ▼
Exotel Virtual Number (DID)
       │
       ▼
Webhook: POST /api/v1/webhooks/exotel/voice/incoming
(Plays Tamil/English IVR prompt asking citizen to record grievance)
       │
       ▼
Exotel Audio Recording
       │
       ▼
Webhook: POST /api/v1/webhooks/exotel/voice/recording
(Delivers audio URL / stream to backend)
       │
       ▼
Whisper Speech Recognition & AI Classification Pipeline
       │
       ▼
Auto-generates Complaint (VOX-YYYY-XXXX) + SMS Confirmation Callback
```

---

## 3. Webhook Endpoints

### 1. Inbound Voice Webhook
- **URL**: `https://<your-public-domain>/api/v1/webhooks/exotel/voice/incoming`
- **Method**: `POST`
- **Payload**: Standard Exotel parameters (`CallSid`, `From`, `To`, `CallType`)
- **Response**: Exotel XML / JSON response to instruct IVR to play prompt and start audio recording.

### 2. Recording Callback Webhook
- **URL**: `https://<your-public-domain>/api/v1/webhooks/exotel/voice/recording`
- **Method**: `POST`
- **Payload**: `CallSid`, `RecordingUrl`, `From`, `Digits`
- **Action**: Downloads audio, submits to `SpeechService` and `AIProvider`, creates complaint, and replies with tracking SMS.

---

## 4. Production Deployment Checklist
1. Obtain an Exotel Virtual Number and API keys from Exotel Dashboard.
2. Deploy backend behind an HTTPS reverse proxy (e.g., Nginx, Caddy, Cloudflare Tunnel, or AWS ALB).
3. Set environment variables in `.env`:
   ```bash
   EXOTEL_ACCOUNT_SID="your_account_sid"
   EXOTEL_API_KEY="your_api_key"
   EXOTEL_API_TOKEN="your_api_token"
   EXOTEL_CALLER_ID="your_virtual_number"
   EXOTEL_WEBHOOK_SECRET="your_shared_secret"
   ```
4. Configure Applets in Exotel portal pointing to the webhook URLs.
