"""Row and summary helpers for buy-hold backtest outputs."""

from __future__ import annotations

import math

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


from typing import Any

import pandas as pd

from lib.selection_core.a_share_selection_model_contracts import (
    EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
    LIMIT_RULES_MODEL_NOT_MODELED,
    TRADABILITY_MODEL_ENTRY_EXIT,
    tradability_model,
)
from lib.selection_core.a_share_selection_sizing_contracts import (
    require_finite_non_negative_number,
    require_finite_number,
)

TRADABILITY_MODEL_STATUS = TRADABILITY_MODEL_ENTRY_EXIT
LIMIT_RULES_MODEL = LIMIT_RULES_MODEL_NOT_MODELED


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
    require_holding_period_tradable: bool = False,
) -> dict[str, Any]:
    row = completed_or_incomplete_row(
        symbol=symbol,
        signal_date=signal_date,
        history=history,
        entry_pos=entry_pos,
        exit_pos=exit_pos,
        holding_days=holding_days,
        cost_bps=cost_bps,
        slippage_bps=slippage_bps,
        require_tradable_bars=require_tradable_bars,
        require_holding_period_tradable=require_holding_period_tradable,
    )
    if row["status"] != "complete":
        raise ValueError(row["missing_reason"])
    return row


def completed_or_incomplete_row(
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
    require_holding_period_tradable: bool = False,
    execution_model: str = EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
) -> dict[str, Any]:
    cost_bps, slippage_bps, total_cost_bps = validated_costs(cost_bps, slippage_bps)
    entry = history.iloc[entry_pos]
    exit_row = history.iloc[exit_pos]
    entry_price = finite_positive_price(entry.get("open"))
    if entry_price is None:
        return incomplete_row(
            symbol=symbol,
            signal_date=signal_date,
            holding_days=holding_days,
            reason="invalid_entry_open",
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
            require_tradable_bars=require_tradable_bars,
            require_holding_period_tradable=require_holding_period_tradable,
            execution_model=execution_model,
        )
    exit_price = finite_positive_price(exit_row.get("close"))
    if exit_price is None:
        return incomplete_row(
            symbol=symbol,
            signal_date=signal_date,
            holding_days=holding_days,
            reason="invalid_exit_close",
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
            require_tradable_bars=require_tradable_bars,
            require_holding_period_tradable=require_holding_period_tradable,
            execution_model=execution_model,
        )
    gross_return = require_finite_number(exit_price / entry_price - 1, "gross-return")
    total_deduction = bps_to_ratio(total_cost_bps)
    net_return = require_finite_number(gross_return - total_deduction, "return")
    return {
        **base_row(
            symbol,
            signal_date,
            require_tradable_bars=require_tradable_bars,
            require_holding_period_tradable=require_holding_period_tradable,
            execution_model=execution_model,
        ),
        "entry_date": entry["date"].date().isoformat(),
        "exit_date": exit_row["date"].date().isoformat(),
        "entry_price": entry_price,
        "entry_price_field": "open",
        "exit_price": exit_price,
        "exit_price_field": "close",
        "hold_days_requested": holding_days,
        "holding_observed_bars": int(exit_pos - entry_pos + 1),
        "holding_period": int(exit_pos - entry_pos),
        "gross_return": gross_return,
        "cost_bps": cost_bps,
        "slippage_bps": slippage_bps,
        "return": net_return,
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
    require_holding_period_tradable: bool = False,
    execution_model: str = EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
) -> dict[str, Any]:
    cost_bps, slippage_bps, _total_cost_bps = validated_costs(cost_bps, slippage_bps)
    return {
        **base_row(
            symbol,
            signal_date,
            require_tradable_bars=require_tradable_bars,
            require_holding_period_tradable=require_holding_period_tradable,
            execution_model=execution_model,
        ),
        "entry_date": "",
        "exit_date": "",
        "entry_price": pd.NA,
        "entry_price_field": "open",
        "exit_price": pd.NA,
        "exit_price_field": "close",
        "hold_days_requested": holding_days,
        "holding_observed_bars": pd.NA,
        "holding_period": pd.NA,
        "gross_return": pd.NA,
        "cost_bps": cost_bps,
        "slippage_bps": slippage_bps,
        "return": pd.NA,
        "missing_data": True,
        "missing_reason": reason,
        "status": "incomplete",
    }


def base_row(
    symbol: str,
    signal_date: Any,
    require_tradable_bars: bool = False,
    require_holding_period_tradable: bool = False,
    execution_model: str = EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "signal_date": str(signal_date),
        "execution_model": execution_model,
        "cost_model": "round_trip_bps",
        "slippage_model": "round_trip_bps",
        "tradability_model": tradability_model(
            require_tradable_bars,
            require_holding_period_tradable=require_holding_period_tradable,
        ),
        "limit_rules_model": LIMIT_RULES_MODEL,
    }


def build_summary(
    result: pd.DataFrame,
    holding_days: int,
    cost_bps: float,
    slippage_bps: float,
    require_tradable_bars: bool,
    require_holding_period_tradable: bool = False,
    execution_model: str = EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
) -> dict[str, Any]:
    cost_bps, slippage_bps, _total_cost_bps = validated_costs(cost_bps, slippage_bps)
    completed = int((result["missing_data"] == False).sum())
    total = int(len(result))
    return {
        "candidates": total,
        "completed_trades": completed,
        "incomplete_trades": total - completed,
        "hold_days": int(holding_days),
        "cost_bps": float(cost_bps),
        "slippage_bps": float(slippage_bps),
        "execution_model": execution_model,
        "tradability_required": bool(
            require_tradable_bars or require_holding_period_tradable
        ),
        "tradability_model": tradability_model(
            require_tradable_bars,
            require_holding_period_tradable=require_holding_period_tradable,
        ),
        "missing_reason_counts": missing_reason_counts(result),
    }


def bps_to_ratio(value: float) -> float:
    value = require_finite_non_negative_number(value, "total-cost-bps")
    return require_finite_number(value / 10000.0, "total-cost-ratio")


def validated_costs(cost_bps: float, slippage_bps: float) -> tuple[float, float, float]:
    cost_bps = require_finite_non_negative_number(cost_bps, "cost-bps")
    slippage_bps = require_finite_non_negative_number(slippage_bps, "slippage-bps")
    total_cost_bps = require_finite_non_negative_number(
        cost_bps + slippage_bps, "total-cost-bps"
    )
    return cost_bps, slippage_bps, total_cost_bps


def finite_positive_price(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric <= 0:
        return None
    return numeric


def missing_reason_counts(result: pd.DataFrame) -> str:
    missing = result[result["missing_data"] == True]
    if missing.empty:
        return ""
    counts = missing["missing_reason"].value_counts().sort_index()
    return ",".join(f"{reason}:{count}" for reason, count in counts.items())
