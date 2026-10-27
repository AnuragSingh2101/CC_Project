"""
Tests for emergency request creation, status transitions, search, and cancellation.
Covers: TC-07 through TC-10, TC-14
"""
import pytest
from datetime import date, timedelta, datetime, timezone
from services.request_service import (
    create_request, get_requests_for_hospital, get_all_requests,
    update_request_status, cancel_request
)
from models.emergency_request import EmergencyRequest


class TestRequestCreation:
    """TC-07: Emergency request creation."""

    def test_create_valid_request(self, db, seed_org):
        req = create_request(
            db=db,
            hospital_id=seed_org["hospital"].id,
            blood_group="A+",
            units_requested=5,
            urgency="urgent"
        )
        db.flush()
        assert req.id is not None
        assert req.reference.startswith("BBR-")
        assert req.status == "pending"
        assert req.blood_group == "A+"
        assert req.units_requested == 5

    def test_create_request_all_urgency_levels(self, db, seed_org):
        for urgency in ["routine", "urgent", "critical"]:
            req = create_request(
                db=db, hospital_id=seed_org["hospital"].id,
                blood_group="O+", units_requested=1, urgency=urgency
            )
            db.flush()
            assert req.urgency == urgency

    def test_create_request_invalid_blood_group(self, db, seed_org):
        with pytest.raises(ValueError, match="Invalid blood group"):
            create_request(db=db, hospital_id=seed_org["hospital"].id,
                           blood_group="XY", units_requested=1, urgency="routine")

    def test_create_request_zero_units(self, db, seed_org):
        with pytest.raises(ValueError, match="positive"):
            create_request(db=db, hospital_id=seed_org["hospital"].id,
                           blood_group="A+", units_requested=0, urgency="routine")

    def test_create_request_negative_units(self, db, seed_org):
        with pytest.raises(ValueError, match="positive"):
            create_request(db=db, hospital_id=seed_org["hospital"].id,
                           blood_group="A+", units_requested=-3, urgency="routine")

    def test_create_request_for_blood_bank_org_fails(self, db, seed_org):
        """Cannot create a request with a blood bank as the hospital."""
        with pytest.raises(ValueError, match="Invalid hospital"):
            create_request(db=db, hospital_id=seed_org["blood_bank"].id,
                           blood_group="A+", units_requested=1, urgency="routine")

    def test_unique_references(self, db, seed_org):
        """Each request must have a unique reference."""
        refs = set()
        for _ in range(10):
            req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                                 blood_group="B+", units_requested=1, urgency="routine")
            db.flush()
            assert req.reference not in refs
            refs.add(req.reference)


class TestRequestSearch:
    """TC-08: Search by blood group and filters."""

    def test_search_by_hospital(self, db, seed_org):
        create_request(db=db, hospital_id=seed_org["hospital"].id,
                       blood_group="AB+", units_requested=2, urgency="urgent")
        db.flush()
        requests = get_requests_for_hospital(db, hospital_id=seed_org["hospital"].id)
        assert any(r.blood_group == "AB+" for r in requests)

    def test_filter_by_status(self, db, seed_org):
        create_request(db=db, hospital_id=seed_org["hospital"].id,
                       blood_group="O-", units_requested=1, urgency="routine")
        db.flush()
        pending = get_requests_for_hospital(db, hospital_id=seed_org["hospital"].id,
                                            status="pending")
        assert all(r.status == "pending" for r in pending)

    def test_filter_by_urgency(self, db, seed_org):
        create_request(db=db, hospital_id=seed_org["hospital"].id,
                       blood_group="B-", units_requested=1, urgency="critical")
        db.flush()
        critical = get_requests_for_hospital(db, hospital_id=seed_org["hospital"].id,
                                             urgency="critical")
        assert all(r.urgency == "critical" for r in critical)

    def test_get_all_requests_admin(self, db, seed_org):
        create_request(db=db, hospital_id=seed_org["hospital"].id,
                       blood_group="A-", units_requested=3, urgency="urgent")
        db.flush()
        all_reqs = get_all_requests(db)
        assert len(all_reqs) >= 1


class TestStatusTransitions:
    """TC-14: Invalid status transition rejection."""

    def test_valid_transition_pending_to_cancelled(self, db, seed_org):
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="O+", units_requested=1, urgency="routine")
        db.flush()
        updated = update_request_status(db=db, request_id=req.id, new_status="cancelled")
        assert updated.status == "cancelled"

    def test_valid_transition_pending_to_matched(self, db, seed_org):
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="O+", units_requested=1, urgency="routine")
        db.flush()
        updated = update_request_status(db=db, request_id=req.id, new_status="matched")
        assert updated.status == "matched"

    def test_invalid_transition_fulfilled_to_any(self, db, seed_org):
        """Cannot transition from a terminal 'fulfilled' state."""
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="A+", units_requested=1, urgency="routine")
        db.flush()
        req.status = "fulfilled"
        db.flush()
        with pytest.raises(ValueError, match="Cannot transition"):
            update_request_status(db=db, request_id=req.id, new_status="pending")

    def test_invalid_transition_cancelled_to_any(self, db, seed_org):
        """Cannot transition from a terminal 'cancelled' state."""
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="A+", units_requested=1, urgency="routine")
        db.flush()
        req.status = "cancelled"
        db.flush()
        with pytest.raises(ValueError, match="Cannot transition"):
            update_request_status(db=db, request_id=req.id, new_status="pending")

    def test_hospital_can_only_cancel_own_request(self, db, seed_org):
        """TC: Hospital cannot modify another hospital's request."""
        from models.organization import Organization
        other_hosp = Organization(
            name="Other Hospital", type="hospital",
            city="City", state="State"
        )
        db.add(other_hosp)
        db.flush()
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="A+", units_requested=1, urgency="routine")
        db.flush()
        with pytest.raises(PermissionError, match="own requests"):
            update_request_status(db=db, request_id=req.id, new_status="cancelled",
                                  requesting_hospital_id=other_hosp.id)

    def test_hospital_cannot_change_status_to_non_cancel(self, db, seed_org):
        """Hospital can only cancel, not change to matched/fulfilled."""
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="A+", units_requested=1, urgency="routine")
        db.flush()
        with pytest.raises(PermissionError, match="only cancel"):
            update_request_status(db=db, request_id=req.id, new_status="matched",
                                  requesting_hospital_id=seed_org["hospital"].id)
