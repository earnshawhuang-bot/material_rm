"""Inventory query APIs."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import inventory_service
from ..services.action_service import normalize_action_status
from ..services.batch_service import normalize_batch_no
from ..services.material_service import normalize_material_code
from ..services.plant_service import build_plant_group_expr, normalize_plant_filter
from .. import models

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def _get_unmatched_material_groups(db: Session, snapshot_month: str):
    """Aggregate unmatched facts at material level for UI and export.

    Unmatched means `category_primary` is NULL after mapping backfill.
    We group by material to present a concise action list instead of noisy
    batch-level details.
    """
    snap = models.InventorySnapshot
    return (
        db.query(
            snap.material_code.label("material_code"),
            func.max(snap.material_name).label("material_name"),
            func.count(snap.id).label("batch_count"),
            func.coalesce(func.sum(snap.weight_kg), 0.0).label("weight_kg"),
        )
        .filter(
            snap.snapshot_month == snapshot_month,
            snap.category_primary.is_(None),
        )
        .group_by(snap.material_code)
        .order_by(snap.material_code)
        .all()
    )


@router.get("/list", response_model=schemas.InventoryListResponse)
def list_inventory(
    snapshot_month: str = Query(..., description="快照月 YYYY-MM"),
    plant: str | None = None,
    category_primary: list[str] | None = Query(None),
    aging_category: list[str] | None = Query(None),
    action_status: list[str] | None = Query(None),
    is_new_batch: bool | None = None,
    is_abnormal: bool | None = None,
    quality_flag: str | None = None,
    material_code: str | None = None,
    supplier_name: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    _: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.InventoryListResponse:
    """Paginated inventory list, joined with pending action if exists."""
    params = schemas.InventoryFilterParams(
        snapshot_month=snapshot_month,
        plant=plant,
        category_primary=category_primary,
        aging_category=aging_category,
        action_status=action_status,
        is_new_batch=is_new_batch,
        is_abnormal=is_abnormal,
        quality_flag=quality_flag,
        material_code=material_code,
        supplier_name=supplier_name,
        keyword=keyword,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items, total = inventory_service.list_inventory(db, params)
    return schemas.InventoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/months")
def get_months(db: Session = Depends(get_db), _: object = Depends(get_current_user)):
    """Get all uploaded snapshot months."""
    return inventory_service.list_months(db)


@router.get("/stats", response_model=schemas.StatsResponse)
def get_stats(
    snapshot_month: str = Query(..., description="快照月 YYYY-MM"),
    plant: str | None = None,
    category_primary: list[str] | None = Query(None),
    aging_category: list[str] | None = Query(None),
    action_status: list[str] | None = Query(None),
    is_new_batch: bool | None = None,
    is_abnormal: bool | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> schemas.StatsResponse:
    """Return aggregated stats for the current filter context (full dataset, no pagination)."""

    snap = models.InventorySnapshot
    plant_group_expr = build_plant_group_expr(snap.plant, snap.plant_group)
    base = db.query(snap).filter(snap.snapshot_month == snapshot_month)
    if plant:
        plant_filter = normalize_plant_filter(plant)
        if plant_filter in {"KS", "IDN"}:
            base = base.filter(plant_group_expr == plant_filter)
        else:
            base = base.filter(snap.plant == plant_filter)
    if category_primary:
        matched_codes = inventory_service.resolve_material_codes_for_categories(
            db=db,
            snapshot_month=snapshot_month,
            categories=category_primary,
        )
        if not matched_codes:
            return schemas.StatsResponse()
        base = base.filter(snap.material_code.in_(matched_codes))
    if aging_category:
        base = base.filter(snap.aging_category.in_(aging_category))
    if keyword:
        k = f"%{keyword}%"
        base = base.filter(
            snap.material_code.like(k)
            | snap.material_name.like(k)
            | snap.batch_no.like(k)
            | snap.supplier_name.like(k)
        )

    snapshot_rows = base.with_entities(
        snap.batch_no,
        snap.plant,
        snap.plant_group,
        snap.weight_kg,
        snap.quality_flag,
        snap.is_abnormal,
    ).all()

    action_rows = (
        db.query(
            models.BatchAction.batch_no,
            models.BatchAction.action_status,
            models.BatchAction.updated_at,
            models.BatchAction.id,
        )
        .filter(models.BatchAction.snapshot_month == snapshot_month)
        .order_by(models.BatchAction.updated_at.desc(), models.BatchAction.id.desc())
        .all()
    )
    action_map: dict[str, str | None] = {}
    for row in action_rows:
        key = normalize_batch_no(row.batch_no)
        if key and key not in action_map:
            action_map[key] = normalize_action_status(row.action_status)

    selected_status = [s.strip() for s in (action_status or []) if s and s.strip()]
    status_set = {
        normalize_action_status("待定" if s in {"__UNASSIGNED__", "未分配", "未填写"} else s)
        for s in selected_status
    }

    def _status_match(status_value: str | None) -> bool:
        if not status_set:
            return True
        normalized = normalize_action_status(status_value)
        return normalized in status_set

    rows_for_total: list[tuple] = []
    for row in snapshot_rows:
        status_value = normalize_action_status(action_map.get(normalize_batch_no(row.batch_no)))
        if _status_match(status_value):
            rows_for_total.append((row, status_value))

    previous_month = inventory_service.get_previous_snapshot_month(db, snapshot_month)
    previous_batch_keys = inventory_service.load_previous_batch_keys(
        db=db,
        current_month=snapshot_month,
        previous_month=previous_month,
        snapshots=[row for row, _ in rows_for_total],
    )
    if is_new_batch is not None:
        rows_for_total = [
            (row, status_value)
            for row, status_value in rows_for_total
            if inventory_service.is_new_batch_row(row, previous_month, previous_batch_keys) == is_new_batch
        ]

    # 业务口径：总库存不受“异常状态”筛选影响，其它指标继续受异常状态影响
    rows_for_metrics = rows_for_total
    if is_abnormal is not None:
        rows_for_metrics = [
            (row, status_value)
            for row, status_value in rows_for_total
            if bool(row.is_abnormal) == is_abnormal
        ]

    total = 0
    total_weight = 0.0
    defective = 0
    defective_weight = 0.0
    pending = 0
    pending_weight = 0.0
    done = 0
    done_weight = 0.0
    for row, _ in rows_for_total:
        total += 1
        total_weight += float(row.weight_kg or 0.0)

    for row, status_value in rows_for_metrics:
        weight = float(row.weight_kg or 0.0)

        if row.quality_flag == "N":
            defective += 1
            defective_weight += weight

        if bool(row.is_abnormal) and status_value == "待定":
            pending += 1
            pending_weight += weight

        if status_value == "已完成":
            done += 1
            done_weight += weight

    def _t(kg) -> float:
        return round((kg or 0) / 1000, 1)

    rate      = round(done / defective * 100, 1) if defective > 0 else 0.0

    return schemas.StatsResponse(
        total=total,
        total_weight=_t(total_weight),
        defective=defective,
        defective_weight=_t(defective_weight),
        pending=pending,
        pending_weight=_t(pending_weight),
        done=done,
        done_weight=_t(done_weight),
        completion_rate=rate,
    )


@router.get("/category-primaries")
def get_category_primaries(
    snapshot_month: str = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    """Return category_primary values derived from mapping by material_code matching."""
    material_rows = (
        db.query(models.InventorySnapshot.material_code)
        .filter(models.InventorySnapshot.snapshot_month == snapshot_month)
        .distinct()
        .all()
    )
    material_keys = {
        normalize_material_code(r[0])
        for r in material_rows
        if normalize_material_code(r[0])
    }
    if not material_keys:
        return {"items": []}

    mapping_rows = db.query(
        models.MaterialMapping.sku,
        models.MaterialMapping.category_primary,
    ).all()
    categories = sorted({
        (row.category_primary or "").strip()
        for row in mapping_rows
        if row.category_primary and normalize_material_code(row.sku) in material_keys
    })
    return {"items": categories}


@router.get("/unmatched")
def get_unmatched(
    snapshot_month: str = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    """Return snapshot rows whose material_code didn't match any mapping SKU (category_primary is NULL)."""
    rows = _get_unmatched_material_groups(db, snapshot_month)
    return {
        "total": len(rows),
        "items": [
            {
                "material_code": r.material_code,
                "material_name": r.material_name,
                "batch_count": int(r.batch_count or 0),
                "weight_kg": float(r.weight_kg) if r.weight_kg is not None else 0.0,
            }
            for r in rows
        ],
    }


