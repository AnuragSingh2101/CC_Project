"""
Seed script — creates synthetic demonstration data.
Run explicitly: python -m database.seed
Does NOT run automatically on app startup.
All records are clearly labeled as synthetic demonstration data.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date, timedelta, datetime, timezone
from database.connection import init_database, get_session
from models.organization import Organization
from models.user import User
from models.inventory import InventoryLot
from models.emergency_request import EmergencyRequest, _generate_ref
from models.donor import Donor, Appointment
from models.transfer_request import TransferRequest, _generate_transfer_ref
from services.auth_service import create_user
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMO_BLOOD_BANKS = [
    {
        "name": "[DEMO] Bengaluru Apex Blood Bank",
        "city": "Bengaluru",
        "state": "Karnataka",
        "address": "22 Victoria Road, Ashok Nagar, Bengaluru",
        "contact_number": "080-2222-1111",
        "latitude": 12.9716,
        "longitude": 77.5946,
    },
    {
        "name": "[DEMO] Tumakuru District Blood Centre",
        "city": "Tumakuru",
        "state": "Karnataka",
        "address": "15 B.H. Road, Tumakuru",
        "contact_number": "0816-2278-900",
        "latitude": 13.3392,
        "longitude": 77.1017,
    },
    {
        "name": "[DEMO] Mysuru Red Cross Blood Bank",
        "city": "Mysuru",
        "state": "Karnataka",
        "address": "8 Sayyaji Rao Road, Mysuru",
        "contact_number": "0821-2422-333",
        "latitude": 12.2958,
        "longitude": 76.6394,
    },
    {
        "name": "[DEMO] Mangaluru Coast Blood Centre",
        "city": "Mangaluru",
        "state": "Karnataka",
        "address": "40 Light House Hill Road, Mangaluru",
        "contact_number": "0824-2444-555",
        "latitude": 12.9141,
        "longitude": 74.8560,
    },
    {
        "name": "[DEMO] Mumbai Central Blood Bank",
        "city": "Mumbai",
        "state": "Maharashtra",
        "address": "12 Health Road, Andheri, Mumbai",
        "contact_number": "022-1234-5678",
        "latitude": 19.1176,
        "longitude": 72.8483,
    },
    {
        "name": "[DEMO] Pune Regional Blood Bank",
        "city": "Pune",
        "state": "Maharashtra",
        "address": "45 Medical Lane, Kothrud, Pune",
        "contact_number": "020-9876-5432",
        "latitude": 18.5204,
        "longitude": 73.8567,
    },
]

DEMO_HOSPITALS = [
    {
        "name": "[DEMO] Victoria Multi-Specialty Hospital - Bengaluru",
        "city": "Bengaluru",
        "state": "Karnataka",
        "address": "Fort, Krishna Rajendra Road, Bengaluru",
        "contact_number": "080-2670-1150",
        "latitude": 12.9634,
        "longitude": 77.5756,
    },
    {
        "name": "[DEMO] Tumakuru General Hospital",
        "city": "Tumakuru",
        "state": "Karnataka",
        "address": "District Hospital Campus, Tumakuru",
        "contact_number": "0816-2251-200",
        "latitude": 13.3400,
        "longitude": 77.1000,
    },
    {
        "name": "[DEMO] K.R. Hospital - Mysuru",
        "city": "Mysuru",
        "state": "Karnataka",
        "address": "Irwin Road, Mysuru",
        "contact_number": "0821-2520-200",
        "latitude": 12.3160,
        "longitude": 76.6490,
    },
    {
        "name": "[DEMO] Wenlock District Hospital - Mangaluru",
        "city": "Mangaluru",
        "state": "Karnataka",
        "address": "Hampankatta, Mangaluru",
        "contact_number": "0824-2423-000",
        "latitude": 12.8680,
        "longitude": 74.8430,
    },
    {
        "name": "[DEMO] City General Hospital - Mumbai",
        "city": "Mumbai",
        "state": "Maharashtra",
        "address": "55 Hospital Road, Bandra, Mumbai",
        "contact_number": "022-8765-4321",
        "latitude": 19.0596,
        "longitude": 72.8295,
    },
]

INVENTORY_TEMPLATE = [
    {"blood_group": "A+",  "component": "packed_red_cells", "units": 45, "days_till_expiry": 30, "status": "available"},
    {"blood_group": "A+",  "component": "whole_blood",      "units": 20, "days_till_expiry": 25, "status": "available"},
    {"blood_group": "A+",  "component": "platelets",        "units": 8,  "days_till_expiry": 4,  "status": "available"},
    {"blood_group": "A+",  "component": "plasma",           "units": 25, "days_till_expiry": 300, "status": "available"},
    {"blood_group": "A-",  "component": "packed_red_cells", "units": 12, "days_till_expiry": 25, "status": "available"},
    {"blood_group": "B+",  "component": "packed_red_cells", "units": 38, "days_till_expiry": 35, "status": "available"},
    {"blood_group": "B+",  "component": "platelets",        "units": 6,  "days_till_expiry": 3,  "status": "available"},
    {"blood_group": "B-",  "component": "packed_red_cells", "units": 8,  "days_till_expiry": 20, "status": "available"},
    {"blood_group": "AB+", "component": "plasma",           "units": 30, "days_till_expiry": 320, "status": "available"},
    {"blood_group": "AB+", "component": "packed_red_cells", "units": 15, "days_till_expiry": 28, "status": "available"},
    {"blood_group": "AB-", "component": "packed_red_cells", "units": 5,  "days_till_expiry": 15, "status": "available"},
    {"blood_group": "O+",  "component": "packed_red_cells", "units": 50, "days_till_expiry": 28, "status": "available"},
    {"blood_group": "O+",  "component": "whole_blood",      "units": 30, "days_till_expiry": 22, "status": "available"},
    {"blood_group": "O-",  "component": "packed_red_cells", "units": 18, "days_till_expiry": 22, "status": "available"},
    {"blood_group": "O-",  "component": "plasma",           "units": 10, "days_till_expiry": 180, "status": "available"},
    # Near expiry demonstration lot
    {"blood_group": "O+",  "component": "platelets",        "units": 4,  "days_till_expiry": 2,  "status": "available"},
    # Quarantine demonstration lot
    {"blood_group": "B+",  "component": "whole_blood",      "units": 15, "days_till_expiry": 34, "status": "quarantine"},
    # Tested demonstration lot
    {"blood_group": "A-",  "component": "packed_red_cells", "units": 10, "days_till_expiry": 40, "status": "tested"},
]

SYNTHETIC_DONORS = [
    {"name": "Aarav Sharma",   "blood_group": "O+",  "phone": "+91-98451-23456", "city": "Bengaluru", "days_ago": 90},
    {"name": "Ananya Rao",     "blood_group": "A+",  "phone": "+91-98452-34567", "city": "Bengaluru", "days_ago": 60},
    {"name": "Rohan Hegde",    "blood_group": "O-",  "phone": "+91-98453-45678", "city": "Bengaluru", "days_ago": 30},  # Ineligible
    {"name": "Pooja Patil",    "blood_group": "B+",  "phone": "+91-98454-56789", "city": "Bengaluru", "days_ago": None}, # First-time
    {"name": "Suresh Gowda",   "blood_group": "O+",  "phone": "+91-98455-67890", "city": "Tumakuru",  "days_ago": 75},
    {"name": "Deepa Murthy",   "blood_group": "A-",  "phone": "+91-98456-78901", "city": "Tumakuru",  "days_ago": 45},  # Ineligible
    {"name": "Kiran Kumar",    "blood_group": "AB+", "phone": "+91-98457-89012", "city": "Mysuru",    "days_ago": 120},
    {"name": "Meera Nayak",    "blood_group": "B-",  "phone": "+91-98458-90123", "city": "Mangaluru", "days_ago": 80},
    {"name": "Vikram Desai",   "blood_group": "O-",  "phone": "+91-98459-01234", "city": "Mumbai",    "days_ago": 150},
    {"name": "Sneha Joshi",    "blood_group": "A+",  "phone": "+91-98460-12345", "city": "Pune",      "days_ago": 70},
]


def seed(db, admin_password: str = "Admin@BloodBank123!"):
    """Seed the database with demonstration data."""
    logger.info("Starting database seed...")

    # Create admin user
    existing_admin = db.query(User).filter(User.username == "admin").first()
    if not existing_admin:
        create_user(
            db=db, username="admin", password=admin_password,
            role="admin", organization_id=None
        )
        logger.info("Created admin user.")

    blood_banks = []
    for i, bb_data in enumerate(DEMO_BLOOD_BANKS):
        existing = db.query(Organization).filter(
            Organization.name == bb_data["name"]
        ).first()
        if existing:
            # Update lat/lon if needed
            existing.latitude = bb_data["latitude"]
            existing.longitude = bb_data["longitude"]
            blood_banks.append(existing)
        else:
            org = Organization(type="blood_bank", **bb_data)
            db.add(org)
            db.flush()

            username = f"bb_{i+1}"
            existing_user = db.query(User).filter(User.username == username).first()
            if not existing_user:
                create_user(
                    db=db, username=username, password=f"BloodBank{i+1}@Pass",
                    role="blood_bank", organization_id=org.id
                )
            blood_banks.append(org)
            logger.info(f"Blood bank ready: {bb_data['name']} (user: {username})")

    hospitals = []
    for i, h_data in enumerate(DEMO_HOSPITALS):
        existing = db.query(Organization).filter(
            Organization.name == h_data["name"]
        ).first()
        if existing:
            existing.latitude = h_data["latitude"]
            existing.longitude = h_data["longitude"]
            hospitals.append(existing)
        else:
            org = Organization(type="hospital", **h_data)
            db.add(org)
            db.flush()

            username = f"hospital_{i+1}"
            existing_user = db.query(User).filter(User.username == username).first()
            if not existing_user:
                create_user(
                    db=db, username=username, password=f"Hospital{i+1}@Pass",
                    role="hospital", organization_id=org.id
                )
            hospitals.append(org)
            logger.info(f"Hospital ready: {h_data['name']} (user: {username})")

    db.flush()

    # Seed inventory lots
    for j, bb in enumerate(blood_banks):
        existing_lots = db.query(InventoryLot).filter(
            InventoryLot.blood_bank_id == bb.id
        ).count()
        if existing_lots == 0:
            for tmpl in INVENTORY_TEMPLATE:
                units = max(1, tmpl["units"] - (j * 2))
                coll_date = date.today() - timedelta(days=5)
                expiry = date.today() + timedelta(days=tmpl["days_till_expiry"])
                lot = InventoryLot(
                    blood_bank_id=bb.id,
                    blood_group=tmpl["blood_group"],
                    component=tmpl["component"],
                    units_total=units,
                    units_reserved=0,
                    collection_date=coll_date,
                    expiry_date=expiry,
                    status=tmpl.get("status", "available"),
                )
                db.add(lot)
            logger.info(f"Added inventory for {bb.name}")

    # Seed donors
    if blood_banks and db.query(Donor).count() == 0:
        for idx, d_data in enumerate(SYNTHETIC_DONORS):
            target_bb = blood_banks[idx % len(blood_banks)]
            last_date = (date.today() - timedelta(days=d_data["days_ago"])) if d_data["days_ago"] else None
            donor = Donor(
                organization_id=target_bb.id,
                name=f"[DEMO] {d_data['name']}",
                blood_group=d_data["blood_group"],
                phone=d_data["phone"],
                city=d_data["city"],
                last_donation_date=last_date,
                consent=True,
                active=True,
            )
            db.add(donor)
            db.flush()

            # Seed an appointment for eligible donors
            if d_data["days_ago"] and d_data["days_ago"] >= 56:
                appt = Appointment(
                    donor_id=donor.id,
                    blood_bank_id=target_bb.id,
                    appointment_date=datetime.now(timezone.utc) + timedelta(days=2),
                    status="scheduled",
                    notes="[DEMO] Routine voluntary donation appointment",
                )
                db.add(appt)
        logger.info("Added synthetic donors and sample appointments.")

    # Seed emergency requests
    if hospitals and db.query(EmergencyRequest).count() == 0:
        sample_requests = [
            {
                "hospital_id": hospitals[0].id, "blood_group": "O+", "component": "packed_red_cells",
                "units_requested": 4, "urgency": "critical",
                "notes": "[DEMO] Emergency trauma care - demonstration data"
            },
            {
                "hospital_id": hospitals[0].id, "blood_group": "A+", "component": "platelets",
                "units_requested": 2, "urgency": "urgent",
                "notes": "[DEMO] Oncology transfusion - demonstration data"
            },
            {
                "hospital_id": hospitals[1].id if len(hospitals) > 1 else hospitals[0].id,
                "blood_group": "B+", "component": "whole_blood", "units_requested": 3,
                "urgency": "routine",
                "notes": "[DEMO] Orthopedic surgery - demonstration data"
            },
        ]
        for req_data in sample_requests:
            req = EmergencyRequest(
                reference=_generate_ref(),
                status="pending",
                **req_data
            )
            db.add(req)
        logger.info("Added sample emergency requests.")

    # Seed sample inter-bank transfer requests
    if len(blood_banks) >= 2 and db.query(TransferRequest).count() == 0:
        sample_transfers = [
            {
                "requesting_org_id": blood_banks[1].id,
                "supplying_org_id": blood_banks[0].id,
                "blood_group": "O-",
                "component": "packed_red_cells",
                "units": 2,
                "status": "pending",
                "notes": "[DEMO] Critical reserve replenishment request",
            },
            {
                "requesting_org_id": blood_banks[2].id if len(blood_banks) > 2 else blood_banks[0].id,
                "supplying_org_id": blood_banks[1].id,
                "blood_group": "A+",
                "component": "plasma",
                "units": 3,
                "status": "approved",
                "notes": "[DEMO] Approved inter-bank stock balance",
            },
        ]
        for t_data in sample_transfers:
            trf = TransferRequest(
                reference=_generate_transfer_ref(),
                **t_data
            )
            db.add(trf)
        logger.info("Added sample inter-bank transfer requests.")

    db.commit()
    logger.info("Seed complete.")

    print("\n" + "="*65)
    print("DEMONSTRATION ACCOUNTS (All synthetic data)")
    print("="*65)
    print(f"Admin        : admin / Admin@BloodBank123!")
    for i in range(len(blood_banks)):
        print(f"Blood Bank {i+1} : bb_{i+1} / BloodBank{i+1}@Pass  ({blood_banks[i].name})")
    for i in range(len(hospitals)):
        print(f"Hospital  {i+1} : hospital_{i+1} / Hospital{i+1}@Pass  ({hospitals[i].name})")
    print("="*65)


def reset_and_reseed():
    """Drop and recreate all tables, then seed."""
    from database.connection import Base, get_engine
    import database.schema  # noqa
    engine = get_engine()
    logger.warning("Dropping all tables and reseeding...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = get_session()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
    db = get_session()
    try:
        seed(db)
    finally:
        db.close()
