# Centralized Cloud Blood Bank & Emergency Registry

A **Cloud Computing** academic project demonstrating a centralized web platform for blood bank inventory management and emergency blood request coordination.

> **Academic Prototype** — Synthetic data only. Not intended for clinical use. All blood products require professional verification before transfusion.

## Problem Statement

Blood banks and hospitals operate in isolation, creating delays during emergencies when patients urgently need specific blood types. A centralized, cloud-accessible platform can provide real-time inventory visibility and coordinate emergency requests across organizations.

## Features

- 🔐 **Role-based access control** — Admin, Blood Bank, Hospital roles
- 🩸 **Blood inventory management** — Create lots, track expiry, monitor low stock
- 🚨 **Emergency request registry** — Submit, track, cancel requests with urgency levels
- 🔍 **Blood bank search** — Find available inventory by blood group, city, and quantity
- ✅ **Atomic reservations** — Oversell-safe inventory reservation with transaction safety
- 📊 **Admin dashboard** — Live metrics, charts, and alerts from real database data
- 📋 **Reports & audit log** — Full activity history
- 🌐 **Cloud deployable** — Streamlit Community Cloud compatible

## Architecture

```
Browser → HTTPS → Streamlit App → Service Layer → SQLAlchemy ORM → SQLite / PostgreSQL
```

See [`docs/diagrams/architecture.mmd`](docs/diagrams/architecture.mmd) for the full diagram.

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.13 |
| Web Framework | Streamlit 1.32+ |
| Database ORM | SQLAlchemy 2.x |
| Database | SQLite (local) / PostgreSQL (cloud) |
| Password Hashing | bcrypt |
| Data Analysis | Pandas |
| Charts | Plotly |
| Testing | pytest |
| Deployment | Streamlit Community Cloud / GitHub |

## Project Structure

```
blood-bank-cloud/
├── app.py                    # Main entry point, login, home
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── alembic/                  # Database migration scripts
│   ├── env.py
│   └── versions/             # Migration revisions
├── config/
│   └── settings.py           # Environment-based configuration & component shelf-lives
├── database/
│   ├── connection.py         # Engine factory (SQLite WAL + PostgreSQL)
│   ├── schema.py             # Model registry
│   └── seed.py               # Synthetic demo data (Indian cities, donors, lots, transfers)
├── models/                   # SQLAlchemy ORM models
│   ├── organization.py       # Hospitals & blood banks with latitude/longitude
│   ├── user.py               # Role-based user accounts with Bcrypt hashing
│   ├── inventory.py          # Lots with component, status, and shelf life
│   ├── emergency_request.py  # Emergency requests with component and urgency
│   ├── reservation.py        # Anti-oversell stock reservation
│   ├── audit_log.py          # Immutable system event logs
│   ├── donor.py              # Voluntary donor registry & appointment booking
│   └── transfer_request.py   # Inter-bank stock transfer requests
├── services/                 # Business logic & domain services
│   ├── auth_service.py       # Authentication & session controls
│   ├── inventory_service.py  # Lot management, status workflow, expiry calculations
│   ├── compatibility.py      # Component-aware ABO/Rh rules & scarcity ranking
│   ├── matching_service.py   # FEFO & compatibility search engine
│   ├── geo.py                # Haversine distance calculations & coordinates
│   ├── request_service.py    # Emergency request state machine
│   ├── reservation_service.py # Atomic concurrency-safe reservations
│   ├── donor_service.py      # 56-day whole blood eligibility & donor outreach
│   ├── transfer_service.py   # Bank-to-bank stock transfer approvals & reallocation
│   └── audit_service.py      # Audit trail recording
├── pages/                    # Streamlit multi-page web application
│   ├── 1_Admin_Dashboard.py  # Executive metrics, charts, and alerts
│   ├── 2_Blood_Inventory.py  # Inventory, shelf-life, and status workflow
│   ├── 3_Emergency_Registry.py # Hospital emergency requests & reservations
│   ├── 4_Blood_Bank_Search.py # Geolocation search, radius filter, and map
│   ├── 5_Reports.py          # Activity audits and data exports
│   ├── 6_Transfers.py        # Inter-bank transfer management
│   └── 7_Donor_Registry.py   # Voluntary donor registry & appointments
├── tests/                    # Automated pytest test suite (102 tests)
│   ├── conftest.py           # In-memory SQLite fixtures
│   ├── test_inventory.py     # Lot creation, updates, bounds
│   ├── test_requests.py      # Requests lifecycle & validation
│   ├── test_reservations.py  # Reservation mechanics & releases
│   ├── test_permissions.py   # Authentication & tenant isolation
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

## Running Tests

```powershell
python -m pytest tests/ -v
```

**Actual test results:** 60 tests, 60 passed, 0 failed (Python 3.13, pytest 9.1.1)

For coverage report:
```powershell
python -m pytest tests/ --cov=services --cov-report=term-missing
```

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

> Change all passwords before deploying to a shared environment.

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
| `SECRET_KEY` | `dev-secret-key-...` | Application secret key |
| `ADMIN_USERNAME` | `admin` | Admin username for first-run setup |
| `ADMIN_PASSWORD` | `Admin@BloodBank123!` | Admin password (change immediately) |
| `DEBUG` | `false` | Enable debug logging |
| `SEED_DATABASE` | `false` | Auto-seed on startup (not recommended) |

## Limitations

1. **SQLite concurrency** — SQLite uses write-level locking. Under high concurrent write load, transactions may serialize. PostgreSQL should be used for production.
2. **SQLite persistence on cloud** — Ephemeral filesystems lose the database on restart.
3. **No real-time notifications** — Streamlit requires manual refresh to see updates.
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
