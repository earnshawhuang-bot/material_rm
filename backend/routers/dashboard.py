"""Dashboard aggregate API — 一次请求返回全部可视化数据。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, literal
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ── 业务常量 ──────────────────────────────────────────
IDR_TO_CNY = 2300  # 固定汇率：1 CNY = 2,300 IDR

AGING_LABELS = {
    "A": "≤30天",
    "B": ">30-90天",
    "C": ">90-180天",
    "D": ">180-360天",
    "E": ">360天",
}


def _plant_group(plant_col):
    """Plant 3000/3001 → 'KS', 3301 → 'IDN'."""
    return case(
        (plant_col == "3301", literal("IDN")),
        else_=literal("KS"),
    )


def _cost_as_cny(cost_col, currency_col):
    """financial_cost 统一换算为 CNY：IDR / 2300，其余原值。"""
    return case(
        (currency_col == "IDR", cost_col / IDR_TO_CNY),
        else_=cost_col,
    )


@router.get("/overview", response_model=schemas.DashboardOverview)
def dashboard_overview(
    month: str = Query(..., description="快照月份 YYYY-MM"),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    snap = models.InventorySnapshot
    act = models.BatchAction

    # ══════════════════════════════════════════════════
    #  Zone 1 — KPI 指标卡
    # ══════════════════════════════════════════════════

    # 总重量 & 异常重量（吨）
    weight_agg = (
        db.query(
            func.coalesce(func.sum(snap.weight_kg), 0).label("total_kg"),
            func.coalesce(
                func.sum(case((snap.is_abnormal == True, snap.weight_kg), else_=0)), 0  # noqa: E712
            ).label("abnormal_kg"),
        )
        .filter(snap.snapshot_month == month)
        .one()
    )
    total_weight_tons = round(float(weight_agg.total_kg) / 1000, 1)
    abnormal_weight_tons = round(float(weight_agg.abnormal_kg) / 1000, 1)
    abnormal_rate = round(abnormal_weight_tons / total_weight_tons * 100, 1) if total_weight_tons > 0 else 0.0

    # 上月异常率（按重量）
    prev_months = (
        db.query(snap.snapshot_month)
        .filter(snap.snapshot_month < month)
        .distinct()
        .order_by(snap.snapshot_month.desc())
        .limit(1)
        .all()
    )
    abnormal_rate_prev = None
    if prev_months:
        pm = prev_months[0][0]
        pm_agg = (
            db.query(
                func.coalesce(func.sum(snap.weight_kg), 0).label("t"),
                func.coalesce(
                    func.sum(case((snap.is_abnormal == True, snap.weight_kg), else_=0)), 0  # noqa: E712
                ).label("a"),
            )
            .filter(snap.snapshot_month == pm)
            .one()
        )
        pm_total = float(pm_agg.t)
        if pm_total > 0:
            abnormal_rate_prev = round(float(pm_agg.a) / pm_total * 100, 1)

    # 异常金额统一为 CNY
    cost_cny = _cost_as_cny(snap.financial_cost, snap.currency)
    abnormal_amount_cny_raw = (
        db.query(func.coalesce(func.sum(cost_cny), 0))
        .filter(snap.snapshot_month == month, snap.is_abnormal == True)  # noqa: E712
        .scalar()
    )
    abnormal_amount_cny = round(float(abnormal_amount_cny_raw), 2)

    # 行动项完成率
    action_total = (
        db.query(func.count(act.id))
        .filter(act.snapshot_month == month)
        .scalar() or 0
    )
    action_done = (
        db.query(func.count(act.id))
        .filter(act.snapshot_month == month, act.action_status.in_(["已完成", "已关闭"]))
        .scalar() or 0
    )
    action_closure_rate = round(action_done / action_total * 100, 1) if action_total > 0 else 0.0

    # ══════════════════════════════════════════════════
    #  Zone 2 — 分布图
    # ══════════════════════════════════════════════════

    # 按 RM 类型（category_primary）
    cat_rows = (
        db.query(
            snap.category_primary,
            func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
        )
        .filter(snap.snapshot_month == month, snap.is_abnormal == True)  # noqa: E712
        .group_by(snap.category_primary)
        .all()
    )
    by_category = [
        schemas.CategoryBreakdown(
            name=r.category_primary or "Unknown",
            weight_tons=round(float(r.w) / 1000, 1),
        )
        for r in cat_rows
    ]

    # 按库龄
    aging_rows = (
        db.query(
            snap.aging_category,
            func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
        )
        .filter(snap.snapshot_month == month, snap.is_abnormal == True)  # noqa: E712
        .group_by(snap.aging_category)
        .order_by(snap.aging_category)
        .all()
    )
    by_aging = [
        schemas.AgingBreakdown(
            aging_category=r.aging_category or "?",
            label=AGING_LABELS.get(r.aging_category, r.aging_category or "?"),
            weight_tons=round(float(r.w) / 1000, 1),
        )
        for r in aging_rows
    ]

    # 按工厂（KS vs IDN）
    pg = _plant_group(snap.plant)
    plant_rows = (
        db.query(
            pg.label("pg"),
            func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
            func.coalesce(func.sum(cost_cny), 0).label("cost"),
        )
        .filter(snap.snapshot_month == month, snap.is_abnormal == True)  # noqa: E712
        .group_by(pg)
        .all()
    )
    by_plant = [
        schemas.PlantBreakdown(
            plant_group=r.pg,
            weight_tons=round(float(r.w) / 1000, 1),
            amount_cny=round(float(r.cost), 2),
        )
        for r in plant_rows
    ]

    # 按处理状态（关联异常批次重量）
    status_rows = (
        db.query(
            act.action_status,
            func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
        )
        .join(snap, and_(
            snap.snapshot_month == act.snapshot_month,
            snap.batch_no == act.batch_no,
        ))
        .filter(act.snapshot_month == month)
        .group_by(act.action_status)
        .all()
    )
    by_action_status = [
        schemas.ActionStatusBreakdown(
            status=r.action_status or "未分配",
            weight_tons=round(float(r.w) / 1000, 1),
        )
        for r in status_rows
    ]

    # ══════════════════════════════════════════════════
    #  Zone 3 — 详情
    # ══════════════════════════════════════════════════

    # 供应商 Top 10（按异常重量）
    supplier_rows = (
        db.query(
            snap.supplier_name,
            func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
        )
        .filter(
            snap.snapshot_month == month,
            snap.is_abnormal == True,  # noqa: E712
            snap.supplier_name.isnot(None),
        )
        .group_by(snap.supplier_name)
        .order_by(func.sum(snap.weight_kg).desc())
        .limit(10)
        .all()
    )
    supplier_top10 = [
        schemas.SupplierTop(
            supplier_name=r.supplier_name,
            weight_tons=round(float(r.w) / 1000, 1),
        )
        for r in supplier_rows
    ]

    # 月度趋势（全部月份）
    trend_rows = (
        db.query(
            snap.snapshot_month,
            func.coalesce(func.sum(snap.weight_kg), 0).label("total_kg"),
            func.coalesce(
                func.sum(case((snap.is_abnormal == True, snap.weight_kg), else_=0)), 0  # noqa: E712
            ).label("abn_kg"),
        )
        .group_by(snap.snapshot_month)
        .order_by(snap.snapshot_month)
        .all()
    )
    monthly_trend = [
        schemas.MonthlyTrend(
            month=r.snapshot_month,
            abnormal_weight_tons=round(float(r.abn_kg) / 1000, 1),
            abnormal_rate=round(float(r.abn_kg) / float(r.total_kg) * 100, 1) if float(r.total_kg) > 0 else 0.0,
        )
        for r in trend_rows
    ]

    return schemas.DashboardOverview(
        total_weight_tons=total_weight_tons,
        abnormal_weight_tons=abnormal_weight_tons,
        abnormal_rate=abnormal_rate,
        abnormal_rate_prev=abnormal_rate_prev,
        abnormal_amount_cny=abnormal_amount_cny,
        action_total=action_total,
        action_done=action_done,
        action_closure_rate=action_closure_rate,
        by_category=by_category,
        by_aging=by_aging,
        by_plant=by_plant,
        by_action_status=by_action_status,
        supplier_top10=supplier_top10,
        monthly_trend=monthly_trend,
    )
