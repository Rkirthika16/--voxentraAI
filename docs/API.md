# VoxentraAI REST API Specification

Base URL: `http://localhost:8000/api/v1`

---

## 1. System Health
- **`GET /health`**
  - Public endpoint.
  - Returns service status, database connectivity, and speech recognition module status.

---

## 2. Authentication (`/auth`)
- **`POST /api/v1/auth/register`**
  - **Body**: `{ "full_name": "...", "email": "...", "password": "...", "phone": "..." }`
  - Creates a citizen account, returning user profile and access token.
- **`POST /api/v1/auth/login`**
  - **Body**: `{ "email": "...", "password": "..." }`
  - Validates credentials and returns JWT bearer token + user role.
- **`GET /api/v1/auth/me`**
  - **Headers**: `Authorization: Bearer <token>`
  - Returns authenticated user details.
- **`POST /api/v1/auth/logout`**
  - Client-side token invalidation.

---

## 3. User Management (`/users`)
- **`GET /api/v1/users/profile`**
  - Retrieves profile information for current user.
- **`PUT /api/v1/users/profile`**
  - Updates profile fields (`full_name`, `phone`).
- **`GET /api/v1/users`** *(Admin only)*
  - Lists users filtered by role.
- **`POST /api/v1/users/officer`** *(Admin only)*
  - Creates officer account assigned to a specific department.

---

## 4. Departments (`/departments`)
- **`GET /api/v1/departments`**
  - Lists all active civic departments (Water, Electricity, Roads, Sanitation, Drainage, Streetlights, Public Safety, General).
- **`POST /api/v1/departments`** *(Admin only)*
  - Create/configure departments.
- **`PUT /api/v1/departments/{id}`** *(Admin only)*
  - Edit department details or active status.

---

## 5. AI Analysis & Speech (`/analysis`, `/audio`)
- **`POST /api/v1/analysis/text`**
  - **Body**: `{ "text": "Gandhipuram-la thanni pipe odanju pochu" }`
  - **Returns**: `{ "category": "Water", "priority": "High", "department": "Water Supply & Sewage", "extracted_location": "Gandhipuram", "detected_language": "Tanglish", "summary": "...", "analysis_method": "deterministic_fallback" }`
- **`POST /api/v1/analysis/audio`**
  - **Form Data**: `file` (WAV/MP3/M4A/WEBM)
  - Transcribes audio using Whisper (or returns honest fallback status if Whisper is unconfigured) and runs full analysis.
- **`POST /api/v1/audio/transcribe`**
  - **Form Data**: `file`
  - Transcribes speech to text.

---

## 6. Complaints Lifecycle (`/complaints`)
- **`GET /api/v1/complaints`** *(Admin / Officer)*
  - Supports query filters: `status`, `category`, `priority`, `department_id`, `search`, `page`, `page_size`.
- **`GET /api/v1/complaints/my`** *(Citizen)*
  - Returns only complaints submitted by the authenticated citizen.
- **`POST /api/v1/complaints`** *(Citizen / Public with confirmation)*
  - Submits a confirmed complaint, generates tracking ID (`VOX-YYYY-XXXX`), performs automatic department routing, and sends notification.
- **`GET /api/v1/complaints/{complaint_id}`**
  - Fetches complaint details, attachments, AI classification report, and timeline history.
- **`PATCH /api/v1/complaints/{complaint_id}/status`** *(Officer / Admin)*
  - Updates complaint status (`UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `REJECTED`, `REOPENED`) with mandatory resolution note.
- **`GET /api/v1/complaints/{complaint_id}/history`**
  - Returns full auditable timeline of status changes.

---

## 7. Officer Management (`/officers`)
- **`GET /api/v1/officers/complaints`** *(Officer)*
  - Returns complaints assigned to current officer or their department.
- **`POST /api/v1/officers/assign`** *(Admin / Officer)*
  - Assigns complaint to a specific officer.

---

## 8. Admin Dashboard & Escalations (`/admin`)
- **`GET /api/v1/admin/stats`**
  - Live database metrics: total, submitted, in-progress, resolved, overdue, category breakdown, department breakdown, priority breakdown.
- **`GET /api/v1/admin/escalations`**
  - Lists escalated complaints.

---

## 9. Notifications (`/notifications`)
- **`GET /api/v1/notifications`**
  - Lists notifications for authenticated user.
- **`PATCH /api/v1/notifications/{id}/read`**
  - Marks notification as read.
- **`POST /api/v1/notifications/read-all`**
  - Marks all notifications as read.

---

## 10. IVR & Telephony Webhooks (`/webhooks/exotel`)
- **`POST /api/v1/webhooks/exotel/voice/incoming`**
- **`POST /api/v1/webhooks/exotel/voice/recording`**
- **`POST /api/v1/webhooks/exotel/sms/incoming`**

---

## 11. AI Voice & Talking Assistant (`/assistant`)
- **`POST /api/v1/assistant/chat`**
  - **Body**: `{ "message": "Water pipe broken near Gandhipuram bus stand", "session_id": "...", "language_hint": "Tamil" }`
  - **Returns**: Conversational AI response with intent analysis, structured grievance draft, tracking status lookup, and natural spoken text for TTS.
- **`POST /api/v1/assistant/voice-chat`**
  - **Form Data**: `file` (audio stream/file), `session_id`, `language_hint`
  - Transcribes audio, processes intent, generates AI grievance draft, and returns spoken talking response.
- **`GET /api/v1/assistant/suggestions`**
  - Returns sample quick-starter prompts, Tamil Nadu emergency helplines, and municipal category cards.

