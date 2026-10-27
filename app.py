"""
Centralized Cloud Blood Bank & Emergency Registry
Main application entry point.

Run with: streamlit run app.py
"""
import streamlit as st
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Page config — must be first Streamlit call
st.set_page_config(
    page_title="Cloud Blood Bank & Emergency Registry",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database on first run
from database.connection import init_database
try:
    init_database()
except Exception as e:
    st.error(f"Database initialization failed: {e}")
    st.stop()

from services.auth_service import (
    authenticate, login, logout, get_current_user, is_logged_in
)
from database.connection import get_session


# ──────────────────────────────────────────────────────────────
# Custom CSS — clean hospital-management style
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Base */
html, body, [class*="css"] {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    color: #1a2744;
    background-color: #f5f6fa;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e0e3ed;
}

/* Sidebar title */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #1a2744;
}

/* Metric cards */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e0e3ed;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* Primary buttons */
.stButton > button[kind="primary"] {
    background-color: #c0392b;
    color: white;
    border: none;
    border-radius: 5px;
    font-weight: 600;
}
.stButton > button[kind="primary"]:hover {
    background-color: #a93226;
}

/* Tables */
.stDataFrame {
    border: 1px solid #e0e3ed;
    border-radius: 6px;
}

/* Alerts */
.stAlert {
    border-radius: 6px;
}

