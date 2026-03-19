"""Inventory query services for P0 API."""

from __future__ import annotations

from typing import Tuple

from sqlalchemy import and_, asc, case, desc, func, literal
from sqlalchemy.orm import Session, aliased

from .. import models, schemas
from .action_service import normalize_action_status
from .batch_service import normalize_batch_no
from .material_service import normalize_material_code
from .plant_service import build_plant_group_expr, normalize_plant_filter


def resolve_material_codes_for_categories(
    db: Session,
    snapshot_month: str,
    categories: list[str],
) -> set[str]:
    """Resolve raw snapshot material_code set by mapping-based category matching."""
    wanted = {
        str(c).strip()
        for c in (categories or [])
        if str(c).strip()
    }
    if not wanted:
        return set()

    mapping_rows = (
        db.query(models.MaterialMapping.sku, models.MaterialMapping.category_primary)
        .filter(models.MaterialMapping.category_primary.in_(wanted))
        .all()
    )
    mapped_keys = {
        normalize_material_code(row.sku)
        for row in mapping_rows
        if normalize_material_code(row.sku)
    }
    if not mapped_keys:
        return set()

    snapshot_codes = (
        db.query(models.InventorySnapshot.material_code)
        .filter(models.InventorySnapshot.snapshot_month == snapshot_month)
        .distinct()
        .all()
    )
    return {
        raw_code
        for (raw_code,) in snapshot_codes
        if raw_code and normalize_material_code(raw_code) in mapped_keys
    }


