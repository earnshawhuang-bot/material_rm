"""Material mapping import and maintenance services."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import UploadFile
from sqlalchemy.orm import Session

from .. import models
from .material_service import normalize_material_code


MAPPING_REQUIRED_COLUMNS = {
    "sku": "sku",
    "物料编码": "sku",
    "material_code": "sku",
    "materialcode": "sku",
    "类别": "category",
    "品类": "category",
    "category": "category",
    "categoryname": "category",
    "家族": "family",
    "family": "family",
    "family_name": "family",
    "familyname": "family",
    "一级分类": "category_primary",
    "category_primary": "category_primary",
    "categoryprimary": "category_primary",
    "category primary": "category_primary",
    "primarycategory": "category_primary",
    "primary category": "category_primary",
    "主分类": "category_primary",
}


@dataclass
class MappingUploadResult:
    file_name: str
    row_count: int
    replaced: bool


def _normalize_str(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _normalize_sku(value: Any) -> str | None:
    """Compatibility wrapper for SKU normalization."""
    return normalize_material_code(value)


def _to_normalized_columns(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in df.columns:
        key = str(row).strip().replace(" ", "").lower()
        for source, target in MAPPING_REQUIRED_COLUMNS.items():
            if key == str(source).strip().replace(" ", "").lower():
                rows.append((str(row), target))
                break
        else:
            rows.append((str(row), str(row).strip()))
    return df.rename(columns=dict(rows))


def _parse_file(file: UploadFile) -> pd.DataFrame:
    raw = file.file.read()
    try:
        # Read all mapping columns as text to avoid Excel auto-casting.
        # This is especially important for SKU, which is numeric in the sheet
        # but must be matched as a text key in the database.
        return pd.read_excel(BytesIO(raw), dtype=str)
    except Exception as exc:
        raise ValueError("映射文件必须为 Excel 文件(.xlsx)") from exc


def parse_and_upload_mapping(file: UploadFile, db: Session) -> MappingUploadResult:
    """Import mapping rows, replacing existing mapping when sku appears in file."""
    df = _parse_file(file)
    if df.empty:
        raise ValueError("映射文件无内容")

    df = _to_normalized_columns(df)
    df.columns = [str(col).strip() for col in df.columns]

    required = {"sku"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"映射文件缺少必填列: {', '.join(missing)}")

    for col in ("category", "family", "category_primary"):
        if col not in df.columns:
            df[col] = None

    work_df = df[["sku", "category", "family", "category_primary"]].copy()
    work_df = work_df.drop_duplicates(subset=["sku"], keep="last")
    if "sku" not in work_df.columns:
        raise ValueError("映射文件缺少 sku 列")

    prepared_rows = []
    for _, row in work_df.iterrows():
        sku = _normalize_sku(row["sku"])
        if not sku:
            continue
        prepared_rows.append(
            models.MaterialMapping(
                sku=sku,
                category=_normalize_str(row["category"]),
                family=_normalize_str(row["family"]),
                category_primary=_normalize_str(row["category_primary"]),
            )
        )

    if not prepared_rows:
        raise ValueError("映射文件未解析到有效行")

    db.query(models.MaterialMapping).delete(synchronize_session=False)
    db.bulk_save_objects(prepared_rows)
    db.flush()
    return MappingUploadResult(
        file_name=file.filename or "unknown.xlsx",
        row_count=len(prepared_rows),
        replaced=True,
    )


def backfill_snapshot_mapping(db: Session) -> int:
    """Refresh historical snapshots using the latest mapping table.

    This closes the operational loop: if mapping is uploaded after SAP facts,
    existing snapshots still get `rm_family` / `category_primary` backfilled
    without requiring the user to re-upload SAP files.
    """
    mapping_rows = db.query(models.MaterialMapping).all()
    mapping_map = {
        normalize_material_code(item.sku): item
        for item in mapping_rows
        if normalize_material_code(item.sku)
    }

    snapshots = db.query(models.InventorySnapshot).all()
    updated = 0
    for snapshot in snapshots:
        mapped = mapping_map.get(normalize_material_code(snapshot.material_code))
        new_family = mapped.family if mapped else None
        new_primary = mapped.category_primary if mapped else None
        if snapshot.rm_family != new_family or snapshot.category_primary != new_primary:
            snapshot.rm_family = new_family
            snapshot.category_primary = new_primary
            updated += 1

    db.flush()
    return updated


def list_mappings(db: Session) -> list[models.MaterialMapping]:
    return db.query(models.MaterialMapping).order_by(models.MaterialMapping.sku).all()
