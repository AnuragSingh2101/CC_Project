"""
Tests for inventory creation, update, validation, and stock calculations.
Covers: TC-01 through TC-06
"""
import pytest
from datetime import date, timedelta
from services.inventory_service import (
    create_lot, get_lots_for_bank, update_lot_quantity,
    get_all_lots, get_available_units_by_group, get_low_stock_lots
)
from models.inventory import InventoryLot


class TestInventoryCreation:
    """TC-01: Inventory lot creation."""

    def test_create_valid_lot(self, db, seed_org, future_date):
        lot = create_lot(
            db=db,
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="A+",
            units_total=50,
            expiry_date=future_date,
        )
        db.flush()
        assert lot.id is not None
        assert lot.blood_group == "A+"
        assert lot.units_total == 50
        assert lot.units_reserved == 0

    def test_create_lot_all_blood_groups(self, db, seed_org, future_date):
        groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
        for g in groups:
            lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                             blood_group=g, units_total=10, expiry_date=future_date)
            db.flush()
            assert lot.blood_group == g

    def test_create_lot_invalid_blood_group(self, db, seed_org, future_date):
        with pytest.raises(ValueError, match="Invalid blood group"):
            create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                       blood_group="X+", units_total=10, expiry_date=future_date)

    def test_create_lot_negative_units(self, db, seed_org, future_date):
        with pytest.raises(ValueError, match="non-negative"):
            create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                       blood_group="A+", units_total=-5, expiry_date=future_date)

    def test_create_lot_past_expiry(self, db, seed_org, past_date):
        with pytest.raises(ValueError, match="future"):
            create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                       blood_group="A+", units_total=10, expiry_date=past_date)

    def test_create_lot_wrong_org_type(self, db, seed_org, future_date):
        """Cannot create inventory for a hospital organization."""
        with pytest.raises(ValueError, match="Invalid blood bank"):
            create_lot(db=db, blood_bank_id=seed_org["hospital"].id,
                       blood_group="A+", units_total=10, expiry_date=future_date)


class TestInventoryUpdate:
    """TC-02: Inventory lot updates."""

    def test_update_total_units(self, db, seed_org, future_date):
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="B+", units_total=20, expiry_date=future_date)
        db.flush()
        updated = update_lot_quantity(db=db, lot_id=lot.id, new_total=30)
        assert updated.units_total == 30

    def test_update_refuses_negative(self, db, seed_org, future_date):
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="B+", units_total=20, expiry_date=future_date)
        db.flush()
        with pytest.raises(ValueError, match="negative"):
            update_lot_quantity(db=db, lot_id=lot.id, new_total=-1)

    def test_update_refuses_below_reserved(self, db, seed_org, future_date):
        """Cannot set total below reserved amount."""
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="O+", units_total=20, expiry_date=future_date)
        db.flush()
        lot.units_reserved = 15
        db.flush()
        with pytest.raises(ValueError, match="reserved"):
            update_lot_quantity(db=db, lot_id=lot.id, new_total=10)

    def test_update_cross_org_denied(self, db, seed_org, future_date):
        """Blood bank B cannot update blood bank A's lot."""
        from models.organization import Organization
        other_bank = Organization(
            name="Other Bank", type="blood_bank",
            city="Other", state="State"
        )
        db.add(other_bank)
        db.flush()
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="A-", units_total=10, expiry_date=future_date)
        db.flush()
        with pytest.raises(PermissionError):
            update_lot_quantity(db=db, lot_id=lot.id, new_total=20,
                                requesting_org_id=other_bank.id)


class TestAvailableUnits:
    """TC-03 & TC-04: Available unit calculations."""

    def test_available_units_calculation(self, db, seed_org, future_date):
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="AB+", units_total=40, expiry_date=future_date)
        db.flush()
        lot.units_reserved = 15
        assert lot.available_units == 25

    def test_available_units_zero_when_fully_reserved(self, db, seed_org, future_date):
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="O-", units_total=10, expiry_date=future_date)
        db.flush()
        lot.units_reserved = 10
        assert lot.available_units == 0

    def test_is_expired_false_for_future(self, db, seed_org, future_date):
        lot = create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                         blood_group="A+", units_total=5, expiry_date=future_date)
        db.flush()
        assert not lot.is_expired

    def test_is_expired_true_for_past(self, db, seed_org):
        """TC-05: Expired stock should not count as available."""
        from datetime import timedelta
        past = date.today() - timedelta(days=1)
        lot = InventoryLot(
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="B-", units_total=10, units_reserved=0,
            expiry_date=past
        )
        db.add(lot)
        db.flush()
        assert lot.is_expired
        assert not lot.is_available

    def test_expired_excluded_from_get_lots(self, db, seed_org):
        """TC-05: get_lots_for_bank excludes expired by default."""
        from datetime import timedelta
        past = date.today() - timedelta(days=2)
        future = date.today() + timedelta(days=30)
        expired_lot = InventoryLot(
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="A+", units_total=10, units_reserved=0,
            expiry_date=past
        )
        valid_lot = InventoryLot(
            blood_bank_id=seed_org["blood_bank"].id,
            blood_group="A+", units_total=5, units_reserved=0,
            expiry_date=future
        )
        db.add_all([expired_lot, valid_lot])
        db.flush()
        lots = get_lots_for_bank(db, blood_bank_id=seed_org["blood_bank"].id)
        lot_ids = [l.id for l in lots]
        assert expired_lot.id not in lot_ids
        assert valid_lot.id in lot_ids

    def test_available_units_by_group_aggregation(self, db, seed_org, future_date):
        """TC-06: get_available_units_by_group aggregates correctly."""
        create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                   blood_group="A+", units_total=20, expiry_date=future_date)
        create_lot(db=db, blood_bank_id=seed_org["blood_bank"].id,
                   blood_group="A+", units_total=15, expiry_date=future_date)
        db.flush()
        groups = get_available_units_by_group(db)
        assert groups["A+"] >= 35  # 20 + 15 (may have more from other tests in isolation)
