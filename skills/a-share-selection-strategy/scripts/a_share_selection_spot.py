"""Realtime spot display helpers for A-share selection outputs."""

from __future__ import annotations

from typing import Any

import pandas as pd

from a_share_selection_symbols import (
    A_SHARE_EXCHANGES,
    normalize_hk_symbol,
    normalize_symbol_values,
    stock_symbol_key,
    valid_hk_symbol_text,
)


SYMBOL_COLUMN_ALIASES = ["symbol", "code", "code_id", "stock_code", "ticker", "Ticker"]


def merge_spot_view(
    input_frame: pd.DataFrame, spot: pd.DataFrame | None
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if spot is None:
        return pd.DataFrame(columns=spot_columns()), spot_summary(0, 0)
    input_symbols = preferred_input_symbol_map(input_frame)
    view = normalized_spot_view(spot, preferred_symbols=input_symbols)
    matched = int(view["_symbol_key"].isin(input_symbols.keys()).sum()) if not view.empty else 0
    return view, spot_summary(len(view), matched)


def merge_latest_spot_fields(scored: pd.DataFrame, spot_view: pd.DataFrame) -> pd.DataFrame:
    if scored.empty or spot_view.empty:
        return scored
    result = scored.copy()
    result["symbol"] = result["symbol"].astype(str).str.strip()
    result["_symbol_key"] = result["symbol"].map(stock_symbol_key)
    merged = result.merge(spot_view, on="_symbol_key", how="left", suffixes=("", "_spot"))
    if "symbol_spot" in merged.columns:
        merged = merged.drop(columns=["symbol_spot"])
    if "name_spot" in merged.columns:
        merged["name"] = merged["name"].where(
            merged["name"].notna()
            & merged["name"].astype(str).str.strip().ne("")
            & ~merged["name"].astype(str).str.fullmatch(r"\d+"),
            merged["name_spot"],
        )
        merged = merged.drop(columns=["name_spot"])
    return merged.drop(columns=["_symbol_key"])


def spot_summary(rows: int, matched: int) -> dict[str, Any]:
    return {
        "spot_rows": int(rows),
        "spot_matched_symbols": int(matched),
        "spot_unmatched_symbols": int(max(rows - matched, 0)),
    }


def normalized_spot_view(
    spot: pd.DataFrame,
    preferred_symbols: dict[str, str] | None = None,
) -> pd.DataFrame:
    source_frame = spot.reset_index(drop=True)
    symbol_values = first_existing_required(source_frame, SYMBOL_COLUMN_ALIASES, "symbol")
    preferred_symbols = preferred_symbols or {}
    result = pd.DataFrame(
        {
            "_symbol_key": [stock_symbol_key(value) for value in symbol_values],
            "symbol": normalize_spot_symbol_values(
                symbol_values,
                preferred_symbols=preferred_symbols,
            )
        }
    )
    for source, target in spot_column_map().items():
        if source in source_frame.columns and target not in result.columns:
            result[target] = source_frame[source]
    for column in spot_columns():
        if column not in result.columns:
            result[column] = pd.NA
    return result[["_symbol_key", "symbol", *spot_columns()]].drop_duplicates(
        subset=["_symbol_key"], keep="last"
    )


def preferred_input_symbol_map(frame: pd.DataFrame) -> dict[str, str]:
    if "symbol" not in frame:
        return {}
    preferred: dict[str, str] = {}
    for symbol in frame["symbol"].astype(str).str.strip():
        key = stock_symbol_key(symbol)
        if key and key not in preferred:
            preferred[key] = symbol
    return preferred


def normalize_spot_symbol_values(values: Any, preferred_symbols: dict[str, str]) -> list[str]:
    base_values = normalize_symbol_values(values, allowed_exchanges=A_SHARE_EXCHANGES)
    return [
        normalized_spot_symbol(raw, normalized, preferred_symbols.get(stock_symbol_key(raw), ""))
        for raw, normalized in zip(values, base_values)
    ]


def normalized_spot_symbol(raw: Any, normalized: str, preferred_symbol: str) -> str:
    if preferred_symbol:
        return preferred_symbol
    hk = hk_aliases(raw)
    return hk or normalized


def hk_aliases(value: Any) -> str:
    if not valid_hk_symbol_text(value):
        return ""
    return normalize_hk_symbol(value).zfill(5)


def spot_columns() -> list[str]:
    return ["name", "spot_price", "spot_pct_chg", "spot_amount", "spot_industry"]


def spot_column_map() -> dict[str, str]:
    return {
        "name": "name",
        "stock_name": "name",
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

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
