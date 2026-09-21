# VoxentraAI — Comprehensive Project Audit

**Audit Date**: 2026-09-20  
**Project Name**: VoxentraAI (AI-Powered Citizen Complaint Management System)  
**Target Environment**: Tamil Nadu Civic Administration & Citizen Portal  
**Project Workspace Root**: `c:\Users\Akshaya\OneDrive\voxentraAII`

---

## 1. Executive Summary

A comprehensive inspection of the workspace was conducted prior to code implementation. The workspace root `c:\Users\Akshaya\OneDrive\voxentraAII` is established as the canonical, clean root directory for the complete full-stack application.

An earlier prototype directory `voxentra01` located in the parent directory was examined to preserve and upgrade useful domain data—specifically Tamil Nadu location coordinates (such as Coimbatore Gandhipuram, RS Puram, Ukkadam, Chennai, Madurai landmarks), bilingual keyword dictionaries, and sample audio structures.

The architecture eliminates all duplicate directory nesting, enforces strict role-based access control, provides an offline-first deterministic multilingual AI engine, and delivers a modern, accessible civic interface.

---

## 2. Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Server**: Uvicorn (ASGI)
- **Database ORM**: SQLAlchemy 2.0 (Declarative Base)
- **Validation**: Pydantic v2
- **Authentication**: JWT (JSON Web Tokens) with standard HMAC-SHA256 and `passlib[bcrypt]`
- **Testing**: Pytest with HTTPX Async/Sync TestClient
- **Database**: SQLite for development; fully PostgreSQL-compatible for deployment

### AI & Speech Engine
- **Language Detection**: Deterministic script & Romanized lexicon analyzer (Tamil, English, Tanglish)
- **Normalization**: Unicode sanitizer, phonetic keyword standardizer
- **Classification**: Configurable multi-category keyword and pattern matcher
- **Location Extraction**: Tamil Nadu district, ward, and landmark extractor with coordinates
- **Priority Assessment**: Severity rule engine with safety overrides (Fire, Accident, Electrical)
- **Speech Service**: Modular Whisper interface (`faster-whisper` / `openai-whisper`) with graceful fallback status

### Frontend
- **Framework**: React 18 with TypeScript
- **Bundler & Dev Server**: Vite
- **Routing**: React Router DOM v6
- **Icons**: Lucide React
- **API Client**: Axios with automatic Bearer token interceptor
- **Styling**: Custom Civic Design System (CSS variables, dark/light theme tokens, glassmorphism, responsive grid)

---

## 3. Directory Layout

```
voxentraAII/
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
│   │   ├── logging_config.py
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

## 4. Key Architectural Safeguards

1. **No Fabricated Data**: If an audio file cannot be transcribed (e.g. Whisper is not yet loaded), the system returns an honest status indicating speech configuration status rather than hallucinating transcriptions.
2. **Deterministic Fallback**: Text complaints in Tamil, English, and Tanglish are analyzed locally and instantaneously without requiring paid cloud APIs.
3. **Data Isolation**: Citizens can only view and update their own submitted complaints; officers can only access assigned complaints; administrators maintain global supervision.
4. **Lifecycle Auditing**: Every status change (from `SUBMITTED` through `RESOLVED`) is logged in `ComplaintHistory` with the responsible user ID and notes.
