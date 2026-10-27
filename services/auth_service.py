"""
Authentication service — login, session management, and role enforcement.
Never stores plain-text passwords.
"""
import streamlit as st
from sqlalchemy.orm import Session
from models.user import User
from models.organization import Organization
from services.audit_service import log_action
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
    """
    if not username or not password:
        return None
    user = db.query(User).filter(
        User.username == username.strip(),
        User.is_active == True  # noqa
    ).first()
    if user and user.check_password(password):
        return user
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
