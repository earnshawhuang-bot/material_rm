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
        from_attributes = True


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
        from_attributes = True


class InventoryListResponse(BaseModel):
    items: list[InventoryItem]
    total: int
    page: int
    page_size: int


class ActionSaveRequest(BaseModel):
    snapshot_month: str
    batch_no: str
    reason_note: Optional[str] = None
    responsible_dept: Optional[str] = None
    action_plan: Optional[str] = None
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


class UserCreateRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    department: Optional[str] = None
    plant: Optional[str] = None
    role: str = "user"


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    department: Optional[str] = None
    plant: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserListResponse(BaseModel):
    items: list[UserInfo]


class ActionImportResponse(BaseModel):
    matched: int
    skipped: int
    errors: int
    error_details: list[str] = []


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


# ── Dashboard v2 — GM 决策级 ──────────────────────────

class CategoryBreakdown(BaseModel):
    name: str                # "Paper", "AL", "PE"
    weight_tons: float
    amount_cny: float        # 金额（CNY）

class AgingBreakdown(BaseModel):
    aging_category: str      # "A"~"E"
    label: str               # "≤30天", ">30-90天" …
    weight_tons: float
    amount_cny: float

class PlantBreakdown(BaseModel):
    plant_group: str         # "KS" or "IDN"
    total_weight_tons: float
    abnormal_weight_tons: float
    abnormal_rate: float     # %
    amount_cny: float

class ActionStatusBreakdown(BaseModel):
    status: str
    count: int
    weight_tons: float

class SupplierTop(BaseModel):
    supplier_name: str
    weight_tons: float
    amount_cny: float
    batch_count: int
    is_recurring: bool = False   # 上月也出现异常

class MonthlyTrend(BaseModel):
    month: str
    total_weight_tons: float
    abnormal_weight_tons: float
    abnormal_rate: float         # %
    abnormal_amount_cny: float

class NormalAgingBreakdown(BaseModel):
    """正常物料的库龄分布。"""
    aging_category: str
    label: str
    weight_tons: float
    amount_cny: float
    batch_count: int

class NormalCategoryAging(BaseModel):
    """正常物料 品类×库龄 热力图数据。"""
    category: str
    aging_category: str
    weight_tons: float

class OverdueItem(BaseModel):
    """逾期未处理批次。"""
    batch_no: str
    material_name: Optional[str] = None
    plant: Optional[str] = None
    weight_kg: Optional[float] = None
    amount_cny: Optional[float] = None
    responsible_dept: Optional[str] = None
    expected_completion: Optional[date] = None
    overdue_days: int = 0

class DeptCompletion(BaseModel):
    """责任部门完成率。"""
    dept: str
    total: int
    done: int
    rate: float   # %

class DashboardOverview(BaseModel):
    """GET /api/dashboard/overview — GM 决策级看板。"""
    # ── Layer 1: KPI 卡片 ──
    total_weight_tons: float
    abnormal_weight_tons: float
    abnormal_rate: float                        # %
    abnormal_rate_prev: Optional[float] = None  # 上月异常率
    abnormal_amount_cny: float                  # 统一 CNY
    abnormal_amount_prev: Optional[float] = None
    action_total: int
    action_done: int
    action_closure_rate: float                  # %
    claim_total_cny: float                      # 索赔总额
    claim_recovery_rate: float                  # 回收率 %
    overdue_count: int                          # 逾期未处理批次数
    overdue_amount_cny: float                   # 逾期金额
    coverage_rate: float                        # 异常批次行动覆盖率 %

    # ── Layer 2: 异常物料深度拆解 ──
    by_category: list[CategoryBreakdown]
    by_aging: list[AgingBreakdown]
    by_plant: list[PlantBreakdown]
    by_action_status: list[ActionStatusBreakdown]
    supplier_top10: list[SupplierTop]
    monthly_trend: list[MonthlyTrend]

    # ── Layer 2b: 正常物料健康度 ──
    normal_by_aging: list[NormalAgingBreakdown]
    normal_category_aging: list[NormalCategoryAging]

    # ── Layer 3: 行动追踪 ──
    overdue_items: list[OverdueItem]
    dept_completion: list[DeptCompletion]