def list_inventory(
    db: Session,
    params: schemas.InventoryFilterParams,
) -> Tuple[list[schemas.InventoryItem], int]:
    """Query inventory list with join to batch action table."""
    plant_group_expr = build_plant_group_expr(
        models.InventorySnapshot.plant,
        models.InventorySnapshot.plant_group,
    )
    action_alias = aliased(models.BatchAction)
    normalized_status_expr = case(
        (
            func.trim(func.coalesce(action_alias.action_status, "")).in_(["", "待处理", "待定"]),
            literal("待定"),
        ),
        (
            func.lower(func.trim(func.coalesce(action_alias.action_status, ""))).in_(["pending"]),
            literal("待定"),
        ),
        (
            func.trim(func.coalesce(action_alias.action_status, "")).in_(["进行中", "讨论中"]),
            literal("进行中"),
        ),
        (
            func.lower(func.trim(func.coalesce(action_alias.action_status, ""))).in_(["in progress"]),
            literal("进行中"),
        ),
        (
            func.trim(func.coalesce(action_alias.action_status, "")).in_(["已完成", "已关闭"]),
            literal("已完成"),
        ),
        (
            func.lower(func.trim(func.coalesce(action_alias.action_status, ""))).in_(["done", "completed"]),
            literal("已完成"),
        ),
        else_=literal("待定"),
    )
    query = (
        db.query(models.InventorySnapshot, action_alias)
        .outerjoin(
            action_alias,
            and_(
                models.InventorySnapshot.snapshot_month == action_alias.snapshot_month,
                models.InventorySnapshot.batch_no == action_alias.batch_no,
            ),
        )
        .filter(models.InventorySnapshot.snapshot_month == params.snapshot_month)
    )

    if params.plant:
        plant_filter = normalize_plant_filter(params.plant)
        if plant_filter in {"KS", "IDN"}:
            query = query.filter(plant_group_expr == plant_filter)
        else:
            query = query.filter(models.InventorySnapshot.plant == plant_filter)
    if params.category_primary:
        matched_codes = resolve_material_codes_for_categories(
            db=db,
            snapshot_month=params.snapshot_month,
            categories=params.category_primary,
        )
        if not matched_codes:
            return [], 0
        query = query.filter(models.InventorySnapshot.material_code.in_(matched_codes))
    if params.aging_category:
        query = query.filter(models.InventorySnapshot.aging_category.in_(params.aging_category))
    if params.action_status:
        selected_status = [s.strip() for s in params.action_status if s and s.strip()]
        if selected_status:
            selected_canonical = sorted(
                {
                    normalize_action_status("待定" if s in {"__UNASSIGNED__", "未分配", "未填写"} else s)
                    for s in selected_status
                }
            )
            query = query.filter(normalized_status_expr.in_(selected_canonical))
    if params.is_abnormal is not None:
        query = query.filter(models.InventorySnapshot.is_abnormal == params.is_abnormal)
    if params.quality_flag:
        query = query.filter(models.InventorySnapshot.quality_flag == params.quality_flag)
    if params.material_code:
        query = query.filter(models.InventorySnapshot.material_code == params.material_code)
    if params.supplier_name:
        query = query.filter(
            models.InventorySnapshot.supplier_name.like(f"%{params.supplier_name}%")
        )
    if params.keyword:
        key = f"%{params.keyword}%"
        query = query.filter(
            (models.InventorySnapshot.material_code.like(key))
            | (models.InventorySnapshot.material_name.like(key))
            | (models.InventorySnapshot.batch_no.like(key))
            | (models.InventorySnapshot.supplier_name.like(key))
        )

    sort_column = getattr(models.InventorySnapshot, params.sort_by, models.InventorySnapshot.created_at)
    if params.sort_order.lower() == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))

    total = query.count()

    offset = (params.page - 1) * params.page_size
    rows = query.offset(offset).limit(params.page_size).all()

    fallback_actions: dict[str, models.BatchAction] = {}
    if any(action is None for _, action in rows):
        action_rows = (
            db.query(models.BatchAction)
            .filter(models.BatchAction.snapshot_month == params.snapshot_month)
            .order_by(models.BatchAction.updated_at.desc(), models.BatchAction.id.desc())
            .all()
        )
        for act in action_rows:
            key = normalize_batch_no(act.batch_no)
            if key and key not in fallback_actions:
                fallback_actions[key] = act

    items: list[schemas.InventoryItem] = []
    for snapshot, action in rows:
        if action is None:
            action = fallback_actions.get(normalize_batch_no(snapshot.batch_no))
        item = schemas.InventoryItem(
            snapshot_month=snapshot.snapshot_month,
            batch_no=snapshot.batch_no,
            material_code=snapshot.material_code,
            material_name=snapshot.material_name,
            plant=snapshot.plant,
            plant_group=snapshot.plant_group,
            storage_location=snapshot.storage_location,
            storage_loc_desc=snapshot.storage_loc_desc,
            bin_location=snapshot.bin_location,
            actual_stock=float(snapshot.actual_stock) if snapshot.actual_stock is not None else None,
            weight_kg=float(snapshot.weight_kg) if snapshot.weight_kg is not None else None,
            financial_cost=float(snapshot.financial_cost) if snapshot.financial_cost is not None else None,
            production_date=snapshot.production_date,
            inbound_date=snapshot.inbound_date,
            expiry_date=snapshot.expiry_date,
            quality_flag=snapshot.quality_flag,
            obsolete_reason=snapshot.obsolete_reason,
            obsolete_reason_desc=snapshot.obsolete_reason_desc,
            material_group=snapshot.material_group,
            material_type=snapshot.material_type,
            unit=snapshot.unit,
            supplier_code=snapshot.supplier_code,
            supplier_batch=snapshot.supplier_batch,
            supplier_name=snapshot.supplier_name,
            aging_category=snapshot.aging_category,
            aging_description=snapshot.aging_description,
            rm_category=snapshot.rm_category,
            rm_family=snapshot.rm_family,
            category_primary=snapshot.category_primary,
            currency=snapshot.currency,
            is_abnormal=bool(snapshot.is_abnormal),
            abnormal_reasons=snapshot.abnormal_reasons,
            reason_note=action.reason_note if action else None,
            responsible_dept=action.responsible_dept if action else None,
            action_plan=action.action_plan if action else None,
            action_status=(
                normalize_action_status(action.action_status)
                if action and action.action_status and str(action.action_status).strip()
                else None
            ),
            remark=action.remark if action else None,
            claim_amount=float(action.claim_amount) if action and action.claim_amount is not None else None,
            claim_currency=action.claim_currency if action else None,
            expected_completion=action.expected_completion if action else None,
        )
        items.append(item)
    return items, total


def list_months(db: Session) -> list[str]:
    """Return snapshot_month options ordered descending."""
    rows = (
        db.query(models.InventorySnapshot.snapshot_month)
        .distinct()
        .order_by(models.InventorySnapshot.snapshot_month.desc())
        .all()
    )
    return [row[0] for row in rows if row[0]]