@router.get("/unmatched/download")
def download_unmatched(
    snapshot_month: str = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    """Download unmatched materials as Excel."""
    import pandas as pd

    rows = _get_unmatched_material_groups(db, snapshot_month)

    data = [
        {
            "物料编号": r.material_code,
            "物料名称": r.material_name,
            "未匹配批次数": int(r.batch_count or 0),
            "未匹配重量(KG)": float(r.weight_kg) if r.weight_kg is not None else 0.0,
        }
        for r in rows
    ]

    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="未匹配物料")
    buf.seek(0)

    filename = f"unmatched_{snapshot_month}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/debug-flags")
def debug_flags(
    snapshot_month: str = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    """Diagnostic: return raw DB values for quality_flag and related columns."""
    rows = (
        db.query(
            models.InventorySnapshot.material_code,
            models.InventorySnapshot.batch_no,
            models.InventorySnapshot.quality_flag,
            models.InventorySnapshot.obsolete_reason,
            models.InventorySnapshot.obsolete_reason_desc,
            models.InventorySnapshot.is_abnormal,
            models.InventorySnapshot.abnormal_reasons,
        )
        .filter(models.InventorySnapshot.snapshot_month == snapshot_month)
        .limit(30)
        .all()
    )
    return [
        {
            "material_code": r.material_code,
            "batch_no": r.batch_no,
            "quality_flag": r.quality_flag,       # raw DB value
            "obsolete_reason": r.obsolete_reason,
            "obsolete_reason_desc": r.obsolete_reason_desc,
            "is_abnormal": r.is_abnormal,
            "abnormal_reasons": r.abnormal_reasons,
        }
        for r in rows
    ]


@router.get("/{batch_no}")
def get_batch_detail(batch_no: str, snapshot_month: str, db: Session = Depends(get_db)):
    """Return one batch detail for demo and P1 extension."""
    snapshot = (
        db.query(models.InventorySnapshot)
        .filter(
            and_(
                models.InventorySnapshot.batch_no == batch_no,
                models.InventorySnapshot.snapshot_month == snapshot_month,
            )
        )
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在")

    action = (
        db.query(models.BatchAction)
        .filter(
            and_(
                models.BatchAction.batch_no == batch_no,
                models.BatchAction.snapshot_month == snapshot_month,
            )
        )
        .first()
    )
    return {
        "snapshot": {
            "snapshot_month": snapshot.snapshot_month,
            "batch_no": snapshot.batch_no,
            "material_code": snapshot.material_code,
            "material_name": snapshot.material_name,
            "plant": snapshot.plant,
            "plant_group": snapshot.plant_group,
            "storage_location": snapshot.storage_location,
            "storage_loc_desc": snapshot.storage_loc_desc,
            "bin_location": snapshot.bin_location,
            "aging_category": snapshot.aging_category,
            "aging_description": snapshot.aging_description,
            "financial_cost": float(snapshot.financial_cost) if snapshot.financial_cost is not None else None,
            "actual_stock": float(snapshot.actual_stock) if snapshot.actual_stock is not None else None,
            "weight_kg": float(snapshot.weight_kg) if snapshot.weight_kg is not None else None,
            "quality_flag": snapshot.quality_flag,
            "is_abnormal": bool(snapshot.is_abnormal),
            "abnormal_reasons": snapshot.abnormal_reasons,
            "rm_category": snapshot.rm_category,
            "rm_family": snapshot.rm_family,
            "category_primary": snapshot.category_primary,
            "production_date": snapshot.production_date,
            "inbound_date": snapshot.inbound_date,
            "expiry_date": snapshot.expiry_date,
            "currency": snapshot.currency,
            "supplier_name": snapshot.supplier_name,
        },
        "action": {
            "reason_note": action.reason_note if action else None,
            "responsible_dept": action.responsible_dept if action else None,
            "action_plan": action.action_plan if action else None,
            "action_status": (
                normalize_action_status(action.action_status)
                if action and action.action_status and str(action.action_status).strip()
                else None
            ),
            "remark": action.remark if action else None,
            "claim_amount": float(action.claim_amount) if action and action.claim_amount is not None else None,
            "claim_currency": action.claim_currency if action else None,
            "expected_completion": action.expected_completion if action else None,
        },
    }
