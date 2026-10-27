"""Organization model — hospitals and blood banks."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, CheckConstraint
from database.connection import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    type = Column(
        String(20),
        nullable=False,
        comment="hospital or blood_bank"
    )
    address = Column(String(500))
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    contact_number = Column(String(20))
    is_active = Column(String(5), default="true")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        CheckConstraint("type IN ('hospital', 'blood_bank')", name="chk_org_type"),
    )

    def __repr__(self):
        return f"<Organization id={self.id} name={self.name!r} type={self.type}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "contact_number": self.contact_number,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
