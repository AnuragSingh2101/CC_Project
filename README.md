# Centralized Cloud Blood Bank & Emergency Registry

A **Cloud Computing** academic project demonstrating a centralized web platform for blood bank inventory management and emergency blood request coordination.

> **Academic Prototype** — Synthetic data only. Not intended for clinical use. All blood products require professional verification before transfusion.

## Problem Statement

Blood banks and hospitals operate in isolation, creating delays during emergencies when patients urgently need specific blood types. A centralized, cloud-accessible platform can provide real-time inventory visibility and coordinate emergency requests across organizations.

## Features

### Core Features
- 🔐 **Role-based access control** — Admin, Blood Bank, Hospital roles with service-layer authorization
- 🩸 **Blood inventory management** — Create lots, track expiry, monitor low stock, FEFO workflow
- 🚨 **Emergency request registry** — Submit, track, cancel requests with urgency levels (critical/urgent/routine)
- 🔍 **Blood bank search** — Find available inventory by blood group, city, quantity, and distance
- ✅ **Atomic reservations** — Oversell-safe inventory reservation with transaction safety
- 📊 **Admin dashboard** — Live metrics, charts, and alerts from real database data
- 📋 **Reports & audit log** — Full activity history with filtering

### New Features (v2.0)
- ⚡ **Auto-refresh & Escalation** — Emergency Registry auto-refreshes every 15s via `st.fragment`; requests past SLA (critical: 15min, urgent: 60min) show OVERDUE badge; admin escalation notifies nearby blood banks within configurable radius
- 🔔 **Notifications** — In-app notification center with unread count in sidebar; optional SMTP email delivery (enabled only when SMTP_* env vars set, fails silently otherwise)
- 📈 **Reports & Forecasting** — CSV exports for inventory, requests, audit log; HTML print view for browser PDF; weekly demand trend per blood group with 4-week moving average forecast (Plotly chart)
- 🌐 **FastAPI Layer** — REST API exposing all service functions: `/auth/login` (JWT), `/inventory`, `/search`, `/requests`, `/requests/{id}/reserve`, `/transfers`, `/donors`, `/notifications`; OpenAPI docs at `/docs`
- 🐳 **Docker Support** — Multi-service `docker-compose.yml` with Streamlit, FastAPI, and PostgreSQL (named volume, healthcheck)
- 🔄 **CI/CD** — GitHub Actions workflow: pytest with coverage, fails if services/ coverage < 80%
- 🔒 **Security Hardening** — Login lockout (5 failed attempts → 15min lock), change-password page, production secret validation (refuses default SECRET_KEY/ADMIN_PASSWORD when DEBUG=false), demo accounts hidden unless `DEMO_MODE=true`
- 📊 **Role-scoped Home Metrics** — Admin sees all; blood banks see their inventory/requests; hospitals see only their own requests

## Architecture

```
Browser → HTTPS → Streamlit App (port 8501) → Service Layer → SQLAlchemy ORM → SQLite / PostgreSQL
                    ↓
              FastAPI (port 8000) → Same Service Layer → JWT Auth → OpenAPI /docs
```

See [`docs/diagrams/architecture.mmd`](docs/diagrams/architecture.mmd) for the full diagram.

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Web Framework | Streamlit 1.37+ |
| API Framework | FastAPI 0.110+ |
| Database ORM | SQLAlchemy 2.0+ |
| Database | SQLite (local) / PostgreSQL 16 (cloud/Docker) |
| Password Hashing | bcrypt |
| Data Analysis | Pandas 2.2+ |
| Charts | Plotly 5.22+ |
| Testing | pytest 8.2+ / pytest-cov |
| Migrations | Alembic 1.13+ |
| Deployment | Docker Compose / Streamlit Community Cloud |

## Project Structure

