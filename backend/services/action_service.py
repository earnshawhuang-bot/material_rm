"""Batch action persistence service."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import UploadFile
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from .. import models, schemas
from .batch_service import normalize_batch_no


def _find_action_by_normalized_batch(
    db: Session,
    snapshot_month: str,
    normalized_batch_no: str,
) -> models.BatchAction | None:
    """Find one action row by month + normalized batch key."""
    exact = (
        db.query(models.BatchAction)
        .filter(
            models.BatchAction.snapshot_month == snapshot_month,
            models.BatchAction.batch_no == normalized_batch_no,
        )
        .first()
    )
    if exact is not None:
        return exact

    rows = (
        db.query(models.BatchAction)
        .filter(models.BatchAction.snapshot_month == snapshot_month)
        .order_by(models.BatchAction.updated_at.desc(), models.BatchAction.id.desc())
        .all()
    )
    for row in rows:
        if normalize_batch_no(row.batch_no) == normalized_batch_no:
            return row
    return None


def save_or_update_action(db, payload: schemas.ActionSaveRequest, updated_by: str) -> models.BatchAction:
    """Create or update one batch action record."""
    batch_no = normalize_batch_no(payload.batch_no)
    if not batch_no:
        raise ValueError("批次编号不能为空")

    action = _find_action_by_normalized_batch(
        db=db,
        snapshot_month=payload.snapshot_month,
        normalized_batch_no=batch_no,
    )

    if action is None:
        action = models.BatchAction(
            snapshot_month=payload.snapshot_month,
            batch_no=batch_no,
        )
        db.add(action)
    elif action.batch_no != batch_no:
        action.batch_no = batch_no

    action.reason_note = payload.reason_note
    action.responsible_dept = payload.responsible_dept
    action.action_plan = payload.action_plan
    action.action_status = payload.action_status
    action.remark = payload.remark
    action.claim_amount = payload.claim_amount
    action.claim_currency = payload.claim_currency
    action.expected_completion = payload.expected_completion
    action.updated_by = updated_by
    db.flush()
    db.commit()
    db.refresh(action)
    return action


# ── 月度行动项自动继承 ──────────────────────────────────────


def _get_previous_month(snapshot_month: str) -> str:
    """'2026-03' → '2026-02', '2026-01' → '2025-12'."""
    year, month = int(snapshot_month[:4]), int(snapshot_month[5:7])
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def carry_forward_actions(db: Session, new_month: str) -> dict:
    """将上月的行动项继承到新月份（除"已关闭"外）。

    规则：
    - 上月行动项状态为"已关闭" → 跳过
    - 新月份中该 batch_no 不存在于快照 → 跳过
    - 新月份中该 batch_no 已有行动项 → 跳过（补空不覆盖）
    - 其余 → 复制到新月份
    """
    prev_month = _get_previous_month(new_month)

    # 获取上月所有行动项
    prev_actions = (
        db.query(models.BatchAction)
        .filter(models.BatchAction.snapshot_month == prev_month)
        .all()
    )

    if not prev_actions:
        return {"carried": 0, "skipped_closed": 0, "skipped_existing": 0, "skipped_no_snapshot": 0}

    # 获取新月份快照中所有 batch_no
    new_batches = set(
        normalize_batch_no(row[0])
        for row in db.query(models.InventorySnapshot.batch_no)
        .filter(models.InventorySnapshot.snapshot_month == new_month)
        .all()
        if normalize_batch_no(row[0])
    )

    # 获取新月份已有的行动项 batch_no
    existing_actions = set(
        normalize_batch_no(row[0])
        for row in db.query(models.BatchAction.batch_no)
        .filter(models.BatchAction.snapshot_month == new_month)
        .all()
        if normalize_batch_no(row[0])
    )

    stats = {"carried": 0, "skipped_closed": 0, "skipped_existing": 0, "skipped_no_snapshot": 0}

    for act in prev_actions:
        if act.action_status == "已关闭":
            stats["skipped_closed"] += 1
            continue
        normalized_batch = normalize_batch_no(act.batch_no)
        if normalized_batch not in new_batches:
            stats["skipped_no_snapshot"] += 1
            continue
        if normalized_batch in existing_actions:
            stats["skipped_existing"] += 1
            continue

        db.add(
            models.BatchAction(
                snapshot_month=new_month,
                batch_no=normalized_batch,
                reason_note=act.reason_note,
                responsible_dept=act.responsible_dept,
                action_plan=act.action_plan,
                action_status=act.action_status,
                remark=act.remark,
                claim_amount=act.claim_amount,
                claim_currency=act.claim_currency,
                expected_completion=act.expected_completion,
                updated_by="system:carry-forward",
            )
        )
        stats["carried"] += 1

    db.flush()
    return stats


# ── 线下 Excel 处理记录一次性导入 ──────────────────────────


# 处理状态关键词 → 标准值映射
_STATUS_KEYWORDS: list[tuple[str, str]] = [
    ("已关闭", "已关闭"),
    ("已完成", "已完成"),
    ("进行中", "进行中"),
    ("讨论中", "讨论中"),
    ("待定", "待定"),
    ("待处理", "待处理"),
]


def _map_status(raw: str | None) -> tuple[str, str | None]:
    """将原始处理状态文本映射为标准枚举值。

    返回 (mapped_status, extra_note)：
    - 若匹配到标准值：(标准值, None)
    - 若不匹配：("待处理", "原始状态: xxx")
    """
    if not raw or not str(raw).strip():
        return "待处理", None
    text = str(raw).strip()
    for keyword, std_val in _STATUS_KEYWORDS:
        if keyword in text:
            return std_val, None
    return "待处理", f"原始状态: {text}"


def _parse_claim_amount(raw: Any) -> float | None:
    """解析索赔金额，失败返回 None。"""
    if raw is None:
        return None
    try:
        if pd.isna(raw):
            return None
    except (TypeError, ValueError):
        pass
    try:
        val = float(raw)
        return val if val != 0 else None
    except (TypeError, ValueError):
        return None


def _parse_expected_date(raw: Any) -> tuple[date | None, str | None]:
    """解析预计完成时间。

    返回 (parsed_date, extra_note)：
    - 合法日期（含 Excel 序列号）→ (date, None)
    - 非日期文本（Pending / 3月底前）→ (None, "预计完成: xxx")
    - 空 → (None, None)
    """
    if raw is None:
        return None, None
    try:
        if pd.isna(raw):
            return None, None
    except (TypeError, ValueError):
        pass

    # Excel 数字序列号（如 46096）
    if isinstance(raw, (int, float)):
        try:
            parsed = pd.to_datetime(raw, unit="D", origin="1899-12-30", errors="coerce")
            if pd.notna(parsed):
                return parsed.date(), None
        except Exception:
            pass

    # 尝试标准日期解析
    try:
        parsed = pd.to_datetime(raw, errors="coerce")
        if pd.notna(parsed):
            return parsed.date(), None
    except Exception:
        pass

    # 非日期文本
    text = str(raw).strip()
    if text and text.lower() not in ("nan", "none", "nat"):
        return None, f"预计完成: {text}"
    return None, None


def _safe_str(val: Any) -> str | None:
    """安全转换为字符串，NaN/None → None。"""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    return s


def _merge_action_fill_blanks(target: models.BatchAction, source: models.BatchAction) -> None:
    """Merge source into target using fill-empty-only strategy."""
    if not target.reason_note and source.reason_note:
        target.reason_note = source.reason_note
    if not target.responsible_dept and source.responsible_dept:
        target.responsible_dept = source.responsible_dept
    if not target.action_plan and source.action_plan:
        target.action_plan = source.action_plan
    if (not target.action_status or target.action_status == "待处理") and source.action_status:
        target.action_status = source.action_status
    if not target.remark and source.remark:
        target.remark = source.remark
    if target.claim_amount is None and source.claim_amount is not None:
        target.claim_amount = source.claim_amount
    if not target.claim_currency and source.claim_currency:
        target.claim_currency = source.claim_currency
    if target.expected_completion is None and source.expected_completion is not None:
        target.expected_completion = source.expected_completion


def _read_action_excel_rows(raw: bytes) -> list[dict[str, Any]]:
    """Read action import rows with openpyxl to preserve text cell values."""
    workbook = load_workbook(filename=BytesIO(raw), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        row_iter = sheet.iter_rows(values_only=False)
        header_cells = next(row_iter, None)
        if not header_cells:
            return []

        headers: list[str] = []
        for cell in header_cells:
            header = _safe_str(cell.value)
            headers.append(header or "")

        rows: list[dict[str, Any]] = []
        for cells in row_iter:
            row_data: dict[str, Any] = {}
            has_value = False
            for idx, cell in enumerate(cells):
                if idx >= len(headers):
                    continue
                header = headers[idx]
                if not header:
                    continue
                row_data[header] = cell.value
                if cell.value is not None:
                    has_value = True
            if has_value:
                rows.append(row_data)
        return rows
    finally:
        workbook.close()


def import_actions_from_excel(
    db: Session,
    file: UploadFile,
    snapshot_month: str,
    uploaded_by: str,
) -> schemas.ActionImportResponse:
    """从线下 Excel 导入处理记录。

    规则：
    - 按"批次编号"列匹配快照中 quality_flag='N' 的批次
    - 责任部门 / 处理方案：直接导入（自由文本）
    - 处理状态：关键词映射，不匹配→"待处理"，原文存备注
    - 索赔金额：解析为数字，失败留空
    - 预计完成时间：解析日期，非日期文本存备注
    - 已存在的行动项：仅补空不覆盖
    """
    raw = file.file.read()
    rows = _read_action_excel_rows(raw)
    df = pd.DataFrame(rows)

    # 必须有 "批次编号" 列
    if "批次编号" not in df.columns:
        raise ValueError("Excel 缺少'批次编号'列")

    # 获取该月份所有 quality_flag='N' 的批次
    abnormal_batches = set(
        normalize_batch_no(row[0])
        for row in db.query(models.InventorySnapshot.batch_no)
        .filter(
            models.InventorySnapshot.snapshot_month == snapshot_month,
            models.InventorySnapshot.quality_flag == "N",
        )
        .all()
        if normalize_batch_no(row[0])
    )

    # 获取该月份已有的行动项
    existing_actions: dict[str, models.BatchAction] = {}
    existing_rows = (
        db.query(models.BatchAction)
        .filter(models.BatchAction.snapshot_month == snapshot_month)
        .order_by(models.BatchAction.updated_at.desc(), models.BatchAction.id.desc())
        .all()
    )
    grouped_actions: dict[str, list[models.BatchAction]] = {}
    for act in existing_rows:
        key = normalize_batch_no(act.batch_no)
        if key:
            grouped_actions.setdefault(key, []).append(act)

    for key, acts in grouped_actions.items():
        primary = next((a for a in acts if a.batch_no == key), acts[0])
        for duplicate in acts:
            if duplicate is primary:
                continue
            _merge_action_fill_blanks(primary, duplicate)
            db.delete(duplicate)
        if primary.batch_no != key:
            primary.batch_no = key
        existing_actions[key] = primary

    stats = schemas.ActionImportResponse(matched=0, skipped=0, errors=0, error_details=[])

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel 行号（标题行是第1行）
        try:
            batch_no = normalize_batch_no(row.get("批次编号"))
            if not batch_no:
                continue  # 无批次号的行直接跳过

            # 仅导入 quality_flag='N' 的批次
            if batch_no not in abnormal_batches:
                stats.skipped += 1
                continue

            # 解析各字段
            dept = _safe_str(row.get("责任部门"))
            if dept:
                dept = dept.replace("\\", "/")  # 修正 "质量\研发" → "质量/研发"

            plan = _safe_str(row.get("处理方案"))

            raw_status = _safe_str(row.get("处理状态"))
            mapped_status, status_note = _map_status(raw_status)

            claim = _parse_claim_amount(row.get("索赔金额"))
            claim_cur = _safe_str(row.get("币种"))

            exp_date, date_note = _parse_expected_date(row.get("预计完成时间"))

            reason_note = _safe_str(row.get("线下原因补充说明"))
            remark_raw = _safe_str(row.get("备注"))

            # 聚合备注：原始备注 + 非标状态 + 非日期文本
            remark_parts = []
            if remark_raw:
                remark_parts.append(remark_raw)
            if status_note:
                remark_parts.append(status_note)
            if date_note:
                remark_parts.append(date_note)
            remark = "; ".join(remark_parts) if remark_parts else None

            # 补空不覆盖逻辑
            if batch_no in existing_actions:
                act = existing_actions[batch_no]
                if not act.responsible_dept and dept:
                    act.responsible_dept = dept
                if not act.action_plan and plan:
                    act.action_plan = plan
                if not act.action_status or act.action_status == "待处理":
                    act.action_status = mapped_status
                if not act.reason_note and reason_note:
                    act.reason_note = reason_note
                if act.claim_amount is None and claim is not None:
                    act.claim_amount = claim
                if not act.claim_currency and claim_cur:
                    act.claim_currency = claim_cur
                if act.expected_completion is None and exp_date is not None:
                    act.expected_completion = exp_date
                if not act.remark and remark:
                    act.remark = remark
                act.updated_by = uploaded_by
            else:
                new_act = models.BatchAction(
                    snapshot_month=snapshot_month,
                    batch_no=batch_no,
                    responsible_dept=dept,
                    action_plan=plan,
                    action_status=mapped_status,
                    reason_note=reason_note,
                    claim_amount=claim,
                    claim_currency=claim_cur,
                    expected_completion=exp_date,
                    remark=remark,
                    updated_by=uploaded_by,
                )
                db.add(new_act)
                existing_actions[batch_no] = new_act

            stats.matched += 1

        except Exception as exc:
            stats.errors += 1
            stats.error_details.append(f"第{row_num}行: {exc}")
            if len(stats.error_details) > 50:
                stats.error_details.append("...更多错误已省略")
                break

    db.flush()
    db.commit()
    return stats
