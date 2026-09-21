# 🏛️ VoxentraAI — AI-Powered Citizen Complaint Management System

VoxentraAI is a full-stack, enterprise-grade civic complaint management platform designed for Tamil Nadu citizens, government department officers, and municipal administrators.

It empowers citizens to submit public grievances using **Tamil**, **English**, or **Tanglish** via text input, in-browser microphone recording, or audio uploads. An offline-first deterministic AI classification engine extracts locations, assesses emergency priority, determines category, and routes grievances to the appropriate civic departments.

---

## 🌟 Key Features

- 🌐 **Multilingual Civic Portal**: Native support for Tamil script, English, and Tanglish (e.g., *"Gandhipuram-la thanni pipe odanju pochu"*).
- 🎙️ **Voice & Audio Processing**: In-browser microphone recording and audio file uploads with modular Whisper-compatible speech recognition.
- 🤖 **Transparent Offline-First AI Engine**: Instant keyword and linguistic pattern classification, Tamil Nadu landmark entity extraction, and safety priority analysis without external API dependencies.
- 🛡️ **Role-Based Access Control**:
  - **Citizen**: Submit complaints, review AI draft, track timeline step-by-step, view history, receive notifications.
  - **Officer**: Manage departmental assigned queue, update statuses with notes, track SLA deadlines.
  - **Admin**: Monitor live municipal analytics, manage departments, manage officers, inspect escalations.
- 📊 **Auditable Complaint Lifecycle**: Full history tracking across all status transitions (`SUBMITTED` ➔ `UNDER_REVIEW` ➔ `ASSIGNED` ➔ `IN_PROGRESS` ➔ `RESOLVED`).
- 📞 **IVR / Telephony Ready**: Extensible Exotel webhook integration for phone-in complaint registrations.

---

## 📁 Project Architecture

```
VOXENTRAAI/
├── README.md
├── PROJECT_AUDIT.md
├── .gitignore
├── .env.example
├── docs/
│   ├── API.md
│   ├── DATABASE.md
│   └── IVR_INTEGRATION.md
├── backend/
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── ai/
│   │   ├── integrations/
│   │   └── utils/
│   └── tests/
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── api/
        ├── components/
        ├── context/
        ├── pages/
        ├── types/
        └── utils/
```

---

## 🚀 Quick Start Guide (Windows / VS Code)

### 1. Prerequisites
- **Python 3.11+** installed
- **Node.js 18+** & **npm** installed

---

### 2. Backend Setup

Open a PowerShell terminal in the project root:

```powershell
# 1. Navigate to backend directory
cd backend

# 2. Create Python virtual environment
python -m venv venv

# 3. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 4. Install backend dependencies
pip install -r requirements.txt

# 5. Initialize Database and seed demo data
python -m app.database.init_db

# 6. Start the FastAPI backend server
uvicorn app.main:app --reload --port 8000
```

The backend server will start at: `http://localhost:8000`  
Interactive Swagger API documentation: `http://localhost:8000/docs`  
Health check endpoint: `http://localhost:8000/health`

---

### 3. Frontend Setup

Open a second PowerShell terminal in the project root:

```powershell
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start the Vite development server
npm run dev
```

The frontend portal will open at: `http://localhost:5173`

---

## 👥 Pre-Configured Demo Accounts

For instant evaluation across all roles, click the **1-Click Demo Login** buttons on the Login page, or enter:

| Role | Email | Password | Scope |
|---|---|---|---|
| **Citizen** | `citizen@voxentra.tn.gov.in` | `Citizen@123` | Submit & track personal grievances |
| **Officer (Water)** | `officer.water@voxentra.tn.gov.in` | `Officer@123` | Water Supply & Sewage Department Queue |
| **Officer (Roads)** | `officer.roads@voxentra.tn.gov.in` | `Officer@123` | Roads & Transport Department Queue |
| **Admin** | `admin@voxentra.tn.gov.in` | `Admin@123` | Municipal System Dashboard & User Management |

---

## 🧪 Running Automated Tests

Run backend tests with coverage:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest -v
```

Run frontend type check & production build:

```powershell
cd frontend
npm run build
```

---

## ⚙️ Offline AI & Whisper Configuration

- **Deterministic Fallback**: Active by default. Analyzes Tamil, English, and Tanglish text complaints instantly without network requests or external API keys.
- **Whisper Speech Recognition**: If `faster-whisper` or `openai-whisper` and FFmpeg are present, audio files and browser microphone recordings are transcribed locally. If not installed, the application returns a clear, transparent status to input text instead of crashing or generating fake text.

---

## 🔒 Security Best Practices
- Passwords hashed with `bcrypt`.
- Stateless JWT authentication with role authorization middleware.
- Data ownership checks prevent citizens from viewing or modifying other citizens' data.
- Input validation on all endpoints using Pydantic schemas.
