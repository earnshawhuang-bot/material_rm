"""Upload service: parse SAP Excel and write snapshots to SQL Server."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Any
import re

import pandas as pd
from fastapi import UploadFile
from sqlalchemy.orm import Session

from .. import models
from .batch_service import normalize_batch_no
from .material_service import normalize_material_code
from .plant_service import derive_plant_group, normalize_plant_code


RM_COLUMNS = {
    "物料编号": "material_code",
    "物料名称": "material_name",
    "工厂": "plant",
    "BIN位": "bin_location",
    "存储地点": "storage_location",
    "存储地点描述": "storage_loc_desc",
    "批次编号": "batch_no",
    "实际库存": "actual_stock",
    "重量(KG)": "weight_kg",
    "生产日期": "production_date",
    "入库日期": "inbound_date",
    "保质期到期日期": "expiry_date",
    "良品标记": "quality_flag",
    "呆滞原因": "obsolete_reason",
    "呆滞原因描述": "obsolete_reason_desc",
    "物料组": "material_group",
    "物料类型": "material_type",
    "单位": "unit",
    "供应商": "supplier_code",
    "供应商批次": "supplier_batch",
    "供应商名称": "supplier_name",
    "库龄分类": "aging_category",
    "库龄分类描述": "aging_description",
    "财务成本额": "financial_cost",
    "生产工单": "production_order",
    "订单类型": "order_type",
    "订单类型名称": "order_type_name",
    "客户编码": "customer_code",
    "客户名称": "customer_name",
    "发票帐户": "invoice_account",
    "发票帐户名称": "invoice_account_name",
    "合同编码": "contract_code",
    "合同行项目": "contract_line_item",
    "已冻结": "is_frozen",
    "质检": "qc_qty",
    "中转": "in_transit",
    "货币": "currency",
}

RM_TYPE_PATTERNS: dict[str, list[str]] = {
    "Paper": ["paper", "base_paper", "basepaper"],
    "AL": ["al_foil", "alfoil", "al"],
    "PE": ["pe"],
}


def _normalize_filename(value: str) -> str:
    return re.sub(r"\.[^.]+$", "", value.strip().lower())


@dataclass
class UploadResult:
    snapshot_month: str
    rm_type: str
    file_name: str
    row_count: int
    abnormal_count: int


def _normalize_value(value: Any) -> Any:
    """Convert pandas NaN-like values (and the string 'nan') to None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        stripped = value.strip()
        # Guard against pandas astype(str) artefact where NaN → "nan"
        if stripped.lower() == "nan":
            return None
        return stripped or None
    return value


