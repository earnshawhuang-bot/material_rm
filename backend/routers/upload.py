"""Upload APIs for SAP snapshots and upload logs."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..services import upload_service
from ..services.action_service import carry_forward_actions, import_actions_from_excel

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_RM_TYPES = {"Paper", "AL", "PE"}


def _normalize_rm_type(value: str) -> str:
    text = str(value or "").strip()
    upper = text.upper()
    if upper == "PAPER":
        return "Paper"
    if upper == "AL":
        return "AL"
    if upper == "PE":
        return "PE"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="rm_type 仅支持 Paper / AL / PE",
    )


@router.post("/sap-data", response_model=schemas.UploadResponse)
def upload_sap_data(
    snapshot_month: str = Form(..., description="快照月 YYYY-MM"),
    rm_type: str = Form(..., description="Paper/AL/PE"),
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Upload one SAP file and overwrite snapshot for same period+type."""
    rm_type = _normalize_rm_type(rm_type)
    try:
        snapshot_month = upload_service.validate_snapshot_month(snapshot_month)
        result = upload_service.parse_and_save_sap_upload(
            db=db,
            file=file,
            snapshot_month=snapshot_month,
            rm_type=rm_type,
            uploaded_by=current_user.username,
        )
        db.add(
            models.SysUploadLog(
                snapshot_month=snapshot_month,
                file_name=file.filename,
                rm_type=rm_type,
                row_count=result.row_count,
                uploaded_by=current_user.username,
                status="success",
            )
        )
        db.commit()
        # 自动继承历史 action
        cf = carry_forward_actions(db, snapshot_month)
        db.commit()
    except Exception as exc:  # pragma: no cover
        db.rollback()
        db.add(
            models.SysUploadLog(
                snapshot_month=snapshot_month,
                file_name=file.filename,
                rm_type=rm_type,
                row_count=0,
                uploaded_by=current_user.username,
                status="failed",
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"上传失败: {exc}",
        ) from exc
    return {
        "snapshot_month": result.snapshot_month,
        "rm_type": result.rm_type,
        "file_name": result.file_name,
        "row_count": result.row_count,
        "abnormal_count": result.abnormal_count,
        "carry_forward": cf,
    }


@router.post("/sap-data/batch")
def upload_sap_data_batch(
    snapshot_month: str = Form(..., description="快照月 YYYY-MM"),
    files: List[UploadFile] = File(..., description="Paper/AL/PE 三个文件"),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Batch upload for Paper/AL/PE files in one step."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少上传一个 Excel 文件",
        )

    if len(files) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请一次上传 3 个文件（Paper / AL / PE 各一个）",
        )

    try:
        snapshot_month = upload_service.validate_snapshot_month(snapshot_month)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    detected: list[tuple[UploadFile, str]] = []
    detected_types: list[str] = []
    try:
        for file in files:
            rm_type = upload_service.detect_rm_type_by_filename(file.filename or "")
            detected.append((file, rm_type))
            detected_types.append(rm_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    uploaded_types = set(detected_types)
    missing_types = sorted(set(ALLOWED_RM_TYPES) - uploaded_types)
    repeat_types = sorted(
        {
            rm_type
            for rm_type in set(detected_types)
            if detected_types.count(rm_type) > 1
        }
    )
    if missing_types or repeat_types:
        details = []
        if missing_types:
            details.append(f"缺少: {', '.join(missing_types)}")
        if repeat_types:
            details.append(f"重复: {', '.join(repeat_types)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"批量上传必须包含且仅包含 Paper / AL / PE 各一个文件。{'; '.join(details)}",
        )

    results = []
    total_rows = 0
    total_abnormal = 0

    try:
        for file, rm_type in detected:
            result = upload_service.parse_and_save_sap_upload(
                db=db,
                file=file,
                snapshot_month=snapshot_month,
                rm_type=rm_type,
                uploaded_by=current_user.username,
            )
            results.append(
                {
                    "snapshot_month": result.snapshot_month,
                    "rm_type": result.rm_type,
                    "file_name": result.file_name,
                    "row_count": result.row_count,
                    "abnormal_count": result.abnormal_count,
                }
            )
            total_rows += result.row_count
            total_abnormal += result.abnormal_count
            db.add(
                models.SysUploadLog(
                    snapshot_month=snapshot_month,
                    file_name=file.filename,
                    rm_type=rm_type,
                    row_count=result.row_count,
                    uploaded_by=current_user.username,
                    status="success",
                )
            )

        db.commit()
        cf = carry_forward_actions(db, snapshot_month)
        db.commit()
    except Exception as exc:
        db.rollback()
        for file in files:
            file_name = file.filename or "unknown.xlsx"
            try:
                rm_type = upload_service.detect_rm_type_by_filename(file_name)
            except Exception:
                rm_type = "未知"
            db.add(
                models.SysUploadLog(
                    snapshot_month=snapshot_month,
                    file_name=file_name,
                    rm_type=rm_type,
                    row_count=0,
                    uploaded_by=current_user.username,
                    status="failed",
                )
            )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"批量上传失败: {exc}",
        ) from exc

    return {
        "snapshot_month": snapshot_month,
        "file_count": len(results),
        "row_count": total_rows,
        "abnormal_count": total_abnormal,
        "items": results,
        "carry_forward": cf,
    }

@router.post("/action-import", response_model=schemas.ActionImportResponse)
def upload_action_import(
    snapshot_month: str = Form(..., description="快照月 YYYY-MM"),
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Import offline action records for one month by batch number."""
    try:
        snapshot_month = upload_service.validate_snapshot_month(snapshot_month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        result = import_actions_from_excel(
            db=db,
            file=file,
            snapshot_month=snapshot_month,
            uploaded_by=current_user.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"导入失败: {exc}",
        ) from exc

    return result

@router.get("/history")
def upload_history(db: Session = Depends(get_db), _: object = Depends(get_current_user)):
    """Upload log list used by admin UI."""
    logs = db.query(models.SysUploadLog).order_by(models.SysUploadLog.uploaded_at.desc()).all()
    return [
        {
            "id": log.id,
            "snapshot_month": log.snapshot_month,
            "file_name": log.file_name,
            "rm_type": log.rm_type,
            "row_count": log.row_count,
            "uploaded_by": log.uploaded_by,
            "uploaded_at": log.uploaded_at,
            "status": log.status,
        }
        for log in logs
    ]


