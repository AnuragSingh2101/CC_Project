"""
API tests using FastAPI TestClient.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta, timezone, date

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.main import app, get_db, create_access_token
from database.connection import Base
from models.user import User
from models.organization import Organization
from models.inventory import InventoryLot
from models.emergency_request import EmergencyRequest
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS, URGENCY_LEVELS


# Test database
TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    @event.listens_for(eng, "connect")
    def set_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    import database.schema  # noqa
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture(scope="function")
def db_session(engine):
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
def client(db_session):
    """Create a TestClient with overridden database dependency."""
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seed_org(db_session):
    bb = Organization(name="Test Blood Bank", type="blood_bank", city="TestCity", state="TestState", contact_number="000-0000")
    hosp = Organization(name="Test Hospital", type="hospital", city="TestCity", state="TestState", contact_number="000-0001")
    db_session.add_all([bb, hosp])
    db_session.flush()
    return {"blood_bank": bb, "hospital": hosp}


@pytest.fixture(scope="function")
def seed_users(db_session, seed_org):
    admin = User(username="test_admin", role="admin", is_active=True)
    admin.set_password("Admin@Test123!")

    bb_user = User(username="test_bb_user", role="blood_bank", organization_id=seed_org["blood_bank"].id, is_active=True)
    bb_user.set_password("BBUser@Test123!")

    hosp_user = User(username="test_hosp_user", role="hospital", organization_id=seed_org["hospital"].id, is_active=True)
    hosp_user.set_password("HospUser@Test123!")

    db_session.add_all([admin, bb_user, hosp_user])
    db_session.flush()
    return {"admin": admin, "bb_user": bb_user, "hosp_user": hosp_user}


@pytest.fixture
def admin_token(seed_users):
    return create_access_token({"user_id": seed_users["admin"].id, "username": "test_admin", "role": "admin", "organization_id": None})


@pytest.fixture
def bb_token(seed_users, seed_org):
    return create_access_token({"user_id": seed_users["bb_user"].id, "username": "test_bb_user", "role": "blood_bank", "organization_id": seed_org["blood_bank"].id})


@pytest.fixture
def hosp_token(seed_users, seed_org):
    return create_access_token({"user_id": seed_users["hosp_user"].id, "username": "test_hosp_user", "role": "hospital", "organization_id": seed_org["hospital"].id})


class TestAuth:
    def test_login_success(self, client, seed_users):
        response = client.post("/auth/login", data={"username": "test_admin", "password": "Admin@Test123!"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_failure(self, client):
        response = client.post("/auth/login", data={"username": "test_admin", "password": "wrong"})
        assert response.status_code == 401

    def test_get_me(self, client, admin_token):
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "test_admin"
        assert data["role"] == "admin"


class TestOrganizations:
    def test_list_blood_banks(self, client, admin_token):
        response = client.get("/organizations/blood-banks", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_organization_admin(self, client, admin_token):
        response = client.post(
            "/organizations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "New Bank", "type": "blood_bank", "city": "City", "state": "State"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Bank"


class TestInventory:
    def test_create_lot_blood_bank(self, client, bb_token, seed_org):
        response = client.post(
            "/inventory",
            headers={"Authorization": f"Bearer {bb_token}"},
            json={
                "blood_bank_id": seed_org["blood_bank"].id,
                "blood_group": "A+",
                "component": "packed_red_cells",
                "units_total": 10,
                "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
                "status": "available"
            }
        )
        assert response.status_code == 200
        assert response.json()["blood_group"] == "A+"

    def test_create_lot_forbidden_hospital(self, client, hosp_token, seed_org):
        response = client.post(
            "/inventory",
            headers={"Authorization": f"Bearer {hosp_token}"},
            json={
                "blood_bank_id": seed_org["blood_bank"].id,
                "blood_group": "A+",
                "component": "packed_red_cells",
                "units_total": 10,
                "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
            }
        )
        assert response.status_code == 403

    def test_list_inventory_blood_bank(self, client, bb_token, seed_org, db_session):
        # Create a lot first
        lot = InventoryLot(
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="O+", component="packed_red_cells",
            units_total=5, units_reserved=0,
            collection_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
            status="available"
        )
        db_session.add(lot)
        db_session.flush()

        response = client.get("/inventory", headers={"Authorization": f"Bearer {bb_token}"})
        assert response.status_code == 200
        assert len(response.json()) >= 1


class TestSearch:
    def test_search_inventory(self, client, bb_token, seed_org, db_session):
        # Create matching lot
        lot = InventoryLot(
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="O+", component="packed_red_cells",
            units_total=10, units_reserved=0,
            collection_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
            status="available"
        )
        db_session.add(lot)
        db_session.flush()

        response = client.post(
            "/search",
            headers={"Authorization": f"Bearer {bb_token}"},
            json={"blood_group": "O+", "component": "packed_red_cells", "units_needed": 5}
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) >= 1
        assert results[0]["blood_group"] == "O+"


class TestRequests:
    def test_create_request_hospital(self, client, hosp_token, seed_org):
        response = client.post(
            "/requests",
            headers={"Authorization": f"Bearer {hosp_token}"},
            json={
                "hospital_id": seed_org["hospital"].id,
                "blood_group": "A+",
                "component": "packed_red_cells",
                "units_requested": 3,
                "urgency": "urgent"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reference"].startswith("BBR-")
        assert data["status"] == "pending"

    def test_create_request_forbidden_wrong_hospital(self, client, hosp_token, seed_org, db_session):
        # Create another hospital
        other = Organization(name="Other Hosp", type="hospital", city="C", state="S")
        db_session.add(other)
        db_session.flush()
        response = client.post(
            "/requests",
            headers={"Authorization": f"Bearer {hosp_token}"},
            json={
                "hospital_id": other.id,  # Not their own
                "blood_group": "A+",
                "component": "packed_red_cells",
                "units_requested": 3,
                "urgency": "urgent"
            }
        )
        assert response.status_code == 403

    def test_list_requests_hospital(self, client, hosp_token, seed_org, db_session):
        req = EmergencyRequest(
            reference="BBR-TEST-1", hospital_id=seed_org["hospital"].id,
            blood_group="O+", component="whole_blood", units_requested=1, urgency="routine", status="pending"
        )
        db_session.add(req)
        db_session.flush()

        response = client.get("/requests", headers={"Authorization": f"Bearer {hosp_token}"})
        assert response.status_code == 200
        assert len(response.json()) >= 1


class TestReservations:
    def test_reserve_units(self, client, hosp_token, seed_org, db_session):
        # Create request
        req = EmergencyRequest(
            reference="BBR-TEST-2", hospital_id=seed_org["hospital"].id,
            blood_group="O+", component="packed_red_cells", units_requested=2, urgency="urgent", status="pending"
        )
        # Create lot
        lot = InventoryLot(
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="O+", component="packed_red_cells",
            units_total=5, units_reserved=0,
            collection_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
            status="available"
        )
        db_session.add_all([req, lot])
        db_session.flush()

        response = client.post(
            f"/requests/{req.id}/reserve",
            headers={"Authorization": f"Bearer {hosp_token}"},
            json={"request_id": req.id, "inventory_lot_id": lot.id, "units_reserved": 2}
        )
        assert response.status_code == 200
        assert response.json()["units_reserved"] == 2


class TestTransfers:
    def test_create_transfer(self, client, bb_token, seed_org, db_session):
        # Need two blood banks
        bb2 = Organization(name="BB2", type="blood_bank", city="C", state="S")
        db_session.add(bb2)
        db_session.flush()

        response = client.post(
            "/transfers",
            headers={"Authorization": f"Bearer {bb_token}"},
            json={
                "requesting_org_id": seed_org["blood_bank"].id,
                "supplying_org_id": bb2.id,
                "blood_group": "O+",
                "component": "packed_red_cells",
                "units": 2
            }
        )
        assert response.status_code == 200
        assert response.json()["reference"].startswith("TRF-")


class TestNotifications:
    def test_unread_count(self, client, admin_token):
        response = client.get("/notifications/unread-count", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        assert "unread_count" in response.json()


class TestEscalation:
    def test_escalate_overdue(self, client, admin_token, seed_org, seed_users, db_session):
        # Create an old critical request
        old_date = datetime.now(timezone.utc) - timedelta(minutes=20)  # Past 15-min SLA
        req = EmergencyRequest(
            reference="BBR-ESCALATE-1", hospital_id=seed_org["hospital"].id,
            blood_group="O+", component="packed_red_cells", units_requested=1, urgency="critical", status="pending",
            created_at=old_date
        )
        db_session.add(req)
        db_session.flush()

        response = client.post(
            "/requests/escalate",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert response.json()["escalated_count"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])