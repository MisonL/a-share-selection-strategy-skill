"""Realtime spot display helpers for stock selection outputs."""

from __future__ import annotations

from typing import Any

import pandas as pd

from stock_selection_symbols import normalize_symbol_values


SYMBOL_COLUMN_ALIASES = ["symbol", "code", "code_id", "stock_code", "ticker", "Ticker"]


def merge_spot_view(
    input_frame: pd.DataFrame, spot: pd.DataFrame | None
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if spot is None:
        return pd.DataFrame(columns=spot_columns()), spot_summary(0, 0)
    view = normalized_spot_view(spot)
    input_symbols = set(input_frame["symbol"].astype(str))
    matched = int(view["symbol"].isin(input_symbols).sum()) if not view.empty else 0
    return view, spot_summary(len(view), matched)


def merge_latest_spot_fields(scored: pd.DataFrame, spot_view: pd.DataFrame) -> pd.DataFrame:
    if scored.empty or spot_view.empty:
        return scored
    result = scored.copy()
    result["symbol"] = result["symbol"].astype(str).str.strip()
    return result.merge(spot_view, on="symbol", how="left")


def spot_summary(rows: int, matched: int) -> dict[str, Any]:
    return {
        "spot_rows": int(rows),
        "spot_matched_symbols": int(matched),
        "spot_unmatched_symbols": int(max(rows - matched, 0)),
    }


def normalized_spot_view(spot: pd.DataFrame) -> pd.DataFrame:
    source_frame = spot.reset_index(drop=True)
    symbol_values = first_existing_required(source_frame, SYMBOL_COLUMN_ALIASES, "symbol")
    result = pd.DataFrame({"symbol": normalize_symbol_values(symbol_values)})
    for source, target in spot_column_map().items():
        if source in source_frame.columns and target not in result.columns:
            result[target] = source_frame[source]
    for column in spot_columns():
        if column not in result.columns:
            result[column] = pd.NA
    return result[["symbol", *spot_columns()]].drop_duplicates(
        subset=["symbol"], keep="last"
    )


def spot_columns() -> list[str]:
    return ["spot_price", "spot_pct_chg", "spot_amount", "spot_industry"]


def spot_column_map() -> dict[str, str]:
    return {
        "spot_price": "spot_price",
        "price": "spot_price",
        "close": "spot_price",
        "spot_pct_chg": "spot_pct_chg",
        "pct_chg": "spot_pct_chg",
        "pctChg": "spot_pct_chg",
        "change_pct": "spot_pct_chg",
        "spot_amount": "spot_amount",
        "amount": "spot_amount",
        "spot_industry": "spot_industry",
        "industry": "spot_industry",
    }


def first_existing_required(frame: pd.DataFrame, columns: list[str], label: str) -> Any:
    for column in columns:
        if column in frame:
            return frame[column]
    raise ValueError(
        f"spot input requires {label} column; accepted aliases: {','.join(columns)}"
    )
