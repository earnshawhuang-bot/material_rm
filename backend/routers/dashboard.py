"""Dashboard overview API for the GM homepage."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, literal, or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import inventory_service
from ..services.action_service import normalize_action_status
from ..services.plant_service import build_plant_group_expr

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

IDR_TO_CNY = 2300
TOP_SUPPLIER_LIMIT = 8
TOP_PRIORITY_LIMIT = 5
STATUS_DISPLAY_ORDER = ["待定", "进行中", "已完成"]


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


def _normalize_status_label(raw_status: str | None) -> str:
    return normalize_action_status(raw_status)


def _normalize_dept_label(raw_dept: str | None) -> str:
    text = str(raw_dept or "").strip()
    if not text:
        return "未分配"

    parts = [part.strip() for part in re.split(r"[/、,，;；]+", text) if part and part.strip()]
    if not parts:
        return "未分配"

    alias_map = {
        "品质": "质量",
        "品保": "质量",
        "研发部": "研发",
        "质量部": "质量",
    }

    normalized_parts: list[str] = []
    for part in parts:
        normalized = alias_map.get(part, part)
        if normalized.endswith("部") and len(normalized) > 1:
            normalized = normalized[:-1]
        normalized_parts.append(normalized)

    unique_sorted = sorted(set(normalized_parts))
    return "/".join(unique_sorted) if unique_sorted else "未分配"


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
    action_join_expr = and_(
        act.snapshot_month == snap.snapshot_month,
        act.batch_no == snap.batch_no,
    )
    status_expr = case(
        (
            or_(
                func.trim(func.coalesce(act.action_status, "")) == "",
                act.action_status.in_(["待处理", "待定"]),
                func.lower(func.trim(func.coalesce(act.action_status, ""))) == "pending",
            ),
            literal("待定"),
        ),
        (
            or_(
                act.action_status.in_(["进行中", "讨论中"]),
                func.lower(func.trim(func.coalesce(act.action_status, ""))) == "in progress",
            ),
            literal("进行中"),
        ),
        (
            or_(
                act.action_status.in_(["已完成", "已关闭"]),
                func.lower(func.trim(func.coalesce(act.action_status, ""))).in_(["done", "completed"]),
            ),
            literal("已完成"),
        ),
        else_=literal("待定"),
    )
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

    abnormal_over_90 = apply_context_filters(
        db.query(
            func.coalesce(func.sum(snap.weight_kg), 0).label("over_kg"),
            func.coalesce(func.sum(cost_cny), 0).label("over_cny"),
        ).filter(
            snap.is_abnormal.is_(True),
            snap.aging_category.in_(["C", "D", "E"]),
        )
    ).one()
    abnormal_over_90_kg = float(abnormal_over_90.over_kg or 0)
    abnormal_over_90_cny = float(abnormal_over_90.over_cny or 0)

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
            .outerjoin(act, action_join_expr)
            .filter(snap.is_abnormal.is_(True))
        )
        .group_by(dept_name)
        .order_by(func.sum(snap.weight_kg).desc())
        .all()
    )
    merged_dept: dict[str, dict[str, float | int]] = {}
    for row in dept_rows:
        key = _normalize_dept_label(row.name)
        item = merged_dept.setdefault(
            key,
            {"kg": 0.0, "cny": 0.0, "cnt": 0},
        )
        item["kg"] = float(item["kg"]) + float(row.kg or 0)
        item["cny"] = float(item["cny"]) + float(row.cny or 0)
        item["cnt"] = int(item["cnt"]) + int(row.cnt or 0)
    merged_dept_rows = sorted(
        merged_dept.items(),
        key=lambda kv: float(kv[1]["kg"]),
        reverse=True,
    )
    dept_breakdown = [
        _build_item(
            name=dept_name_text,
            weight_kg=agg_map["kg"],
            amount_cny=agg_map["cny"],
            batch_count=agg_map["cnt"],
            base_weight_kg=abnormal_kg,
        )
        for dept_name_text, agg_map in merged_dept_rows
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

    # 执行状态分布（不良品）
    status_rows = (
        apply_context_filters(
            db.query(
                status_expr.label("name"),
                func.coalesce(func.sum(snap.weight_kg), 0).label("kg"),
                func.coalesce(func.sum(cost_cny), 0).label("cny"),
                func.count(snap.id).label("cnt"),
            )
            .outerjoin(act, action_join_expr)
            .filter(snap.is_abnormal.is_(True))
        )
        .group_by(status_expr)
        .all()
    )
    status_map = {str(row.name or "").strip(): row for row in status_rows}
    status_breakdown = [
        _build_item(
            name=status_name,
            weight_kg=(status_map.get(status_name).kg if status_map.get(status_name) else 0),
            amount_cny=(status_map.get(status_name).cny if status_map.get(status_name) else 0),
            batch_count=(status_map.get(status_name).cnt if status_map.get(status_name) else 0),
            base_weight_kg=abnormal_kg,
        )
        for status_name in STATUS_DISPLAY_ORDER
    ]

    pending_row = status_map.get("待定")
    in_progress_row = status_map.get("进行中")
    done_row = status_map.get("已完成")

    pending_kg = float(pending_row.kg or 0) if pending_row else 0.0
    pending_cny = float(pending_row.cny or 0) if pending_row else 0.0
    pending_cnt = int(pending_row.cnt or 0) if pending_row else 0

    in_progress_kg = float(in_progress_row.kg or 0) if in_progress_row else 0.0
    in_progress_cny = float(in_progress_row.cny or 0) if in_progress_row else 0.0
    in_progress_cnt = int(in_progress_row.cnt or 0) if in_progress_row else 0

    done_kg = float(done_row.kg or 0) if done_row else 0.0
    done_cny = float(done_row.cny or 0) if done_row else 0.0
    done_cnt = int(done_row.cnt or 0) if done_row else 0

    # Top 动作清单：优先看未分配 + 待定 + 超期 + 吨数大的批次
    priority_rows = apply_context_filters(
        db.query(
            snap.batch_no.label("batch_no"),
            snap.material_code.label("material_code"),
            snap.material_name.label("material_name"),
            snap.supplier_name.label("supplier_name"),
            reason_expr.label("reason"),
            func.coalesce(act.responsible_dept, "").label("responsible_dept"),
            status_expr.label("action_status"),
            func.coalesce(snap.weight_kg, 0).label("kg"),
            func.coalesce(cost_cny, 0).label("cny"),
        )
        .outerjoin(act, action_join_expr)
        .filter(snap.is_abnormal.is_(True))
    ).all()

    priority_candidates: list[dict[str, object]] = []
    for row in priority_rows:
        normalized_status = _normalize_status_label(row.action_status)
        if normalized_status == "已完成":
            continue
        dept_text = str(row.responsible_dept or "").strip()
        reason_text = str(row.reason or "质量不良").strip() or "质量不良"
        weight_kg = float(row.kg or 0)
        amount_cny = float(row.cny or 0)
        priority_candidates.append(
            {
                "sort_key": (
                    0 if not dept_text else 1,
                    0 if normalized_status == "待定" else 1,
                    0 if reason_text == "超期" else 1,
                    -weight_kg,
                    str(row.batch_no or ""),
                ),
                "batch_no": str(row.batch_no or ""),
                "material_code": row.material_code,
                "material_name": row.material_name,
                "supplier_name": row.supplier_name,
                "reason": reason_text,
                "responsible_dept": dept_text or "未分配",
                "action_status": normalized_status,
                "weight_kg": weight_kg,
                "amount_cny": amount_cny,
            }
        )
    priority_candidates.sort(key=lambda x: x["sort_key"])
    priority_actions = [
        schemas.DashboardPriorityActionItem(
            batch_no=str(item["batch_no"]),
            material_code=str(item["material_code"] or "") or None,
            material_name=str(item["material_name"] or "") or None,
            supplier_name=str(item["supplier_name"] or "") or None,
            reason=str(item["reason"]),
            responsible_dept=str(item["responsible_dept"]),
            action_status=str(item["action_status"]),
            weight_tons=_to_tons(item["weight_kg"]),
            amount_cny=_to_amount(item["amount_cny"]),
        )
        for item in priority_candidates[:TOP_PRIORITY_LIMIT]
    ]

    return schemas.DashboardOverview(
        total_weight_tons=_to_tons(total_kg),
        total_amount_cny=_to_amount(total_cny),
        normal_weight_tons=_to_tons(normal_kg),
        normal_amount_cny=_to_amount(normal_cny),
        abnormal_weight_tons=_to_tons(abnormal_kg),
        abnormal_amount_cny=_to_amount(abnormal_cny),
        abnormal_rate=_ratio(abnormal_kg, total_kg),
        abnormal_over_90_weight_tons=_to_tons(abnormal_over_90_kg),
        abnormal_over_90_amount_cny=_to_amount(abnormal_over_90_cny),
        abnormal_over_90_rate=_ratio(abnormal_over_90_kg, abnormal_kg),
        over_180_weight_tons=_to_tons(over_kg),
        over_180_amount_cny=_to_amount(over_cny),
        over_180_rate=_ratio(over_kg, normal_kg),
        pending_weight_tons=_to_tons(pending_kg),
        pending_amount_cny=_to_amount(pending_cny),
        pending_batch_count=pending_cnt,
        in_progress_weight_tons=_to_tons(in_progress_kg),
        in_progress_amount_cny=_to_amount(in_progress_cny),
        in_progress_batch_count=in_progress_cnt,
        done_weight_tons=_to_tons(done_kg),
        done_amount_cny=_to_amount(done_cny),
        done_batch_count=done_cnt,
        completion_rate=_ratio(done_kg, abnormal_kg),
        reason_breakdown=reason_breakdown,
        category_breakdown=category_breakdown,
        dept_breakdown=dept_breakdown,
        supplier_breakdown=supplier_breakdown,
        status_breakdown=status_breakdown,
        priority_actions=priority_actions,
    )
