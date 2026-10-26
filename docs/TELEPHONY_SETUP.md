# VoxentraAI — Real Telephone Helpline Deployment & Integration Guide

This guide describes how to configure, connect, test, and deploy **VoxentraAI** with real programmable telephony providers (Twilio and Exotel) to enable inbound telephone calls from ordinary keypad phones and mobile phones across India (Tamil Nadu civic governance).

---

## 1. System Architecture & Flow

VoxentraAI provides an end-to-end telephone helpline pipeline for Tamil Nadu civic grievance redressal:

```
[Citizen Phone] (Keypad / Mobile)
       │ (Standard GSM/PSTN Call - BSNL/Jio/Airtel/Vi)
       ▼
[Carrier Telecom Network]
       │
       ▼
[Telephony Provider (Twilio / Exotel)]
       │
       ▼ (HTTP POST Webhook - Signed HMAC)
[VoxentraAI Inbound Endpoint: /api/v1/telephony/voice/incoming]
       │
       ├─► Answers Call Automatically & Silently (Citizen Speaks First)
       │
       ▼ (Audio Streaming / Speech Gather)
[Turn Webhook: /api/v1/telephony/voice/turn]
       │
       ├─► Whisper STT + Common Speech Mistake Correction Service
       ├─► Multilingual Language Detection (Tamil, English, Tanglish)
       ├─► Hierarchical Location Resolver (District, Taluk, Town, Ward, Street, Landmark)
       ├─► Conversation State Manager & Structured Memory
       ├─► AI Text-to-Speech Generation (Edge-TTS / Google TTS fallback)
       ├─► Confirmation Summary Turn
       │
       ▼
[Complaint Registration Engine]
       │
       ├─► Creates Grievance Record (`VX-YYYYMMDD-XXXX`)
       ├─► Priority Engine (Critical / High / Medium / Low)
       ├─► Department Assignment (Water Supply, TANGEDCO, Sanitation, etc.)
       │
       ▼
[Telephony Completion TwiML / Passthru]
       │
       ├─► Voice Announcement: Speaks Complaint ID Aloud (spaced characters for clarity)
       ├─► Dispatches Confirmation SMS to Citizen Phone
       └─► Politely Terminates Call with `<Hangup/>`
```

---

## 2. Telephony Provider Options & India Regulatory Compliance

VoxentraAI supports two programmable telephony providers:

| Feature | Twilio | Exotel |
|---|---|---|
| **Primary Region** | Global + India DID / International | India Native (Bangalore, Chennai, Mumbai DIDs) |
| **Inbound Call Format** | TwiML (`<Gather>`, `<Play>`, `<Hangup>`) | Passthru Applet JSON / HTTP XML |
| **Direct Keypad Latency** | Low (~350ms) | Very Low (<250ms within India) |
| **SMS Route** | International / India DLT compliant | Domestic DLT Transactional SMS Route |
| **Recommended For** | Global development, ngrok local testing | Production deployment in India |

### India Regulatory Considerations (TRAI / DoT Compliance):
1. **Virtual Number (DID) KYC**: Telecommunications regulations in India mandate business entity KYC (GSTIN, Certificate of Incorporation, Address Proof) to activate domestic virtual numbers (e.g., 080 / 044 landline series or 1800 Toll-Free).
2. **DLT Registration for Transactional SMS**: To send SMS confirmations to Indian mobile numbers (`+91`), register VoxentraAI on any telecom operator's DLT portal (e.g., Jio, Airtel, Vodafone Idea DLT):
   - Register **Principal Entity**.
   - Register Sender Header (e.g., `VXNTRA` / `GOVTMC`).
   - Register Content Template:
     `"Vanakkam. Ungal pugaar en {#var#} vetrigaramaaga pathivu seiyappattadhu. VoxentraAI Tamil Nadu."`

---

## 3. Environment Configuration

Add the following variables to your `.env` file (see `.env.example`):

```bash
# =================================================================
# TELEPHONY HELPLINE SETTINGS
# =================================================================
# Telephony Provider: "twilio" or "exotel"
TELEPHONY_PROVIDER=twilio

# Public HTTPS Base URL of your deployed server (or ngrok URL for local dev)
# REQUIRED so carriers can stream dynamic synthesized voice responses
VOICE_REGISTER_BASE_URL=https://voxentraai-prmy.onrender.com

# Twilio Credentials
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_INBOUND_VOICE_URL=https://voxentraai-prmy.onrender.com/api/v1/telephony/voice/incoming

# Exotel Credentials (Alternative domestic India carrier)
EXOTEL_ACCOUNT_SID=your_exotel_sid_here
EXOTEL_API_KEY=your_exotel_api_key_here
EXOTEL_API_TOKEN=your_exotel_api_token_here
EXOTEL_PHONE_NUMBER=0804xxxxxxx

# Webhook Security
# Set to True in production to verify HMAC signatures (X-Twilio-Signature)
TELEPHONY_WEBHOOK_VALIDATE_SIGNATURE=False

# Silence & Timeout Limits
TELEPHONY_MAX_SILENCE_RETRIES=3
TELEPHONY_IDEMPOTENCY_CACHE_TTL_SEC=86400
```

---

## 4. Setting Up Twilio Inbound Voice

