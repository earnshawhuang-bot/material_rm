"""Inventory query services for P0 API."""

from __future__ import annotations

from typing import Tuple

from sqlalchemy import and_, desc, asc
from sqlalchemy.orm import Session, aliased

from .. import models, schemas


def list_inventory(
    db: Session,
    params: schemas.InventoryFilterParams,
) -> Tuple[list[schemas.InventoryItem], int]:
    """Query inventory list with join to batch action table."""
    action_alias = aliased(models.BatchAction)
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
        query = query.filter(models.InventorySnapshot.plant == params.plant)
    if params.category_primary:
        query = query.filter(models.InventorySnapshot.category_primary == params.category_primary)
    if params.aging_category:
        query = query.filter(models.InventorySnapshot.aging_category == params.aging_category)
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

    items: list[schemas.InventoryItem] = []
    for snapshot, action in rows:
        item = schemas.InventoryItem(
            snapshot_month=snapshot.snapshot_month,
            batch_no=snapshot.batch_no,
            material_code=snapshot.material_code,
            material_name=snapshot.material_name,
            plant=snapshot.plant,
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
            action_status=action.action_status if action else None,
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
