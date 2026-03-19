"""Shared batch number normalization helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
import re

import pandas as pd


_INT_LIKE_RE = re.compile(r"^\d+\.0+$")
_SCI_RE = re.compile(r"^\d+(?:\.\d+)?[eE][+-]?\d+$")


def normalize_batch_no(value: Any) -> str | None:
    """Normalize batch identifiers while preserving meaningful leading zeros."""
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

    # Pure digit strings are already in the desired identifier form.
    if text.isdigit():
        return text

    # Excel or pandas sometimes stringify integer-like values as "327434.0".
    if _INT_LIKE_RE.fullmatch(text):
        return text.split(".", 1)[0]

    # Scientific notation should collapse back to a plain integer identifier.
    if _SCI_RE.fullmatch(text):
        try:
            dec = Decimal(text)
        except InvalidOperation:
            return text
        if dec == dec.to_integral_value():
            return str(dec.quantize(Decimal("1")))

    return text
