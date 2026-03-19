"""Shared material code normalization helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
import re

import pandas as pd


_INT_LIKE_RE = re.compile(r"^\d+\.0+$")
_SCI_RE = re.compile(r"^\d+(?:\.\d+)?[eE][+-]?\d+$")


def normalize_material_code(value: Any) -> str | None:
    """Normalize material identifiers while preserving meaningful leading zeros."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None

    if text.isdigit():
        return text

    if _INT_LIKE_RE.fullmatch(text):
        return text.split(".", 1)[0]

    if _SCI_RE.fullmatch(text):
        try:
            dec = Decimal(text)
        except InvalidOperation:
            return text
        if dec == dec.to_integral_value():
            return str(dec.quantize(Decimal("1")))

    return text

