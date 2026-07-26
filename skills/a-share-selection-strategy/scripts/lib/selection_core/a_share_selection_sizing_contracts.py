"""Pure field contracts shared by sizing and artifact validation."""

from __future__ import annotations

import math
from typing import Any

from lib.selection_core.a_share_selection_model_contracts import (
    EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
)


CAPITAL_FIELDS = ["weight", "notional", "quantity", "cash_reserved"]
SIZING_EXECUTION_MODEL = EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE
SIZING_EXECUTION_FIELDS = [
    "sizing_execution_model",
    "sizing_entry_date",
    "sizing_entry_price",
    "sizing_entry_price_field",
    "sizing_skip_reason",
]
SIZING_FIELDS = [
    "cash_budget",
    "lot_size",
    "capital_model",
    "signal_close",
    "cash_slot",
    "quantity",
    "cash_reserved",
    "notional",
    "weight",
    "sizing_claim_boundary",
    "unallocated",
    *SIZING_EXECUTION_FIELDS,
]
BACKTEST_CAPITAL_FIELDS = list(SIZING_FIELDS)


def is_non_finite_number(value: Any) -> bool:
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def require_finite_number(value: Any, name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def require_positive_number(value: Any, name: str) -> float:
    numeric = require_finite_number(value, name)
    if numeric <= 0:
        raise ValueError(f"{name} must be > 0")
    return numeric


def require_finite_non_negative_number(value: Any, name: str) -> float:
    numeric = require_finite_number(value, name)
    if numeric < 0:
        raise ValueError(f"{name} must be >= 0")
    return numeric


def require_integer_at_least(value: Any, name: str, minimum: int) -> int:
    numeric = require_finite_number(value, name)
    if not numeric.is_integer():
        raise ValueError(f"{name} must be an integer")
    integer = int(numeric)
    if integer < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return integer
