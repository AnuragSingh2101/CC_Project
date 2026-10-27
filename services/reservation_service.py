"""
Reservation service — atomic reservation and release of inventory.
Uses database transactions to prevent overselling.
"""
from datetime import datetime, timezone, date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from models.inventory import InventoryLot
from models.reservation import Reservation
from models.emergency_request import EmergencyRequest
from services.audit_service import log_action
import logging

logger = logging.getLogger(__name__)


def make_reservation(
    db: Session,
    request_id: int,
    inventory_lot_id: int,
    units_to_reserve: int,
    user_id: int = None
) -> Reservation:
    """
    Atomically reserve units from an inventory lot for a request.

    Rules enforced:
    - Units must be positive.
    - Lot must not be expired.
    - Available units must cover the requested amount.
    - Inventory cannot go below zero.
    - All changes are within one transaction (caller must commit).
    """
    if units_to_reserve <= 0:
        raise ValueError("units_to_reserve must be positive.")

    # Lock the lot for update (for PostgreSQL SELECT FOR UPDATE; SQLite will use WAL)
    lot = db.get(InventoryLot, inventory_lot_id)
    if not lot:
        raise ValueError(f"Inventory lot {inventory_lot_id} not found.")

    if lot.is_expired:
        raise ValueError(f"Inventory lot {inventory_lot_id} is expired.")

    if lot.status != "available":
        raise ValueError(f"Inventory lot {inventory_lot_id} is in '{lot.status}' status. Only 'available' lots can be reserved.")

    available = lot.available_units
    if available < units_to_reserve:
        raise ValueError(
            f"Insufficient stock. Available: {available}, Requested: {units_to_reserve}."
        )

    req = db.get(EmergencyRequest, request_id)
    if not req:
        raise ValueError(f"Request {request_id} not found.")
    if req.status in ("fulfilled", "cancelled"):
        raise ValueError(f"Cannot reserve for a {req.status} request.")

    # Check for existing active reservation on same lot+request
    existing = db.query(Reservation).filter(
        Reservation.request_id == request_id,
        Reservation.inventory_lot_id == inventory_lot_id,
        Reservation.status == "active"
    ).first()
    if existing:
        raise ValueError(
            f"An active reservation already exists for lot {inventory_lot_id} and request {request_id}."
        )

    # Atomically update inventory with WHERE clause check to prevent race-condition overselling
    stmt = (
        update(InventoryLot)
        .where(
            InventoryLot.id == inventory_lot_id,
            InventoryLot.status == "available",
            InventoryLot.expiry_date >= date.today(),
            (InventoryLot.units_total - InventoryLot.units_reserved) >= units_to_reserve
        )
        .values(
            units_reserved=InventoryLot.units_reserved + units_to_reserve,
            updated_at=datetime.now(timezone.utc)
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        raise ValueError(
            f"Insufficient stock. Available units cannot satisfy {units_to_reserve} units."
        )
    db.refresh(lot)

    # Create reservation record
    reservation = Reservation(
        request_id=request_id,
        inventory_lot_id=inventory_lot_id,
        units_reserved=units_to_reserve,
        status="active",
    )
    db.add(reservation)
    db.flush()

    # Update request status to matched if pending
    if req.status == "pending":
        req.status = "matched"
        req.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="make_reservation",
        entity_type="reservation",
        entity_id=reservation.id,
        details=f"Reserved {units_to_reserve} units from lot {inventory_lot_id} for request {request_id}"
    )
    return reservation


def release_reservation(
    db: Session,
    reservation_id: int,
    user_id: int = None
) -> Reservation:
    """
    Release an active reservation and restore units to inventory.
    Prevents double-release.
    """
    res = db.get(Reservation, reservation_id)
    if not res:
        raise ValueError(f"Reservation {reservation_id} not found.")
    if res.status != "active":
        raise ValueError(
            f"Reservation {reservation_id} is already '{res.status}', cannot release."
        )

    lot = db.get(InventoryLot, res.inventory_lot_id)
    if not lot:
        raise ValueError(f"Inventory lot {res.inventory_lot_id} not found.")

    # Return units
    lot.units_reserved = max(0, lot.units_reserved - res.units_reserved)
    lot.updated_at = datetime.now(timezone.utc)

    res.status = "released"
    res.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="release_reservation",
        entity_type="reservation",
        entity_id=reservation_id,
        details=f"Released {res.units_reserved} units back to lot {res.inventory_lot_id}"
    )
    return res


def release_reservations_for_request(
    db: Session,
    request_id: int,
    user_id: int = None
) -> List[Reservation]:
    """Release all active reservations for a cancelled request."""
    active = db.query(Reservation).filter(
        Reservation.request_id == request_id,
        Reservation.status == "active"
    ).all()

    released = []
    for res in active:
        released.append(release_reservation(db=db, reservation_id=res.id, user_id=user_id))
    return released


def fulfill_reservation(
    db: Session,
    reservation_id: int,
    user_id: int = None
) -> Reservation:
    """
    Mark a reservation as fulfilled (blood physically delivered).
    Does NOT change inventory totals — units remain reserved until consumed.
    """
    res = db.get(Reservation, reservation_id)
    if not res:
        raise ValueError(f"Reservation {reservation_id} not found.")
    if res.status != "active":
        raise ValueError(f"Only active reservations can be fulfilled.")

    res.status = "fulfilled"
    res.updated_at = datetime.now(timezone.utc)

    # Also mark the request fulfilled if all reservations are done
    req = db.get(EmergencyRequest, res.request_id)
    if req:
        active_count = db.query(Reservation).filter(
            Reservation.request_id == req.id,
            Reservation.status == "active"
        ).count()
        if active_count == 0:
            req.status = "fulfilled"
            req.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="fulfill_reservation",
        entity_type="reservation",
        entity_id=reservation_id,
        details=f"Fulfilled {res.units_reserved} units for request {res.request_id}"
    )
    return res


def get_reservations_for_request(db: Session, request_id: int) -> List[Reservation]:
    return db.query(Reservation).filter(Reservation.request_id == request_id).all()
