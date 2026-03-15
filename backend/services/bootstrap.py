"""Local-only startup bootstrap for SQLite demo."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..auth import get_password_hash
from ..config import settings
from ..database import SessionLocal
from .. import models


# 责任部门和处理方案已改为自由文本输入，不再使用枚举。
# 仅保留处理状态的枚举。
STATUS_ENUMS = ["待处理", "讨论中", "进行中", "待定", "已完成", "已关闭"]


def _seed_admin(db: Session) -> None:
    if db.query(models.SysUser).filter_by(username=settings.default_admin_username).first():
        return
    db.add(
        models.SysUser(
            username=settings.default_admin_username,
            password_hash=get_password_hash(settings.default_admin_password),
            display_name="系统管理员",
            department="IT",
            plant="3000",
            role="admin",
        )
    )


def _seed_enums(db: Session) -> None:
    """仅播种处理状态枚举。"""
    existing = db.query(models.SysEnumConfig).filter(
        models.SysEnumConfig.enum_type == "action_status"
    ).count()
    if existing > 0:
        return
    for i, value in enumerate(STATUS_ENUMS, start=1):
        db.add(
            models.SysEnumConfig(
                enum_type="action_status",
                enum_value=value,
                sort_order=i,
            )
        )


def _seed_inventory(db: Session) -> None:
    if db.query(models.InventorySnapshot).first():
        return

    db.add_all(
        [
            models.MaterialMapping(
                sku="RM-BASE-001",
                category="Paper",
                family="板材基础料",
                category_primary="Paper",
            ),
            models.MaterialMapping(
                sku="RM-AL-001",
                category="AL",
                family="外贸铝箔",
                category_primary="AL",
            ),
        ]
    )

    month = datetime.now().strftime("%Y-%m")
    db.add_all(
        [
            models.InventorySnapshot(
                snapshot_month=month,
                batch_no="BATCH-001",
                material_code="RM-BASE-001",
                material_name="EVA纸板A",
                plant="3000",
                storage_location="A01",
                storage_loc_desc="原料仓",
                bin_location="B1",
                actual_stock=1200.0,
                weight_kg=3000.0,
                financial_cost=6500.0,
                production_date=date.today() - timedelta(days=120),
                inbound_date=date.today() - timedelta(days=40),
                expiry_date=date.today() + timedelta(days=180),
                currency="CNY",
                quality_flag="N",
                aging_category="C",
                aging_description="预警",
                rm_category="Paper",
                rm_family="板材基础料",
                category_primary="Paper",
                is_abnormal=True,
                abnormal_reasons="不良品",
                supplier_code="S001",
                supplier_name="深圳供应商A",
                is_frozen=1,
                qc_qty=12.0,
                in_transit=0,
            ),
            models.InventorySnapshot(
                snapshot_month=month,
                batch_no="BATCH-002",
                material_code="RM-AL-001",
                material_name="AL箔卷B",
                plant="3001",
                storage_location="A02",
                storage_loc_desc="辅料仓",
                bin_location="B2",
                actual_stock=800.0,
                weight_kg=2000.0,
                financial_cost=12400.0,
                production_date=date.today() - timedelta(days=20),
                inbound_date=date.today() - timedelta(days=10),
                expiry_date=date.today() + timedelta(days=360),
                currency="CNY",
                quality_flag="Y",
                aging_category="A",
                aging_description="正常",
                rm_category="AL",
                rm_family="外贸铝箔",
                category_primary="AL",
                is_abnormal=False,
                is_frozen=0,
                qc_qty=0.0,
                in_transit=1,
            ),
        ]
    )
    db.flush()
    db.add(
        models.BatchAction(
            snapshot_month=month,
            batch_no="BATCH-001",
            responsible_dept="质量",
            action_plan="按呆滞料流程处理",
            action_status="讨论中",
            reason_note="检测到异味",
            remark="待确认原因",
            claim_amount=0.0,
            claim_currency="CNY",
            updated_by="admin",
        )
    )


def initialize_sqlite_demo() -> None:
    """Create default admin + enum data for local demo."""
    if settings.database_dialect != "sqlite" or not settings.seed_sqlite_demo:
        return

    db = SessionLocal()
    try:
        _seed_admin(db)
        _seed_enums(db)
        _seed_inventory(db)
        db.commit()
    finally:
        db.close()
