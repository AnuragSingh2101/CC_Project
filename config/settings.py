"""
Application configuration settings.
Reads from environment variables or Streamlit secrets.
"""
import os
from pathlib import Path

# Try loading .env file for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try loading Streamlit secrets (for cloud deployment)
def _get_streamlit_secret(key: str, default=None):
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


def get_setting(key: str, default=None):
    """Get a configuration value from env vars or Streamlit secrets."""
    value = os.environ.get(key)
    if value is None:
        value = _get_streamlit_secret(key, default)
    return value if value is not None else default


# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database
DATABASE_URL = get_setting(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'blood_bank.db'}"
)

# For SQLite, store absolute path
if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith("sqlite:////"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        DATABASE_URL = f"sqlite:///{BASE_DIR / db_path}"

# Application
APP_ENV = get_setting("APP_ENV", "development")
DEBUG = get_setting("DEBUG", "false").lower() == "true"
SECRET_KEY = get_setting("SECRET_KEY", "dev-secret-key-change-in-production")

# Admin setup
ADMIN_USERNAME = get_setting("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = get_setting("ADMIN_PASSWORD", "Admin@BloodBank123!")

# Blood groups supported
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# Urgency levels
URGENCY_LEVELS = ["routine", "urgent", "critical"]

# Request statuses
REQUEST_STATUSES = ["pending", "matched", "fulfilled", "cancelled"]

# Reservation statuses
RESERVATION_STATUSES = ["active", "released", "fulfilled"]

# Blood components and shelf-life (days)
BLOOD_COMPONENTS = ["whole_blood", "packed_red_cells", "platelets", "plasma"]
COMPONENT_SHELF_LIFE = {
    "whole_blood": 35,
    "packed_red_cells": 42,
    "platelets": 5,
    "plasma": 365,
}

# Lot statuses and workflow
LOT_STATUSES = ["quarantine", "tested", "available", "discarded"]

# Transfer request statuses
TRANSFER_STATUSES = ["pending", "approved", "rejected", "in_transit", "received"]

# Donor eligibility threshold (days since last whole-blood donation)
DONOR_ELIGIBILITY_DAYS = 56

# Thresholds
LOW_STOCK_THRESHOLD = 10   # units
NEAR_EXPIRY_DAYS = 7       # days

# SLA response thresholds (minutes) and escalation radius
SLA_MINUTES = {
    "critical": int(get_setting("SLA_CRITICAL_MINUTES", 15)),
    "urgent": int(get_setting("SLA_URGENT_MINUTES", 60)),
    "routine": int(get_setting("SLA_ROUTINE_MINUTES", 1440)),
}
ESCALATION_RADIUS_KM = float(get_setting("ESCALATION_RADIUS_KM", 100.0))

# Demo mode & Login Lockout
DEMO_MODE = get_setting("DEMO_MODE", "true").lower() == "true"
LOCKOUT_MAX_ATTEMPTS = int(get_setting("LOCKOUT_MAX_ATTEMPTS", 5))
LOCKOUT_DURATION_MINUTES = int(get_setting("LOCKOUT_DURATION_MINUTES", 15))

# Optional SMTP Email Configuration
SMTP_HOST = get_setting("SMTP_HOST")
SMTP_PORT = int(get_setting("SMTP_PORT", 587))
SMTP_USER = get_setting("SMTP_USER")
SMTP_PASSWORD = get_setting("SMTP_PASSWORD")
SMTP_FROM = get_setting("SMTP_FROM", "noreply@cloudbloodbank.org")
SMTP_TLS = get_setting("SMTP_TLS", "true").lower() == "true"

# Is the database PostgreSQL?
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# Seed data flag
SEED_DATABASE = get_setting("SEED_DATABASE", "false").lower() == "true"


def validate_production_secrets():
    """Refuse to start with default credentials or dev secret key when DEBUG is false."""
    if not DEBUG:
        if SECRET_KEY in ("dev-secret-key-change-in-production", "", None):
            raise RuntimeError(
                "Production security violation: SECRET_KEY must be changed from the default development value when DEBUG=false."
            )
        if ADMIN_PASSWORD in ("Admin@BloodBank123!", "Admin@1234", "", None):
            raise RuntimeError(
                "Production security violation: ADMIN_PASSWORD must be changed from the default value when DEBUG=false."
            )

