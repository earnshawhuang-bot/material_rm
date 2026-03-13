"""处理记录相关路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from .. import schemas
from .. import models
from ..auth import get_current_user
from ..database import get_db
from ..services import action_service

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.post("/save")
def save_action(
    payload: schemas.ActionSaveRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update action record by snapshot_month + batch_no."""
    action = action_service.save_or_update_action(
        db=db,
        payload=payload,
        updated_by=current_user.username,
    )
    return {"id": action.id, "message": "保存成功"}


@router.get("/pending")
def list_pending(snapshot_month: str, department: str | None = None, db: Session = Depends(get_db)):
    """
    P0 支持：返回异常批次，默认返回异常且未关闭/未完成。
    """
    query = (
        db.query(models.InventorySnapshot, models.BatchAction)
        .outerjoin(
            models.BatchAction,
            and_(
                models.InventorySnapshot.batch_no == models.BatchAction.batch_no,
                models.InventorySnapshot.snapshot_month == models.BatchAction.snapshot_month,
            ),
        )
        .filter(
            models.InventorySnapshot.snapshot_month == snapshot_month,
            models.InventorySnapshot.is_abnormal.is_(True),
        )
        .filter(
            or_(
                models.BatchAction.action_status.is_(None),
                models.BatchAction.action_status.notin_(["已完成", "已关闭"]),
            )
        )
    )

    if department:
        query = query.filter(
            or_(
                models.BatchAction.responsible_dept.is_(None),
                models.BatchAction.responsible_dept == department,
            )
        )

    items = []
    for snapshot, action in query.order_by(models.InventorySnapshot.id.desc()).all():
        items.append(
            {
                "snapshot_month": snapshot.snapshot_month,
                "batch_no": snapshot.batch_no,
                "material_code": snapshot.material_code,
                "material_name": snapshot.material_name,
                "plant": snapshot.plant,
                "aging_category": snapshot.aging_category,
                "quality_flag": snapshot.quality_flag,
                "is_abnormal": bool(snapshot.is_abnormal),
                "abnormal_reasons": snapshot.abnormal_reasons,
                "responsible_dept": action.responsible_dept if action else None,
                "action_status": action.action_status if action else None,
                "action_plan": action.action_plan if action else None,
                "updated_by": action.updated_by if action else None,
            }
        )
    return {"snapshot_month": snapshot_month, "items": items}
