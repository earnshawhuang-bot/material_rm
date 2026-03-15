"""Dashboard aggregate API v2 — GM 决策级看板。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, literal
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ── 业务常量 ──────────────────────────────────────────
IDR_TO_CNY = 2300

AGING_LABELS = {
    "A": "≤30天",
    "B": ">30-90天",
    "C": ">90-180天",
    "D": ">180-360天",
    "E": ">360天",
}


def _plant_group(plant_col):
    return case((plant_col == "3301", literal("IDN")), else_=literal("KS"))


def _cost_as_cny(cost_col, currency_col):
    return case((currency_col == "IDR", cost_col / IDR_TO_CNY), else_=cost_col)


@router.get("/overview", response_model=schemas.DashboardOverview)
def dashboard_overview(
    month: str = Query(..., description="快照月份 YYYY-MM"),
    plant: str = Query(None, description="工厂筛选: KS / IDN / 空=全部"),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    snap = models.InventorySnapshot
    act = models.BatchAction

    # ── 工厂筛选条件 ──
    def plant_filter(q):
        if plant == "KS":
            return q.filter(snap.plant.in_(["3000", "3001"]))
        elif plant == "IDN":
            return q.filter(snap.plant == "3301")
        return q

    def plant_filter_act(q):
        """对 action 表做工厂筛选（需 join snapshot）。"""
        if plant:
            q = q.join(snap, and_(
                snap.snapshot_month == act.snapshot_month,
                snap.batch_no == act.batch_no,
            ))
            if plant == "KS":
                q = q.filter(snap.plant.in_(["3000", "3001"]))
            elif plant == "IDN":
                q = q.filter(snap.plant == "3301")
        return q

    cost_cny = _cost_as_cny(snap.financial_cost, snap.currency)

    # ══════════════════════════════════════════════════════
    #  Layer 1 — KPI
    # ══════════════════════════════════════════════════════

    base = db.query(
        func.coalesce(func.sum(snap.weight_kg), 0).label("total_kg"),
        func.coalesce(func.sum(case((snap.is_abnormal == True, snap.weight_kg), else_=0)), 0).label("abn_kg"),  # noqa: E712
        func.coalesce(func.sum(case((snap.is_abnormal == True, cost_cny), else_=0)), 0).label("abn_cny"),  # noqa: E712
        func.coalesce(func.sum(cost_cny), 0).label("total_cny"),
    ).filter(snap.snapshot_month == month)
    base = plant_filter(base)
    agg = base.one()

    total_weight_tons = round(float(agg.total_kg) / 1000, 1)
    abnormal_weight_tons = round(float(agg.abn_kg) / 1000, 1)
    abnormal_rate = round(abnormal_weight_tons / total_weight_tons * 100, 1) if total_weight_tons > 0 else 0.0
    abnormal_amount_cny = round(float(agg.abn_cny), 2)

    # 上月数据
    prev_months = (
        db.query(snap.snapshot_month)
        .filter(snap.snapshot_month < month)
        .distinct()
        .order_by(snap.snapshot_month.desc())
        .limit(1)
        .all()
    )
    abnormal_rate_prev = None
    abnormal_amount_prev = None
    prev_abn_suppliers = set()
    if prev_months:
        pm = prev_months[0][0]
        pm_q = db.query(
            func.coalesce(func.sum(snap.weight_kg), 0).label("t"),
            func.coalesce(func.sum(case((snap.is_abnormal == True, snap.weight_kg), else_=0)), 0).label("a"),  # noqa: E712
            func.coalesce(func.sum(case((snap.is_abnormal == True, cost_cny), else_=0)), 0).label("c"),  # noqa: E712
        ).filter(snap.snapshot_month == pm)
        pm_q = plant_filter(pm_q)
        pm_agg = pm_q.one()
        pm_total = float(pm_agg[0])
        if pm_total > 0:
            abnormal_rate_prev = round(float(pm_agg[1]) / pm_total * 100, 1)
        abnormal_amount_prev = round(float(pm_agg[2]), 2)

        # 上月异常供应商名单（用于复发标记）
        prev_sup_q = (
            db.query(snap.supplier_name)
            .filter(snap.snapshot_month == pm, snap.is_abnormal == True, snap.supplier_name.isnot(None))  # noqa: E712
            .distinct()
        )
        prev_sup_q = plant_filter(prev_sup_q)
        prev_abn_suppliers = {r[0] for r in prev_sup_q.all()}

    # 行动覆盖率 & 完成率
    abn_batch_count_q = db.query(func.count(snap.id)).filter(
        snap.snapshot_month == month, snap.is_abnormal == True  # noqa: E712
    )
    abn_batch_count_q = plant_filter(abn_batch_count_q)
    abn_batch_count = abn_batch_count_q.scalar() or 0

    if plant:
        # 有工厂筛选时，需要 join
        action_base = db.query(func.count(act.id)).join(snap, and_(
            snap.snapshot_month == act.snapshot_month, snap.batch_no == act.batch_no,
        )).filter(act.snapshot_month == month)
        if plant == "KS":
            action_base = action_base.filter(snap.plant.in_(["3000", "3001"]))
        elif plant == "IDN":
            action_base = action_base.filter(snap.plant == "3301")
        action_total = action_base.scalar() or 0

        action_done_q = db.query(func.count(act.id)).join(snap, and_(
            snap.snapshot_month == act.snapshot_month, snap.batch_no == act.batch_no,
        )).filter(
            act.snapshot_month == month,
            act.action_status.in_(["已完成", "已关闭"]),
        )
        if plant == "KS":
            action_done_q = action_done_q.filter(snap.plant.in_(["3000", "3001"]))
        elif plant == "IDN":
            action_done_q = action_done_q.filter(snap.plant == "3301")
        action_done = action_done_q.scalar() or 0
    else:
        action_total = db.query(func.count(act.id)).filter(act.snapshot_month == month).scalar() or 0
        action_done = db.query(func.count(act.id)).filter(
            act.snapshot_month == month, act.action_status.in_(["已完成", "已关闭"])
        ).scalar() or 0

    action_closure_rate = round(action_done / action_total * 100, 1) if action_total > 0 else 0.0
    coverage_rate = round(action_total / abn_batch_count * 100, 1) if abn_batch_count > 0 else 0.0

    # 索赔
    claim_q = db.query(
        func.coalesce(func.sum(
            case(
                (act.claim_currency == "IDR", act.claim_amount / IDR_TO_CNY),
                else_=act.claim_amount,
            )
        ), 0)
    ).filter(act.snapshot_month == month, act.claim_amount.isnot(None))
    if plant:
        claim_q = claim_q.join(snap, and_(
            snap.snapshot_month == act.snapshot_month, snap.batch_no == act.batch_no,
        ))
        if plant == "KS":
            claim_q = claim_q.filter(snap.plant.in_(["3000", "3001"]))
        elif plant == "IDN":
            claim_q = claim_q.filter(snap.plant == "3301")
    claim_total_cny = round(float(claim_q.scalar() or 0), 2)
    claim_recovery_rate = round(claim_total_cny / abnormal_amount_cny * 100, 1) if abnormal_amount_cny > 0 else 0.0

    # 逾期未处理
    today = date.today()
    overdue_q = (
        db.query(
            act.batch_no,
            snap.material_name,
            snap.plant,
            snap.weight_kg,
            cost_cny.label("cny"),
            act.responsible_dept,
            act.expected_completion,
        )
        .join(snap, and_(snap.snapshot_month == act.snapshot_month, snap.batch_no == act.batch_no))
        .filter(
            act.snapshot_month == month,
            act.expected_completion < today,
            ~act.action_status.in_(["已完成", "已关闭"]),
        )
    )
    if plant == "KS":
        overdue_q = overdue_q.filter(snap.plant.in_(["3000", "3001"]))
    elif plant == "IDN":
        overdue_q = overdue_q.filter(snap.plant == "3301")
    overdue_q = overdue_q.order_by(cost_cny.desc()).limit(20)
    overdue_rows = overdue_q.all()

    overdue_items = []
    overdue_amount_cny = 0.0
    for r in overdue_rows:
        amt = round(float(r.cny or 0), 2)
        overdue_amount_cny += amt
        od = (today - r.expected_completion).days if r.expected_completion else 0
        overdue_items.append(schemas.OverdueItem(
            batch_no=r.batch_no,
            material_name=r.material_name,
            plant=r.plant,
            weight_kg=float(r.weight_kg) if r.weight_kg else None,
            amount_cny=amt,
            responsible_dept=r.responsible_dept,
            expected_completion=r.expected_completion,
            overdue_days=od,
        ))
    overdue_count = len(overdue_items)
    overdue_amount_cny = round(overdue_amount_cny, 2)

    # ══════════════════════════════════════════════════════
    #  Layer 2a — 异常物料深度拆解
    # ══════════════════════════════════════════════════════

    # 按品类（金额+重量）
    cat_q = db.query(
        snap.category_primary,
        func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
        func.coalesce(func.sum(cost_cny), 0).label("c"),
    ).filter(snap.snapshot_month == month, snap.is_abnormal == True).group_by(snap.category_primary)  # noqa: E712
    cat_q = plant_filter(cat_q)
    by_category = [
        schemas.CategoryBreakdown(
            name=r.category_primary or "未分类",
            weight_tons=round(float(r.w) / 1000, 1),
            amount_cny=round(float(r.c), 2),
        )
        for r in cat_q.all()
    ]
    by_category.sort(key=lambda x: x.amount_cny, reverse=True)

    # 按库龄（异常）
    aging_q = db.query(
        snap.aging_category,
        func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
        func.coalesce(func.sum(cost_cny), 0).label("c"),
    ).filter(snap.snapshot_month == month, snap.is_abnormal == True).group_by(snap.aging_category).order_by(snap.aging_category)  # noqa: E712
    aging_q = plant_filter(aging_q)
    by_aging = [
        schemas.AgingBreakdown(
            aging_category=r.aging_category or "?",
            label=AGING_LABELS.get(r.aging_category, "?"),
            weight_tons=round(float(r.w) / 1000, 1),
            amount_cny=round(float(r.c), 2),
        )
        for r in aging_q.all()
    ]

    # 按工厂对标
    pg = _plant_group(snap.plant)
    plant_q = db.query(
        pg.label("pg"),
        func.coalesce(func.sum(snap.weight_kg), 0).label("total_w"),
        func.coalesce(func.sum(case((snap.is_abnormal == True, snap.weight_kg), else_=0)), 0).label("abn_w"),  # noqa: E712
        func.coalesce(func.sum(case((snap.is_abnormal == True, cost_cny), else_=0)), 0).label("abn_cost"),  # noqa: E712
    ).filter(snap.snapshot_month == month).group_by(pg)
    # 工厂对标不受筛选器影响（始终显示两工厂对比）
    by_plant = [
        schemas.PlantBreakdown(
            plant_group=r.pg,
            total_weight_tons=round(float(r.total_w) / 1000, 1),
            abnormal_weight_tons=round(float(r.abn_w) / 1000, 1),
            abnormal_rate=round(float(r.abn_w) / float(r.total_w) * 100, 1) if float(r.total_w) > 0 else 0.0,
            amount_cny=round(float(r.abn_cost), 2),
        )
        for r in plant_q.all()
    ]

    # 处理状态
    status_q = (
        db.query(
            act.action_status,
            func.count(act.id).label("cnt"),
            func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
        )
        .join(snap, and_(snap.snapshot_month == act.snapshot_month, snap.batch_no == act.batch_no))
        .filter(act.snapshot_month == month)
        .group_by(act.action_status)
    )
    if plant == "KS":
        status_q = status_q.filter(snap.plant.in_(["3000", "3001"]))
    elif plant == "IDN":
        status_q = status_q.filter(snap.plant == "3301")
    by_action_status = [
        schemas.ActionStatusBreakdown(
            status=r.action_status or "未分配",
            count=r.cnt,
            weight_tons=round(float(r.w) / 1000, 1),
        )
        for r in status_q.all()
    ]

    # 供应商 Top10
    sup_q = db.query(
        snap.supplier_name,
        func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
        func.coalesce(func.sum(cost_cny), 0).label("c"),
        func.count(snap.id).label("cnt"),
    ).filter(snap.snapshot_month == month, snap.is_abnormal == True, snap.supplier_name.isnot(None))  # noqa: E712
    sup_q = plant_filter(sup_q)
    sup_q = sup_q.group_by(snap.supplier_name).order_by(func.sum(cost_cny).desc()).limit(10)
    supplier_top10 = [
        schemas.SupplierTop(
            supplier_name=r.supplier_name,
            weight_tons=round(float(r.w) / 1000, 1),
            amount_cny=round(float(r.c), 2),
            batch_count=r.cnt,
            is_recurring=r.supplier_name in prev_abn_suppliers,
        )
        for r in sup_q.all()
    ]

    # 月度趋势
    trend_q = db.query(
        snap.snapshot_month,
        func.coalesce(func.sum(snap.weight_kg), 0).label("total_kg"),
        func.coalesce(func.sum(case((snap.is_abnormal == True, snap.weight_kg), else_=0)), 0).label("abn_kg"),  # noqa: E712
        func.coalesce(func.sum(case((snap.is_abnormal == True, cost_cny), else_=0)), 0).label("abn_cny"),  # noqa: E712
    )
    trend_q = plant_filter(trend_q)
    trend_q = trend_q.group_by(snap.snapshot_month).order_by(snap.snapshot_month)
    monthly_trend = [
        schemas.MonthlyTrend(
            month=r.snapshot_month,
            total_weight_tons=round(float(r.total_kg) / 1000, 1),
            abnormal_weight_tons=round(float(r.abn_kg) / 1000, 1),
            abnormal_rate=round(float(r.abn_kg) / float(r.total_kg) * 100, 1) if float(r.total_kg) > 0 else 0.0,
            abnormal_amount_cny=round(float(r.abn_cny), 2),
        )
        for r in trend_q.all()
    ]

    # ══════════════════════════════════════════════════════
    #  Layer 2b — 正常物料健康度
    # ══════════════════════════════════════════════════════

    norm_aging_q = db.query(
        snap.aging_category,
        func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
        func.coalesce(func.sum(cost_cny), 0).label("c"),
        func.count(snap.id).label("cnt"),
    ).filter(snap.snapshot_month == month, snap.is_abnormal == False).group_by(snap.aging_category).order_by(snap.aging_category)  # noqa: E712
    norm_aging_q = plant_filter(norm_aging_q)
    normal_by_aging = [
        schemas.NormalAgingBreakdown(
            aging_category=r.aging_category or "?",
            label=AGING_LABELS.get(r.aging_category, "?"),
            weight_tons=round(float(r.w) / 1000, 1),
            amount_cny=round(float(r.c), 2),
            batch_count=r.cnt,
        )
        for r in norm_aging_q.all()
    ]

    # 品类×库龄 热力图
    ca_q = db.query(
        snap.category_primary,
        snap.aging_category,
        func.coalesce(func.sum(snap.weight_kg), 0).label("w"),
    ).filter(
        snap.snapshot_month == month, snap.is_abnormal == False,  # noqa: E712
        snap.category_primary.isnot(None),
    ).group_by(snap.category_primary, snap.aging_category)
    ca_q = plant_filter(ca_q)
    normal_category_aging = [
        schemas.NormalCategoryAging(
            category=r.category_primary,
            aging_category=r.aging_category or "?",
            weight_tons=round(float(r.w) / 1000, 1),
        )
        for r in ca_q.all()
    ]

    # ══════════════════════════════════════════════════════
    #  Layer 3 — 行动追踪
    # ══════════════════════════════════════════════════════

    dept_q = (
        db.query(
            act.responsible_dept,
            func.count(act.id).label("total"),
            func.sum(case((act.action_status.in_(["已完成", "已关闭"]), 1), else_=0)).label("done"),
        )
        .filter(act.snapshot_month == month, act.responsible_dept.isnot(None))
        .group_by(act.responsible_dept)
    )
    if plant:
        dept_q = dept_q.join(snap, and_(
            snap.snapshot_month == act.snapshot_month, snap.batch_no == act.batch_no,
        ))
        if plant == "KS":
            dept_q = dept_q.filter(snap.plant.in_(["3000", "3001"]))
        elif plant == "IDN":
            dept_q = dept_q.filter(snap.plant == "3301")
    dept_completion = [
        schemas.DeptCompletion(
            dept=r.responsible_dept,
            total=r.total,
            done=int(r.done),
            rate=round(int(r.done) / r.total * 100, 1) if r.total > 0 else 0.0,
        )
        for r in dept_q.all()
    ]
    dept_completion.sort(key=lambda x: x.rate)

    return schemas.DashboardOverview(
        total_weight_tons=total_weight_tons,
        abnormal_weight_tons=abnormal_weight_tons,
        abnormal_rate=abnormal_rate,
        abnormal_rate_prev=abnormal_rate_prev,
        abnormal_amount_cny=abnormal_amount_cny,
        abnormal_amount_prev=abnormal_amount_prev,
        action_total=action_total,
        action_done=action_done,
        action_closure_rate=action_closure_rate,
        claim_total_cny=claim_total_cny,
        claim_recovery_rate=claim_recovery_rate,
        overdue_count=overdue_count,
        overdue_amount_cny=overdue_amount_cny,
        coverage_rate=coverage_rate,
        by_category=by_category,
        by_aging=by_aging,
        by_plant=by_plant,
        by_action_status=by_action_status,
        supplier_top10=supplier_top10,
        monthly_trend=monthly_trend,
        normal_by_aging=normal_by_aging,
        normal_category_aging=normal_category_aging,
        overdue_items=overdue_items,
        dept_completion=dept_completion,
    )
