"""
Inventory service — CRUD operations for inventory lots.
All quantity mutations use database transactions with constraints.
"""
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from models.inventory import InventoryLot
from models.organization import Organization
from services.audit_service import log_action
from config.settings import (
    BLOOD_GROUPS, BLOOD_COMPONENTS, COMPONENT_SHELF_LIFE,
    LOT_STATUSES, LOW_STOCK_THRESHOLD, NEAR_EXPIRY_DAYS
)
import logging

logger = logging.getLogger(__name__)

# Allowed lot workflow status transitions
LOT_ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "quarantine": ["tested", "discarded"],
    "tested": ["available", "discarded"],
    "available": ["discarded"],
    "discarded": [],
}


def create_lot(
    db: Session,
    blood_bank_id: int,
    blood_group: str,
    units_total: int,
    expiry_date: Optional[date] = None,
    user_id: int = None,
    component: str = "whole_blood",
    collection_date: Optional[date] = None,
    status: str = "available"
) -> InventoryLot:
    """
    Add a new inventory lot for a blood bank.
    Computes expiry_date from collection_date + shelf_life if not explicitly provided.
    Raises ValueError on validation failure.
    """
    if blood_group not in BLOOD_GROUPS:
        raise ValueError(f"Invalid blood group: {blood_group!r}")
    if component not in BLOOD_COMPONENTS:
        raise ValueError(f"Invalid component: {component!r}")
    if status not in LOT_STATUSES:
        raise ValueError(f"Invalid lot status: {status!r}")
    if units_total < 0:
        raise ValueError("units_total must be non-negative.")

    coll_date = collection_date or date.today()
    if expiry_date is None:
        shelf_days = COMPONENT_SHELF_LIFE.get(component, 35)
        computed_expiry = coll_date + timedelta(days=shelf_days)
    else:
        computed_expiry = expiry_date

    if computed_expiry <= date.today():
        raise ValueError("expiry_date must be in the future.")

    # Verify the org is a blood bank
    org = db.get(Organization, blood_bank_id)
    if not org or org.type != "blood_bank":
        raise ValueError("Invalid blood bank ID.")

    lot = InventoryLot(
        blood_bank_id=blood_bank_id,
        blood_group=blood_group,
        component=component,
        units_total=units_total,
        units_reserved=0,
        collection_date=coll_date,
        expiry_date=computed_expiry,
        status=status,
    )
    db.add(lot)
    db.flush()

    log_action(
        db=db,
        user_id=user_id,
        action="create_inventory_lot",
        entity_type="inventory_lot",
        entity_id=lot.id,
        details=(
            f"Blood group={blood_group}, component={component}, units={units_total}, "
            f"status={status}, expiry={computed_expiry}"
        )
    )
    return lot


def update_lot_status(
    db: Session,
    lot_id: int,
    new_status: str,
    user_id: Optional[int] = None,
    requesting_org_id: Optional[int] = None,
    user_role: Optional[str] = None
) -> InventoryLot:
    """
    Update lot status following workflow:
    quarantine -> tested -> available; any -> discarded.
    Only owning blood bank staff or admins can update status.
    """
    lot = db.get(InventoryLot, lot_id)
    if not lot:
        raise ValueError(f"Inventory lot {lot_id} not found.")

    if user_role and user_role not in ("admin", "blood_bank"):
        raise PermissionError("Only blood bank staff and administrators can change lot status.")

    if requesting_org_id is not None and lot.blood_bank_id != requesting_org_id:
        raise PermissionError("You can only modify status for your own blood bank's inventory.")

    if new_status not in LOT_STATUSES:
        raise ValueError(f"Invalid status: {new_status!r}")

    allowed = LOT_ALLOWED_TRANSITIONS.get(lot.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Invalid status transition from '{lot.status}' to '{new_status}'. "
            f"Allowed next states: {allowed}"
        )

    old_status = lot.status
    lot.status = new_status
    lot.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="update_lot_status",
        entity_type="inventory_lot",
        entity_id=lot.id,
        details=f"Status transitioned from '{old_status}' to '{new_status}'"
    )
    return lot


def get_lots_for_bank(
    db: Session,
    blood_bank_id: int,
    include_expired: bool = False,
    blood_group: Optional[str] = None,
    component: Optional[str] = None,
    status: Optional[str] = None
) -> List[InventoryLot]:
    """Get inventory lots for a specific blood bank."""
    q = db.query(InventoryLot).filter(InventoryLot.blood_bank_id == blood_bank_id)
    if not include_expired:
        q = q.filter(InventoryLot.expiry_date >= date.today())
    if blood_group:
        q = q.filter(InventoryLot.blood_group == blood_group)
    if component:
        q = q.filter(InventoryLot.component == component)
    if status:
        q = q.filter(InventoryLot.status == status)
    return q.order_by(InventoryLot.expiry_date).all()


