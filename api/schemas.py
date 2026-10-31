"""
FastAPI Pydantic schemas for request/response validation.
"""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


class RoleEnum(str, Enum):
    admin = "admin"
    hospital = "hospital"
    blood_bank = "blood_bank"


class UrgencyEnum(str, Enum):
    routine = "routine"
    urgent = "urgent"
    critical = "critical"


class RequestStatusEnum(str, Enum):
    pending = "pending"
    matched = "matched"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class ComponentEnum(str, Enum):
    whole_blood = "whole_blood"
    packed_red_cells = "packed_red_cells"
    platelets = "platelets"
    plasma = "plasma"


class BloodGroupEnum(str, Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


# ─── Auth ──────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int
    username: str
    role: str
    organization_id: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ─── User/Organization ─────────────────────────────────
class OrganizationBase(BaseModel):
    name: str
    type: RoleEnum
    address: Optional[str] = None
    city: str
    state: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contact_number: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: int
    is_active: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    username: str
    role: RoleEnum
    organization_id: Optional[int] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    organization_name: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Inventory ─────────────────────────────────────────
class InventoryLotBase(BaseModel):
    blood_group: BloodGroupEnum
    component: ComponentEnum
    units_total: int = Field(..., ge=0)
    units_reserved: int = Field(default=0, ge=0)
    collection_date: Optional[date] = None
    expiry_date: date
    status: str = "available"


class InventoryLotCreate(InventoryLotBase):
    blood_bank_id: int


class InventoryLotUpdate(BaseModel):
    units_total: Optional[int] = Field(None, ge=0)
    status: Optional[str] = None


class InventoryLotResponse(InventoryLotBase):
    id: int
    blood_bank_id: int
    available_units: int
    is_expired: bool
    is_available: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Emergency Requests ────────────────────────────────
class EmergencyRequestBase(BaseModel):
    blood_group: BloodGroupEnum
    component: ComponentEnum = ComponentEnum.whole_blood
    units_requested: int = Field(..., gt=0)
    urgency: UrgencyEnum
    required_by: Optional[datetime] = None
    notes: Optional[str] = None


class EmergencyRequestCreate(EmergencyRequestBase):
    hospital_id: int


class EmergencyRequestUpdate(BaseModel):
    status: Optional[RequestStatusEnum] = None


class EmergencyRequestResponse(EmergencyRequestBase):
    id: int
    reference: str
    hospital_id: int
    status: RequestStatusEnum
    is_escalated: bool
    escalated_at: Optional[datetime] = None
    is_overdue: bool
    elapsed_minutes: float
    created_at: datetime
    updated_at: datetime
    hospital_name: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Reservations ──────────────────────────────────────
class ReservationBase(BaseModel):
    request_id: int
    inventory_lot_id: int
    units_reserved: int = Field(..., gt=0)


class ReservationCreate(ReservationBase):
    pass


class ReservationResponse(ReservationBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Search/Compatibility ──────────────────────────────
class SearchRequest(BaseModel):
    blood_group: BloodGroupEnum
    component: ComponentEnum = ComponentEnum.whole_blood
    units_needed: int = Field(default=1, gt=0)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    max_radius_km: Optional[float] = None
    city_filter: Optional[str] = None
    max_results: int = 25


class CandidateLot(BaseModel):
    lot_id: int
    blood_bank_id: int
    blood_bank_name: str
    city: str
    state: str
    blood_group: str
    component: str
    match_type: str
    available_units: int
    expiry_date: date
    distance_km: Optional[float] = None


# ─── Transfers ─────────────────────────────────────────
class TransferStatusEnum(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    in_transit = "in_transit"
    received = "received"


class TransferRequestBase(BaseModel):
    blood_group: BloodGroupEnum
    component: ComponentEnum
    units: int = Field(..., gt=0)
    notes: Optional[str] = None


class TransferRequestCreate(TransferRequestBase):
    requesting_org_id: int
    supplying_org_id: int


class TransferRequestResponse(TransferRequestBase):
    id: int
    reference: str
    requesting_org_id: int
    supplying_org_id: int
    status: TransferStatusEnum
    created_at: datetime
    updated_at: datetime
    requesting_org_name: Optional[str] = None
    supplying_org_name: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Donors ────────────────────────────────────────────
class DonorBase(BaseModel):
    blood_group: BloodGroupEnum
    phone: str
    city: str
    last_donation_date: Optional[date] = None
    consent: bool = True
    active: bool = True


class DonorCreate(DonorBase):
    organization_id: int
    name: str


class DonorResponse(DonorBase):
    id: int
    organization_id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Pagination ────────────────────────────────────────
class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int