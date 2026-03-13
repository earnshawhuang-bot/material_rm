"""Material mapping APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import require_admin
from ..database import get_db
from ..services import mapping_service

router = APIRouter(prefix="/api/mapping", tags=["mapping"])


@router.get("")
def list_mapping(db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Return all material mappings."""
    mappings = mapping_service.list_mappings(db)
    return schemas.MaterialMappingListResponse(
        items=[
            schemas.MaterialMappingItem(
                id=mapping.id,
                sku=mapping.sku,
                category=mapping.category,
                family=mapping.family,
                category_primary=mapping.category_primary,
                updated_at=mapping.updated_at,
            )
            for mapping in mappings
        ]
    )


@router.post("/upload", response_model=schemas.MaterialMappingUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_mapping(file: UploadFile = File(...), db: Session = Depends(get_db), _: object = Depends(require_admin)):
    """Upload mapping file and replace all existing rows."""
    try:
        result = mapping_service.parse_and_upload_mapping(file=file, db=db)
        mapping_service.backfill_snapshot_mapping(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"映射上传失败: {exc}") from exc
    return schemas.MaterialMappingUploadResponse(
        file_name=result.file_name,
        row_count=result.row_count,
        replaced=result.replaced,
    )
