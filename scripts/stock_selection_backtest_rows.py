"""Row and summary helpers for buy-hold backtest outputs."""

from __future__ import annotations

from typing import Any

import pandas as pd


TRADABILITY_MODEL_NONE = "not_modeled"
TRADABILITY_MODEL_STATUS = "tradestatus_entry_exit_only"
LIMIT_RULES_MODEL = "not_modeled"


def completed_row(
    *,
    symbol: str,
    signal_date: Any,
    history: pd.DataFrame,
    entry_pos: int,
    exit_pos: int,
    holding_days: int,
    cost_bps: float,
    slippage_bps: float,
    require_tradable_bars: bool,
) -> dict[str, Any]:
    entry = history.iloc[entry_pos]
    exit_row = history.iloc[exit_pos]
    entry_close = float(entry["close"])
    exit_close = float(exit_row["close"])
    gross_return = exit_close / entry_close - 1
    total_deduction = bps_to_ratio(cost_bps + slippage_bps)
    return {
        **base_row(symbol, signal_date, require_tradable_bars=require_tradable_bars),
        "entry_date": entry["date"].date().isoformat(),
        "exit_date": exit_row["date"].date().isoformat(),
        "entry_close": entry_close,
        "exit_close": exit_close,
        "hold_days_requested": holding_days,
        "holding_period": int(exit_pos - entry_pos),
        "gross_return": gross_return,
        "cost_bps": cost_bps,
        "slippage_bps": slippage_bps,
        "return": gross_return - total_deduction,
        "missing_data": False,
        "missing_reason": "none",
        "status": "complete",
    }


def incomplete_row(
    *,
    symbol: str,
    signal_date: Any,
    holding_days: int,
    reason: str,
    cost_bps: float,
    slippage_bps: float,
    require_tradable_bars: bool = False,
) -> dict[str, Any]:
    return {
        **base_row(symbol, signal_date, require_tradable_bars=require_tradable_bars),
        "entry_date": "",
        "exit_date": "",
        "entry_close": pd.NA,
        "exit_close": pd.NA,
        "hold_days_requested": holding_days,
        "holding_period": pd.NA,
        "gross_return": pd.NA,
        "cost_bps": cost_bps,
        "slippage_bps": slippage_bps,
        "return": pd.NA,
        "missing_data": True,
        "missing_reason": reason,
        "status": "incomplete",
    }


def base_row(symbol: str, signal_date: Any, require_tradable_bars: bool = False) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "signal_date": str(signal_date),
        "cost_model": "round_trip_bps",
        "slippage_model": "round_trip_bps",
        "tradability_model": tradability_model(require_tradable_bars),
        "limit_rules_model": LIMIT_RULES_MODEL,
    }


def build_summary(
    result: pd.DataFrame,
    holding_days: int,
    cost_bps: float,
    slippage_bps: float,
    require_tradable_bars: bool,
) -> dict[str, Any]:
    completed = int((result["missing_data"] == False).sum())
    total = int(len(result))
    return {
        "candidates": total,
        "completed_trades": completed,
        "incomplete_trades": total - completed,
        "hold_days": int(holding_days),
        "cost_bps": float(cost_bps),
        "slippage_bps": float(slippage_bps),
        "tradability_required": bool(require_tradable_bars),
        "tradability_model": tradability_model(require_tradable_bars),
        "missing_reason_counts": missing_reason_counts(result),
    }


def bps_to_ratio(value: float) -> float:
    return float(value) / 10000.0


def tradability_model(require_tradable_bars: bool) -> str:
    if require_tradable_bars:
        return TRADABILITY_MODEL_STATUS
    return TRADABILITY_MODEL_NONE


def missing_reason_counts(result: pd.DataFrame) -> str:
    missing = result[result["missing_data"] == True]
    if missing.empty:
        return ""
    counts = missing["missing_reason"].value_counts().sort_index()
    return ",".join(f"{reason}:{count}" for reason, count in counts.items())