/* Status badges */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-critical { background: #fdecea; color: #c0392b; }
.badge-urgent   { background: #fef9e7; color: #d68910; }
.badge-routine  { background: #eafaf1; color: #1e8449; }
.badge-pending  { background: #eaf4fb; color: #1a5276; }
.badge-matched  { background: #fdf2f8; color: #7d3c98; }
.badge-fulfilled{ background: #eafaf1; color: #1e8449; }
.badge-cancelled{ background: #f2f3f4; color: #717d7e; }

/* Page header */
.page-header {
    border-bottom: 2px solid #c0392b;
    padding-bottom: 8px;
    margin-bottom: 20px;
}

/* Disclaimer box */
.disclaimer {
    background: #fef9e7;
    border-left: 4px solid #f1c40f;
    padding: 10px 15px;
    border-radius: 4px;
    font-size: 13px;
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# Login page
# ──────────────────────────────────────────────────────────────
def render_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding: 30px 0 20px;">
            <h1 style="color:#c0392b; font-size:2rem; margin-bottom:4px;">🩸 Cloud Blood Bank</h1>
            <p style="color:#5d6d7e; font-size:1rem;">Emergency Registry & Inventory Management</p>
            <hr style="border-color:#e0e3ed;">
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                db = get_session()
                try:
                    user = authenticate(username, password, db)
                    if user:
                        login(user, db)
                        db.commit()
                        st.success(f"Welcome, {user.username}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                except Exception as e:
                    logger.error(f"Login error: {e}")
                    st.error("Login failed. Please try again.")
                finally:
                    db.close()

        st.markdown("""
        <div style="margin-top:20px; padding:12px; background:#f8f9fa; border-radius:6px; font-size:13px;">
        <strong>Demo Accounts</strong><br>
        Admin: <code>admin</code> / <code>Admin@BloodBank123!</code><br>
        Blood Bank: <code>bb_1</code> / <code>BloodBank1@Pass</code><br>
        Hospital: <code>hospital_1</code> / <code>Hospital1@Pass</code><br>
        <em>Run <code>python -m database.seed</code> to initialize demo data.</em>
        </div>
        """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# Sidebar navigation
# ──────────────────────────────────────────────────────────────
def render_sidebar():
    user = get_current_user()
    with st.sidebar:
        st.markdown("### 🩸 Blood Bank Registry")
        st.markdown(f"**{user['username']}** · *{user['role'].replace('_', ' ').title()}*")
        if user['organization_name']:
            st.markdown(f"📍 {user['organization_name']}")
        st.divider()

        role = user['role']
        if role == "admin":
            st.markdown("**Navigation**")
            st.page_link("pages/1_Admin_Dashboard.py", label="📊 Admin Dashboard")
            st.page_link("pages/2_Blood_Inventory.py", label="🩸 Blood Inventory")
            st.page_link("pages/3_Emergency_Registry.py", label="🚨 Emergency Registry")
            st.page_link("pages/4_Blood_Bank_Search.py", label="🔍 Blood Bank Search")
            st.page_link("pages/6_Transfers.py", label="🔄 Inter-Bank Transfers")
            st.page_link("pages/7_Donor_Registry.py", label="👥 Donor Registry")
            st.page_link("pages/5_Reports.py", label="📋 Reports & Activity")
        elif role == "blood_bank":
            st.markdown("**Navigation**")
            st.page_link("pages/2_Blood_Inventory.py", label="🩸 Blood Inventory")
            st.page_link("pages/3_Emergency_Registry.py", label="🚨 Emergency Registry")
            st.page_link("pages/4_Blood_Bank_Search.py", label="🔍 Blood Bank Search")
            st.page_link("pages/6_Transfers.py", label="🔄 Inter-Bank Transfers")
            st.page_link("pages/7_Donor_Registry.py", label="👥 Donor Registry")
        elif role == "hospital":
            st.markdown("**Navigation**")
            st.page_link("pages/3_Emergency_Registry.py", label="🚨 Emergency Registry")
            st.page_link("pages/4_Blood_Bank_Search.py", label="🔍 Blood Bank Search")

        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()
            st.rerun()


# ──────────────────────────────────────────────────────────────
# Home page (landing after login)
# ──────────────────────────────────────────────────────────────
def render_home():
    user = get_current_user()
    role = user['role']

    st.markdown('<div class="page-header"><h2>🏠 Dashboard Home</h2></div>', unsafe_allow_html=True)
    st.write(f"Welcome back, **{user['username']}**. Use the sidebar to navigate.")

    db = get_session()
    try:
        from models.inventory import InventoryLot
        from models.emergency_request import EmergencyRequest
        from models.organization import Organization
        from services.donor_service import get_donors_needed
        from datetime import date

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            banks = db.query(Organization).filter(Organization.type == "blood_bank").count()
            st.metric("Blood Banks", banks)
        with col2:
            hospitals = db.query(Organization).filter(Organization.type == "hospital").count()
            st.metric("Hospitals", hospitals)
        with col3:
            pending = db.query(EmergencyRequest).filter(EmergencyRequest.status == "pending").count()
            st.metric("Pending Requests", pending)
        with col4:
            critical = db.query(EmergencyRequest).filter(
                EmergencyRequest.urgency == "critical",
                EmergencyRequest.status.in_(["pending", "matched"])
            ).count()
            st.metric("Critical Active", critical, delta_color="inverse")

        # ── Blood Bank Donors Needed Panel ──
        if role == "blood_bank" and user.get("organization_id"):
            st.divider()
            st.subheader("🚨 Donors Needed (Low-Stock Alert Panel)")
            needed = get_donors_needed(db, blood_bank_id=user["organization_id"])
            if needed:
                for item in needed:
                    st.warning(
                        f"⚠️ **{item['blood_group']} Stock Low:** {item['current_stock']} units available in {item['city']}. "
                        f"**{item['eligible_donors_count']} eligible voluntary donor(s)** found in {item['city']} for outreach."
                    )
                st.info("👉 Open the **Donor Registry** from the sidebar to view contact details and book donation appointments.")
            else:
                st.success("✅ All blood group stock levels meet or exceed safe reserves.")

        elif role == "admin":
            st.info("👉 Visit **Admin Dashboard** for complete multi-center analytics and system monitoring.")
        elif role == "hospital":
            st.info("👉 Visit **Emergency Registry** to submit and monitor emergency blood requests.")

    except Exception as e:
        logger.error(f"Home page error: {e}")
        st.error("Failed to load summary data.")
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────
# Main routing
# ──────────────────────────────────────────────────────────────
if not is_logged_in():
    render_login()
else:
    render_sidebar()
    render_home()
