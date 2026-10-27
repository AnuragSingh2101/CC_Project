"""
Transfer service — inter-bank blood stock transfers.
Enforces atomic reservation upon supplier approval and inventory lot transfer upon receipt.
"""
from datetime import datetime, timezone, date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from models.transfer_request import TransferRequest, _generate_transfer_ref
from models.organization import Organization
from models.inventory import InventoryLot
from services.audit_service import log_action
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS, TRANSFER_STATUSES
import logging

logger = logging.getLogger(__name__)


def create_transfer_request(
    db: Session,
    requesting_org_id: int,
    supplying_org_id: int,
    blood_group: str,
    component: str,
    units: int,
    notes: Optional[str] = None,
    user_id: Optional[int] = None
) -> TransferRequest:
    """Create an inter-bank transfer request."""
    if blood_group not in BLOOD_GROUPS:
        raise ValueError(f"Invalid blood group: {blood_group!r}")
    if component not in BLOOD_COMPONENTS:
        raise ValueError(f"Invalid component: {component!r}")
    if units <= 0:
        raise ValueError("Transfer units must be positive.")
    if requesting_org_id == supplying_org_id:
        raise ValueError("Requesting bank and supplying bank cannot be the same organization.")

    req_org = db.get(Organization, requesting_org_id)
    sup_org = db.get(Organization, supplying_org_id)

    if not req_org or req_org.type != "blood_bank":
        raise ValueError("Invalid requesting blood bank ID.")
    if not sup_org or sup_org.type != "blood_bank":
        raise ValueError("Invalid supplying blood bank ID.")

    transfer = TransferRequest(
        reference=_generate_transfer_ref(),
        requesting_org_id=requesting_org_id,
        supplying_org_id=supplying_org_id,
        blood_group=blood_group,
        component=component,
        units=units,
        status="pending",
        notes=notes,
    )
    db.add(transfer)
    db.flush()

    log_action(
        db=db,
        user_id=user_id,
        action="create_transfer_request",
        entity_type="transfer_request",
        entity_id=transfer.id,
        details=(
            f"Ref={transfer.reference}: {units} units of {blood_group} ({component}) "
            f"requested by {req_org.name} from {sup_org.name}"
        )
    )
    return transfer


def approve_transfer_request(
    db: Session,
    transfer_id: int,
    user_id: Optional[int] = None,
    user_org_id: Optional[int] = None,
    user_role: Optional[str] = None
) -> TransferRequest:
    """
    Supplying blood bank approves transfer.
    Atomically reserves the requested units across supplier's available lots using FEFO.
    """
    transfer = db.get(TransferRequest, transfer_id)
    if not transfer:
        raise ValueError(f"Transfer request {transfer_id} not found.")

    if transfer.status != "pending":
        raise ValueError(f"Cannot approve transfer with status '{transfer.status}'. Must be 'pending'.")

    # Authorization: must be supplying org or admin
    if user_role != "admin" and user_org_id is not None:
        if transfer.supplying_org_id != user_org_id:
            raise PermissionError("Only the supplying blood bank or an administrator can approve this transfer.")

    # Find supplier lots matching blood_group and component, ordered by earliest expiry (FEFO)
    candidate_lots = (
        db.query(InventoryLot)
        .filter(
            InventoryLot.blood_bank_id == transfer.supplying_org_id,
            InventoryLot.blood_group == transfer.blood_group,
            InventoryLot.component == transfer.component,
            InventoryLot.status == "available",
            InventoryLot.expiry_date >= date.today(),
            InventoryLot.units_total > InventoryLot.units_reserved,
        )
        .order_by(InventoryLot.expiry_date.asc())
        .all()
    )

    total_available = sum(lot.available_units for lot in candidate_lots)
    if total_available < transfer.units:
        raise ValueError(
            f"Insufficient stock to approve transfer. Needed: {transfer.units}, "
            f"Available in supplier inventory: {total_available} units."
        )

    # Reserve units across lots using FEFO
    remaining_to_reserve = transfer.units
    for lot in candidate_lots:
        if remaining_to_reserve <= 0:
            break
        can_take = min(lot.available_units, remaining_to_reserve)
        lot.units_reserved += can_take
        lot.updated_at = datetime.now(timezone.utc)
        remaining_to_reserve -= can_take

    transfer.status = "approved"
    transfer.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="approve_transfer_request",
        entity_type="transfer_request",
        entity_id=transfer.id,
        details=f"Approved transfer {transfer.reference}. {transfer.units} units reserved from supplier inventory."
    )
    return transfer


def reject_transfer_request(
    db: Session,
    transfer_id: int,
    reason: Optional[str] = None,
    user_id: Optional[int] = None,
    user_org_id: Optional[int] = None,
    user_role: Optional[str] = None
) -> TransferRequest:
    """Supplying blood bank or admin rejects transfer request."""
    transfer = db.get(TransferRequest, transfer_id)
    if not transfer:
        raise ValueError(f"Transfer request {transfer_id} not found.")

    if transfer.status != "pending":
        raise ValueError(f"Cannot reject transfer with status '{transfer.status}'.")

    if user_role != "admin" and user_org_id is not None:
        if transfer.supplying_org_id != user_org_id:
            raise PermissionError("Only the supplying blood bank or an administrator can reject this transfer.")

    transfer.status = "rejected"
    if reason:
        transfer.notes = (transfer.notes or "") + f" [Rejection Reason: {reason}]"
    transfer.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="reject_transfer_request",
        entity_type="transfer_request",
        entity_id=transfer.id,
        details=f"Rejected transfer {transfer.reference}: {reason or 'No reason provided'}"
    )
    return transfer


