"""
Authentication service — login, session management, and role enforcement.
Never stores plain-text passwords.
"""
import streamlit as st
from sqlalchemy.orm import Session
from models.user import User
from models.organization import Organization
from services.audit_service import log_action
from services.geo import get_city_coordinates
from config.settings import LOCKOUT_MAX_ATTEMPTS, LOCKOUT_DURATION_MINUTES
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

# --- Session state keys ---
SESSION_USER_ID = "auth_user_id"
SESSION_USERNAME = "auth_username"
SESSION_ROLE = "auth_role"
SESSION_ORG_ID = "auth_org_id"
SESSION_ORG_NAME = "auth_org_name"


def authenticate(username: str, password: str, db: Session):
    """
    Verify credentials and return the User object if valid.
    Returns None if authentication fails.
    Implements login lockout after failed attempts.
    """
    if not username or not password:
        return None
    user = db.query(User).filter(
        User.username == username.strip(),
        User.is_active == True  # noqa
    ).first()
    if not user:
        return None

    # Check if account is locked
    if user.is_locked:
        remaining = None
        if user.locked_until:
            locked = user.locked_until
            if locked.tzinfo is None:
                locked = locked.replace(tzinfo=timezone.utc)
            remaining = int((locked - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        logger.warning(f"Login attempt for locked account: {username}")
        return None

    if user.check_password(password):
        # Reset failed attempts on successful login
        if user.failed_login_attempts > 0:
            user.failed_login_attempts = 0
            user.locked_until = None
            db.flush()
        return user
    else:
        # Increment failed attempts
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= LOCKOUT_MAX_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            logger.warning(f"Account locked due to failed attempts: {username}")
        db.flush()
        return None


def login(user: User, db: Session):
    """Store authenticated user in Streamlit session state."""
    org_name = None
    if user.organization_id:
        org = db.get(Organization, user.organization_id)
        org_name = org.name if org else None

    st.session_state[SESSION_USER_ID] = user.id
    st.session_state[SESSION_USERNAME] = user.username
    st.session_state[SESSION_ROLE] = user.role
    st.session_state[SESSION_ORG_ID] = user.organization_id
    st.session_state[SESSION_ORG_NAME] = org_name

    log_action(
        db=db,
        user_id=user.id,
        action="login",
        entity_type="user",
        entity_id=user.id,
        details=f"User {user.username!r} logged in."
    )
    logger.info(f"User '{user.username}' logged in.")


def logout():
    """Clear session state."""
    for key in [SESSION_USER_ID, SESSION_USERNAME, SESSION_ROLE,
                SESSION_ORG_ID, SESSION_ORG_NAME]:
        st.session_state.pop(key, None)


def get_current_user():
    """Return dict of currently logged-in user info, or None."""
    uid = st.session_state.get(SESSION_USER_ID)
    if uid is None:
        return None
    return {
        "id": uid,
        "username": st.session_state.get(SESSION_USERNAME),
        "role": st.session_state.get(SESSION_ROLE),
        "organization_id": st.session_state.get(SESSION_ORG_ID),
        "organization_name": st.session_state.get(SESSION_ORG_NAME),
    }


def is_logged_in() -> bool:
    return st.session_state.get(SESSION_USER_ID) is not None


def require_login():
    """Redirect to login if not authenticated."""
    if not is_logged_in():
        st.warning("Please log in to access this page.")
        st.stop()


def require_role(*roles: str):
    """Stop execution if current user does not have one of the required roles."""
    user = get_current_user()
    if user is None:
        st.warning("Please log in to access this page.")
        st.stop()
    if user["role"] not in roles:
        st.error(f"Access denied. Required roles: {', '.join(roles)}.")
        st.stop()


def create_user(
    db: Session,
    username: str,
    password: str,
    role: str,
    organization_id: int = None,
    acting_user_id: int = None
) -> User:
    """
    Create a new user with a hashed password.
    Raises ValueError on validation failure.
    """
    if not username or len(username.strip()) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if role not in ("admin", "hospital", "blood_bank"):
        raise ValueError(f"Invalid role: {role!r}")
    existing = db.query(User).filter(User.username == username.strip()).first()
    if existing:
        raise ValueError(f"Username '{username}' is already taken.")

    user = User(
        username=username.strip(),
        role=role,
        organization_id=organization_id,
        is_active=True
    )
    user.set_password(password)
    db.add(user)
    db.flush()  # get id before commit

    log_action(
        db=db,
        user_id=acting_user_id,
        action="create_user",
        entity_type="user",
        entity_id=user.id,
        details=f"Created user {username!r} with role {role!r}."
    )
    return user


def change_password(db: Session, user_id: int, current_password: str, new_password: str) -> bool:
    """
    Change user password after verifying current password.
    Returns True on success, False on failure.
    """
    user = db.get(User, user_id)
    if not user:
        return False
    if not user.check_password(current_password):
        return False
    if len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters.")
    user.set_password(new_password)
    log_action(
        db=db,
        user_id=user_id,
        action="change_password",
        entity_type="user",
        entity_id=user_id,
        details="Password changed by user."
    )
    return True


def reset_failed_attempts(db: Session, user_id: int, acting_user_id: int = None) -> bool:
    """Admin function to reset failed login attempts and unlock account."""
    user = db.get(User, user_id)
    if not user:
        return False
    user.failed_login_attempts = 0
    user.locked_until = None
    log_action(
        db=db,
        user_id=acting_user_id,
        action="reset_failed_attempts",
        entity_type="user",
        entity_id=user_id,
        details=f"Failed attempts reset by admin {acting_user_id}."
    )
    return True


def register_hospital(
    db: Session,
    name: str,
    city: str,
    state: str,
    address: str = None,
    contact_number: str = None,
    latitude: float = None,
    longitude: float = None,
    username: str = None,
    password: str = None,
):
    """
    Register a new hospital organization along with its initial user account.
    Validates hospital details and credentials, geocodes coordinates if omitted,
    and records an audit log.
    """
    if not name or len(name.strip()) < 2:
        raise ValueError("Hospital name must be at least 2 characters.")
    if not city or len(city.strip()) < 2:
        raise ValueError("City must be specified.")
    if not state or len(state.strip()) < 2:
        raise ValueError("State must be specified.")
    if not username or len(username.strip()) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    existing_user = db.query(User).filter(User.username == username.strip()).first()
    if existing_user:
        raise ValueError(f"Username '{username}' is already taken.")

    # Auto-resolve coordinates from city if not provided
    lat = latitude
    lon = longitude
    if lat is None or lon is None:
        coords = get_city_coordinates(city.strip())
        if coords:
            lat, lon = coords

    org = Organization(
        name=name.strip(),
        type="hospital",
        address=address.strip() if address else None,
        city=city.strip(),
        state=state.strip(),
        contact_number=contact_number.strip() if contact_number else None,
        latitude=lat,
        longitude=lon,
        is_active="true"
    )
    db.add(org)
    db.flush()

    user = User(
        username=username.strip(),
        role="hospital",
        organization_id=org.id,
        is_active=True
    )
    user.set_password(password)
    db.add(user)
    db.flush()

    log_action(
        db=db,
        user_id=user.id,
        action="register_hospital",
        entity_type="organization",
        entity_id=org.id,
        details=f"Registered hospital '{org.name}' with user '{user.username}'."
    )

    # Optional: If Docker PostgreSQL is running, mirror registration to it asynchronously
    try:
        from sync_databases import sync_sqlite_to_postgres
        sync_sqlite_to_postgres()
    except Exception as e:
        logger.debug(f"Optional PostgreSQL mirror sync skipped: {e}")

    return org, user
