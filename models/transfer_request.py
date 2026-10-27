"""TransferRequest model — bank-to-bank blood transfer requests."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime,
    ForeignKey, CheckConstraint
)
from sqlalchemy.orm import relationship, validates
from database.connection import Base
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS, TRANSFER_STATUSES


def _generate_transfer_ref():
    """Generate reference like TRF-20241026-A1B2."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    uid = uuid.uuid4().hex[:6].upper()
    return f"TRF-{ts}-{uid}"


class TransferRequest(Base):
    __tablename__ = "transfer_requests"

    id = Column(Integer, primary_key=True, index=True)
    reference = Column(
        String(30), unique=True, nullable=False,
        default=_generate_transfer_ref, index=True
    )
    requesting_org_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    supplying_org_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    blood_group = Column(String(5), nullable=False, index=True)
    component = Column(String(30), nullable=False, default="whole_blood")
    units = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    requesting_org = relationship("Organization", foreign_keys=[requesting_org_id], backref="outgoing_transfers")
    supplying_org = relationship("Organization", foreign_keys=[supplying_org_id], backref="incoming_transfers")

    __table_args__ = (
        CheckConstraint(
            f"blood_group IN ({', '.join(repr(g) for g in BLOOD_GROUPS)})",
            name="chk_transfer_blood_group"
        ),
        CheckConstraint(
            f"component IN ({', '.join(repr(c) for c in BLOOD_COMPONENTS)})",
            name="chk_transfer_component"
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in TRANSFER_STATUSES)})",
            name="chk_transfer_status"
        ),
        CheckConstraint("units > 0", name="chk_transfer_units_pos"),
        CheckConstraint("requesting_org_id != supplying_org_id", name="chk_transfer_different_orgs"),
    )

    @validates("blood_group")
    def validate_blood_group(self, key, value):
        if value not in BLOOD_GROUPS:
            raise ValueError(f"Invalid blood group: {value!r}")
        return value

    @validates("component")
    def validate_component(self, key, value):
        if value not in BLOOD_COMPONENTS:
            raise ValueError(f"Invalid component: {value!r}")
        return value

    @validates("units")
    def validate_units(self, key, value):
        if value <= 0:
            raise ValueError("Units must be positive.")
        return value

    def to_dict(self):
        return {
            "id": self.id,
            "reference": self.reference,
            "requesting_org_id": self.requesting_org_id,
            "requesting_org_name": self.requesting_org.name if self.requesting_org else None,
            "supplying_org_id": self.supplying_org_id,
            "supplying_org_name": self.supplying_org.name if self.supplying_org else None,
            "blood_group": self.blood_group,
            "component": self.component,
            "units": self.units,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
