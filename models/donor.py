"""Donor and Appointment models — blood donor registry."""
from datetime import datetime, timezone, date
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Boolean,
    ForeignKey, CheckConstraint
)
from sqlalchemy.orm import relationship, validates
from database.connection import Base
from config.settings import BLOOD_GROUPS


class Donor(Base):
    __tablename__ = "donors"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name = Column(String(200), nullable=False)
    blood_group = Column(String(5), nullable=False, index=True)
    phone = Column(String(30), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    last_donation_date = Column(Date, nullable=True)
    consent = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    blood_bank = relationship("Organization", backref="donors")
    appointments = relationship("Appointment", back_populates="donor", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            f"blood_group IN ({', '.join(repr(g) for g in BLOOD_GROUPS)})",
            name="chk_donor_blood_group"
        ),
    )

    @validates("blood_group")
    def validate_blood_group(self, key, value):
        if value not in BLOOD_GROUPS:
            raise ValueError(f"Invalid blood group: {value!r}")
        return value

    def get_masked_phone(self) -> str:
        """Return masked phone number (e.g. '******7890')."""
        if not self.phone:
            return ""
        clean_phone = self.phone.strip()
        if len(clean_phone) <= 4:
            return "****"
        return "*" * (len(clean_phone) - 4) + clean_phone[-4:]

    def to_dict(self, mask_phone: bool = True):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "blood_bank_name": self.blood_bank.name if self.blood_bank else None,
            "name": self.name,
            "blood_group": self.blood_group,
            "phone": self.get_masked_phone() if mask_phone else self.phone,
            "city": self.city,
            "last_donation_date": self.last_donation_date.isoformat() if self.last_donation_date else None,
            "consent": self.consent,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Appointment(Base):
    __tablename__ = "donor_appointments"

    id = Column(Integer, primary_key=True, index=True)
    donor_id = Column(
        Integer, ForeignKey("donors.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    blood_bank_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    appointment_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, default="scheduled")
    notes = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    donor = relationship("Donor", back_populates="appointments")
    blood_bank = relationship("Organization")

    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="chk_appointment_status"
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "donor_id": self.donor_id,
            "donor_name": self.donor.name if self.donor else None,
            "blood_group": self.donor.blood_group if self.donor else None,
            "blood_bank_id": self.blood_bank_id,
            "blood_bank_name": self.blood_bank.name if self.blood_bank else None,
            "appointment_date": self.appointment_date.isoformat() if self.appointment_date else None,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
