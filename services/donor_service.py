"""
Donor service — donor registry, 56-day eligibility engine, and appointment booking.
All donor records are synthetic and for demonstration purposes.
"""
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from models.donor import Donor, Appointment
from models.organization import Organization
from services.audit_service import log_action
from config.settings import BLOOD_GROUPS, DONOR_ELIGIBILITY_DAYS, LOW_STOCK_THRESHOLD
import logging

logger = logging.getLogger(__name__)


def is_donor_eligible(
    donor: Donor,
    check_date: Optional[date] = None
) -> Tuple[bool, str]:
    """
    Check if a donor is eligible to donate whole blood.
    Rules:
    - Must be active
    - Must have given consent
    - Must be at least 56 days since last donation (if any)
    
    Returns (is_eligible, reason_message).
    """
    if not donor.active:
        return False, "Donor profile is marked inactive."
    if not donor.consent:
        return False, "Donor has not provided consent."

    current = check_date or date.today()
    if donor.last_donation_date is None:
        return True, "Eligible — first-time donor."

    days_since = (current - donor.last_donation_date).days
    if days_since < 0:
        return False, "Invalid donation date (in future)."

    if days_since < DONOR_ELIGIBILITY_DAYS:
        remaining = DONOR_ELIGIBILITY_DAYS - days_since
        return False, f"Ineligible: {days_since} days since last donation. Eligible in {remaining} day(s)."

    return True, f"Eligible: {days_since} days since last donation (minimum {DONOR_ELIGIBILITY_DAYS} required)."


def create_donor(
    db: Session,
    organization_id: int,
    name: str,
    blood_group: str,
    phone: str,
    city: str,
    last_donation_date: Optional[date] = None,
    consent: bool = True,
    active: bool = True,
    user_id: Optional[int] = None
) -> Donor:
    """Register a new synthetic donor for a blood bank."""
    if blood_group not in BLOOD_GROUPS:
        raise ValueError(f"Invalid blood group: {blood_group!r}")
    if not name or not name.strip():
        raise ValueError("Donor name cannot be empty.")
    if not phone or not phone.strip():
        raise ValueError("Phone number cannot be empty.")
    if not city or not city.strip():
        raise ValueError("City cannot be empty.")

    org = db.get(Organization, organization_id)
    if not org or org.type != "blood_bank":
        raise ValueError("Invalid blood bank ID.")

    if last_donation_date and last_donation_date > date.today():
        raise ValueError("last_donation_date cannot be in the future.")

    donor = Donor(
        organization_id=organization_id,
        name=name.strip(),
        blood_group=blood_group,
        phone=phone.strip(),
        city=city.strip(),
        last_donation_date=last_donation_date,
        consent=consent,
        active=active,
    )
    db.add(donor)
    db.flush()

    log_action(
        db=db,
        user_id=user_id,
        action="create_donor",
        entity_type="donor",
        entity_id=donor.id,
        details=f"Registered donor {donor.name} ({blood_group}) for {org.name}"
    )
    return donor


def get_donors_for_bank(
    db: Session,
    blood_bank_id: int,
    blood_group: Optional[str] = None,
    active_only: bool = False
) -> List[Donor]:
    """Retrieve donors registered under a specific blood bank."""
    q = db.query(Donor).filter(Donor.organization_id == blood_bank_id)
    if blood_group:
        q = q.filter(Donor.blood_group == blood_group)
    if active_only:
        q = q.filter(Donor.active.is_(True))
    return q.order_by(Donor.name).all()


def get_donor_by_id(db: Session, donor_id: int) -> Optional[Donor]:
    return db.get(Donor, donor_id)


def update_donor(
    db: Session,
    donor_id: int,
    user_id: Optional[int] = None,
    requesting_org_id: Optional[int] = None,
    user_role: Optional[str] = None,
    **kwargs
) -> Donor:
    """Update donor details with ownership authorization check."""
    donor = db.get(Donor, donor_id)
    if not donor:
        raise ValueError(f"Donor {donor_id} not found.")

    if user_role != "admin" and requesting_org_id is not None:
        if donor.organization_id != requesting_org_id:
            raise PermissionError("You can only modify donors belonging to your blood bank.")

    allowed_fields = {"name", "blood_group", "phone", "city", "last_donation_date", "consent", "active"}
    changes = []
    for k, v in kwargs.items():
        if k in allowed_fields and v is not None:
            if k == "blood_group" and v not in BLOOD_GROUPS:
                raise ValueError(f"Invalid blood group: {v!r}")
            setattr(donor, k, v)
            changes.append(f"{k}={v}")

    donor.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="update_donor",
        entity_type="donor",
        entity_id=donor_id,
        details=f"Updated fields: {', '.join(changes)}"
    )
    return donor


