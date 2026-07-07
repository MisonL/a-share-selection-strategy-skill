"""Tradability metadata helpers for local price gate files."""

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


from typing import Any

import pandas as pd


TRADABILITY_COLUMNS = [
    "symbol",
    "date",
    "tradestatus",
    "isST",
    "preclose",
    "pctChg",
    "volume",
    "amount",
    "turn",
]
TRADABILITY_FIELDS = ["preclose", "pctChg", "tradestatus", "isST"]


def prefixed_tradability_stats(frame: pd.DataFrame, prefix: str) -> dict[str, Any]:
    return {f"{prefix}{key}": value for key, value in tradability_stats(frame).items()}


def tradability_stats(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty or "tradestatus" not in frame:
        missing = int(len(frame)) if not frame.empty else 0
        return empty_tradability_stats(missing)
    status = frame["tradestatus"].astype(str).str.strip()
    missing = frame[status.eq("")]
    non_trading = frame[status.ne("1")]
    st_rows = st_mask(frame)
    has_symbol = "symbol" in frame
    return {
        "tradability_fields": TRADABILITY_FIELDS,
        "tradestatus_missing_rows": int(len(missing)),
        "non_trading_rows": int(len(non_trading)),
        "non_trading_symbols": symbol_values(non_trading) if has_symbol else [],
        "non_trading_row_examples": tradability_examples(non_trading),
        "st_rows": int(st_rows.sum()),
        "st_symbols": symbol_values(frame.loc[st_rows]) if has_symbol else [],
    }


def empty_tradability_stats(missing_rows: int) -> dict[str, Any]:
    return {
        "tradability_fields": TRADABILITY_FIELDS,
        "tradestatus_missing_rows": missing_rows,
        "non_trading_rows": 0,
        "non_trading_symbols": [],
        "non_trading_row_examples": [],
        "st_rows": 0,
        "st_symbols": [],
    }


def st_mask(frame: pd.DataFrame) -> pd.Series:
    if "isST" not in frame:
        return pd.Series([False] * len(frame), index=frame.index)
    return frame["isST"].astype(str).str.strip().eq("1")


def tradability_examples(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    columns = [column for column in TRADABILITY_COLUMNS if column in frame]
    return frame[columns].head(10).to_dict("records")


def symbol_values(frame: pd.DataFrame) -> list[str]:
    return sorted(frame["symbol"].astype(str).unique().tolist())


def tradability_failure_reason(
    history: pd.DataFrame,
    entry_pos: int,
    exit_pos: int,
    *,
    require_holding_period: bool = False,
) -> str:
    if "tradestatus" not in history:
        return "missing_tradestatus"
    if not is_tradable_status(history.iloc[entry_pos].get("tradestatus")):
        return "non_tradable_entry"
    if not is_tradable_status(history.iloc[exit_pos].get("tradestatus")):
        return "non_tradable_exit"
    if require_holding_period:
        holding_window = history.iloc[entry_pos : exit_pos + 1]
        if not holding_window["tradestatus"].map(is_tradable_status).all():
            return "non_tradable_holding_period"
    return ""


def is_tradable_status(value: object) -> bool:
    return str(value).strip() == "1"
