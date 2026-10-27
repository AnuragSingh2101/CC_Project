"""Emergency request model — hospital blood requests."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, Date,
    ForeignKey, CheckConstraint, Boolean
)
from sqlalchemy.orm import relationship, validates
from database.connection import Base
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS, URGENCY_LEVELS, REQUEST_STATUSES


def _generate_ref():
    """Generate a human-readable request reference like BBR-20241026-A1B2."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    uid = uuid.uuid4().hex[:6].upper()
    return f"BBR-{ts}-{uid}"


class EmergencyRequest(Base):
    __tablename__ = "emergency_requests"

    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String(30), unique=True, nullable=False, default=_generate_ref, index=True)
    hospital_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    blood_group = Column(String(5), nullable=False)
    component = Column(String(30), nullable=False, default="whole_blood")
    units_requested = Column(Integer, nullable=False)
    urgency = Column(String(20), nullable=False, default="routine")
    status = Column(String(20), nullable=False, default="pending")
    required_by = Column(DateTime(timezone=True), nullable=True)
    notes = Column(String(1000), nullable=True)
    is_escalated = Column(Boolean, default=False, nullable=False, index=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    hospital = relationship("Organization", backref="emergency_requests")
    reservations = relationship("Reservation", back_populates="request")

    @property
    def elapsed_minutes(self) -> float:
        if self.created_at is None:
            return 0.0
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 60.0)

    @property
    def is_overdue(self) -> bool:
        """True if still pending and time elapsed exceeds SLA."""
        if self.status != "pending":
            return False
        from config.settings import SLA_MINUTES
        sla_limit = SLA_MINUTES.get(self.urgency, 1440)
        return self.elapsed_minutes > sla_limit

    __table_args__ = (
        CheckConstraint(
            f"urgency IN ({', '.join(repr(u) for u in URGENCY_LEVELS)})",
            name="chk_urgency"
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in REQUEST_STATUSES)})",
            name="chk_request_status"
        ),
        CheckConstraint(
            f"component IN ({', '.join(repr(c) for c in BLOOD_COMPONENTS)})",
            name="chk_request_component"
        ),
        CheckConstraint("units_requested > 0", name="chk_units_requested_pos"),
    )

    @validates("component")
    def validate_component(self, key, value):
        if value not in BLOOD_COMPONENTS:
            raise ValueError(f"Invalid component: {value!r}. Must be one of {BLOOD_COMPONENTS}")
        return value

    def __repr__(self):
        return (
            f"<EmergencyRequest ref={self.reference!r} "
            f"blood_group={self.blood_group} component={self.component} status={self.status}>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "reference": self.reference,
            "hospital_id": self.hospital_id,
            "blood_group": self.blood_group,
            "component": self.component,
            "units_requested": self.units_requested,
            "urgency": self.urgency,
            "status": self.status,
            "required_by": self.required_by.isoformat() if self.required_by else None,
            "notes": self.notes,
            "is_escalated": self.is_escalated,
            "escalated_at": self.escalated_at.isoformat() if self.escalated_at else None,
            "is_overdue": self.is_overdue,
            "elapsed_minutes": round(self.elapsed_minutes, 1),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
