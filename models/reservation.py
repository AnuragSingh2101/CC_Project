"""Reservation model — links requests to inventory lots."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, CheckConstraint
)
from sqlalchemy.orm import relationship
from database.connection import Base


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer, ForeignKey("emergency_requests.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    inventory_lot_id = Column(
        Integer, ForeignKey("inventory_lots.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    units_reserved = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    request = relationship("EmergencyRequest", back_populates="reservations")
    inventory_lot = relationship("InventoryLot", backref="reservations")

    __table_args__ = (
        CheckConstraint("units_reserved > 0", name="chk_res_units_pos"),
        CheckConstraint(
            "status IN ('active', 'released', 'fulfilled')",
            name="chk_res_status"
        ),
    )

    def __repr__(self):
        return (
            f"<Reservation id={self.id} request_id={self.request_id} "
            f"lot_id={self.inventory_lot_id} units={self.units_reserved} status={self.status}>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "inventory_lot_id": self.inventory_lot_id,
            "units_reserved": self.units_reserved,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
