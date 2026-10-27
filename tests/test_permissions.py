"""
Tests for authentication, authorization, and cross-organization access control.
Covers: TC-12 through TC-15
"""
import pytest
from models.user import User
from models.organization import Organization
from services.auth_service import create_user
from services.inventory_service import create_lot, update_lot_quantity
from services.request_service import create_request, update_request_status


class TestAuthentication:
    """Password hashing and login validation."""

    def test_password_hashed_not_plain(self, db, seed_org):
        user = User(username="hashtest", role="admin", is_active=True)
        user.set_password("MySecurePass123!")
        db.add(user)
        db.flush()
        assert user.password_hash != "MySecurePass123!"
        assert user.password_hash.startswith("$2b$")

    def test_correct_password_verifies(self, db):
        user = User(username="verifytest", role="admin", is_active=True)
        user.set_password("CorrectPass@456!")
        assert user.check_password("CorrectPass@456!") is True

    def test_wrong_password_fails(self, db):
        user = User(username="wrongpass_test", role="admin", is_active=True)
        user.set_password("RealPass@789!")
        assert user.check_password("WrongPass@789!") is False

    def test_short_password_rejected(self, db):
        user = User(username="shortpass_test", role="admin", is_active=True)
        with pytest.raises(ValueError, match="8 characters"):
            user.set_password("abc")

    def test_username_uniqueness_enforced(self, db, seed_org):
        create_user(db=db, username="unique_user_123", password="ValidPass@123!",
                    role="admin")
        db.flush()
        with pytest.raises(ValueError, match="already taken"):
            create_user(db=db, username="unique_user_123", password="AnotherPass@!",
                        role="admin")

    def test_invalid_role_rejected(self, db):
        with pytest.raises(ValueError, match="Invalid role"):
            create_user(db=db, username="badrole_user", password="ValidPass@123!",
                        role="superuser")


class TestCrossOrganizationAccess:
    """TC-12 & TC-13: Cross-organization access restrictions."""

    def test_blood_bank_cannot_modify_other_banks_inventory(self, db, seed_org, future_date):
        other_bank = Organization(
            name="Other Blood Bank", type="blood_bank",
            city="OtherCity", state="OtherState"
        )
        db.add(other_bank)
        db.flush()

        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="A+", units_total=20, expiry_date=future_date)
        db.flush()

        # Other bank tries to update our lot
        with pytest.raises(PermissionError):
            update_lot_quantity(db=db, lot_id=lot.id, new_total=30,
                                requesting_org_id=other_bank.id)

    def test_blood_bank_can_modify_own_inventory(self, db, seed_org, future_date):
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="B+", units_total=20, expiry_date=future_date)
        db.flush()
        updated = update_lot_quantity(
            db=db, lot_id=lot.id, new_total=30,
            requesting_org_id=seed_org["blood_bank"].id
        )
        assert updated.units_total == 30

    def test_hospital_cannot_update_request_status_to_matched(self, db, seed_org):
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="O+", units_requested=5, urgency="urgent")
        db.flush()
        # Hospital user tries to set status to "matched" (not allowed)
        with pytest.raises(PermissionError, match="only cancel"):
            update_request_status(
                db=db, request_id=req.id, new_status="matched",
                requesting_hospital_id=seed_org["hospital"].id
            )

    def test_hospital_can_cancel_own_request(self, db, seed_org):
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="A-", units_requested=2, urgency="routine")
        db.flush()
        updated = update_request_status(
            db=db, request_id=req.id, new_status="cancelled",
            requesting_hospital_id=seed_org["hospital"].id
        )
        assert updated.status == "cancelled"

    def test_hospital_cannot_cancel_other_hospital_request(self, db, seed_org):
        other_hosp = Organization(
            name="Other Hospital", type="hospital",
            city="City", state="State"
        )
        db.add(other_hosp)
        db.flush()

        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="B-", units_requested=1, urgency="routine")
        db.flush()

        with pytest.raises(PermissionError, match="own requests"):
            update_request_status(db=db, request_id=req.id, new_status="cancelled",
                                  requesting_hospital_id=other_hosp.id)


class TestDatabasePersistence:
    """TC-15: Database persistence across restarts (simulated by separate sessions)."""

    def test_data_survives_session_close(self, engine):
        """Create data in one session, read in another."""
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)

        # Session 1: create data
        s1 = Session()
        try:
            org = Organization(
                name="Persistence Test Bank", type="blood_bank",
                city="PersistCity", state="PersistState"
            )
            s1.add(org)
            s1.commit()
            org_id = org.id
        finally:
            s1.close()

        # Session 2: read data
        s2 = Session()
        try:
            found = s2.get(Organization, org_id)
            assert found is not None
            assert found.name == "Persistence Test Bank"
        finally:
            # Cleanup
            s2.delete(found)
            s2.commit()
            s2.close()
