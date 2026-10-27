"""
Tests for bank-to-bank transfer requests, atomic stock reservation, and inventory receipt.
"""
import pytest
from datetime import date, timedelta
from services.inventory_service import create_lot, get_lots_for_bank
from services.transfer_service import (
    create_transfer_request,
    approve_transfer_request,
    reject_transfer_request,
    dispatch_transfer_request,
    receive_transfer_request,
)
from models.organization import Organization


@pytest.fixture
def two_banks(db):
    """Create two blood bank organizations for transfer testing."""
    b1 = Organization(
        name="Requesting Bank 1", type="blood_bank",
        city="Bengaluru", state="Karnataka", contact_number="111"
    )
    b2 = Organization(
        name="Supplying Bank 2", type="blood_bank",
        city="Tumakuru", state="Karnataka", contact_number="222"
    )
    db.add_all([b1, b2])
    db.flush()
    return {"requester": b1, "supplier": b2}


class TestTransferWorkflow:
    """Inter-bank transfer lifecycle."""

    def test_create_transfer_request(self, db, two_banks):
        trf = create_transfer_request(
            db=db,
            requesting_org_id=two_banks["requester"].id,
            supplying_org_id=two_banks["supplier"].id,
            blood_group="A+",
            component="packed_red_cells",
            units=4
        )
        assert trf.id is not None
        assert trf.status == "pending"
        assert trf.units == 4

    def test_transfer_to_same_bank_rejected(self, db, two_banks):
        with pytest.raises(ValueError, match="cannot be the same"):
            create_transfer_request(
                db=db,
                requesting_org_id=two_banks["requester"].id,
                supplying_org_id=two_banks["requester"].id,
                blood_group="A+",
                component="packed_red_cells",
                units=2
            )

    def test_approve_transfer_with_sufficient_stock(self, db, two_banks, future_date):
        # Supplier has 10 units of A+
        lot = create_lot(
            db=db,
            blood_bank_id=two_banks["supplier"].id,
            blood_group="A+",
            component="packed_red_cells",
            units_total=10,
            expiry_date=future_date
        )
        db.flush()

        trf = create_transfer_request(
            db=db,
            requesting_org_id=two_banks["requester"].id,
            supplying_org_id=two_banks["supplier"].id,
            blood_group="A+",
            component="packed_red_cells",
            units=4
        )

        approve_transfer_request(
            db=db,
            transfer_id=trf.id,
            user_org_id=two_banks["supplier"].id,
            user_role="blood_bank"
        )
        assert trf.status == "approved"
        # 4 units are reserved in supplier lot
        assert lot.units_reserved == 4
        assert lot.available_units == 6

    def test_approve_transfer_insufficient_stock_fails(self, db, two_banks, future_date):
        # Supplier has only 2 units, but transfer requests 5
        create_lot(
            db=db,
            blood_bank_id=two_banks["supplier"].id,
            blood_group="B+",
            component="packed_red_cells",
            units_total=2,
            expiry_date=future_date
        )
        db.flush()

        trf = create_transfer_request(
            db=db,
            requesting_org_id=two_banks["requester"].id,
            supplying_org_id=two_banks["supplier"].id,
            blood_group="B+",
            component="packed_red_cells",
            units=5
        )

        with pytest.raises(ValueError, match="Insufficient stock to approve transfer"):
            approve_transfer_request(
                db=db,
                transfer_id=trf.id,
                user_org_id=two_banks["supplier"].id,
                user_role="blood_bank"
            )

    def test_end_to_end_transfer_receipt_moves_inventory(self, db, two_banks, future_date):
        # 1. Supplier lot
        supplier_lot = create_lot(
            db=db,
            blood_bank_id=two_banks["supplier"].id,
            blood_group="O-",
            component="packed_red_cells",
            units_total=8,
            expiry_date=future_date
        )
        db.flush()

        # 2. Request transfer of 3 units
        trf = create_transfer_request(
            db=db,
            requesting_org_id=two_banks["requester"].id,
            supplying_org_id=two_banks["supplier"].id,
            blood_group="O-",
            component="packed_red_cells",
            units=3
        )

        # 3. Approve
        approve_transfer_request(
            db=db, transfer_id=trf.id,
            user_org_id=two_banks["supplier"].id, user_role="blood_bank"
        )

        # 4. Dispatch (in_transit)
        dispatch_transfer_request(
            db=db, transfer_id=trf.id,
            user_org_id=two_banks["supplier"].id, user_role="blood_bank"
        )
        assert trf.status == "in_transit"

        # 5. Receive by requester
        receive_transfer_request(
            db=db, transfer_id=trf.id,
            user_org_id=two_banks["requester"].id, user_role="blood_bank"
        )
        assert trf.status == "received"

        # Supplier inventory was permanently deducted (total went from 8 to 5)
        assert supplier_lot.units_total == 5
        assert supplier_lot.units_reserved == 0

        # Requester received a new lot of 3 units
        requester_lots = get_lots_for_bank(
            db=db, blood_bank_id=two_banks["requester"].id, blood_group="O-"
        )
        assert len(requester_lots) == 1
        assert requester_lots[0].units_total == 3
        assert requester_lots[0].available_units == 3

    def test_unauthorized_bank_cannot_approve_transfer(self, db, two_banks, future_date):
        create_lot(
            db=db, blood_bank_id=two_banks["supplier"].id,
            blood_group="A+", units_total=5, expiry_date=future_date
        )
        trf = create_transfer_request(
            db=db, requesting_org_id=two_banks["requester"].id,
            supplying_org_id=two_banks["supplier"].id,
            blood_group="A+", component="whole_blood", units=2
        )
        # Random bank (ID 9999) tries to approve
        with pytest.raises(PermissionError, match="Only the supplying blood bank"):
            approve_transfer_request(
                db=db, transfer_id=trf.id,
                user_org_id=9999, user_role="blood_bank"
            )
