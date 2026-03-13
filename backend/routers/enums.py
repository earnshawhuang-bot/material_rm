"""Enum config APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import require_admin
from ..database import get_db
from .. import models

router = APIRouter(prefix="/api/enums", tags=["enums"])


@router.get("/{enum_type}", response_model=schemas.EnumListResponse)
def list_enum(enum_type: str, db: Session = Depends(get_db)):
    items = (
        db.query(models.SysEnumConfig)
        .filter(
            models.SysEnumConfig.enum_type == enum_type,
            models.SysEnumConfig.is_active.is_(True),
        )
        .order_by(models.SysEnumConfig.sort_order)
        .all()
    )
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
