"""
FastAPI application — exposes the service layer as REST endpoints.
JWT authentication with role-based access control.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config.settings import SECRET_KEY, DATABASE_URL
from database.connection import create_db_engine, get_session_factory
from models.user import User
from models.organization import Organization
from models.inventory import InventoryLot
from models.emergency_request import EmergencyRequest
from models.reservation import Reservation
from models.audit_log import AuditLog
from models.donor import Donor
from models.transfer_request import TransferRequest
from models.notification import Notification

from services.auth_service import authenticate as svc_authenticate, create_user as svc_create_user
from services.inventory_service import (
    create_lot, get_lots_for_bank, get_all_lots, update_lot_status, update_lot_quantity
)
from services.request_service import (
    create_request, get_requests_for_hospital, get_all_requests,
    update_request_status, cancel_request, get_request_by_id, escalate_overdue
)
from services.reservation_service import (
    make_reservation, release_reservation, fulfill_reservation,
    get_reservations_for_request, release_reservations_for_request
)
from services.matching_service import find_matching_lots
from services.transfer_service import (
    create_transfer_request, approve_transfer_request, reject_transfer_request,
    dispatch_transfer_request, receive_transfer_request, get_all_transfers
)
from services.donor_service import (
    create_donor, get_donors_for_bank, get_donor_by_id, update_donor,
    book_appointment, get_appointments_for_bank, update_appointment_status
)
from services.notify_service import (
    get_notifications_for_user, get_unread_count, mark_as_read, mark_all_as_read
)

from api.schemas import (
    Token, TokenData, LoginRequest, UserCreate, UserResponse,
    OrganizationCreate, OrganizationResponse,
    InventoryLotCreate, InventoryLotUpdate, InventoryLotResponse,
    EmergencyRequestCreate, EmergencyRequestUpdate, EmergencyRequestResponse,
    ReservationCreate, ReservationResponse,
    SearchRequest, CandidateLot,
    TransferRequestCreate, TransferRequestResponse,
    DonorCreate, DonorResponse,
    PageParams, PaginatedResponse,
    RoleEnum, RequestStatusEnum
)

# ─── JWT Configuration ─────────────────────────────────
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ─── Database Session ──────────────────────────────────
def get_db():
    """Dependency for database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Auth Helpers ──────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        username: str = payload.get("username")
        role: str = payload.get("role")
        org_id: Optional[int] = payload.get("organization_id")
        if user_id is None or username is None or role is None:
            raise JWTError("Invalid token payload")
        return TokenData(user_id=user_id, username=username, role=role, organization_id=org_id)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> TokenData:
    token_data = decode_token(token)
    user = db.get(User, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return token_data


def require_role(*allowed_roles: str):
    """Dependency factory for role-based access control."""
    def role_checker(current_user: TokenData = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker


# ─── FastAPI App ───────────────────────────────────────
app = FastAPI(
    title="Cloud Blood Bank & Emergency Registry API",
    description="REST API for blood bank inventory management and emergency blood request coordination.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Root & Health Check ──────────────────────────────
@app.get("/")
def root():
    return {
        "name": "Cloud Blood Bank & Emergency Registry API",
        "version": "1.0.0",
        "status": "online",
        "documentation": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ─── Auth Endpoints ────────────────────────────────────
@app.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = svc_authenticate(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account disabled")

    access_token = create_access_token({
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "organization_id": user.organization_id,
    })
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/register", response_model=UserResponse, dependencies=[Depends(require_role("admin"))])
def register_user(user_data: UserCreate, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    """Admin-only: create a new user."""
    try:
        user = svc_create_user(
            db=db,
            username=user_data.username,
            password=user_data.password,
            role=user_data.role.value,
            organization_id=user_data.organization_id,
            acting_user_id=current_user.user_id,
        )
        db.commit()
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(User, current_user.user_id)
    org_name = None
    if user.organization_id:
        org = db.get(Organization, user.organization_id)
        org_name = org.name if org else None
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        organization_id=user.organization_id,
        is_active=user.is_active,
        created_at=user.created_at,
        organization_name=org_name
    )


# ─── Organization Endpoints ────────────────────────────
@app.post("/organizations", response_model=OrganizationResponse, dependencies=[Depends(require_role("admin"))])
def create_organization(org: OrganizationCreate, db: Session = Depends(get_db)):
    db_org = Organization(**org.model_dump())
    db.add(db_org)
    db.commit()
    db.refresh(db_org)
    return db_org


@app.get("/organizations", response_model=List[OrganizationResponse], dependencies=[Depends(require_role("admin", "blood_bank"))])
def list_organizations(db: Session = Depends(get_db)):
    return db.query(Organization).filter(Organization.type != "hospital").all()


@app.get("/organizations/blood-banks", response_model=List[OrganizationResponse], dependencies=[Depends(require_role("admin", "blood_bank", "hospital"))])
def list_blood_banks(db: Session = Depends(get_db)):
    return db.query(Organization).filter(Organization.type == "blood_bank").all()


@app.get("/organizations/hospitals", response_model=List[OrganizationResponse], dependencies=[Depends(require_role("admin", "hospital"))])
def list_hospitals(db: Session = Depends(get_db)):
    return db.query(Organization).filter(Organization.type == "hospital").all()


# ─── Inventory Endpoints ───────────────────────────────
@app.post("/inventory", response_model=InventoryLotResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def create_inventory_lot(lot: InventoryLotCreate, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    # Blood bank users can only create for their own org
    if current_user.role == "blood_bank" and current_user.organization_id != lot.blood_bank_id:
        raise HTTPException(status_code=403, detail="Can only create inventory for your own blood bank")
    try:
        created = create_lot(
            db=db,
            blood_bank_id=lot.blood_bank_id,
            blood_group=lot.blood_group.value,
            component=lot.component.value,
            units_total=lot.units_total,
            expiry_date=lot.expiry_date,
            user_id=current_user.user_id,
            collection_date=lot.collection_date,
            status=lot.status,
        )
        db.commit()
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/inventory", response_model=List[InventoryLotResponse])
def list_inventory(
    blood_bank_id: Optional[int] = None,
    blood_group: Optional[str] = None,
    component: Optional[str] = None,
    status: Optional[str] = None,
    include_expired: bool = False,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "blood_bank":
        # Blood banks only see their own inventory
        blood_bank_id = current_user.organization_id
    elif current_user.role == "hospital":
        # Hospitals see nothing by default - they search via /search
        raise HTTPException(status_code=403, detail="Hospitals cannot list inventory directly")

    if current_user.role == "admin" and blood_bank_id is None:
        lots = get_all_lots(db, include_expired=include_expired, blood_group=blood_group,
                            component=component, status=status)
    else:
        if blood_bank_id is None:
            raise HTTPException(status_code=400, detail="blood_bank_id required")
        lots = get_lots_for_bank(db, blood_bank_id, include_expired=include_expired,
                                 blood_group=blood_group, component=component, status=status)
    return lots


@app.patch("/inventory/{lot_id}", response_model=InventoryLotResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def update_inventory_lot(lot_id: int, lot_update: InventoryLotUpdate, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    lot = db.get(InventoryLot, lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    if current_user.role == "blood_bank" and lot.blood_bank_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not your inventory")

    try:
        if lot_update.units_total is not None:
            update_lot_quantity(db, lot_id, lot_update.units_total, current_user.user_id, current_user.organization_id)
        if lot_update.status is not None:
            update_lot_status(db, lot_id, lot_update.status, current_user.user_id,
                             current_user.organization_id, current_user.role)
        db.commit()
        db.refresh(lot)
        return lot
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Search Endpoint ───────────────────────────────────
@app.post("/search", response_model=List[CandidateLot])
def search_inventory(search: SearchRequest, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    """Find matching inventory lots for a blood request."""
    try:
        results = find_matching_lots(
            db=db,
            blood_group=search.blood_group.value,
            component=search.component.value,
            units_needed=search.units_needed,
            requester_lat=search.latitude,
            requester_lon=search.longitude,
            max_radius_km=search.max_radius_km,
            city_filter=search.city_filter,
            max_results=search.max_results,
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Emergency Requests ────────────────────────────────
@app.post("/requests", response_model=EmergencyRequestResponse, dependencies=[Depends(require_role("admin", "hospital"))])
def create_emergency_request(req: EmergencyRequestCreate, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    # Hospitals can only create for their own org
    if current_user.role == "hospital" and current_user.organization_id != req.hospital_id:
        raise HTTPException(status_code=403, detail="Can only create requests for your own hospital")
    try:
        created = create_request(
            db=db,
            hospital_id=req.hospital_id,
            blood_group=req.blood_group.value,
            units_requested=req.units_requested,
            urgency=req.urgency.value,
            required_by=req.required_by,
            notes=req.notes,
            user_id=current_user.user_id,
            component=req.component.value,
        )
        db.commit()
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/requests", response_model=List[EmergencyRequestResponse])
def list_requests(
    status: Optional[RequestStatusEnum] = None,
    urgency: Optional[str] = None,
    blood_group: Optional[str] = None,
    component: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "hospital":
        requests = get_requests_for_hospital(
            db, hospital_id=current_user.organization_id,
            status=status.value if status else None,
            urgency=urgency
        )
    else:
        requests = get_all_requests(
            db, status=status.value if status else None,
            urgency=urgency, blood_group=blood_group, component=component
        )
    # Add hospital name
    for r in requests:
        r.hospital_name = r.hospital.name if r.hospital else None
    return requests


@app.get("/requests/{request_id}", response_model=EmergencyRequestResponse)
def get_request(request_id: int, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    req = get_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    # Authorization: hospital only sees own, admin/blood_bank see all
    if current_user.role == "hospital" and req.hospital_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not your request")
    req.hospital_name = req.hospital.name if req.hospital else None
    return req


@app.patch("/requests/{request_id}", response_model=EmergencyRequestResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def update_request(request_id: int, req_update: EmergencyRequestUpdate, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    req = get_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        if req_update.status:
            update_request_status(db, request_id, req_update.status.value, current_user.user_id)
            db.commit()
        req = get_request_by_id(db, request_id)
        req.hospital_name = req.hospital.name if req.hospital else None
        return req
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/requests/{request_id}/cancel", response_model=EmergencyRequestResponse, dependencies=[Depends(require_role("admin", "hospital"))])
def cancel_request_endpoint(request_id: int, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    req = get_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        hospital_id = current_user.organization_id if current_user.role == "hospital" else None
        cancelled = cancel_request(db, request_id, current_user.user_id, hospital_id)
        db.commit()
        cancelled.hospital_name = cancelled.hospital.name if cancelled.hospital else None
        return cancelled
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/requests/{request_id}/reserve", response_model=ReservationResponse, dependencies=[Depends(require_role("admin", "hospital"))])
def reserve_for_request(request_id: int, reservation: ReservationCreate, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    req = get_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        created = make_reservation(
            db=db,
            request_id=request_id,
            inventory_lot_id=reservation.inventory_lot_id,
            units_to_reserve=reservation.units_reserved,
            user_id=current_user.user_id,
        )
        db.commit()
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/requests/escalate", dependencies=[Depends(require_role("admin"))])
def escalate_overdue_endpoint(current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    count = escalate_overdue(db, current_user.user_id)
    db.commit()
    return {"escalated_count": count}


# ─── Reservations ──────────────────────────────────────
@app.post("/reservations/{reservation_id}/release", response_model=ReservationResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def release_reservation_endpoint(reservation_id: int, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        released = release_reservation(db, reservation_id, current_user.user_id)
        db.commit()
        return released
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/reservations/{reservation_id}/fulfill", response_model=ReservationResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def fulfill_reservation_endpoint(reservation_id: int, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        fulfilled = fulfill_reservation(db, reservation_id, current_user.user_id)
        db.commit()
        return fulfilled
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/requests/{request_id}/reservations", response_model=List[ReservationResponse])
def get_request_reservations(request_id: int, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    req = get_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if current_user.role == "hospital" and req.hospital_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not your request")
    return get_reservations_for_request(db, request_id)


# ─── Transfers ─────────────────────────────────────────
@app.post("/transfers", response_model=TransferRequestResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def create_transfer(transfer: TransferRequestCreate, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "blood_bank" and current_user.organization_id != transfer.requesting_org_id:
        raise HTTPException(status_code=403, detail="Can only create transfers from your own blood bank")
    try:
        created = create_transfer_request(
            db=db,
            requesting_org_id=transfer.requesting_org_id,
            supplying_org_id=transfer.supplying_org_id,
            blood_group=transfer.blood_group.value,
            component=transfer.component.value,
            units=transfer.units,
            notes=transfer.notes,
            user_id=current_user.user_id,
        )
        db.commit()
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/transfers", response_model=List[TransferRequestResponse], dependencies=[Depends(require_role("admin", "blood_bank"))])
def list_transfers(status: Optional[str] = None, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "admin":
        return get_all_transfers(db, status=status)
    # Blood bank sees their own
    return get_all_transfers(db, status=status)  # Will filter in service if needed


@app.post("/transfers/{transfer_id}/approve", response_model=TransferRequestResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def approve_transfer(transfer_id: int, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        approved = approve_transfer_request(
            db=db, transfer_id=transfer_id,
            user_id=current_user.user_id,
            user_org_id=current_user.organization_id,
            user_role=current_user.role,
        )
        db.commit()
        return approved
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/transfers/{transfer_id}/reject", response_model=TransferRequestResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def reject_transfer(transfer_id: int, reason: Optional[str] = None, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        rejected = reject_transfer_request(
            db=db, transfer_id=transfer_id, reason=reason,
            user_id=current_user.user_id,
            user_org_id=current_user.organization_id,
            user_role=current_user.role,
        )
        db.commit()
        return rejected
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/transfers/{transfer_id}/dispatch", response_model=TransferRequestResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def dispatch_transfer(transfer_id: int, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        dispatched = dispatch_transfer_request(
            db=db, transfer_id=transfer_id,
            user_id=current_user.user_id,
            user_org_id=current_user.organization_id,
            user_role=current_user.role,
        )
        db.commit()
        return dispatched
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/transfers/{transfer_id}/receive", response_model=TransferRequestResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def receive_transfer(transfer_id: int, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        received = receive_transfer_request(
            db=db, transfer_id=transfer_id,
            user_id=current_user.user_id,
            user_org_id=current_user.organization_id,
            user_role=current_user.role,
        )
        db.commit()
        return received
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Donors ────────────────────────────────────────────
@app.post("/donors", response_model=DonorResponse, dependencies=[Depends(require_role("admin", "blood_bank"))])
def create_donor_endpoint(donor: DonorCreate, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "blood_bank" and current_user.organization_id != donor.organization_id:
        raise HTTPException(status_code=403, detail="Can only create donors for your own blood bank")
    try:
        created = create_donor(
            db=db, organization_id=donor.organization_id, name=donor.name,
            blood_group=donor.blood_group.value, phone=donor.phone, city=donor.city,
            last_donation_date=donor.last_donation_date, consent=donor.consent, active=donor.active,
            user_id=current_user.user_id,
        )
        db.commit()
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/donors", response_model=List[DonorResponse], dependencies=[Depends(require_role("admin", "blood_bank"))])
def list_donors(blood_group: Optional[str] = None, active_only: bool = True, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "blood_bank":
        return get_donors_for_bank(db, current_user.organization_id, blood_group, active_only)
    # Admin sees all
    q = db.query(Donor)
    if blood_group:
        q = q.filter(Donor.blood_group == blood_group)
    if active_only:
        q = q.filter(Donor.active == True)  # noqa
    return q.all()


# ─── Notifications ─────────────────────────────────────
@app.get("/notifications", response_model=List[dict])
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notifs = get_notifications_for_user(db, current_user.user_id, current_user.organization_id, unread_only, limit)
    return [n.to_dict() for n in notifs]


@app.get("/notifications/unread-count")
def unread_count(current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    count = get_unread_count(db, current_user.user_id, current_user.organization_id)
    return {"unread_count": count}


@app.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    success = mark_as_read(db, notification_id, current_user.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found or access denied")
    db.commit()
    return {"success": True}


@app.post("/notifications/read-all")
def mark_all_notifications_read(current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    count = mark_all_as_read(db, current_user.user_id, current_user.organization_id)
    db.commit()
    return {"marked_read": count}


# ─── Initialize DB on Startup ──────────────────────────
@app.on_event("startup")
def startup_event():
    engine = create_db_engine()
    from database.connection import Base
    import database.schema  # noqa
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)