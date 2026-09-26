# 🏛️ VoxentraAI — Live Multilingual Two-Way AI IVR & Civic Grievance System

VoxentraAI is a state-of-the-art civic complaint management platform and two-way conversational AI IVR system designed for Tamil Nadu citizens, government department officers, and municipal administrators.

Citizens can report civic issues naturally in **Tamil**, **English**, or **Tanglish** via hands-free two-way voice conversations, web forms, audio recordings, or telephone IVR. An intelligent conversational engine listens, detects language, extracts complaint slots (category, location, problem, duration, affected scope), remembers context across dialogue turns, asks relevant missing questions, clarifies uncertainty, summarizes, and registers grievances with verified database tracking numbers.

---

## 🌟 Key Features

- 🎙️ **Live Two-Way Conversational AI IVR (`/tollfree-ivr`, `/new-ivr` & `/api/v1/complaints/ivr/turn`)**:
  - Real hands-free two-way conversational turn taking: Citizen speaks first ➔ Whisper STT ➔ Automatic Language Detection (Tamil, Tanglish, English) ➔ Multi-turn Contextual Slot Extraction (6-10 context-aware questions) ➔ Edge-TTS Tamil/English audio streaming ➔ Automated Grievance Registration with Tracking ID (`VX-YYYYMMDD-XXXX`) ➔ GIS & Department Routing.
  - Browser MediaRecorder audio stream processing (WebM/Opus, Ogg, WAV) with automatic 16kHz mono PCM conversion via FFmpeg.
  - Speech-To-Text via Whisper (faster-whisper / openai-whisper) with clear, deterministic offline fallback when unavailable.
  - Provider-agnostic Telephony Provider Interface (`TelephonyProvider`) for Exotel, Twilio, and toll-free telco webhooks.
- 🌐 **True Multilingual Intelligence**: Native dynamic adaptation across Tamil script, English, and Tanglish (*e.g., "Gandhipuram-la thanni varala"*).
- 🧠 **Context-Aware Structured Dialogue Memory**:
  - Retains Category, Problem, Location, Duration, Scope, Frequency, Severity across all turns.
  - Asks category-specific questions **one question at a time**, never re-asking already gathered information.
- 🛡️ **Role-Based Access Control**:
  - **Citizen**: Submit complaints, live IVR simulator, track step-by-step progress, view audit history, receive notifications.
  - **Officer**: Manage departmental queues (Water, Electricity, Roads, Sanitation, Drainage, Streetlights, Public Safety), update status with notes, track SLAs.
  - **Admin**: Monitor live municipal analytics, manage departments, manage officers, inspect escalations.
- 📊 **Auditable Complaint Lifecycle**: Full history tracking across all status transitions (`SUBMITTED` ➔ `UNDER_REVIEW` ➔ `ASSIGNED` ➔ `IN_PROGRESS` ➔ `RESOLVED`).
- 📞 **Dual Telephony Provider Ready**: Built-in webhook adapters for Exotel and Twilio with Passthru and TwiML integration.

---

## 📁 Project Architecture

```
VOXENTRAAI/
├── README.md
├── PROJECT_AUDIT.md
├── .gitignore
├── .env.example
├── render.yaml                         # Production Render Blueprint
├── backend/
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   ├── app/
│   │   ├── main.py                     # FastAPI entry point
│   │   ├── config.py                   # Environment & settings
│   │   ├── api/                        # Central routers & endpoints
│   │   ├── core/                       # Security, dependencies, exceptions
│   │   ├── database/                   # SQLAlchemy engine, session & init
│   │   ├── db/                         # Database module forwarder
│   │   ├── models/                     # User, Department, Complaint, IVR models
│   │   ├── schemas/                    # Pydantic validation schemas
│   │   ├── services/                   # Auth, Complaint, Speech, Conversational IVR
│   │   ├── ai/                         # Whisper STT, TTS, NLP, and collectors
│   │   ├── integrations/               # Telephony adapters (Exotel, Twilio)
│   │   ├── telephony/                  # Telephony forwarder package
│   │   └── utils/                      # Audio conversion, FFmpeg & validators
│   └── tests/                          # 125+ automated unit & integration tests
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── api/                        # Typed Axios clients (IVR, Voice, Complaints)
        ├── components/                 # UI, Audio visualizer, OpenStreetMap
        ├── context/                    # Auth and global state
        ├── pages/                      # Toll-Free IVR, Voice Assistant, Dashboards
        ├── types/                      # TypeScript definitions
        └── utils/                      # useVoiceConversationEngine, speech, audio
```

