"""User model with bcrypt password hashing."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship
import bcrypt
from database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, comment="admin, hospital, blood_bank")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    organization = relationship("Organization", backref="users")

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        now = datetime.now(timezone.utc)
        locked_time = self.locked_until
        if locked_time.tzinfo is None:
            locked_time = locked_time.replace(tzinfo=timezone.utc)
        return now < locked_time

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'hospital', 'blood_bank')",
            name="chk_user_role"
        ),
    )

    def set_password(self, plain_password: str):
        """Hash and store the password."""
        if not plain_password or len(plain_password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(
            plain_password.encode("utf-8"), salt
        ).decode("utf-8")

    def check_password(self, plain_password: str) -> bool:
        """Verify a password against the stored hash."""
        if not self.password_hash or not plain_password:
            return False
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            self.password_hash.encode("utf-8")
        )

    def __repr__(self):
        return f"<User id={self.id} username={self.username!r} role={self.role}>"

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "organization_id": self.organization_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
