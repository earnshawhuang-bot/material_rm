"""Dashboard overview API for the GM homepage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, literal
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import inventory_service
from ..services.plant_service import build_plant_group_expr

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

IDR_TO_CNY = 2300
TOP_SUPPLIER_LIMIT = 8


def _cost_as_cny(cost_col, currency_col):
    return case((currency_col == "IDR", cost_col / IDR_TO_CNY), else_=cost_col)


def _reason_group_expr(desc_col):
    """强制熵减：仅输出两类原因。"""
    desc = func.coalesce(desc_col, "")
    return case(
        (desc.like("%原材料过期%"), literal("超期")),
        (desc.like("%库存逾期%"), literal("超期")),
        else_=literal("质量不良"),
    )


def _to_tons(weight_kg: float | int | None) -> int:
    return int(round(float(weight_kg or 0) / 1000))


def _to_amount(amount_cny: float | int | None) -> float:
    return round(float(amount_cny or 0), 2)


def _ratio(part_kg: float | int | None, total_kg: float | int | None) -> int:
    part = float(part_kg or 0)
    total = float(total_kg or 0)
    if total <= 0:
        return 0
    return int(round(part / total * 100))


def _build_item(
    *,
    name: str,
    weight_kg: float | int | None,
    amount_cny: float | int | None,
    batch_count: int | None,
    base_weight_kg: float | int | None,
) -> schemas.DashboardBreakdownItem:
    return schemas.DashboardBreakdownItem(
        name=name,
        weight_tons=_to_tons(weight_kg),
        ratio=_ratio(weight_kg, base_weight_kg),
        amount_cny=_to_amount(amount_cny),
        batch_count=int(batch_count or 0),
    )


@router.get("/overview", response_model=schemas.DashboardOverview)
def dashboard_overview(
    month: str = Query(..., description="快照月份 YYYY-MM"),
    plant: str | None = Query(None, description="工厂筛选：KS / IDN / 空=全部"),
    category_primary: str | None = Query(None, description="主分类筛选"),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    snap = models.InventorySnapshot
    act = models.BatchAction
    plant_group_expr = build_plant_group_expr(snap.plant, snap.plant_group)
    cost_cny = _cost_as_cny(snap.financial_cost, snap.currency)
    reason_expr = _reason_group_expr(snap.obsolete_reason_desc)
    matched_category_codes: set[str] | None = None
    if category_primary and category_primary.strip():
        matched_category_codes = inventory_service.resolve_material_codes_for_categories(
            db=db,
            snapshot_month=month,
            categories=[category_primary.strip()],
        )

    def apply_context_filters(query):
        query = query.filter(snap.snapshot_month == month)

        if plant:
            p = plant.strip().upper()
            if p in {"KS", "IDN"}:
                query = query.filter(plant_group_expr == p)
            else:
                query = query.filter(snap.plant == p)

        if category_primary and category_primary.strip():
            if not matched_category_codes:
                return query.filter(snap.id == -1)
            query = query.filter(snap.material_code.in_(matched_category_codes))

        return query

    # 基础总览（吨数主导，金额辅助）
    agg = apply_context_filters(
        db.query(
            func.coalesce(func.sum(snap.weight_kg), 0).label("total_kg"),
            func.coalesce(
                func.sum(case((snap.is_abnormal.is_(True), snap.weight_kg), else_=0)),
                0,
            ).label("abnormal_kg"),
            func.coalesce(func.sum(cost_cny), 0).label("total_cny"),
            func.coalesce(
                func.sum(case((snap.is_abnormal.is_(True), cost_cny), else_=0)),
                0,
            ).label("abnormal_cny"),
        )
    ).one()

    total_kg = float(agg.total_kg or 0)
    abnormal_kg = float(agg.abnormal_kg or 0)
    total_cny = float(agg.total_cny or 0)
    abnormal_cny = float(agg.abnormal_cny or 0)

    normal_kg = max(total_kg - abnormal_kg, 0.0)
    normal_cny = max(total_cny - abnormal_cny, 0.0)

    over180 = apply_context_filters(
        db.query(
            func.coalesce(func.sum(snap.weight_kg), 0).label("over_kg"),
            func.coalesce(func.sum(cost_cny), 0).label("over_cny"),
        ).filter(
            snap.is_abnormal.is_(False),
            snap.aging_category.in_(["D", "E"]),
        )
    ).one()
    over_kg = float(over180.over_kg or 0)
    over_cny = float(over180.over_cny or 0)

    # Risk Composition - 不良原因（仅两类）
    reason_rows = (
        apply_context_filters(
            db.query(
                reason_expr.label("name"),
                func.coalesce(func.sum(snap.weight_kg), 0).label("kg"),
                func.coalesce(func.sum(cost_cny), 0).label("cny"),
                func.count(snap.id).label("cnt"),
            ).filter(snap.is_abnormal.is_(True))
        )
        .group_by(reason_expr)
        .all()
    )
    reason_map = {row.name: row for row in reason_rows}
    reason_breakdown = [
        _build_item(
            name="超期",
            weight_kg=(reason_map.get("超期").kg if reason_map.get("超期") else 0),
            amount_cny=(reason_map.get("超期").cny if reason_map.get("超期") else 0),
            batch_count=(reason_map.get("超期").cnt if reason_map.get("超期") else 0),
            base_weight_kg=abnormal_kg,
        ),
        _build_item(
            name="质量不良",
            weight_kg=(reason_map.get("质量不良").kg if reason_map.get("质量不良") else 0),
            amount_cny=(reason_map.get("质量不良").cny if reason_map.get("质量不良") else 0),
            batch_count=(reason_map.get("质量不良").cnt if reason_map.get("质量不良") else 0),
            base_weight_kg=abnormal_kg,
        ),
    ]

    # Risk Composition - 不良品类
    category_rows = (
        apply_context_filters(
            db.query(
                snap.category_primary.label("name"),
                func.coalesce(func.sum(snap.weight_kg), 0).label("kg"),
                func.coalesce(func.sum(cost_cny), 0).label("cny"),
                func.count(snap.id).label("cnt"),
            ).filter(snap.is_abnormal.is_(True))
        )
        .group_by(snap.category_primary)
        .order_by(func.sum(snap.weight_kg).desc())
        .all()
    )
    category_breakdown = [
        _build_item(
            name=row.name or "未分类",
            weight_kg=row.kg,
            amount_cny=row.cny,
            batch_count=row.cnt,
            base_weight_kg=abnormal_kg,
        )
        for row in category_rows
    ]

    # 责任部门分布（不良品）
    dept_name = func.coalesce(act.responsible_dept, "未分配")
    dept_rows = (
        apply_context_filters(
            db.query(
                dept_name.label("name"),
                func.coalesce(func.sum(snap.weight_kg), 0).label("kg"),
                func.coalesce(func.sum(cost_cny), 0).label("cny"),
                func.count(snap.id).label("cnt"),
            )
            .outerjoin(
                act,
                and_(
                    act.snapshot_month == snap.snapshot_month,
                    act.batch_no == snap.batch_no,
                ),
            )
            .filter(snap.is_abnormal.is_(True))
        )
        .group_by(dept_name)
        .order_by(func.sum(snap.weight_kg).desc())
        .all()
    )
    dept_breakdown = [
        _build_item(
            name=row.name or "未分配",
            weight_kg=row.kg,
            amount_cny=row.cny,
            batch_count=row.cnt,
            base_weight_kg=abnormal_kg,
        )
        for row in dept_rows
    ]

    # 供应商风险分布（不良品 Top）
    supplier_rows = (
        apply_context_filters(
            db.query(
                snap.supplier_name.label("name"),
                func.coalesce(func.sum(snap.weight_kg), 0).label("kg"),
                func.coalesce(func.sum(cost_cny), 0).label("cny"),
                func.count(snap.id).label("cnt"),
            ).filter(
                snap.is_abnormal.is_(True),
                snap.supplier_name.isnot(None),
                snap.supplier_name != "",
            )
        )
        .group_by(snap.supplier_name)
        .order_by(func.sum(snap.weight_kg).desc())
        .limit(TOP_SUPPLIER_LIMIT)
        .all()
    )
    supplier_breakdown = [
        _build_item(
            name=row.name,
            weight_kg=row.kg,
            amount_cny=row.cny,
            batch_count=row.cnt,
            base_weight_kg=abnormal_kg,
        )
        for row in supplier_rows
    ]

    return schemas.DashboardOverview(
        total_weight_tons=_to_tons(total_kg),
        total_amount_cny=_to_amount(total_cny),
        normal_weight_tons=_to_tons(normal_kg),
        normal_amount_cny=_to_amount(normal_cny),
        abnormal_weight_tons=_to_tons(abnormal_kg),
        abnormal_amount_cny=_to_amount(abnormal_cny),
        abnormal_rate=_ratio(abnormal_kg, total_kg),
        over_180_weight_tons=_to_tons(over_kg),
        over_180_amount_cny=_to_amount(over_cny),
        over_180_rate=_ratio(over_kg, normal_kg),
        reason_breakdown=reason_breakdown,
        category_breakdown=category_breakdown,
        dept_breakdown=dept_breakdown,
        supplier_breakdown=supplier_breakdown,
    )
