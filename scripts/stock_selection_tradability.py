"""Tradability metadata helpers for local price gate files."""

from __future__ import annotations

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
    return {
        "tradability_fields": TRADABILITY_FIELDS,
        "tradestatus_missing_rows": int(len(missing)),
        "non_trading_rows": int(len(non_trading)),
        "non_trading_symbols": sorted(non_trading["symbol"].astype(str).unique().tolist()),
        "non_trading_row_examples": tradability_examples(non_trading),
        "st_rows": int(st_rows.sum()),
        "st_symbols": sorted(frame.loc[st_rows, "symbol"].astype(str).unique().tolist()),
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


def tradability_failure_reason(
    history: pd.DataFrame,
    entry_pos: int,
    exit_pos: int,
) -> str:
    if "tradestatus" not in history:
        return "missing_tradestatus"
    if not is_tradable_status(history.iloc[entry_pos].get("tradestatus")):
        return "non_tradable_entry"
    if not is_tradable_status(history.iloc[exit_pos].get("tradestatus")):
        return "non_tradable_exit"
    return ""


def is_tradable_status(value: object) -> bool:
    return str(value).strip() == "1"
