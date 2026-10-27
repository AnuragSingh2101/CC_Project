"""
Shared test fixtures for pytest.
Uses an in-memory SQLite database, never touches the production database.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base


TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """Create a shared in-memory test engine."""
    from sqlalchemy import event as sa_event
    eng = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    @sa_event.listens_for(eng, "connect")
    def set_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Import all models
    import database.schema  # noqa
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture(scope="function")
def db(engine):
    """Provide a transactional database session, rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def seed_org(db):
    """Create a blood bank and hospital organization for testing."""
    from models.organization import Organization
    bb = Organization(
        name="Test Blood Bank", type="blood_bank",
        city="TestCity", state="TestState",
        contact_number="000-0000"
    )
    hosp = Organization(
        name="Test Hospital", type="hospital",
        city="TestCity", state="TestState",
        contact_number="000-0001"
    )
    db.add_all([bb, hosp])
    db.flush()
    return {"blood_bank": bb, "hospital": hosp}


@pytest.fixture(scope="function")
def seed_users(db, seed_org):
    """Create test users for each role."""
    from models.user import User
    admin = User(username="test_admin", role="admin", is_active=True)
    admin.set_password("Admin@Test123!")

    bb_user = User(
        username="test_bb_user", role="blood_bank",
        organization_id=seed_org["blood_bank"].id, is_active=True
    )
    bb_user.set_password("BBUser@Test123!")

    hosp_user = User(
        username="test_hosp_user", role="hospital",
        organization_id=seed_org["hospital"].id, is_active=True
    )
    hosp_user.set_password("HospUser@Test123!")

    db.add_all([admin, bb_user, hosp_user])
    db.flush()
    return {"admin": admin, "bb_user": bb_user, "hosp_user": hosp_user}


@pytest.fixture(scope="function")
def future_date():
    return date.today() + timedelta(days=30)


@pytest.fixture(scope="function")
def past_date():
    return date.today() - timedelta(days=1)