```
blood-bank-cloud/
├── app.py                    # Main entry point, login, home, change-password
├── requirements.txt          # Runtime deps (pinned)
├── requirements-dev.txt      # Dev deps (pytest, coverage)
├── README.md
├── .env.example
├── .gitignore
├── Dockerfile                # Multi-stage build
├── docker-compose.yml        # Streamlit + FastAPI + PostgreSQL
├── alembic/                  # Database migration scripts
│   ├── env.py
│   └── versions/             # Migration revisions
├── config/
│   └── settings.py           # Environment-based configuration & SLA/escalation
├── database/
│   ├── connection.py         # Engine factory (SQLite WAL + PostgreSQL)
│   ├── schema.py             # Model registry
│   └── seed.py               # Synthetic demo data (Indian cities, donors, lots, transfers)
├── models/                   # SQLAlchemy ORM models
│   ├── organization.py       # Hospitals & blood banks with latitude/longitude
│   ├── user.py               # Role-based user accounts with Bcrypt + lockout fields
│   ├── inventory.py          # Lots with component, status, and shelf life
│   ├── emergency_request.py  # Emergency requests with component, urgency, escalation
│   ├── reservation.py        # Anti-oversell stock reservation
│   ├── audit_log.py          # Immutable system event logs
│   ├── donor.py              # Voluntary donor registry & appointment booking
│   ├── transfer_request.py   # Inter-bank stock transfer requests
│   └── notification.py       # In-app notifications (user/org target, read flag)
├── services/                 # Business logic & domain services
│   ├── auth_service.py       # Authentication, session, lockout, password change
│   ├── inventory_service.py  # Lot management, status workflow, expiry calculations
│   ├── compatibility.py      # Component-aware ABO/Rh rules & scarcity ranking
│   ├── matching_service.py   # FEFO & compatibility search engine
│   ├── geo.py                # Haversine distance calculations & coordinates
│   ├── request_service.py    # Emergency request state machine + escalation
│   ├── reservation_service.py # Atomic concurrency-safe reservations
│   ├── donor_service.py      # 56-day whole blood eligibility & donor outreach
│   ├── transfer_service.py   # Bank-to-bank stock transfer approvals & reallocation
│   ├── audit_service.py      # Audit trail recording
│   └── notify_service.py     # In-app + optional SMTP email notifications
├── pages/                    # Streamlit multi-page web application
│   ├── 1_Admin_Dashboard.py  # Executive metrics, charts, and alerts
│   ├── 2_Blood_Inventory.py  # Inventory, shelf-life, and status workflow
│   ├── 3_Emergency_Registry.py # Auto-refresh requests, overdue badges, escalation
│   ├── 4_Blood_Bank_Search.py # Geolocation search, radius filter, and map
│   ├── 5_Reports.py          # CSV exports, HTML print, demand forecast chart
│   ├── 6_Transfers.py        # Inter-bank transfer management
│   └── 7_Donor_Registry.py   # Voluntary donor registry & appointments
├── api/                      # FastAPI REST API
│   ├── main.py               # FastAPI app with JWT auth, all endpoints
│   ├── schemas.py            # Pydantic request/response models
│   ├── requirements.txt      # API-specific deps
│   └── tests/                # API tests with TestClient
│       └── test_api.py
├── tests/                    # Automated pytest test suite (102 tests + API tests)
│   ├── conftest.py           # In-memory SQLite fixtures
│   ├── test_inventory.py     # Lot creation, updates, bounds
│   ├── test_requests.py      # Requests lifecycle, SLA boundaries, validation
│   ├── test_reservations.py  # Reservation mechanics & releases
│   ├── test_permissions.py   # Authentication, tenant isolation, lockout
│   ├── test_compatibility.py # ABO/Rh compatibility & scarcity ranking
│   ├── test_components_and_status.py # Shelf life & lot status transitions
│   ├── test_geo_and_search.py # Haversine distance & radius filters
│   ├── test_donors.py        # 56-day eligibility edge cases & appointments
│   ├── test_transfers.py     # Bank-to-bank transfer approvals & receipt
│   └── test_concurrency_stress.py # Multi-threaded concurrent reservation stress test
└── docs/
    ├── project_report.md     # Academic project report
    ├── presentation_slides.md # Presentation slides with speaker notes
    ├── viva_questions.md     # Viva voce preparation guide
    ├── deployment_guide.md   # Cloud deployment instructions
    └── diagrams/             # Mermaid architectural diagrams
```

## Installation (Windows PowerShell)

### Prerequisites

- Python 3.10 or later
- Git

### Step 1 — Clone the repository

```powershell
git clone https://github.com/<your-username>/blood-bank-cloud.git
cd blood-bank-cloud
```

### Step 2 — Create a virtual environment (recommended)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3 — Install dependencies

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -r api/requirements.txt
```

### Step 4 — Configure environment

```powershell
Copy-Item .env.example .env
# Edit .env to set your preferred configuration (optional for local dev)
```

### Step 5 — Initialize the database

```powershell
python -c "from database.connection import init_database; init_database()"
```

### Step 6 — Seed demonstration data

```powershell
python -m database.seed
```

This creates synthetic blood banks, hospitals, inventory, and requests — all clearly labeled as demonstration data.

To reset and reseed (WARNING: deletes all data):
```powershell
python -m database.seed --reset
```

### Step 7 — Run the application

```powershell
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

## Running with Docker

```powershell
# Set required environment variables first (or use .env)
docker compose up --build
```

Services:
- **Streamlit UI**: http://localhost:8501
- **FastAPI API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432

## Running Tests

```powershell
# Core tests (102 tests)
python -m pytest tests/ -v

# API tests
python -m pytest api/tests/ -v

# All tests with coverage
python -m pytest tests/ api/tests/ --cov=services --cov-report=term-missing --cov-fail-under=80
```