1. Log in to the [Twilio Console](https://console.twilio.com/).
2. Navigate to **Phone Numbers** -> **Manage** -> **Active numbers**.
3. Select your designated phone number.
4. Under the **Voice Configuration** section:
   - **Configure With**: `Webhook`
   - **A CALL COMES IN**: `Webhook`
   - **URL**: `https://<YOUR_DOMAIN>/api/v1/telephony/voice/incoming`
   - **HTTP Method**: `HTTP POST`
   - **CALL STATUS CHANGES**:
     - **URL**: `https://<YOUR_DOMAIN>/api/v1/telephony/voice/status`
     - **HTTP Method**: `HTTP POST`
5. Click **Save Configuration**.

---

## 5. Setting Up Exotel Inbound Voice

1. Log in to your [Exotel Dashboard](https://my.exotel.com/).
2. Go to **App Bazaar** -> **Create New Flow**.
3. Create a **Passthru Applet**:
   - **Passthru URL**: `https://<YOUR_DOMAIN>/api/v1/telephony/voice/incoming`
   - **HTTP Method**: `POST`
   - **Pass Data as**: `JSON` or `Form URL Encoded`
4. Connect the Passthru response loop to `/api/v1/telephony/voice/turn`.
5. Link this flow to your Exotel Virtual Phone Number under **Numbers** -> **Installed Apps**.

---

## 6. Local Testing with ngrok

To test live phone calls from your actual mobile phone against your local workstation:

1. Start your local VoxentraAI backend:
   ```powershell
   cd backend
   .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. In a separate terminal, expose port 8000 using ngrok:
   ```bash
   ngrok http 8000
   ```
3. Copy the forwarding HTTPS URL (e.g., `https://a1b2-xx-xx.ngrok-free.app`).
4. Update `VOICE_REGISTER_BASE_URL` in `backend/.env`:
   ```bash
   VOICE_REGISTER_BASE_URL=https://a1b2-xx-xx.ngrok-free.app
   ```
5. Update the Inbound Webhook URL in your Twilio / Exotel dashboard to:
   ```
   https://a1b2-xx-xx.ngrok-free.app/api/v1/telephony/voice/incoming
   ```

---

## 7. Verifying End-to-End Telephone Calls

### Automated Verification Script:
Run the comprehensive telephony flow test suite:
```powershell
.\backend\venv\Scripts\python.exe scripts\test_real_telephony_flow.py
```
This tests:
- Status check of telephony endpoints.
- Inbound silent answer (`<Gather input="speech">` without greeting prompt).
- Conversational dialogue loop in Tamil/Tanglish.
- Dynamic hierarchical location resolution (District, Area, Street, Duration, Scope).
- Confirmation summary.
- Database grievance persistence (`VX-YYYYMMDD-XXXX`).
- Aloud voice announcement of the actual Complaint ID with telephony pacing.
- Webhook idempotency and retry handling.
- Silence and timeout handling (max 3 retries, polite disconnect).
- Call status lifecycle callbacks.

### Real Mobile / Keypad Phone Test:
1. Dial the configured helpline number from any mobile phone (e.g., basic keypad phone or smartphone).
2. When the call connects:
   - Notice that the AI remains completely silent (waiting for you to speak first).
3. Speak naturally in Tamil or Tanglish:
   - *"Hello, enga oorla thanni varala."*
4. AI responds and asks for location:
   - Reply: *"Coimbatore, Vadavalli."*
5. AI asks for street name:
   - Reply: *"Anna Nagar second street."*
6. AI asks how many days:
   - Reply: *"Three days."*
7. AI asks for scope:
   - Reply: *"Full street."*
8. AI presents confirmation summary:
   - *"சரிங்க. கோயம்புத்தூர், வடவள்ளி, அண்ணா நகர் 2வது தெருவில் கடந்த 3 நாட்களாக குடிநீர் வரவில்லை என்று புகார் பதிவு செய்யட்டுமா?"*
9. Confirm:
   - Reply: *"Aama, correct, register pannunga."*
10. AI announces your actual generated Complaint ID aloud:
    - *"நன்றி! உங்கள் புகார் வெற்றிகரமாக பதிவு செய்யப்பட்டது. உங்கள் புகார் எண்: V X 2 0 2 6 0 0 4 4 8. விவரங்கள் எஸ்.எம்.எஸ் மூலம் அனுப்பப்பட்டுள்ளது. உரிய நடவடிக்கை எடுக்கப்படும்."*
11. Call ends automatically and an SMS notification is dispatched to your phone.

---

## 8. Network Resiliency & Privacy Guidelines

- **Silence Detection**: If the caller is on a noisy line or silent, the system gives up to 3 gentle reminder prompts in their detected language before hanging up politely.
- **DTMF Keypad Fallbacks**:
  - Press `1`: Repeat the last AI prompt.
  - Press `2`: Immediately confirm and register complaint.
  - Press `9`: Cancel and end the call.
- **Idempotency**: All turn submissions are indexed by `CallSid`. Webhook retries from telecom carriers will safely return the cached response without creating duplicate complaints in the database.
- **Privacy & Retention**: Audio data is synthesized ephemerally in memory (`TELEPHONY_AUDIO_CACHE`). Temporary recordings downloaded for Whisper transcription are immediately removed after processing.