---

## 🚀 Step-by-Step Windows VS Code Setup Guide

### Step 1: Open Project Folder
Open VS Code and select the `voxentraAII` root folder:
```powershell
cd C:\Users\Akshaya\OneDrive\voxentraAII
```

### Step 2: Create Python Virtual Environment
```powershell
cd backend
python -m venv venv
```

### Step 3: Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

### Step 4: Install Backend Dependencies
```powershell
pip install -r requirements.txt
```

### Step 5: Configure `.env`
Copy the environment template:
```powershell
cp .env.example .env
```
Ensure `SECRET_KEY`, `DATABASE_URL=sqlite:///./voxentra.db`, and `ENABLE_FALLBACK_AI=true` are configured.

### Step 6: Initialize Database and Seed Data
```powershell
python -m app.database.init_db
```

### Step 7: Start FastAPI Backend Server
```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### Step 8: Install Frontend Dependencies
In a second PowerShell terminal:
```powershell
cd frontend
npm install
```

### Step 9: Start Vite Development Server
```powershell
npm run dev
```
- Web Application: `http://localhost:5173`
- Toll-Free IVR Simulator: `http://localhost:5173/ivr`
- Voice Assistant: `http://localhost:5173/voice`

### Step 10: Test API Endpoints
Verify health and status endpoints:
```powershell
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/departments
```

### Step 11: Test IVR Simulator
1. Open `http://localhost:5173/ivr`.
2. Click **Start Call** or dial `1913`.
3. The AI gives a short bilingual greeting and stops speaking.
4. Speak naturally (*e.g., "Gandhipuram-la thanni varala"*).
5. Notice:
   - Live VAD detects speech energy.
   - Dynamic language detected as **Tanglish**.
   - Category identified as **Water Supply**.
   - Location pinned to **Gandhipuram**.
   - AI asks for missing information: *"Idhu eppo lendhu varala?"*
6. Answer: *"Two days-ah"*.
7. AI summarizes and asks for confirmation.
8. Answer: *"Aama register pannunga"*.
9. Official complaint record is generated (*e.g., `VX-2026-000101`*) and spoken back to you!

### Step 12: Install FFmpeg (Optional, for raw audio conversions)
On Windows:
```powershell
winget install Gyan.FFmpeg
# or
choco install ffmpeg
```

### Step 13: Configure Whisper (Optional, for offline neural speech transcription)
Install Whisper dependencies:
```powershell
pip install faster-whisper
# or
pip install openai-whisper
```
When installed, `speech_service.py` automatically utilizes the model on CPU/CUDA.

### Step 14: Configure Text-to-Speech (TTS)
By default, the backend synthesizes voice via `gTTS` / `edge-tts` and falls back gracefully to the browser Web Speech API synthesis engine in Tamil, English, and Tanglish.

### Step 15: Configure Exotel for Real Phone Calls
To receive calls from normal phones:
1. Obtain an Exotel virtual phone number and API credentials (`EXOTEL_ACCOUNT_SID`, `EXOTEL_API_KEY`, `EXOTEL_API_TOKEN`).
2. Expose your backend via HTTPS (e.g. using ngrok or a Cloud VM):
   ```powershell
   ngrok http 8000
   ```
3. Set Exotel Passthru Applet URL to:
   `https://<your-domain>/api/v1/webhooks/exotel/voice/incoming`
4. Set Exotel Voice Recording Callback URL to:
   `https://<your-domain>/api/v1/webhooks/exotel/voice/recording`

### Step 16: Deployment Instructions
- **Backend (Linux/Docker)**:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
  ```
- **Frontend (Static Hosting / Vercel / Nginx)**:
  ```bash
  npm run build
  # Serve dist/ directory
  ```

---

## 👥 Demo Credentials

| Role | Email | Password | Scope |
|---|---|---|---|
| **Citizen** | `citizen@voxentra.tn.gov.in` | `Citizen@123` | Submit & track personal grievances |
| **Officer (Water)** | `officer.water@voxentra.tn.gov.in` | `Officer@123` | Water Supply & Sewage Department Queue |
| **Officer (Roads)** | `officer.roads@voxentra.tn.gov.in` | `Officer@123` | Roads & Transport Department Queue |
| **Admin** | `admin@voxentra.tn.gov.in` | `Admin@123` | Municipal System Dashboard & User Management |

---

## 🧪 Automated Testing

Run the complete 92-test test suite:
```powershell
cd backend
python -m pytest tests/ -v
```

Build and validate the frontend bundle:
```powershell
cd frontend
npm run build
```
