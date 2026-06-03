"""Universe filtering helpers for A-share selection scoring."""

from __future__ import annotations

from typing import Any

import pandas as pd


EMPTY_UNIVERSE_SUMMARY = {
    "market_filtered_symbols": 0,
    "prefix_allow_filtered_symbols": 0,
    "prefix_excluded_symbols": 0,
}


def apply_universe_filter(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, int]]:
    universe = config.get("universe", {})
    result = frame.copy()
    summary = dict(EMPTY_UNIVERSE_SUMMARY)
    result = apply_market_filter(result, universe, summary)
    result = apply_prefix_allow_filter(result, universe, summary)
    result = apply_prefix_exclude_filter(result, universe, summary)
    return result.reset_index(drop=True), summary


def apply_market_filter(
    frame: pd.DataFrame, universe: dict[str, Any], summary: dict[str, int]
) -> pd.DataFrame:
    market = universe.get("market")
    if not market or "market" not in frame.columns:
        return frame
    before = frame["symbol"].nunique()
    result = frame[frame["market"].astype(str) == str(market)]
    summary["market_filtered_symbols"] = int(before - result["symbol"].nunique())
    return result


def apply_prefix_allow_filter(
    frame: pd.DataFrame, universe: dict[str, Any], summary: dict[str, int]
) -> pd.DataFrame:
    allow_regex = universe.get("symbol_prefix_allow_regex")
    if not allow_regex:
        return frame
    result = frame.copy()
    result["symbol"] = symbol_text(result)
    before = result["symbol"].nunique()
    result = result[result["symbol"].str.match(str(allow_regex), na=False)]
    summary["prefix_allow_filtered_symbols"] = int(
        before - result["symbol"].nunique()
    )
    return result


def apply_prefix_exclude_filter(
    frame: pd.DataFrame, universe: dict[str, Any], summary: dict[str, int]
) -> pd.DataFrame:
    exclude = tuple(str(value) for value in universe.get("symbol_prefix_exclude", []))
    if not exclude:
        return frame
    result = frame.copy()
    result["symbol"] = symbol_text(result)
    before = result["symbol"].nunique()
    result = result[~result["symbol"].str.startswith(exclude, na=False)]
    summary["prefix_excluded_symbols"] = int(before - result["symbol"].nunique())
    return result


def symbol_text(frame: pd.DataFrame) -> pd.Series:
    return frame["symbol"].fillna("").astype(str).str.strip()
