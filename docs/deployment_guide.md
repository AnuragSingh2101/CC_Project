# Cloud Deployment Guide

## Centralized Cloud Blood Bank & Emergency Registry
**Subject:** Cloud Computing  
**Application Architecture:** Python Streamlit Web Application + SQLAlchemy ORM + Cloud Relational Database (PostgreSQL / SQLite).

---

## 1. Deployment Overview

This application is designed using 12-factor cloud principles and can be deployed in two primary configurations:

| Component | Option A: Free Cloud PaaS (Recommended) | Option B: Full Cloud Database + PaaS |
| :--- | :--- | :--- |
| **Hosting Platform** | Streamlit Community Cloud | Streamlit Community Cloud or Render |
| **Database** | File-backed SQLite (bundled or seeded) | Managed Cloud PostgreSQL (Neon / Supabase / ElephantSQL) |
| **Cost** | 100% Free | 100% Free Tier |
| **Setup Time** | ~3 minutes | ~8 minutes |

---

## 2. Option A: Streamlit Community Cloud Deployment (Zero Cost)

Streamlit Community Cloud is a platform-as-a-service designed for Streamlit applications, providing direct deployment from GitHub with automatic HTTPS/TLS certificates.

### Step 1: Push Repository to GitHub
1. Initialize git in your local project directory if not already done:
   ```powershell
   git init
   git add .
   git commit -m "feat: complete Centralized Cloud Blood Bank & Emergency Registry"
   ```
2. Create a new repository on your GitHub account (e.g., `blood-bank-cloud`).
3. Link and push your code:
   ```powershell
   git remote add origin https://github.com/<your-username>/blood-bank-cloud.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Deploy on Streamlit Community Cloud
1. Navigate to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
2. Click **"New app"**.
3. Select your repository: `<your-username>/blood-bank-cloud`.
4. Set the branch: `main`.
5. Set the Main file path: `app.py`.
6. Click **"Deploy!"**.

### Step 3: Configure Cloud Secrets / Environment Variables
In the Streamlit Cloud dashboard:
1. Go to **Settings** -> **Secrets**.
2. Add your environment variables:
   ```toml
   [general]
   APP_ENV = "production"
   SECRET_KEY = "generate-a-random-secure-32-char-string"
   # To use local SQLite storage on the cloud instance:
   DATABASE_URL = "sqlite:///blood_bank.db"
   ```
3. Save. The app will automatically restart and initialize the database.

---

## 3. Option B: Connecting a Managed Cloud PostgreSQL Database

For a production-grade multi-tier architecture, connect the application to an external cloud database service (e.g., [Neon.tech](https://neon.tech/) or [Supabase](https://supabase.com/)):

### Step 1: Provision Free PostgreSQL Database
1. Sign up at [Neon.tech](https://neon.tech/) or [Supabase](https://supabase.com/).
2. Create a new project named `blood-bank-db`.
3. Copy the PostgreSQL connection URI, which looks like:
   `postgresql://username:password@ep-cool-cloud.us-east-2.aws.neon.tech/blood_bank?sslmode=require`

### Step 2: Seed the Cloud Database
From your local terminal, initialize and seed the cloud database by setting `DATABASE_URL`:
```powershell
$env:DATABASE_URL="postgresql://username:password@ep-cool-cloud.us-east-2.aws.neon.tech/blood_bank?sslmode=require"
python -c "from database.connection import init_database; init_database(); print('Cloud DB Initialized!')"
python -m database.seed
```

### Step 3: Configure Streamlit Secrets for PostgreSQL
In Streamlit Community Cloud -> **Settings** -> **Secrets**:
```toml
[general]
APP_ENV = "production"
SECRET_KEY = "your-secure-production-key"
DATABASE_URL = "postgresql://username:password@ep-cool-cloud.us-east-2.aws.neon.tech/blood_bank?sslmode=require"
```
The application will automatically connect to your cloud PostgreSQL database.

---

## 4. Alternative: Deploying on Render (PaaS Web Service)

Render provides free web service containers:

1. Create a `render.yaml` or use the Render Web UI:
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
2. Add Environment Variables:
   - `PYTHON_VERSION`: `3.11.8`
   - `DATABASE_URL`: `sqlite:///blood_bank.db` (or cloud postgres link)
   - `APP_ENV`: `production`
3. Click **"Deploy"**.

---

## 5. Verification Checklist Post-Deployment

After cloud deployment completes:

1. **Verify HTTPS:** Ensure the URL uses `https://` with a valid TLS certificate.
2. **Database Verification:**
   - Log in using demo administrator credentials: `admin` / `Admin@1234`
   - Verify that the Dashboard loads organization and inventory metrics.
3. **Emergency Workflow Test:**
   - Log in as Hospital (`hospital_general` / `Hospital@1234`).
   - Create an Emergency Request.
   - Perform a Search and Reserve 1 unit.
   - Log out, log in as Blood Bank (`bank_city` / `Bank@1234`).
   - Verify the reservation and mark it fulfilled.
4. **Audit Trail:**
   - Log back in as `admin` and open the **Audit Logs** tab to confirm all events were recorded with timestamps.

---

## 6. Troubleshooting Common Deployment Issues

| Problem | Root Cause | Solution |
| :--- | :--- | :--- |
| **`ModuleNotFoundError: No module named 'psycopg2'`** | PostgreSQL URI used without driver | `requirements.txt` includes `psycopg2-binary`. Ensure requirements installed properly. |
| **Database Reset on Restart (SQLite on PaaS)** | PaaS containers have ephemeral disks | Switch to Neon/Supabase cloud PostgreSQL or use a persistent mount for `blood_bank.db`. |
| **Streamlit blank screen or port error** | Server trying to bind to localhost | Ensure `--server.address 0.0.0.0` and `--server.headless true` flags are used. |
| **Timezone mismatch in logs** | Cloud container defaults to UTC | Application converts timestamps to UTC ISO-8601 strings, displayed in local time. |
