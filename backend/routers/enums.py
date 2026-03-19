"""Enum config APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import require_admin
from ..database import get_db
from .. import models

router = APIRouter(prefix="/api/enums", tags=["enums"])
CANONICAL_ACTION_STATUSES = ["待定", "进行中", "已完成"]


@router.get("/{enum_type}", response_model=schemas.EnumListResponse)
def list_enum(enum_type: str, db: Session = Depends(get_db)):
    items = (
        db.query(models.SysEnumConfig)
        .filter(
            models.SysEnumConfig.enum_type == enum_type,
            models.SysEnumConfig.is_active.is_(True),
        )
        .all()
    )
    if enum_type == "action_status":
        by_value = {item.enum_value: item for item in items}
        ordered_items = []
        for i, value in enumerate(CANONICAL_ACTION_STATUSES, start=1):
            item = by_value.get(value)
            if item is None:
                ordered_items.append(
                    schemas.EnumItem(
                        enum_type="action_status",
                        enum_value=value,
                        sort_order=i,
                        is_active=True,
                    )
                )
            else:
                ordered_items.append(
                    schemas.EnumItem(
                        enum_type=item.enum_type,
                        enum_value=item.enum_value,
                        sort_order=i,
                        is_active=item.is_active,
                    )
                )
        return schemas.EnumListResponse(items=ordered_items)

    items = sorted(items, key=lambda item: item.sort_order)
    return schemas.EnumListResponse(
        items=[
            schemas.EnumItem(
                enum_type=item.enum_type,
                enum_value=item.enum_value,
                sort_order=item.sort_order,
                is_active=item.is_active,
            )
            for item in items
        ]
    )


@router.post("/", dependencies=[Depends(require_admin)])
def create_enum():
    """P1 完整功能。当前先预留写接口用于后续权限控制。"""
    return {"message": "待实现"}