**Actual test results:** 102 core tests + API tests, all passing (Python 3.11, pytest 8.2)

## Demo Accounts

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `Admin@BloodBank123!` |
| Blood Bank 1 | `bb_1` | `BloodBank1@Pass` |
| Blood Bank 2 | `bb_2` | `BloodBank2@Pass` |
| Blood Bank 3 | `bb_3` | `BloodBank3@Pass` |
| Blood Bank 4 | `bb_4` | `BloodBank4@Pass` |
| Hospital 1 | `hospital_1` | `Hospital1@Pass` |
| Hospital 2 | `hospital_2` | `Hospital2@Pass` |
| Hospital 3 | `hospital_3` | `Hospital3@Pass` |

> Change all passwords before deploying to a shared environment. Demo accounts only shown when `DEMO_MODE=true`.

## Cloud Deployment (Streamlit Community Cloud)

### Requirements

- GitHub account (free)
- Streamlit Community Cloud account (free at share.streamlit.io)

### Steps

1. Push the repository to GitHub (make sure `.env` and `blood_bank.db` are in `.gitignore`)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** → connect your GitHub repository
4. Set the main file path to `app.py`
5. Add secrets in the app dashboard:
   ```toml
   DATABASE_URL = "sqlite:///blood_bank.db"
   SECRET_KEY = "your-random-secret-key"
   ADMIN_USERNAME = "admin"
   ADMIN_PASSWORD = "your-secure-admin-password"
   DEBUG = "false"
   DEMO_MODE = "false"
   ```
6. Deploy

### SQLite Limitation on Cloud

Streamlit Community Cloud uses an ephemeral filesystem. A SQLite database file created during a session may not persist between restarts. For durable data, configure a PostgreSQL URL from a free managed service (e.g., Neon, Supabase, ElephantSQL).

### PostgreSQL Configuration

Set `DATABASE_URL` in your Streamlit secrets to:
```
postgresql://username:password@host:5432/blood_bank_db
```

The application uses `psycopg2` and SQLAlchemy and will automatically use the configured database.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///blood_bank.db` | Database connection string |
| `SECRET_KEY` | `dev-secret-key-...` | Application secret key (must change in production) |
| `ADMIN_USERNAME` | `admin` | Admin username for first-run setup |
| `ADMIN_PASSWORD` | `Admin@BloodBank123!` | Admin password (must change in production) |
| `DEBUG` | `false` | Enable debug logging |
| `SEED_DATABASE` | `false` | Auto-seed on startup (not recommended) |
| `DEMO_MODE` | `true` | Show demo accounts on login page |
| `SLA_CRITICAL_MINUTES` | `15` | SLA for critical requests (minutes) |
| `SLA_URGENT_MINUTES` | `60` | SLA for urgent requests (minutes) |
| `SLA_ROUTINE_MINUTES` | `1440` | SLA for routine requests (minutes) |
| `ESCALATION_RADIUS_KM` | `100.0` | Radius to notify blood banks on escalation |
| `LOCKOUT_MAX_ATTEMPTS` | `5` | Failed login attempts before lockout |
| `LOCKOUT_DURATION_MINUTES` | `15` | Lockout duration in minutes |
| `SMTP_HOST` | *(empty)* | SMTP server host (optional) |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | *(empty)* | SMTP username |
| `SMTP_PASSWORD` | *(empty)* | SMTP password |
| `SMTP_FROM` | `noreply@cloudbloodbank.org` | From email address |
| `SMTP_TLS` | `true` | Use TLS for SMTP |

## Limitations

1. **SQLite concurrency** — SQLite uses write-level locking. Under high concurrent write load, transactions may serialize. PostgreSQL should be used for production.
2. **SQLite persistence on cloud** — Ephemeral filesystems lose the database on restart.
3. **No real-time notifications** — Streamlit requires manual refresh to see updates (except Emergency Registry which uses `st.fragment`).
4. **Single-process** — Streamlit runs in a single process; horizontal scaling requires a shared database.
5. **Medical disclaimer** — This prototype does NOT perform clinical compatibility validation. All transfusion decisions require qualified medical professional review.
6. **Security** — This is a demonstration prototype. Production deployment requires a full security review, proper secrets management, TLS, rate limiting, and data protection compliance.

## Security Notes

- Passwords are hashed using bcrypt (salt factor 12)
- No plaintext passwords stored anywhere
- Authorization enforced in service layer, not only in UI
- Input validation on all user-provided data
- Parameterized queries via SQLAlchemy ORM
- No real patient data collected or stored
- Login lockout after 5 failed attempts (15-minute lockout)
- Production startup refuses default SECRET_KEY and ADMIN_PASSWORD when DEBUG=false
- Demo accounts hidden unless `DEMO_MODE=true`
- Change password page for authenticated users