def get_all_lots(
    db: Session,
    include_expired: bool = False,
    blood_group: Optional[str] = None,
    blood_bank_id: Optional[int] = None,
    component: Optional[str] = None,
    status: Optional[str] = None
) -> List[InventoryLot]:
    """Get all inventory lots (admin view)."""
    q = db.query(InventoryLot)
    if not include_expired:
        q = q.filter(InventoryLot.expiry_date >= date.today())
    if blood_group:
        q = q.filter(InventoryLot.blood_group == blood_group)
    if blood_bank_id:
        q = q.filter(InventoryLot.blood_bank_id == blood_bank_id)
    if component:
        q = q.filter(InventoryLot.component == component)
    if status:
        q = q.filter(InventoryLot.status == status)
    return q.order_by(InventoryLot.blood_group, InventoryLot.expiry_date).all()


def update_lot_quantity(
    db: Session,
    lot_id: int,
    new_total: int,
    user_id: int = None,
    requesting_org_id: int = None
) -> InventoryLot:
    """
    Update the total units of an inventory lot.
    Enforces that new total >= currently reserved units.
    """
    lot = db.get(InventoryLot, lot_id)
    if not lot:
        raise ValueError(f"Inventory lot {lot_id} not found.")

    # Authorization: blood bank users can only modify their own lots
    if requesting_org_id is not None and lot.blood_bank_id != requesting_org_id:
        raise PermissionError("You can only modify your own blood bank's inventory.")

    if new_total < 0:
        raise ValueError("Total units cannot be negative.")
    if new_total < lot.units_reserved:
        raise ValueError(
            f"Cannot set total to {new_total}: {lot.units_reserved} units are already reserved."
        )

    old_total = lot.units_total
    lot.units_total = new_total
    lot.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="update_inventory_lot",
        entity_type="inventory_lot",
        entity_id=lot_id,
        details=f"units_total changed from {old_total} to {new_total}"
    )
    return lot


def get_low_stock_lots(
    db: Session,
    threshold: int = LOW_STOCK_THRESHOLD,
    component: Optional[str] = None,
    blood_bank_id: Optional[int] = None
) -> List[InventoryLot]:
    """Return lots where available units are below the threshold and not expired."""
    lots = get_all_lots(
        db,
        include_expired=False,
        blood_bank_id=blood_bank_id,
        component=component,
        status="available"
    )
    return [lot for lot in lots if lot.available_units < threshold and lot.available_units >= 0]


def get_near_expiry_lots(
    db: Session,
    days: int = NEAR_EXPIRY_DAYS,
    component: Optional[str] = None,
    blood_bank_id: Optional[int] = None
) -> List[InventoryLot]:
    """Return lots expiring within the next N days."""
    cutoff = date.today() + timedelta(days=days)
    q = db.query(InventoryLot).filter(
        InventoryLot.expiry_date >= date.today(),
        InventoryLot.expiry_date <= cutoff,
        InventoryLot.status != "discarded"
    )
    if component:
        q = q.filter(InventoryLot.component == component)
    if blood_bank_id:
        q = q.filter(InventoryLot.blood_bank_id == blood_bank_id)
    return q.order_by(InventoryLot.expiry_date).all()


def get_available_units_by_group(
    db: Session,
    component: Optional[str] = None,
    blood_bank_id: Optional[int] = None
) -> Dict[str, int]:
    """Return a dict of blood_group -> total available units (non-expired, status=available)."""
    lots = get_all_lots(
        db,
        include_expired=False,
        blood_bank_id=blood_bank_id,
        component=component,
        status="available"
    )
    result = {g: 0 for g in BLOOD_GROUPS}
    for lot in lots:
        result[lot.blood_group] = result.get(lot.blood_group, 0) + lot.available_units
    return result


def get_inventory_summary_by_component(
    db: Session,
    blood_bank_id: Optional[int] = None
) -> Dict[str, Dict[str, int]]:
    """Return total available units grouped by component and blood group."""
    summary = {c: {g: 0 for g in BLOOD_GROUPS} for c in BLOOD_COMPONENTS}
    lots = get_all_lots(
        db,
        include_expired=False,
        blood_bank_id=blood_bank_id,
        status="available"
    )
    for lot in lots:
        if lot.component in summary and lot.blood_group in summary[lot.component]:
            summary[lot.component][lot.blood_group] += lot.available_units
    return summary
