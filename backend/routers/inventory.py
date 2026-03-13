"""Inventory query APIs."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session, aliased

from .. import schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import inventory_service
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
    category_primary: str | None = None,
    aging_category: str | None = None,
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
    category_primary: str | None = None,
    aging_category: str | None = None,
    is_abnormal: bool | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> schemas.StatsResponse:
    """Return aggregated stats for the current filter context (full dataset, no pagination)."""

    snap = models.InventorySnapshot
    base = db.query(snap).filter(snap.snapshot_month == snapshot_month)
    if plant:
        base = base.filter(snap.plant == plant)
    if category_primary:
        base = base.filter(snap.category_primary == category_primary)
    if aging_category:
        base = base.filter(snap.aging_category == aging_category)
    if is_abnormal is not None:
        base = base.filter(snap.is_abnormal == is_abnormal)
    if keyword:
        k = f"%{keyword}%"
        base = base.filter(
            snap.material_code.like(k)
            | snap.material_name.like(k)
            | snap.batch_no.like(k)
            | snap.supplier_name.like(k)
        )

    act = aliased(models.BatchAction)
    q = base.outerjoin(
        act,
        and_(snap.snapshot_month == act.snapshot_month, snap.batch_no == act.batch_no),
    )

    w          = func.coalesce(snap.weight_kg, 0.0)
    is_def     = snap.quality_flag == "N"
    is_pending = and_(snap.is_abnormal == True, act.action_status.is_(None))  # noqa: E712
    is_done    = act.action_status == "已完成"

    result = q.with_entities(
        func.count(snap.id).label("total"),
        func.sum(w).label("total_weight"),
        func.sum(case((is_def,     1),   else_=0  )).label("defective"),
        func.sum(case((is_def,     w),   else_=0.0)).label("defective_weight"),
        func.sum(case((is_pending, 1),   else_=0  )).label("pending"),
        func.sum(case((is_pending, w),   else_=0.0)).label("pending_weight"),
        func.sum(case((is_done,    1),   else_=0  )).label("done"),
        func.sum(case((is_done,    w),   else_=0.0)).label("done_weight"),
    ).one()

    def _t(kg) -> float:
        return round((kg or 0) / 1000, 1)

    defective = result.defective or 0
    done      = result.done or 0
    rate      = round(done / defective * 100, 1) if defective > 0 else 0.0

    return schemas.StatsResponse(
        total=result.total or 0,
        total_weight=_t(result.total_weight),
        defective=defective,
        defective_weight=_t(result.defective_weight),
        pending=result.pending or 0,
        pending_weight=_t(result.pending_weight),
        done=done,
        done_weight=_t(result.done_weight),
        completion_rate=rate,
    )


@router.get("/category-primaries")
def get_category_primaries(
    snapshot_month: str = Query(...),
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
):
    """Return distinct non-null category_primary values for the given month."""
    rows = (
        db.query(models.InventorySnapshot.category_primary)
        .filter(
            models.InventorySnapshot.snapshot_month == snapshot_month,
            models.InventorySnapshot.category_primary.isnot(None),
        )
        .distinct()
        .order_by(models.InventorySnapshot.category_primary)
        .all()
    )
    return {"items": [r[0] for r in rows]}


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
            "action_status": action.action_status if action else None,
            "remark": action.remark if action else None,
            "claim_amount": float(action.claim_amount) if action and action.claim_amount is not None else None,
            "claim_currency": action.claim_currency if action else None,
            "expected_completion": action.expected_completion if action else None,
        },
    }
