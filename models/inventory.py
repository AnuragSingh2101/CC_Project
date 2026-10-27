"""Inventory lot model — blood units at a blood bank."""
from datetime import datetime, timezone, date
from sqlalchemy import (
    Column, Integer, String, Date, DateTime,
    ForeignKey, CheckConstraint
)
from sqlalchemy.orm import relationship, validates
from database.connection import Base
from config.settings import BLOOD_GROUPS, BLOOD_COMPONENTS, LOT_STATUSES


class InventoryLot(Base):
    __tablename__ = "inventory_lots"

    id = Column(Integer, primary_key=True, index=True)
    blood_bank_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    blood_group = Column(String(5), nullable=False, index=True)
    component = Column(
        String(30),
        nullable=False,
        default="whole_blood",
        index=True
    )
    units_total = Column(Integer, nullable=False, default=0)
    units_reserved = Column(Integer, nullable=False, default=0)
    collection_date = Column(Date, nullable=False, default=date.today)
    expiry_date = Column(Date, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="available",
        index=True
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    blood_bank = relationship("Organization", backref="inventory_lots")

    __table_args__ = (
        CheckConstraint(
            f"blood_group IN ({', '.join(repr(g) for g in BLOOD_GROUPS)})",
            name="chk_blood_group"
        ),
        CheckConstraint(
            f"component IN ({', '.join(repr(c) for c in BLOOD_COMPONENTS)})",
            name="chk_component"
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in LOT_STATUSES)})",
            name="chk_lot_status"
        ),
        CheckConstraint("units_total >= 0", name="chk_units_total_nonneg"),
        CheckConstraint("units_reserved >= 0", name="chk_units_reserved_nonneg"),
        CheckConstraint(
            "units_reserved <= units_total",
            name="chk_reserved_le_total"
        ),
    )

    @validates("units_total")
    def validate_units_total(self, key, value):
        if value < 0:
            raise ValueError("units_total cannot be negative.")
        return value

    @validates("units_reserved")
    def validate_units_reserved(self, key, value):
        if value < 0:
            raise ValueError("units_reserved cannot be negative.")
        return value

    @validates("component")
    def validate_component(self, key, value):
        if value not in BLOOD_COMPONENTS:
            raise ValueError(f"Invalid component: {value!r}. Must be one of {BLOOD_COMPONENTS}")
        return value

    @validates("status")
    def validate_status(self, key, value):
        if value not in LOT_STATUSES:
            raise ValueError(f"Invalid status: {value!r}. Must be one of {LOT_STATUSES}")
        return value

    @property
    def available_units(self) -> int:
        """Units available for reservation (not expired, not reserved, and available status)."""
        if self.status != "available":
            return 0
        return max(0, self.units_total - self.units_reserved)

    @property
    def is_expired(self) -> bool:
        return self.expiry_date < date.today()

    @property
    def is_available(self) -> bool:
        return self.status == "available" and not self.is_expired and (self.units_total - self.units_reserved) > 0

    def __repr__(self):
        return (
            f"<InventoryLot id={self.id} blood_group={self.blood_group} component={self.component} "
            f"status={self.status} available={self.available_units} expiry={self.expiry_date}>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "blood_bank_id": self.blood_bank_id,
            "blood_group": self.blood_group,
            "component": self.component,
            "units_total": self.units_total,
            "units_reserved": self.units_reserved,
            "available_units": self.available_units,
            "collection_date": self.collection_date.isoformat() if self.collection_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "status": self.status,
            "is_expired": self.is_expired,
            "is_available": self.is_available,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