def dispatch_transfer_request(
    db: Session,
    transfer_id: int,
    user_id: Optional[int] = None,
    user_org_id: Optional[int] = None,
    user_role: Optional[str] = None
) -> TransferRequest:
    """Transition transfer from approved to in_transit."""
    transfer = db.get(TransferRequest, transfer_id)
    if not transfer:
        raise ValueError(f"Transfer request {transfer_id} not found.")

    if transfer.status != "approved":
        raise ValueError(f"Cannot dispatch transfer with status '{transfer.status}'. Must be 'approved'.")

    if user_role != "admin" and user_org_id is not None:
        if transfer.supplying_org_id != user_org_id:
            raise PermissionError("Only the supplying blood bank can mark transfer in_transit.")

    transfer.status = "in_transit"
    transfer.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="dispatch_transfer_request",
        entity_type="transfer_request",
        entity_id=transfer.id,
        details=f"Dispatched transfer {transfer.reference} (in_transit)"
    )
    return transfer


def receive_transfer_request(
    db: Session,
    transfer_id: int,
    user_id: Optional[int] = None,
    user_org_id: Optional[int] = None,
    user_role: Optional[str] = None
) -> TransferRequest:
    """
    Requesting blood bank receives the transferred units.
    - Supplier's reserved units and total_units are permanently deducted.
    - Requester receives new inventory lot with the transferred units.
    """
    transfer = db.get(TransferRequest, transfer_id)
    if not transfer:
        raise ValueError(f"Transfer request {transfer_id} not found.")

    if transfer.status not in ("approved", "in_transit"):
        raise ValueError(
            f"Cannot receive transfer with status '{transfer.status}'. "
            f"Must be 'approved' or 'in_transit'."
        )

    if user_role != "admin" and user_org_id is not None:
        if transfer.requesting_org_id != user_org_id:
            raise PermissionError("Only the requesting blood bank can confirm receipt of the transfer.")

    # Deduct reserved units from supplier lots
    units_to_deduct = transfer.units
    supplier_lots = (
        db.query(InventoryLot)
        .filter(
            InventoryLot.blood_bank_id == transfer.supplying_org_id,
            InventoryLot.blood_group == transfer.blood_group,
            InventoryLot.component == transfer.component,
            InventoryLot.units_reserved > 0
        )
        .order_by(InventoryLot.expiry_date.asc())
        .all()
    )

    expiry_for_new_lot = None
    for slot in supplier_lots:
        if units_to_deduct <= 0:
            break
        deduct = min(slot.units_reserved, units_to_deduct)
        slot.units_reserved -= deduct
        slot.units_total -= deduct
        slot.updated_at = datetime.now(timezone.utc)
        units_to_deduct -= deduct
        if expiry_for_new_lot is None or slot.expiry_date < expiry_for_new_lot:
            expiry_for_new_lot = slot.expiry_date

    if expiry_for_new_lot is None or expiry_for_new_lot <= date.today():
        from config.settings import COMPONENT_SHELF_LIFE
        shelf = COMPONENT_SHELF_LIFE.get(transfer.component, 35)
        expiry_for_new_lot = date.today() + timedelta(days=shelf)

    # Add inventory lot for the requesting blood bank
    new_lot = InventoryLot(
        blood_bank_id=transfer.requesting_org_id,
        blood_group=transfer.blood_group,
        component=transfer.component,
        units_total=transfer.units,
        units_reserved=0,
        collection_date=date.today(),
        expiry_date=expiry_for_new_lot,
        status="available",
    )
    db.add(new_lot)

    transfer.status = "received"
    transfer.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="receive_transfer_request",
        entity_type="transfer_request",
        entity_id=transfer.id,
        details=(
            f"Confirmed receipt of transfer {transfer.reference}. {transfer.units} units "
            f"of {transfer.blood_group} ({transfer.component}) added to inventory."
        )
    )
    return transfer


def get_transfers_for_bank(
    db: Session,
    blood_bank_id: int,
    status: Optional[str] = None
) -> Dict[str, List[TransferRequest]]:
    """Return incoming (supplier is bank) and outgoing (requester is bank) transfers."""
    in_q = db.query(TransferRequest).filter(TransferRequest.supplying_org_id == blood_bank_id)
    out_q = db.query(TransferRequest).filter(TransferRequest.requesting_org_id == blood_bank_id)

    if status:
        in_q = in_q.filter(TransferRequest.status == status)
        out_q = out_q.filter(TransferRequest.status == status)

    return {
        "incoming": in_q.order_by(TransferRequest.created_at.desc()).all(),
        "outgoing": out_q.order_by(TransferRequest.created_at.desc()).all(),
    }


def get_all_transfers(
    db: Session,
    status: Optional[str] = None
) -> List[TransferRequest]:
    """Admin view: all transfers."""
    q = db.query(TransferRequest)
    if status:
        q = q.filter(TransferRequest.status == status)
    return q.order_by(TransferRequest.created_at.desc()).all()
