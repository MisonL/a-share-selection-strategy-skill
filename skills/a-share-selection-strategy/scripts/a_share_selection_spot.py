"""Realtime spot display helpers for A-share selection outputs."""

from __future__ import annotations

from typing import Any

import pandas as pd

from a_share_selection_symbols import (
    A_SHARE_EXCHANGES,
    normalize_hk_symbol,
    normalize_symbol_values,
    valid_hk_symbol_text,
)


SYMBOL_COLUMN_ALIASES = ["symbol", "code", "code_id", "stock_code", "ticker", "Ticker"]


def merge_spot_view(
    input_frame: pd.DataFrame, spot: pd.DataFrame | None
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if spot is None:
        return pd.DataFrame(columns=spot_columns()), spot_summary(0, 0)
    input_symbols = normalized_input_symbols(input_frame)
    view = normalized_spot_view(spot, input_symbols=input_symbols)
    matched = int(view["symbol"].isin(input_symbols).sum()) if not view.empty else 0
    return view, spot_summary(len(view), matched)


def merge_latest_spot_fields(scored: pd.DataFrame, spot_view: pd.DataFrame) -> pd.DataFrame:
    if scored.empty or spot_view.empty:
        return scored
    result = scored.copy()
    result["symbol"] = result["symbol"].astype(str).str.strip()
    merged = result.merge(spot_view, on="symbol", how="left", suffixes=("", "_spot"))
    if "name_spot" in merged.columns:
        merged["name"] = merged["name"].where(
            merged["name"].notna()
            & merged["name"].astype(str).str.strip().ne("")
            & ~merged["name"].astype(str).str.fullmatch(r"\d+"),
            merged["name_spot"],
        )
        merged = merged.drop(columns=["name_spot"])
    return merged


def spot_summary(rows: int, matched: int) -> dict[str, Any]:
    return {
        "spot_rows": int(rows),
        "spot_matched_symbols": int(matched),
        "spot_unmatched_symbols": int(max(rows - matched, 0)),
    }


def normalized_spot_view(
    spot: pd.DataFrame,
    input_symbols: set[str] | None = None,
) -> pd.DataFrame:
    source_frame = spot.reset_index(drop=True)
    symbol_values = first_existing_required(source_frame, SYMBOL_COLUMN_ALIASES, "symbol")
    result = pd.DataFrame(
        {
            "symbol": normalize_spot_symbol_values(
                symbol_values,
                input_symbols=input_symbols or set(),
            )
        }
    )
    for source, target in spot_column_map().items():
        if source in source_frame.columns and target not in result.columns:
            result[target] = source_frame[source]
    for column in spot_columns():
        if column not in result.columns:
            result[column] = pd.NA
    return result[["symbol", *spot_columns()]].drop_duplicates(
        subset=["symbol"], keep="last"
    )


def normalized_input_symbols(frame: pd.DataFrame) -> set[str]:
    symbols = set(frame["symbol"].astype(str).str.strip())
    markets = normalized_market_values(frame)
    if any(is_hk_market(value) for value in markets):
        symbols.update(
            alias
            for symbol in list(symbols)
            if (alias := hk_aliases(symbol))
        )
    return symbols


def normalized_market_values(frame: pd.DataFrame) -> list[str]:
    if "market" not in frame:
        return []
    return list(frame["market"].astype(str).str.strip().str.lower())


def is_hk_market(value: str) -> bool:
    return value in {"hk", "港股", "hong kong", "hong-kong"}


def normalize_spot_symbol_values(values: Any, input_symbols: set[str]) -> list[str]:
    base_values = normalize_symbol_values(values, allowed_exchanges=A_SHARE_EXCHANGES)
    return [
        normalized_spot_symbol(raw, normalized, input_symbols)
        for raw, normalized in zip(values, base_values)
    ]


def normalized_spot_symbol(raw: Any, normalized: str, input_symbols: set[str]) -> str:
    if normalized in input_symbols:
        return normalized
    hk = hk_aliases(raw)
    if hk and hk in input_symbols:
        return hk
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
