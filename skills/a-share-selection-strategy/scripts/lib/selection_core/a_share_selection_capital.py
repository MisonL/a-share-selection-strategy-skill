"""Helpers for optional portfolio capital fields."""

from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _SCRIPT_PATH = Path(__file__).resolve()
    _SCRIPTS_DIR = next(
        parent for parent in _SCRIPT_PATH.parents if parent.name == "scripts"
    )
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from lib.a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)


from dataclasses import dataclass
import math
from typing import Any

import pandas as pd

from lib.selection_core.a_share_selection_sizing_contracts import (
    BACKTEST_CAPITAL_FIELDS,
    CAPITAL_FIELDS,
    SIZING_EXECUTION_MODEL,
    SIZING_FIELDS,
    is_non_finite_number,
    require_finite_non_negative_number,
    require_integer_at_least,
    require_positive_number,
)


DAILY_CAPACITY_FIELDS = {
    "weight": "gross_weight",
    "notional": "gross_notional",
    "cash_reserved": "cash_reserved",
}


@dataclass(frozen=True)
class NextObservedOpenEntry:
    signal_position: int
    entry_position: int
    entry_date: str
    entry_price: float


def next_observed_open_entry(
    history: pd.DataFrame, signal_date: Any
) -> tuple[NextObservedOpenEntry | None, str]:
    positions = [
        position
        for position, value in enumerate(history["date"])
        if value == signal_date
    ]
    if not positions:
        return None, "missing_entry_price"
    signal_position = positions[0]
    entry_position = signal_position + 1
    if entry_position >= len(history):
        return None, "missing_next_observed_bar"
    entry = history.iloc[entry_position]
    entry_price = finite_positive_price(entry.get("open"))
    if entry_price is None:
        return None, "invalid_entry_open"
    entry_date = pd.to_datetime(entry["date"], errors="coerce")
    if pd.isna(entry_date):
        return None, "invalid_entry_date"
    return (
        NextObservedOpenEntry(
            signal_position=signal_position,
            entry_position=entry_position,
            entry_date=entry_date.date().isoformat(),
            entry_price=entry_price,
        ),
        "",
    )


def finite_positive_price(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric <= 0:
        return None
    return numeric


def lot_floor_quantity(
    cash_available: Any,
    entry_price: Any,
    lot_size: Any,
) -> int:
    cash_available = require_finite_non_negative_number(cash_available, "cash-slot")
    entry_price = require_positive_number(entry_price, "sizing-entry-price")
    lot_size = require_integer_at_least(lot_size, "lot-size", 1)
    try:
        lot_cost = entry_price * lot_size
    except OverflowError as exc:
        raise ValueError("lot cost must be finite") from exc
    if not math.isfinite(lot_cost) or lot_cost <= 0:
        raise ValueError("lot cost must be finite and > 0")
    lot_count = cash_available / lot_cost
    if not math.isfinite(lot_count) or lot_count < 0:
        raise ValueError("lot quantity calculation must be finite")
    quantity = int(lot_count) * lot_size
    require_finite_non_negative_number(quantity, "quantity")
    return quantity


SUMMARY_CAPACITY_FIELDS = {
    "gross_weight": "max_gross_weight",
    "gross_notional": "max_gross_notional",
    "cash_reserved": "max_cash_reserved",
}


def add_candidate_capital_fields(
    result: pd.DataFrame,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    present = [field for field in BACKTEST_CAPITAL_FIELDS if field in candidates]
    if not present:
        return result
    if len(result) != len(candidates):
        raise ValueError("candidate and backtest result row counts differ")
    enriched = result.copy()
    source = candidates.reset_index(drop=True)
    for field in present:
        enriched[field] = source[field]
    return enriched


def normalize_complete_capital_fields(complete: pd.DataFrame) -> pd.DataFrame:
    result = complete.copy()
    for field in CAPITAL_FIELDS:
        if field not in result:
            continue
        if result[field].map(is_non_finite_number).any():
            raise ValueError(f"{field} must be finite for complete trades")
        values = pd.to_numeric(result[field], errors="coerce")
        if values.isna().any():
            raise ValueError(f"{field} must be numeric for complete trades")
        if (values < 0).any():
            raise ValueError(f"{field} must be >= 0 for complete trades")
        result[field] = values
    return result


def trade_capital_values(row: pd.Series) -> dict[str, float]:
    return {field: float(row[field]) for field in CAPITAL_FIELDS if field in row}


def daily_capacity_values(group: pd.DataFrame) -> dict[str, float]:
    result = {}
    for source, output in DAILY_CAPACITY_FIELDS.items():
        if source not in group:
            continue
        try:
            total = math.fsum(float(value) for value in group[source])
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError(f"daily {output} must be finite") from exc
        result[output] = require_finite_non_negative_number(total, f"daily-{output}")
    return result


def max_capacity_summary(
    daily: pd.DataFrame, field: str
) -> tuple[float | None, list[str]]:
    if daily.empty or field not in daily:
        return None, []
    maximum = require_finite_non_negative_number(
        daily[field].max(), field.replace("_", "-")
    )
    dates = daily.loc[daily[field] == maximum, "date"].astype(str).tolist()
    return maximum, dates


def capacity_summary_fields(daily: pd.DataFrame) -> dict[str, Any]:
    result = {}
    for daily_field, summary_field in SUMMARY_CAPACITY_FIELDS.items():
        maximum, dates = max_capacity_summary(daily, daily_field)
        result[summary_field] = maximum
        result[f"{summary_field}_dates"] = dates
    return result


def capacity_gate(
    summary: dict[str, Any],
    violations: list[str],
    field: str,
    summary_field: str,
    limit: float | None,
) -> None:
    if limit is None:
        return
    limit = require_finite_non_negative_number(limit, summary_field.replace("_", "-"))
    if field not in summary["capital_fields_present"]:
        violations.append(f"{field}_missing")
        return
    raw_maximum = summary[summary_field]
    maximum = (
        0.0
        if raw_maximum is None
        else require_finite_non_negative_number(raw_maximum, summary_field)
    )
    if maximum > limit:
        violations.append(f"{summary_field}={maximum} limit={limit}")
