"""Helpers for optional portfolio capital fields."""

from __future__ import annotations

import pandas as pd


CAPITAL_FIELDS = ["weight", "notional", "quantity", "cash_reserved"]


def add_candidate_capital_fields(
    result: pd.DataFrame,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    present = [field for field in CAPITAL_FIELDS if field in candidates]
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


def max_gross_weight_summary(daily: pd.DataFrame) -> tuple[float | None, list[str]]:
    if daily.empty or "gross_weight" not in daily:
        return None, []
    max_weight = float(daily["gross_weight"].max())
    dates = daily.loc[daily["gross_weight"] == max_weight, "date"].astype(str).tolist()
    return max_weight, dates