def get_donor_display_dict(
    donor: Donor,
    requesting_org_id: Optional[int] = None,
    user_role: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format donor for display, masking phone number unless the viewer is
    the owning blood bank staff or system administrator.
    """
    is_owner = (user_role == "admin") or (requesting_org_id is not None and donor.organization_id == requesting_org_id)
    eligible, reason = is_donor_eligible(donor)
    data = donor.to_dict(mask_phone=not is_owner)
    data["is_eligible"] = eligible
    data["eligibility_reason"] = reason
    return data


def book_appointment(
    db: Session,
    donor_id: int,
    blood_bank_id: int,
    appointment_date: datetime,
    notes: Optional[str] = None,
    user_id: Optional[int] = None
) -> Appointment:
    """Book a donor donation appointment."""
    donor = db.get(Donor, donor_id)
    if not donor:
        raise ValueError(f"Donor {donor_id} not found.")

    org = db.get(Organization, blood_bank_id)
    if not org or org.type != "blood_bank":
        raise ValueError("Invalid blood bank ID.")

    eligible, reason = is_donor_eligible(donor, check_date=appointment_date.date())
    if not eligible:
        raise ValueError(f"Cannot book appointment: Donor is not eligible. {reason}")

    appt = Appointment(
        donor_id=donor_id,
        blood_bank_id=blood_bank_id,
        appointment_date=appointment_date,
        status="scheduled",
        notes=notes,
    )
    db.add(appt)
    db.flush()

    log_action(
        db=db,
        user_id=user_id,
        action="book_donor_appointment",
        entity_type="donor_appointment",
        entity_id=appt.id,
        details=f"Booked appointment for donor {donor.name} on {appointment_date.isoformat()}"
    )
    return appt


def get_appointments_for_bank(
    db: Session,
    blood_bank_id: int,
    status: Optional[str] = None
) -> List[Appointment]:
    """List appointments for a blood bank."""
    q = db.query(Appointment).filter(Appointment.blood_bank_id == blood_bank_id)
    if status:
        q = q.filter(Appointment.status == status)
    return q.order_by(Appointment.appointment_date.asc()).all()


def update_appointment_status(
    db: Session,
    appointment_id: int,
    new_status: str,
    user_id: Optional[int] = None,
    requesting_org_id: Optional[int] = None,
    user_role: Optional[str] = None
) -> Appointment:
    """Update appointment status (scheduled -> completed/cancelled)."""
    appt = db.get(Appointment, appointment_id)
    if not appt:
        raise ValueError(f"Appointment {appointment_id} not found.")

    if user_role != "admin" and requesting_org_id is not None:
        if appt.blood_bank_id != requesting_org_id:
            raise PermissionError("You can only manage appointments for your blood bank.")

    if new_status not in ("scheduled", "completed", "cancelled"):
        raise ValueError(f"Invalid status: {new_status!r}")

    old_status = appt.status
    appt.status = new_status

    # If completed, update donor last_donation_date to appointment date
    if new_status == "completed" and appt.donor:
        appt.donor.last_donation_date = appt.appointment_date.date()
        appt.donor.updated_at = datetime.now(timezone.utc)

    log_action(
        db=db,
        user_id=user_id,
        action="update_appointment_status",
        entity_type="donor_appointment",
        entity_id=appt.id,
        details=f"Status changed from '{old_status}' to '{new_status}'"
    )
    return appt


def get_donors_needed(
    db: Session,
    blood_bank_id: int
) -> List[Dict[str, Any]]:
    """
    Find blood groups below low stock threshold for this bank, and identify
    eligible donors in the same city who can be contacted.
    """
    from services.inventory_service import get_available_units_by_group
    org = db.get(Organization, blood_bank_id)
    if not org:
        return []

    stock_by_group = get_available_units_by_group(db, blood_bank_id=blood_bank_id)
    needed = []

    for bg, units in stock_by_group.items():
        if units < LOW_STOCK_THRESHOLD:
            # Query eligible donors in same city
            city_donors = db.query(Donor).filter(
                Donor.blood_group == bg,
                Donor.city.ilike(org.city),
                Donor.active.is_(True),
                Donor.consent.is_(True)
            ).all()

            eligible_list = []
            for d in city_donors:
                el, reason = is_donor_eligible(d)
                if el:
                    eligible_list.append(get_donor_display_dict(d, requesting_org_id=blood_bank_id))

            needed.append({
                "blood_group": bg,
                "current_stock": units,
                "deficit": LOW_STOCK_THRESHOLD - units,
                "city": org.city,
                "eligible_donors_count": len(eligible_list),
                "donors": eligible_list,
            })

    return needed
