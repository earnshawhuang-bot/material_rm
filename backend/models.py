"""ORM models aligned with PRD SQL definitions."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, DateTime, Integer, UniqueConstraint
from sqlalchemy import String, Date, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class InventorySnapshot(Base):
    """SAP 库存快照表（按月份+批次聚合主键）。"""

    __tablename__ = "rm_inventory_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    snapshot_month: Mapped[str] = mapped_column(String(7), index=True, nullable=False)
    batch_no: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    material_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    material_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    plant: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    plant_group: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    bin_location: Mapped[str | None] = mapped_column(String(20), nullable=True)
    storage_location: Mapped[str | None] = mapped_column(String(10), nullable=True)
    storage_loc_desc: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actual_stock: Mapped[float | None] = mapped_column(DECIMAL(18, 3))
    weight_kg: Mapped[float | None] = mapped_column(DECIMAL(18, 3))
    production_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    inbound_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quality_flag: Mapped[str | None] = mapped_column(String(1), nullable=True)
    obsolete_reason: Mapped[str | None] = mapped_column(String(10), nullable=True)
    obsolete_reason_desc: Mapped[str | None] = mapped_column(String(100), nullable=True)
    material_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    material_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    supplier_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    supplier_batch: Mapped[str | None] = mapped_column(String(50), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    aging_category: Mapped[str | None] = mapped_column(String(1), nullable=True, index=True)
    aging_description: Mapped[str | None] = mapped_column(String(50), nullable=True)
    financial_cost: Mapped[float | None] = mapped_column(DECIMAL(18, 2), nullable=True)
    production_order: Mapped[str | None] = mapped_column(String(20), nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    order_type_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoice_account: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contract_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contract_line_item: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_frozen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qc_qty: Mapped[float] = mapped_column(DECIMAL(18, 3), default=0, nullable=False)
    in_transit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str | None] = mapped_column(String(5), nullable=True)
    rm_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rm_family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_primary: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_abnormal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    abnormal_reasons: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (UniqueConstraint("snapshot_month", "batch_no"),)


class BatchAction(Base):
    """Web 端处理记录。"""

    __tablename__ = "rm_batch_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    snapshot_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    reason_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    responsible_dept: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_plan: Mapped[str | None] = mapped_column(String(500), nullable=True)
    action_status: Mapped[str | None] = mapped_column(String(20), default="待定")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    claim_weight_tons: Mapped[float | None] = mapped_column(DECIMAL(18, 3), nullable=True)
    claim_amount: Mapped[float | None] = mapped_column(DECIMAL(18, 2), nullable=True)
    claim_currency: Mapped[str | None] = mapped_column(String(5), nullable=True)
    expected_completion: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (UniqueConstraint("snapshot_month", "batch_no"),)


class MaterialMapping(Base):
    """物料主数据映射表。"""

    __tablename__ = "rm_material_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_primary: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class SysUser(Base):
    """轻量级用户表。"""

    __tablename__ = "sys_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plant: Mapped[str | None] = mapped_column(String(10), nullable=True)
    role: Mapped[str] = mapped_column(String(10), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class SysUploadLog(Base):
    """导入记录。"""

    __tablename__ = "sys_upload_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    snapshot_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    file_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rm_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    status: Mapped[str] = mapped_column(String(20), default="success")


class SysEnumConfig(Base):
    """枚举项配置（仅处理状态使用枚举）。"""

    __tablename__ = "sys_enum_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    enum_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    enum_value: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