def _to_date(value: Any) -> date | None:
    if pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _to_decimal(value: Any) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if pd.isna(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_rows(file: UploadFile) -> pd.DataFrame:
    raw = file.file.read()
    df = pd.read_excel(
        BytesIO(raw),
        converters={
            "批次编号": normalize_batch_no,
        },
    )
    df.columns = [str(col).strip() for col in df.columns]

    # Force text columns to clean strings BEFORE rename/selection.
    # pd.read_excel may auto-detect boolean / numeric types for SAP exports
    # (e.g. "Y"→True, "N"→False). We normalise them here so downstream
    # logic always receives plain str or None.
    _TEXT_COLS = [
        "良品标记", "呆滞原因", "呆滞原因描述",
        "物料编号", "批次编号", "供应商", "供应商批次",
        "库龄分类", "库龄分类描述", "物料组", "物料类型",
        "存储地点", "存储地点描述", "单位", "货币", "工厂",
    ]
    for col in _TEXT_COLS:
        if col in df.columns:
            if col == "批次编号":
                df[col] = df[col].apply(normalize_batch_no)
            elif col == "物料编号":
                df[col] = df[col].apply(normalize_material_code)
            else:
                df[col] = df[col].apply(
                    lambda x: str(x).strip() if pd.notna(x) else None
                )

    return df


def _validate_columns(df: pd.DataFrame) -> list[str]:
    missing = [col for col in RM_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Excel 缺少必填列: {', '.join(missing)}")
    return list(RM_COLUMNS.keys())


def validate_snapshot_month(snapshot_month: str) -> str:
    month = (snapshot_month or "").strip()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("snapshot_month 必须是 YYYY-MM 格式")
    return month


def detect_rm_type_by_filename(file_name: str) -> str:
    """Infer rm_type from file name for batch upload."""
    raw_name = _normalize_filename(file_name)
    normalized = f"_{re.sub(r'[^a-z0-9]+', '_', raw_name)}_"

    def contains_token(token: str) -> bool:
        return re.search(rf"(^|_)({token})($|_)", normalized) is not None

    if contains_token("paper") or "basepaper" in normalized or "base_paper" in normalized:
        return "Paper"
    if contains_token("base") and contains_token("paper"):
        return "Paper"
    if contains_token("al") or contains_token("foil") or "alfoil" in normalized or "al_foil" in normalized:
        return "AL"
    if contains_token("pe") or contains_token("pe_") or "pe_" in normalized:
        return "PE"

    raise ValueError(
        f"无法识别原材料类型：{file_name}，请使用文件名包含 Paper / AL / PE 关键词"
    )


def _build_abnormal_info(row: pd.Series) -> tuple[bool, str]:
    reasons: list[str] = []
    # 异常判定逻辑：仅基于良品标记 (quality_flag)
    # Y 为良品，N 为不良品。若为 N 则判定为异常。
    is_abnormal = False
    q_flag = str(row.get("quality_flag", "")).strip().upper()
    if q_flag == "N":
        is_abnormal = True
        reasons.append("不良品")
    
    # 其他辅助标记（不直接触发 is_abnormal，但记录原因供参考）
    if row.get("aging_category") in ["D", "E"]:
        reasons.append("超期库存(>180天)")
    if (_to_int(row.get("is_frozen")) or 0) != 0:
        reasons.append("已冻结")
    qc_value = _to_decimal(row.get("qc_qty"))
    if qc_value is not None and qc_value > 0:
        reasons.append("质检中")
    if str(_normalize_value(row.get("obsolete_reason")) or "").strip():
        reasons.append("呆滞原因")
        
    return (is_abnormal, ",".join(reasons))


def _get_material_mapping(db: Session) -> dict[str, models.MaterialMapping]:
    mapping_rows = db.query(models.MaterialMapping).all()
    return {
        normalize_material_code(item.sku): item
        for item in mapping_rows
        if normalize_material_code(item.sku)
    }


def parse_and_save_sap_upload(
    db: Session,
    file: UploadFile,
    snapshot_month: str,
    rm_type: str,
    uploaded_by: str | None,
) -> UploadResult:
    """Parse one SAP file and rewrite corresponding monthly snapshot rows."""
    df = _parse_rows(file)
    _validate_columns(df)

    work_df = df.rename(columns=RM_COLUMNS)[list(RM_COLUMNS.values())].copy()

    # Normalize to target types and required flags.
    work_df["snapshot_month"] = snapshot_month
    work_df["rm_category"] = rm_type
    work_df["is_abnormal"] = False
    work_df["abnormal_reasons"] = None

    # material_code / batch_no: SAP exports sometimes use scientific notation
    # (e.g. 1.9E+12). We force them to plain string here as a safety net,
    # even though _parse_rows already handled the raw columns before rename.
    work_df["material_code"] = work_df["material_code"].apply(
        normalize_material_code
    )
    work_df["batch_no"] = work_df["batch_no"].apply(normalize_batch_no)
    work_df["plant"] = work_df["plant"].apply(normalize_plant_code)
    work_df["plant_group"] = work_df["plant"].apply(derive_plant_group)

    mapping_map = _get_material_mapping(db)

    # 同一上传文件里若出现重复批次，保留最后一条
    work_df = work_df.drop_duplicates(subset=["batch_no"], keep="last")

    abnormal_count = 0
    prepared_rows = []
    for _, row in work_df.iterrows():
        is_abnormal, reasons = _build_abnormal_info(row)
        if is_abnormal:
            abnormal_count += 1
        mapped = mapping_map.get(normalize_material_code(row["material_code"]))
        # NOTE: `row` from iterrows() is a row snapshot; writing back to work_df
        # here does not guarantee the current `row` view will see updates.
        mapped_family = mapped.family if mapped is not None else None
        mapped_primary = mapped.category_primary if mapped is not None else None

        snapshot = models.InventorySnapshot(
            snapshot_month=_normalize_value(row["snapshot_month"]),
            batch_no=_normalize_value(row["batch_no"]),
            material_code=_normalize_value(row["material_code"]),
            material_name=_normalize_value(row["material_name"]),
            plant=_normalize_value(row["plant"]),
            plant_group=_normalize_value(row.get("plant_group")),
            bin_location=_normalize_value(row["bin_location"]),
            storage_location=_normalize_value(row["storage_location"]),
            storage_loc_desc=_normalize_value(row["storage_loc_desc"]),
            actual_stock=_to_decimal(row["actual_stock"]),
            weight_kg=_to_decimal(row["weight_kg"]),
            production_date=_to_date(row["production_date"]),
            inbound_date=_to_date(row["inbound_date"]),
            expiry_date=_to_date(row["expiry_date"]),
            quality_flag=_normalize_value(row["quality_flag"]),
            obsolete_reason=_normalize_value(row["obsolete_reason"]),
            obsolete_reason_desc=_normalize_value(row["obsolete_reason_desc"]),
            material_group=_normalize_value(row["material_group"]),
            material_type=_normalize_value(row["material_type"]),
            unit=_normalize_value(row["unit"]),
            supplier_code=_normalize_value(row["supplier_code"]),
            supplier_batch=_normalize_value(row["supplier_batch"]),
            supplier_name=_normalize_value(row["supplier_name"]),
            aging_category=_normalize_value(row["aging_category"]),
            aging_description=_normalize_value(row["aging_description"]),
            financial_cost=_to_decimal(row["financial_cost"]),
            production_order=_normalize_value(row["production_order"]),
            order_type=_normalize_value(row["order_type"]),
            order_type_name=_normalize_value(row["order_type_name"]),
            customer_code=_normalize_value(row["customer_code"]),
            customer_name=_normalize_value(row["customer_name"]),
            invoice_account=_normalize_value(row["invoice_account"]),
            invoice_account_name=_normalize_value(row["invoice_account_name"]),
            contract_code=_normalize_value(row["contract_code"]),
            contract_line_item=_normalize_value(row["contract_line_item"]),
            is_frozen=_to_int(row["is_frozen"]) or 0,
            qc_qty=_to_decimal(row["qc_qty"]) or 0,
            in_transit=_to_int(row["in_transit"]) or 0,
            currency=_normalize_value(row["currency"]),
            rm_category=rm_type,
            rm_family=_normalize_value(mapped_family),
            category_primary=_normalize_value(mapped_primary),
            is_abnormal=is_abnormal,
            abnormal_reasons=reasons,
        )
        if snapshot.batch_no:
            prepared_rows.append(snapshot)

    # 保留上传文件内后续行，避免重复批次造成主键冲突
    if not prepared_rows:
        raise ValueError("导入文件未解析到有效批次")

    db.query(models.InventorySnapshot).filter(
        models.InventorySnapshot.snapshot_month == snapshot_month,
        models.InventorySnapshot.rm_category == rm_type,
    ).delete(synchronize_session=False)
    db.bulk_save_objects(prepared_rows)
    db.flush()

    return UploadResult(
        snapshot_month=snapshot_month,
        rm_type=rm_type,
        file_name=file.filename or "unknown.xlsx",
        row_count=len(prepared_rows),
        abnormal_count=abnormal_count,
    )
