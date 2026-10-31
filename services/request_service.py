"""
Emergency request service — create, view, update, and cancel requests.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from models.emergency_request import EmergencyRequest, _generate_ref
from models.organization import Organization
from models.notification import Notification
from services.audit_service import log_action
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS, URGENCY_LEVELS, SLA_MINUTES, ESCALATION_RADIUS_KM
from services.matching_service import find_matching_lots
import logging

logger = logging.getLogger(__name__)

# Valid status transitions
VALID_TRANSITIONS = {
    "pending": ["matched", "cancelled"],
    "matched": ["fulfilled", "cancelled", "pending"],
    "fulfilled": [],      # terminal state
    "cancelled": [],      # terminal state
}


def create_request(
    db: Session,
    hospital_id: int,
    blood_group: str,
    units_requested: int,
    urgency: str,
    required_by: datetime = None,
    notes: str = None,
    user_id: int = None,
    component: str = "whole_blood"
) -> EmergencyRequest:
    """
    Create an emergency blood request with specified component.
    Raises ValueError on validation failure.
    """
    if blood_group not in BLOOD_GROUPS:
        raise ValueError(f"Invalid blood group: {blood_group!r}")
    if component not in BLOOD_COMPONENTS:
        raise ValueError(f"Invalid component: {component!r}")
    if urgency not in URGENCY_LEVELS:
        raise ValueError(f"Invalid urgency: {urgency!r}")
    if units_requested <= 0:
        raise ValueError("units_requested must be positive.")

    org = db.get(Organization, hospital_id)
    if not org or org.type != "hospital":
        raise ValueError("Invalid hospital ID.")

    req = EmergencyRequest(
        reference=_generate_ref(),
        hospital_id=hospital_id,
        blood_group=blood_group,
        component=component,
        units_requested=units_requested,
        urgency=urgency,
        status="pending",
        required_by=required_by,
        notes=notes,
    )
    db.add(req)
    db.flush()

    log_action(
        db=db,
        user_id=user_id,
        action="create_request",
        entity_type="emergency_request",
        entity_id=req.id,
        details=(
            f"Ref={req.reference}, blood_group={blood_group}, component={component}, "
            f"units={units_requested}, urgency={urgency}"
        )
    )
    return req


def get_requests_for_hospital(
    db: Session,
    hospital_id: int,
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    component: Optional[str] = None
) -> List[EmergencyRequest]:
    """Get requests for a specific hospital."""
    q = db.query(EmergencyRequest).filter(EmergencyRequest.hospital_id == hospital_id)
    if status:
        q = q.filter(EmergencyRequest.status == status)
    if urgency:
        q = q.filter(EmergencyRequest.urgency == urgency)
    if component:
        q = q.filter(EmergencyRequest.component == component)
    return q.order_by(EmergencyRequest.created_at.desc()).all()


def get_all_requests(
    db: Session,
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    blood_group: Optional[str] = None,
    component: Optional[str] = None
) -> List[EmergencyRequest]:
    """Get all requests (admin view)."""
    q = db.query(EmergencyRequest)
    if status:
        q = q.filter(EmergencyRequest.status == status)
    if urgency:
        q = q.filter(EmergencyRequest.urgency == urgency)
    if blood_group:
        q = q.filter(EmergencyRequest.blood_group == blood_group)
    if component:
        q = q.filter(EmergencyRequest.component == component)
    return q.order_by(EmergencyRequest.created_at.desc()).all()


def get_request_by_id(db: Session, request_id: int) -> Optional[EmergencyRequest]:
    return db.get(EmergencyRequest, request_id)


def update_request_status(
    db: Session,
    request_id: int,
    new_status: str,
    user_id: int = None,
    requesting_hospital_id: int = None
) -> EmergencyRequest:
    """
    Update request status with transition validation.
    Hospitals can only cancel their own requests.
    """
    req = db.get(EmergencyRequest, request_id)
    if not req:
        raise ValueError(f"Request {request_id} not found.")

    if new_status not in VALID_TRANSITIONS.get(req.status, []):
        raise ValueError(
            f"Cannot transition from '{req.status}' to '{new_status}'."
        )

    # Hospital users can only cancel their own requests
    if requesting_hospital_id is not None:
        if req.hospital_id != requesting_hospital_id:
            raise PermissionError("You can only manage your own requests.")
        if new_status != "cancelled":
            raise PermissionError("Hospitals may only cancel requests.")

    old_status = req.status
    req.status = new_status
    req.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="update_request_status",
        entity_type="emergency_request",
        entity_id=request_id,
        details=f"Status changed from '{old_status}' to '{new_status}'"
    )
    return req


def cancel_request(
    db: Session,
    request_id: int,
    user_id: int = None,
    hospital_id: int = None
) -> EmergencyRequest:
    """Cancel a pending or matched request and release reservations."""
    from services.reservation_service import release_reservations_for_request
    req = update_request_status(
        db=db,
        request_id=request_id,
        new_status="cancelled",
        user_id=user_id,
        requesting_hospital_id=hospital_id
    )
    # Release any active reservations
    release_reservations_for_request(db=db, request_id=request_id, user_id=user_id)
    return req


def escalate_overdue(db: Session, user_id: int = None) -> int:
    """
    Find pending requests past their SLA, mark them escalated, and create
    notifications for blood banks within the configured radius.
    Returns the number of requests escalated.
    """
    now = datetime.now(timezone.utc)
    pending_requests = db.query(EmergencyRequest).filter(
        EmergencyRequest.status == "pending",
        EmergencyRequest.is_escalated == False  # noqa
    ).all()

    escalated_count = 0
    for req in pending_requests:
        # Check if request is past SLA
        sla_limit = SLA_MINUTES.get(req.urgency, 1440)
        created = req.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed_minutes = (now - created).total_seconds() / 60.0 if created else 0

        if elapsed_minutes > sla_limit:
            # Mark as escalated
            req.is_escalated = True
            req.escalated_at = now
            req.updated_at = now

            # Find nearby blood banks using matching service
            req_hosp = req.hospital
            if req_hosp and req_hosp.latitude and req_hosp.longitude:
                nearby_banks = find_matching_lots(
                    db=db,
                    blood_group=req.blood_group,
                    component=req.component,
                    units_needed=1,  # just to get banks in radius
                    requester_lat=req_hosp.latitude,
                    requester_lon=req_hosp.longitude,
                    max_radius_km=ESCALATION_RADIUS_KM,
                    max_results=100
                )
                # Extract unique blood bank IDs
                bank_ids = set(c["blood_bank_id"] for c in nearby_banks)
            else:
                # Fallback: all blood banks
                bank_ids = set(
                    db.query(Organization.id).filter(Organization.type == "blood_bank").all()
                )
                bank_ids = {b[0] for b in bank_ids}

            # Create notification for each blood bank
            for bank_id in bank_ids:
                notif = Notification(
                    organization_id=bank_id,
                    title=f"🚨 ESCALATED: {req.urgency.title()} Request Overdue",
                    message=(
                        f"Emergency request {req.reference} ({req.blood_group} "
                        f"{req.component}, {req.units_requested} units) from "
                        f"{req_hosp.name if req_hosp else 'Unknown Hospital'} "
                        f"has exceeded its {sla_limit}-minute SLA. "
                        f"Elapsed: {elapsed_minutes:.0f} minutes. "
                        f"Please review and respond urgently."
                    ),
                    is_read=False,
                )
                db.add(notif)

            log_action(
                db=db,
                user_id=user_id,
                action="escalate_request",
                entity_type="emergency_request",
                entity_id=req.id,
                details=f"Escalated overdue {req.urgency} request after {elapsed_minutes:.0f} min (SLA: {sla_limit} min)"
            )
            escalated_count += 1

    if escalated_count > 0:
        db.flush()

    return escalated_count
