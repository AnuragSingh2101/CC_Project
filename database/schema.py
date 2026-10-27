"""
SQLAlchemy ORM models — registers all tables with Base.
Import this module to ensure all models are registered before create_all().
"""
from database.connection import Base  # noqa

# Import all models so they register with Base
from models.organization import Organization  # noqa
from models.user import User  # noqa
from models.inventory import InventoryLot  # noqa
from models.emergency_request import EmergencyRequest  # noqa
from models.reservation import Reservation  # noqa
from models.audit_log import AuditLog  # noqa
from models.donor import Donor, Appointment  # noqa
from models.transfer_request import TransferRequest  # noqa
from models.notification import Notification  # noqa
