"""
Tests for reservation creation, release, concurrency safety, and stock integrity.
Covers: TC-09 through TC-12, TC-16
"""
import pytest
from datetime import date, timedelta
from services.inventory_service import create_lot
from services.request_service import create_request
from services.reservation_service import (
    make_reservation, release_reservation, fulfill_reservation,
    get_reservations_for_request, release_reservations_for_request
)
from models.inventory import InventoryLot
from models.reservation import Reservation


@pytest.fixture
def lot_and_request(db, seed_org, future_date):
    """Create a standard lot and request for reservation tests."""
    lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                     blood_group="A+", units_total=100, expiry_date=future_date)
    req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                         blood_group="A+", units_requested=20, urgency="urgent")
    db.flush()
    return {"lot": lot, "request": req}


class TestReservationCreation:
    """TC-09: Successful reservation."""

    def test_make_valid_reservation(self, db, lot_and_request):
        lot = lot_and_request["lot"]
        req = lot_and_request["request"]
        initial_reserved = lot.units_reserved

        res = make_reservation(db=db, request_id=req.id,
                               inventory_lot_id=lot.id, units_to_reserve=10)
        db.flush()
        assert res.id is not None
        assert res.status == "active"
        assert res.units_reserved == 10
        assert lot.units_reserved == initial_reserved + 10

    def test_reservation_updates_request_status(self, db, lot_and_request):
        """Reservation should set request status to 'matched'."""
        req = lot_and_request["request"]
        lot = lot_and_request["lot"]
        assert req.status == "pending"
        make_reservation(db=db, request_id=req.id,
                         inventory_lot_id=lot.id, units_to_reserve=5)
        db.flush()
        assert req.status == "matched"

    def test_reservation_insufficient_stock(self, db, seed_org, future_date):
        """TC-08: Insufficient stock rejection."""
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="B-", units_total=5, expiry_date=future_date)
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="B-", units_requested=10, urgency="urgent")
        db.flush()
        with pytest.raises(ValueError, match="Insufficient stock"):
            make_reservation(db=db, request_id=req.id,
                             inventory_lot_id=lot.id, units_to_reserve=10)

    def test_reservation_expired_lot_rejected(self, db, seed_org):
        """Cannot reserve from an expired lot."""
        past = date.today() - timedelta(days=1)
        lot = InventoryLot(
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="AB+", units_total=50, units_reserved=0,
            expiry_date=past
        )
        db.add(lot)
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="AB+", units_requested=5, urgency="routine")
        db.flush()
        with pytest.raises(ValueError, match="expired"):
            make_reservation(db=db, request_id=req.id,
                             inventory_lot_id=lot.id, units_to_reserve=5)

    def test_reservation_zero_units_rejected(self, db, lot_and_request):
        with pytest.raises(ValueError, match="positive"):
            make_reservation(db=db, request_id=lot_and_request["request"].id,
                             inventory_lot_id=lot_and_request["lot"].id,
                             units_to_reserve=0)

    def test_duplicate_reservation_rejected(self, db, lot_and_request):
        """Prevent duplicate active reservation on same lot+request."""
        lot = lot_and_request["lot"]
        req = lot_and_request["request"]
        make_reservation(db=db, request_id=req.id,
                         inventory_lot_id=lot.id, units_to_reserve=5)
        db.flush()
        with pytest.raises(ValueError, match="already exists"):
            make_reservation(db=db, request_id=req.id,
                             inventory_lot_id=lot.id, units_to_reserve=3)


class TestReservationCancellation:
    """TC-10 & TC-11: Reservation release and duplicate release prevention."""

    def test_release_restores_stock(self, db, lot_and_request):
        lot = lot_and_request["lot"]
        req = lot_and_request["request"]
        res = make_reservation(db=db, request_id=req.id,
                               inventory_lot_id=lot.id, units_to_reserve=15)
        db.flush()
        reserved_after = lot.units_reserved
        assert reserved_after == 15

        release_reservation(db=db, reservation_id=res.id)
        db.flush()
        assert lot.units_reserved == 0
        assert res.status == "released"

    def test_double_release_prevented(self, db, lot_and_request):
        """TC-11: Duplicate cancellation must fail."""
        lot = lot_and_request["lot"]
        req = lot_and_request["request"]
        res = make_reservation(db=db, request_id=req.id,
                               inventory_lot_id=lot.id, units_to_reserve=5)
        db.flush()
        release_reservation(db=db, reservation_id=res.id)
        db.flush()
        with pytest.raises(ValueError, match="already.*released"):
            release_reservation(db=db, reservation_id=res.id)

    def test_release_all_reservations_for_request(self, db, seed_org, future_date):
        """Cancelling a request releases all its active reservations."""
        from services.request_service import cancel_request
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="O+", units_total=50, expiry_date=future_date)
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="O+", units_requested=10, urgency="urgent")
        db.flush()
        make_reservation(db=db, request_id=req.id,
                         inventory_lot_id=lot.id, units_to_reserve=10)
        db.flush()
        assert lot.units_reserved == 10

        cancel_request(db=db, request_id=req.id)
        db.flush()
        assert lot.units_reserved == 0
        assert req.status == "cancelled"


