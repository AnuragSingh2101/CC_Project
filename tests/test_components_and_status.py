"""
Tests for blood components, shelf lives, and lot status workflow.
"""
import pytest
from datetime import date, timedelta
from services.inventory_service import (
    create_lot,
    update_lot_status,
    get_lots_for_bank,
    get_low_stock_lots,
    get_near_expiry_lots,
    get_available_units_by_group,
)
from services.reservation_service import make_reservation
from services.request_service import create_request
from config.settings import COMPONENT_SHELF_LIFE


class TestComponentAndShelfLife:
    """Testing components and automatic shelf-life computation."""

    def test_shelf_life_whole_blood(self, db, seed_org):
        """Whole blood shelf life is 35 days."""
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="A+",
            units_total=10,
            component="whole_blood"
        )
        db.flush()
        expected = date.today() + timedelta(days=35)
        assert lot.expiry_date == expected
        assert lot.component == "whole_blood"

    def test_shelf_life_packed_red_cells(self, db, seed_org):
        """Packed red blood cells shelf life is 42 days."""
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="O+",
            units_total=15,
            component="packed_red_cells"
        )
        db.flush()
        expected = date.today() + timedelta(days=42)
        assert lot.expiry_date == expected

    def test_shelf_life_platelets(self, db, seed_org):
        """Platelets shelf life is 5 days."""
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="B+",
            units_total=5,
            component="platelets"
        )
        db.flush()
        expected = date.today() + timedelta(days=5)
        assert lot.expiry_date == expected

    def test_shelf_life_plasma(self, db, seed_org):
        """Plasma shelf life is 365 days."""
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="AB+",
            units_total=20,
            component="plasma"
        )
        db.flush()
        expected = date.today() + timedelta(days=365)
        assert lot.expiry_date == expected

    def test_invalid_component_rejected(self, db, seed_org):
        with pytest.raises(ValueError, match="Invalid component"):
            create_lot(
                db=db,
                blood_bank_id=seed_org["blood_bank"].id,
                blood_group="A+",
                units_total=10,
                component="synthetic_blood"
            )


class TestLotStatusWorkflow:
    """Testing lot status transitions: quarantine -> tested -> available; any -> discarded."""

    def test_valid_workflow_transition_path(self, db, seed_org):
        """quarantine -> tested -> available -> discarded"""
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="O+",
            units_total=20,
            status="quarantine"
        )
        db.flush()
        assert lot.status == "quarantine"
        assert lot.available_units == 0  # not available for reservation!

        # quarantine -> tested
        update_lot_status(db=db, lot_id=lot.id, new_status="tested", requesting_org_id=seed_org["blood_bank"].id)
        assert lot.status == "tested"
        assert lot.available_units == 0

        # tested -> available
        update_lot_status(db=db, lot_id=lot.id, new_status="available", requesting_org_id=seed_org["blood_bank"].id)
        assert lot.status == "available"
        assert lot.available_units == 20  # Now available!

        # available -> discarded
        update_lot_status(db=db, lot_id=lot.id, new_status="discarded", requesting_org_id=seed_org["blood_bank"].id)
        assert lot.status == "discarded"
        assert lot.available_units == 0

    def test_invalid_transition_quarantine_to_available_rejected(self, db, seed_org):
        """Cannot bypass testing: quarantine -> available is prohibited."""
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="A+",
            units_total=10,
            status="quarantine"
        )
        db.flush()
        with pytest.raises(ValueError, match="Invalid status transition"):
            update_lot_status(db=db, lot_id=lot.id, new_status="available", requesting_org_id=seed_org["blood_bank"].id)

    def test_discarded_terminal_state(self, db, seed_org):
        """Discarded lots cannot be revived."""
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="A+",
            units_total=10,
            status="available"
        )
        update_lot_status(db=db, lot_id=lot.id, new_status="discarded", requesting_org_id=seed_org["blood_bank"].id)
        with pytest.raises(ValueError, match="Invalid status transition"):
            update_lot_status(db=db, lot_id=lot.id, new_status="available", requesting_org_id=seed_org["blood_bank"].id)

    def test_cannot_reserve_non_available_lot(self, db, seed_org):
        """Only 'available' lots can be reserved."""
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="O+",
            units_total=10,
            status="quarantine"
        )
        req = create_request(
            db=db,
            hospital_id=seed_org["hospital"].id,
            blood_group="O+",
            units_requested=2,
            urgency="urgent"
        )
        db.flush()
        with pytest.raises(ValueError, match="Only 'available' lots can be reserved"):
            make_reservation(db=db, request_id=req.id, inventory_lot_id=lot.id, units_to_reserve=2)

    def test_cross_org_status_change_denied(self, db, seed_org):
        """Another blood bank cannot change status of lots it does not own."""
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="A+",
            units_total=10,
            status="quarantine"
        )
        db.flush()
        with pytest.raises(PermissionError, match="own blood bank"):
            update_lot_status(db=db, lot_id=lot.id, new_status="tested", requesting_org_id=9999)
