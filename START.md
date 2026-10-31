# 🩸 Centralized Cloud Blood Bank & Emergency Registry
## Complete Project Setup, Quickstart & Architecture Guide

A **Cloud Computing** project demonstrating a centralized web platform for blood bank inventory management and emergency blood request coordination across hospitals and blood banks.

This document contains everything needed to start, access, and inspect all components of the project (**Frontend**, **FastAPI Backend**, **SQLite Database**, and **Docker PostgreSQL Container**).

---

## 🌐 Quick Access URL Directory

When all services are running, access every layer via these links:

| Component | Port | Browser URL | Description |
|---|---|---|---|
| **Streamlit Web Portal** | `8501` | **[http://localhost:8501](http://localhost:8501)** | Main user interface (Admin, Blood Bank, Hospital views) |
| **FastAPI REST API** | `8000` | **[http://localhost:8000](http://localhost:8000)** | Backend root service |
| **Interactive API Docs (Swagger)** | `8000` | **[http://localhost:8000/docs](http://localhost:8000/docs)** | Test REST endpoints and schemas |
| **Alternative API Docs (ReDoc)** | `8000` | **[http://localhost:8000/redoc](http://localhost:8000/redoc)** | ReDoc formatted API documentation |
| **SQLite Database Explorer** | `8050` | **[http://localhost:8050](http://localhost:8050)** | Web inspector for local `blood_bank.db` |
| **Docker PostgreSQL (Adminer)** | `8088` | **[http://localhost:8088](http://localhost:8088)** | Containerized PostgreSQL web manager |

---

## 📋 Prerequisites

* **Python 3.10+** (Tested on Python 3.11 / 3.13)
* **Git**
* **Docker Desktop** (Optional, required for PostgreSQL container stack)

---

## 🚀 Option 1: Standard Local Setup (Fastest)

### Step 1: Open Terminal & Navigate to Project Directory
```powershell
cd C:\Users\hp\OneDrive\Desktop\CCproject
```

### Step 2: Create & Activate Virtual Environment
* **Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
* **macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install All Dependencies
```powershell
pip install -r requirements.txt
pip install -r api/requirements.txt
```

### Step 4: Configure `.env`
Ensure your `.env` file exists in the root folder with:
```env
APP_ENV=development
DEBUG=true
DEMO_MODE=true
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=sqlite:///blood_bank.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin@BloodBank123!
```

### Step 5: Initialize & Seed Database
```powershell
# Create database tables
python -c "from database.connection import init_database; init_database()"

# Seed demonstration data (hospitals, blood banks, inventory lots, donors)
python -m database.seed
```

### Step 6: Start the Services
Run each service in separate terminal windows (or in the background):

1. **Frontend (Streamlit Web App):**
   ```powershell
   python -m streamlit run app.py
   ```
   👉 Open **http://localhost:8501**

2. **Backend (FastAPI REST Service):**
   ```powershell
   python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```
   👉 Open **http://localhost:8000/docs**

3. **SQLite Database Web Inspector:**
   ```powershell
   python db_viewer.py
   ```
   👉 Open **http://localhost:8050**

---

## 🐳 Option 2: Docker Containerized Setup (Full Cloud Stack)

To run the containerized cloud environment with PostgreSQL 16, Streamlit, FastAPI, and Adminer:

### Step 1: Launch Containers
```powershell
docker compose up -d
```

### Step 2: Access Docker Services
* **Streamlit App**: [http://localhost:8501](http://localhost:8501)
* **FastAPI Backend**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **PostgreSQL Database UI (Adminer)**: [http://localhost:8088](http://localhost:8088)

#### Login Credentials for Adminer (PostgreSQL):
* **System**: `PostgreSQL`
* **Server**: `postgres` (or `bloodbank_postgres`)
* **Username**: `bloodbank`
* **Password**: `changeme`
* **Database**: `blood_bank_db`

*Direct pre-filled login URL:*  
👉 **[http://localhost:8088/?pgsql=postgres&username=bloodbank&db=blood_bank_db](http://localhost:8088/?pgsql=postgres&username=bloodbank&db=blood_bank_db)** *(password: `changeme`)*

### Step 3: Stop Docker Services
```powershell
docker compose down
```

---

## 🔄 Dual Database Synchronization (SQLite ⇄ Docker PostgreSQL)

The project includes an automatic synchronization script ([`sync_databases.py`](sync_databases.py)):
* Whenever a hospital registers on the website, it is stored in SQLite and automatically mirrored into Docker PostgreSQL.
* To manually sync all tables from SQLite to PostgreSQL at any time, run:
```powershell
python sync_databases.py
```

---

## 🔐 Authorized Demo Accounts

| Role | Username | Password | Accessible Features |
|---|---|---|---|
| **Administrator** | `admin` | `Admin@BloodBank123!` | Executive Dashboard, Low-stock/expiry alerts, Demand Forecast, Audit logs |
| **Hospital** | `hospital_1` | `Hospital1@Pass` | Submit emergency requests, proximity & compatibility blood search |
| **Blood Bank** | `bb_1` | `BloodBank1@Pass` | FEFO Inventory lots, status workflow, donor registry outreach |

*New hospitals can also register their own credentials anytime via the **`🏥 Register Hospital`** tab on the login page.*

---

## 🧪 Automated Testing Suite

To run all 120 unit and integration tests (RBAC permissions, concurrency stress tests, atomic reservations, and API tests):
```powershell
python -m pytest tests/ api/tests/ -v
```

---

## 📂 Key Architecture Files

* **`app.py`**: Main Streamlit entry point, authentication portal, role-based routing.
* **`pages/`**: Streamlit pages (`1_Admin_Dashboard.py`, `2_Blood_Inventory.py`, `3_Emergency_Registry.py`, `4_Blood_Bank_Search.py`, `5_Reports.py`, `6_Transfers.py`, `7_Donor_Registry.py`).
* **`api/main.py`**: FastAPI application exposing JWT authentication and REST endpoints.
* **`db_viewer.py`**: Web-based SQLite inspector (`http://localhost:8050`).
* **`sync_databases.py`**: Real-time replicator between SQLite and Docker PostgreSQL.
* **`docker-compose.yml`**: Multi-container stack (PostgreSQL 16, Adminer, FastAPI, Streamlit).
* **`blood_bank.db`**: Local SQLite database file with WAL mode enabled.
