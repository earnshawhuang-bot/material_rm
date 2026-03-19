"""Plant normalization and grouping helpers."""

from __future__ import annotations

from typing import Any
import re

from sqlalchemy import case, literal

VALID_PLANT_CODES = {"3000", "3001", "3301"}
PLANT_GROUPS = {
    "3000": "KS",
    "3001": "KS",
    "3301": "IDN",
}


def normalize_plant_code(value: Any) -> str | None:
    """Normalize raw SAP plant values like 3301 / 3301.0 / ' 3301 '."""
    if value is None:
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None

    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    elif re.fullmatch(r"\d+", text):
        pass
    else:
        try:
            numeric = float(text)
            if numeric.is_integer():
                text = str(int(numeric))
        except (TypeError, ValueError):
            pass

    if text not in VALID_PLANT_CODES:
        raise ValueError(f"工厂编码不受支持: {value}")
    return text


def derive_plant_group(plant_code: str | None) -> str | None:
    return PLANT_GROUPS.get(plant_code) if plant_code else None


def normalize_plant_filter(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if text in PLANT_GROUPS.values():
        return text
    return normalize_plant_code(text)


def build_plant_group_expr(plant_code_col, plant_group_col):
    """SQL expression that falls back to plant_code when plant_group is null."""
    return case(
        (plant_group_col.isnot(None), plant_group_col),
        (plant_code_col == "3301", literal("IDN")),
        (plant_code_col.in_(["3000", "3001"]), literal("KS")),
        else_=literal(None),
    )
