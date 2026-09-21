# VoxentraAI Database Architecture

## 1. Overview
The database uses SQLAlchemy 2.0 with declarative mapping. It runs on **SQLite** for local development and is fully compatible with **PostgreSQL** in production without schema modifications.

---

## 2. Entity-Relationship Schema

```mermaid
erDiagram
    USERS ||--o{ COMPLAINTS : "submits"
    USERS ||--o{ ASSIGNMENTS : "assigned to"
    USERS ||--o{ NOTIFICATIONS : "receives"
    DEPARTMENTS ||--o{ COMPLAINTS : "manages"
    COMPLAINTS ||--o{ COMPLAINT_HISTORY : "tracks"
    COMPLAINTS ||--o{ ASSIGNMENTS : "assigned via"
    COMPLAINTS ||--o{ NOTIFICATIONS : "generates"
    COMPLAINTS ||--o{ ESCALATIONS : "triggers"

    USERS {
        int id PK
        string public_id UK
        string full_name
        string email UK
        string phone
        string password_hash
        string role "CITIZEN | OFFICER | ADMIN"
        int department_id FK "optional"
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    DEPARTMENTS {
        int id PK
        string code UK
        string name
        string description
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    COMPLAINTS {
        int id PK
        string complaint_number UK
        int citizen_id FK
        int department_id FK
        int assigned_officer_id FK
        string title
        text description
        text original_text
        text normalized_text
        string language
        string category
        string location
        string latitude
        string longitude
        string priority "CRITICAL | HIGH | MEDIUM | LOW"
        string status "SUBMITTED | UNDER_REVIEW | ASSIGNED | IN_PROGRESS | RESOLVED | REJECTED | REOPENED | OVERDUE"
        json ai_metadata
        boolean citizen_confirmed
        datetime due_at
        datetime resolved_at
        datetime created_at
        datetime updated_at
    }

    COMPLAINT_HISTORY {
        int id PK
        int complaint_id FK
        string previous_status
        string new_status
        text note
        int changed_by_id FK
        datetime created_at
    }

    ASSIGNMENTS {
        int id PK
        int complaint_id FK
        int officer_id FK
        int assigned_by_id FK
        datetime assigned_at
        datetime unassigned_at
        text notes
    }

    NOTIFICATIONS {
        int id PK
        int user_id FK
        int complaint_id FK
        string title
        text message
        boolean is_read
        datetime created_at
    }

    ESCALATIONS {
        int id PK
        int complaint_id FK
        int triggered_by_id FK
        text reason
        string status "OPEN | RESOLVED"
        datetime created_at
        datetime resolved_at
    }
```

---

## 3. Allowed Status Transitions

| Current Status | Allowed Next Statuses | Permitted Roles |
|---|---|---|
| `SUBMITTED` | `UNDER_REVIEW`, `ASSIGNED`, `REJECTED` | Officer, Admin |
| `UNDER_REVIEW` | `ASSIGNED`, `IN_PROGRESS`, `REJECTED` | Officer, Admin |
| `ASSIGNED` | `IN_PROGRESS`, `REJECTED` | Officer, Admin |
| `IN_PROGRESS` | `RESOLVED`, `REJECTED` | Officer, Admin |
| `RESOLVED` | `REOPENED` | Citizen (own complaint), Admin |
| `REJECTED` | `REOPENED` | Citizen (own complaint), Admin |
| `REOPENED` | `UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS` | Officer, Admin |
| Any Status | `OVERDUE` | System Cron / Officer / Admin |
