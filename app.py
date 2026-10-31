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

# Import settings and validate production secrets
from config.settings import DEMO_MODE, validate_production_secrets
validate_production_secrets()

# Initialize database on first run
from database.connection import init_database
try:
    init_database()
except Exception as e:
    st.error(f"Database initialization failed: {e}")
    st.stop()

from services.auth_service import (
    authenticate, login, logout, get_current_user, is_logged_in, change_password, register_hospital
)
from services.notify_service import get_unread_count
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

/* Sidebar title & text */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] a,
section[data-testid="stSidebar"] div {
    color: #1a2744 !important;
}

section[data-testid="stSidebar"] a:hover {
    color: #c0392b !important;
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
    st.markdown("""
    <style>
    /* Hide sidebar completely on authentication page */
    section[data-testid="stSidebar"], [data-testid="collapsedControl"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding: 30px 0 20px;">
            <h1 style="color:#c0392b; font-size:2rem; margin-bottom:4px;">🩸 Cloud Blood Bank</h1>
            <p style="color:#5d6d7e; font-size:1rem;">Emergency Registry & Inventory Management</p>
            <hr style="border-color:#e0e3ed;">
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["🔐 Sign In", "🏥 Register Hospital"])

        with tab_login:
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
                            # Check if account is locked
                            from models.user import User
                            db_user = db.query(User).filter(User.username == username.strip()).first()
                            if db_user and db_user.is_locked:
                                remaining = 0
                                if db_user.locked_until:
                                    from datetime import datetime, timezone
                                    locked = db_user.locked_until
                                    if locked.tzinfo is None:
                                        locked = locked.replace(tzinfo=timezone.utc)
                                    remaining = int((locked - datetime.now(timezone.utc)).total_seconds() / 60) + 1
                                st.error(f"Account temporarily locked due to multiple failed attempts. Try again in {remaining} minute(s).")
                            else:
                                st.error("Invalid username or password.")
                    except Exception as e:
                        logger.error(f"Login error: {e}")
                        st.error("Login failed. Please try again.")
                    finally:
                        db.close()

            # Only show demo accounts if DEMO_MODE is true
            if DEMO_MODE:
                st.markdown("""
                <div style="margin-top:20px; padding:16px; background:#edf2f7; border:1px solid #cbd5e0; border-radius:8px; font-size:13px; color:#2d3748;">
                <strong style="color:#1a202c; font-size:14px;">Demo Accounts</strong><br>
                <div style="margin-top:6px; line-height:1.7;">
                    Admin: <code style="background:#e2e8f0; color:#c53030; padding:2px 6px; border-radius:4px;">admin</code> / <code style="background:#e2e8f0; color:#2b6cb0; padding:2px 6px; border-radius:4px;">Admin@BloodBank123!</code><br>
                    Blood Bank: <code style="background:#e2e8f0; color:#c53030; padding:2px 6px; border-radius:4px;">bb_1</code> / <code style="background:#e2e8f0; color:#2b6cb0; padding:2px 6px; border-radius:4px;">BloodBank1@Pass</code><br>
                    Hospital: <code style="background:#e2e8f0; color:#c53030; padding:2px 6px; border-radius:4px;">hospital_1</code> / <code style="background:#e2e8f0; color:#2b6cb0; padding:2px 6px; border-radius:4px;">Hospital1@Pass</code>
                </div>
                <div style="margin-top:8px; color:#718096; font-size:12px;">
                    <em>Run <code>python -m database.seed</code> to initialize demo data.</em>
                </div>
                </div>
                """, unsafe_allow_html=True)

        with tab_register:
            st.markdown("##### 🏥 New Hospital Registration")
            st.caption("Register your hospital to participate in the Emergency Registry network.")
            with st.form("hospital_registration_form"):
                st.markdown("**Hospital Information**")
                h_name = st.text_input("Hospital Name *", placeholder="e.g. Apollo Memorial Hospital")
                h_city = st.text_input("City *", placeholder="e.g. Bengaluru")
                h_state = st.text_input("State *", placeholder="e.g. Karnataka")
                h_address = st.text_input("Street Address", placeholder="e.g. 15 Bannerghatta Road")
                h_contact = st.text_input("Emergency Contact Number", placeholder="e.g. +91 80 2345 6789")

                with st.expander("Optional: Geographic Coordinates"):
                    st.caption("If left blank, coordinates will be automatically assigned from city database.")
                    h_lat_str = st.text_input("Latitude", placeholder="e.g. 12.9716")
                    h_lon_str = st.text_input("Longitude", placeholder="e.g. 77.5946")

                st.markdown("**Hospital Portal Account**")
                h_user = st.text_input("Account Username *", placeholder="e.g. apollo_admin")
                h_pass = st.text_input("Account Password *", type="password", help="Minimum 8 characters")
                h_pass_confirm = st.text_input("Confirm Password *", type="password")

                reg_submitted = st.form_submit_button("Register Hospital", use_container_width=True, type="primary")

            if reg_submitted:
                if not h_name or not h_city or not h_state or not h_user or not h_pass:
                    st.error("Please fill in all required fields (*).")
                elif h_pass != h_pass_confirm:
                    st.error("Passwords do not match.")
                elif len(h_pass) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    h_lat = float(h_lat_str.strip()) if h_lat_str and h_lat_str.strip() else None
                    h_lon = float(h_lon_str.strip()) if h_lon_str and h_lon_str.strip() else None

                    db = get_session()
                    try:
                        org, new_user = register_hospital(
                            db=db,
                            name=h_name,
                            city=h_city,
                            state=h_state,
                            address=h_address,
                            contact_number=h_contact,
                            latitude=h_lat,
                            longitude=h_lon,
                            username=h_user,
                            password=h_pass,
                        )
                        db.commit()
                        st.success(f"🎉 Hospital '{org.name}' successfully registered! You can now sign in on the 'Sign In' tab.")
                    except ValueError as ve:
                        st.error(str(ve))
                    except Exception as ex:
                        db.rollback()
                        logger.error(f"Registration error: {ex}")
                        st.error("Failed to register hospital. Please check details and try again.")
                    finally:
                        db.close()


# ──────────────────────────────────────────────────────────────
# Change Password page
# ──────────────────────────────────────────────────────────────
def render_change_password():
    user = get_current_user()
    st.markdown('<div class="page-header"><h2>🔐 Change Password</h2></div>', unsafe_allow_html=True)

    with st.form("change_password_form"):
        current_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input("New Password", type="password", help="Minimum 8 characters")
        confirm_pw = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Update Password", type="primary")

    if submitted:
        if not current_pw or not new_pw or not confirm_pw:
            st.error("Please fill in all fields.")
        elif new_pw != confirm_pw:
            st.error("New passwords do not match.")
        elif len(new_pw) < 8:
            st.error("New password must be at least 8 characters.")
        else:
            db = get_session()
            try:
                success = change_password(db, user['id'], current_pw, new_pw)
                if success:
                    db.commit()
                    st.success("Password updated successfully!")
                    st.rerun()
                else:
                    st.error("Current password is incorrect.")
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                logger.error(f"Change password error: {e}")
                st.error("Failed to update password.")
            finally:
                db.close()


# ──────────────────────────────────────────────────────────────
# Sidebar navigation
# ──────────────────────────────────────────────────────────────
def render_sidebar():
    user = get_current_user()
    user_id = user['id']
    org_id = user.get('organization_id')

    with st.sidebar:
        st.markdown("### 🩸 Blood Bank Registry")
        st.markdown(f"**{user['username']}** · *{user['role'].replace('_', ' ').title()}*")
        if user['organization_name']:
            st.markdown(f"📍 {user['organization_name']}")

        # ── Notifications ──────────────────────────────────────
        db = get_session()
        try:
            unread_count = get_unread_count(db, user_id, org_id)
        finally:
            db.close()

        if unread_count > 0:
            st.markdown(f"🔔 **Notifications** <span class='badge badge-critical'>{unread_count}</span>", unsafe_allow_html=True)
            with st.expander("View Notifications", expanded=False):
                db = get_session()
                try:
                    from services.notify_service import get_notifications_for_user, mark_as_read
                    notifications = get_notifications_for_user(db, user_id, org_id, limit=20)
                    for notif in notifications:
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            read_style = "" if notif.is_read else "font-weight:600;"
                            st.markdown(
                                f"<div style='{read_style} padding:4px 0;'>"
                                f"<strong>{notif.title}</strong><br>"
                                f"<small>{notif.message[:100]}{'...' if len(notif.message) > 100 else ''}</small><br>"
                                f"<small style='color:#888'>{notif.created_at.strftime('%Y-%m-%d %H:%M') if notif.created_at else ''}</small>"
                                f"</div>", unsafe_allow_html=True
                            )
                        with col2:
                            if not notif.is_read:
                                if st.button("✓", key=f"read_{notif.id}", help="Mark as read"):
                                    db_act = get_session()
                                    try:
                                        mark_as_read(db_act, notif.id, user_id)
                                        db_act.commit()
                                        st.rerun()
                                    finally:
                                        db_act.close()
                        st.divider()
                    if st.button("Mark All as Read", use_container_width=True):
                        db_act = get_session()
                        try:
                            from services.notify_service import mark_all_as_read
                            mark_all_as_read(db_act, user_id, org_id)
                            db_act.commit()
                            st.rerun()
                        finally:
                            db_act.close()
                finally:
                    db.close()
        else:
            st.markdown("🔔 **Notifications** <span class='badge badge-routine'>0</span>", unsafe_allow_html=True)

        st.divider()

        # ── Change Password Link ──────────────────────────────
        if st.button("🔐 Change Password", use_container_width=True):
            st.session_state["page"] = "change_password"
            st.rerun()

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
# Home page (landing after login) — role-scoped metrics
# ──────────────────────────────────────────────────────────────
def render_home():
    user = get_current_user()
    role = user['role']
    org_id = user.get('organization_id')

    st.markdown('<div class="page-header"><h2>🏠 Dashboard Home</h2></div>', unsafe_allow_html=True)
    st.write(f"Welcome back, **{user['username']}**. Use the sidebar to navigate.")

    db = get_session()
    try:
        from models.inventory import InventoryLot
        from models.emergency_request import EmergencyRequest
        from models.organization import Organization
        from services.donor_service import get_donors_needed
        from datetime import date

        if role == "admin":
            # Admin sees everything
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

            st.info("👉 Visit **Admin Dashboard** for complete multi-center analytics and system monitoring.")

        elif role == "blood_bank":
            # Blood bank sees their inventory and relevant requests
            col1, col2, col3 = st.columns(3)
            with col1:
                # Their inventory lots
                lots = db.query(InventoryLot).filter(
                    InventoryLot.blood_bank_id == org_id,
                    InventoryLot.status == "available",
                    InventoryLot.expiry_date >= date.today()
                ).count()
                st.metric("Active Inventory Lots", lots)
            with col2:
                # Available units
                avail = db.query(InventoryLot).filter(
                    InventoryLot.blood_bank_id == org_id,
                    InventoryLot.status == "available",
                    InventoryLot.expiry_date >= date.today()
                ).all()
                total_units = sum(l.available_units for l in avail)
                st.metric("Available Units", total_units)
            with col3:
                # Pending requests for their blood group/city
                from services.matching_service import find_matching_lots
                # Approximation: show all pending requests
                pending = db.query(EmergencyRequest).filter(
                    EmergencyRequest.status == "pending"
                ).count()
                st.metric("Pending Requests (System)", pending)

            # Donors needed panel
            st.divider()
            st.subheader("🚨 Donors Needed (Low-Stock Alert Panel)")
            needed = get_donors_needed(db, blood_bank_id=org_id)
            if needed:
                for item in needed:
                    st.warning(
                        f"⚠️ **{item['blood_group']} Stock Low:** {item['current_stock']} units available in {item['city']}. "
                        f"**{item['eligible_donors_count']} eligible voluntary donor(s)** found in {item['city']} for outreach."
                    )
                st.info("👉 Open the **Donor Registry** from the sidebar to view contact details and book donation appointments.")
            else:
                st.success("✅ All blood group stock levels meet or exceed safe reserves.")

        elif role == "hospital":
            # Hospital sees only their own requests
            col1, col2, col3 = st.columns(3)
            with col1:
                my_pending = db.query(EmergencyRequest).filter(
                    EmergencyRequest.hospital_id == org_id,
                    EmergencyRequest.status == "pending"
                ).count()
                st.metric("My Pending Requests", my_pending)
            with col2:
                my_matched = db.query(EmergencyRequest).filter(
                    EmergencyRequest.hospital_id == org_id,
                    EmergencyRequest.status == "matched"
                ).count()
                st.metric("My Matched Requests", my_matched)
            with col3:
                my_critical = db.query(EmergencyRequest).filter(
                    EmergencyRequest.hospital_id == org_id,
                    EmergencyRequest.urgency == "critical",
                    EmergencyRequest.status.in_(["pending", "matched"])
                ).count()
                st.metric("My Critical Active", my_critical, delta_color="inverse")

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
    # Check for change password page
    if st.session_state.get("page") == "change_password":
        render_change_password()
        # Add back button
        if st.button("← Back to Dashboard"):
            st.session_state.pop("page", None)
            st.rerun()
    else:
        render_sidebar()
        render_home()