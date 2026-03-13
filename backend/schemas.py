"""Pydantic request / response schema."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    department: Optional[str] = None
    plant: Optional[str] = None
    role: str = "user"
    is_active: bool = True

    class Config:
        orm_mode = True


class UploadResponse(BaseModel):
    snapshot_month: str
    rm_type: str
    file_name: str
    row_count: int
    abnormal_count: int


class InventoryFilterParams(BaseModel):
    snapshot_month: str
    plant: Optional[str] = None
    category_primary: Optional[str] = None   # replaces rm_category for user-facing filter
    aging_category: Optional[str] = None
    is_abnormal: Optional[bool] = None
    quality_flag: Optional[str] = None
    material_code: Optional[str] = None
    supplier_name: Optional[str] = None
    keyword: Optional[str] = None
    page: int = 1
    page_size: int = 50
    sort_by: Optional[str] = "created_at"
    sort_order: str = "desc"


class InventoryItem(BaseModel):
    snapshot_month: str
    batch_no: str
    material_code: Optional[str]
    material_name: Optional[str]
    plant: Optional[str]
    storage_location: Optional[str]
    storage_loc_desc: Optional[str]
    bin_location: Optional[str]
    actual_stock: Optional[float]
    weight_kg: Optional[float]
    financial_cost: Optional[float]
    production_date: Optional[date]
    inbound_date: Optional[date]
    expiry_date: Optional[date]
    quality_flag: Optional[str] = None
    obsolete_reason: Optional[str] = None
    obsolete_reason_desc: Optional[str] = None
    material_group: Optional[str] = None
    material_type: Optional[str] = None
    unit: Optional[str] = None
    supplier_code: Optional[str] = None
    supplier_batch: Optional[str] = None
    supplier_name: Optional[str] = None
    aging_category: Optional[str]
    aging_description: Optional[str]
    rm_category: Optional[str]
    rm_family: Optional[str]
    category_primary: Optional[str]
    currency: Optional[str]
    is_abnormal: bool = False
    abnormal_reasons: Optional[str] = None
    reason_note: Optional[str] = None
    responsible_dept: Optional[str] = None
    action_plan: Optional[str] = None
    action_status: Optional[str] = None
    remark: Optional[str] = None
    claim_amount: Optional[float] = None
    claim_currency: Optional[str] = None
    expected_completion: Optional[date] = None

    class Config:
        orm_mode = True


class InventoryListResponse(BaseModel):
    items: list[InventoryItem]
    total: int
    page: int
    page_size: int


class ActionSaveRequest(BaseModel):
    snapshot_month: str
    batch_no: str
    reason_note: Optional[str] = None
    responsible_dept: str
    action_plan: str
    action_status: str
    remark: Optional[str] = None
    claim_amount: Optional[float] = None
    claim_currency: Optional[str] = None
    expected_completion: Optional[date] = None


class ActionItem(BaseModel):
    snapshot_month: str
    batch_no: str
    reason_note: Optional[str] = None
    responsible_dept: Optional[str] = None
    action_plan: Optional[str] = None
    action_status: Optional[str] = None
    remark: Optional[str] = None
    claim_amount: Optional[float] = None
    claim_currency: Optional[str] = None
    expected_completion: Optional[date] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class EnumItem(BaseModel):
    enum_type: str
    enum_value: str
    sort_order: int = 0
    is_active: bool = True


class EnumListResponse(BaseModel):
    items: list[EnumItem]


class MaterialMappingItem(BaseModel):
    id: int | None = None
    sku: str
    category: Optional[str] = None
    family: Optional[str] = None
    category_primary: Optional[str] = None
    updated_at: Optional[datetime] = None


class MaterialMappingListResponse(BaseModel):
    items: list[MaterialMappingItem]


class MaterialMappingUploadResponse(BaseModel):
    file_name: str
    row_count: int
    replaced: bool


class StatsResponse(BaseModel):
    total: int = 0
    total_weight: float = 0.0
    defective: int = 0
    defective_weight: float = 0.0
    pending: int = 0
    pending_weight: float = 0.0
    done: int = 0
    done_weight: float = 0.0
    completion_rate: float = 0.0   # done / defective * 100, 0 if no defectives