class TestReservationFulfillment:
    """Fulfillment workflow."""

    def test_fulfill_reservation(self, db, lot_and_request):
        lot = lot_and_request["lot"]
        req = lot_and_request["request"]
        res = make_reservation(db=db, request_id=req.id,
                               inventory_lot_id=lot.id, units_to_reserve=10)
        db.flush()
        fulfilled_res = fulfill_reservation(db=db, reservation_id=res.id)
        db.flush()
        assert fulfilled_res.status == "fulfilled"

    def test_cannot_fulfill_already_released(self, db, lot_and_request):
        lot = lot_and_request["lot"]
        req = lot_and_request["request"]
        res = make_reservation(db=db, request_id=req.id,
                               inventory_lot_id=lot.id, units_to_reserve=5)
        db.flush()
        release_reservation(db=db, reservation_id=res.id)
        db.flush()
        with pytest.raises(ValueError, match="active"):
            fulfill_reservation(db=db, reservation_id=res.id)


class TestConcurrencyAndOversell:
    """TC-16: Competing reservations cannot oversell stock."""

    def test_no_oversell_sequential(self, db, seed_org, future_date):
        """Sequential reservations cannot exceed total units."""
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="AB-", units_total=10, expiry_date=future_date)
        req1 = create_request(db=db, hospital_id=seed_org["hospital"].id,
                               blood_group="AB-", units_requested=7, urgency="urgent")
        req2 = create_request(db=db, hospital_id=seed_org["hospital"].id,
                               blood_group="AB-", units_requested=7, urgency="urgent")
        db.flush()

        # First reservation succeeds
        make_reservation(db=db, request_id=req1.id,
                         inventory_lot_id=lot.id, units_to_reserve=7)
        db.flush()
        assert lot.units_reserved == 7
        assert lot.available_units == 3

        # Second reservation exceeds remaining stock
        with pytest.raises(ValueError, match="Insufficient stock"):
            make_reservation(db=db, request_id=req2.id,
                             inventory_lot_id=lot.id, units_to_reserve=7)

        # Stock must not be negative
        assert lot.units_reserved <= lot.units_total
        assert lot.available_units >= 0

    def test_stock_never_negative_after_failed_reservation(self, db, seed_org, future_date):
        """Inventory must not go negative even after a failed reservation attempt."""
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="B+", units_total=5, expiry_date=future_date)
        req = create_request(db=db, hospital_id=seed_org["hospital"].id,
                             blood_group="B+", units_requested=10, urgency="critical")
        db.flush()
        with pytest.raises(ValueError, match="Insufficient"):
            make_reservation(db=db, request_id=req.id,
                             inventory_lot_id=lot.id, units_to_reserve=10)
        # Verify units_reserved unchanged
        assert lot.units_reserved == 0
        assert lot.available_units == 5

    def test_fulfilled_request_cannot_be_reserved(self, db, lot_and_request):
        """Cannot make reservation for a fulfilled request."""
        lot = lot_and_request["lot"]
        req = lot_and_request["request"]
        req.status = "fulfilled"
        db.flush()
        with pytest.raises(ValueError, match="fulfilled"):
            make_reservation(db=db, request_id=req.id,
                             inventory_lot_id=lot.id, units_to_reserve=5)

    def test_cancelled_request_cannot_be_reserved(self, db, lot_and_request):
        """Cannot make reservation for a cancelled request."""
        lot = lot_and_request["lot"]
        req = lot_and_request["request"]
        req.status = "cancelled"
        db.flush()
        with pytest.raises(ValueError, match="cancelled"):
            make_reservation(db=db, request_id=req.id,
                             inventory_lot_id=lot.id, units_to_reserve=5)
