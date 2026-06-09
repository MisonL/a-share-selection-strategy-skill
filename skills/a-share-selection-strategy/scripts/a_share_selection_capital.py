"""Helpers for optional portfolio capital fields."""

from __future__ import annotations

from typing import Any

import pandas as pd


CAPITAL_FIELDS = ["weight", "notional", "quantity", "cash_reserved"]
BACKTEST_CAPITAL_FIELDS = [
    "capital_model",
    "sizing_claim_boundary",
    "weight",
    "notional",
    "quantity",
    "cash_reserved",
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
]
DAILY_CAPACITY_FIELDS = {
    "weight": "gross_weight",
    "notional": "gross_notional",
    "cash_reserved": "cash_reserved",
}
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
    return {
        output: float(group[source].sum())
        for source, output in DAILY_CAPACITY_FIELDS.items()
        if source in group
    }


def max_capacity_summary(daily: pd.DataFrame, field: str) -> tuple[float | None, list[str]]:
    if daily.empty or field not in daily:
        return None, []
    maximum = float(daily[field].max())
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
    if limit < 0:
        raise ValueError(f"{summary_field.replace('_', '-')} must be >= 0")
    if field not in summary["capital_fields_present"]:
        violations.append(f"{field}_missing")
        return
    maximum = summary[summary_field] or 0.0
    if maximum > limit:
        violations.append(f"{summary_field}={maximum} limit={limit}")
