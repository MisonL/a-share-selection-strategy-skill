"""Diagnostics helpers for stock selection scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from stock_selection_diagnostic_labels import (
    failed_thresholds_zh,
    selection_status,
    short_reason,
)
from stock_selection_metrics import is_prediction_mode


DIAGNOSTIC_COLUMNS = [
    "symbol",
    "name",
    "market",
    "date",
    "close",
    "volume",
    "amount",
    "turn",
    "tradestatus",
    "isST",
    "one_word_bar",
    "spot_price",
    "spot_pct_chg",
    "spot_amount",
    "spot_industry",
    "rsi",
    "volatility",
    "momentum_score",
    "trend_score",
    "prediction_score",
    "explosion_score",
    "risk_score",
    "total_score",
    "passed_thresholds",
    "selected_candidate",
    "failed_thresholds",
    "failed_thresholds_zh",
    "selection_status",
    "short_reason",
]

def threshold_masks(
    frame: pd.DataFrame, thresholds: dict[str, Any]
) -> dict[str, pd.Series]:
    masks = {
        "min_total_score": frame["total_score"] >= float(thresholds["min_total_score"]),
        "min_momentum_score": frame["momentum_score"]
        >= float(thresholds["min_momentum_score"]),
        "min_rsi": frame["rsi"] >= float(thresholds["min_rsi"]),
        "max_rsi": frame["rsi"] <= float(thresholds["max_rsi"]),
        "max_volatility": frame["volatility"] <= float(thresholds["max_volatility"]),
        "min_volume": frame["volume"] >= float(thresholds["min_volume"]),
        "min_close": frame["close"] >= float(thresholds["min_close"]),
    }
    if "max_close" in thresholds:
        masks["max_close"] = frame["close"] <= float(thresholds["max_close"])
    if "min_amount" in thresholds:
        masks["min_amount"] = frame["amount"] >= float(thresholds["min_amount"])
    if "min_turn" in thresholds:
        masks["min_turn"] = frame["turn"] >= float(thresholds["min_turn"])
    if thresholds.get("exclude_st"):
        masks["exclude_st"] = ~is_st_series(frame["isST"])
    if thresholds.get("require_tradestatus"):
        required = str(thresholds["require_tradestatus"]).strip()
        masks["require_tradestatus"] = (
            frame["tradestatus"].astype(str).str.strip().eq(required)
        )
    if thresholds.get("exclude_one_word_bar"):
        masks["exclude_one_word_bar"] = ~frame["one_word_bar"].astype(bool)
    if "min_prediction_score" in thresholds:
        masks["min_prediction_score"] = frame["prediction_score"] >= float(
            thresholds["min_prediction_score"]
        )
    else:
        masks["min_trend_score"] = frame["trend_score"] >= float(
            thresholds["min_trend_score"]
        )
    return masks


def threshold_failure_counts(
    frame: pd.DataFrame, config: dict[str, Any]
) -> dict[str, int]:
    failures = {}
    for name, mask in threshold_masks(frame, config["thresholds"]).items():
        count = int((~mask).sum())
        if count:
            failures[name] = count
    return failures


def turnover_assumption_for(frame: pd.DataFrame, config: dict[str, Any]) -> str:
    if is_prediction_mode(config):
        return ""
    if any(column in frame.columns for column in ["turn", "turnover"]):
        return ""
    return "neutral_series_missing_turnover"


def prediction_source_for(config: dict[str, Any]) -> str:
    return "external_unverified" if is_prediction_mode(config) else ""


def build_summary(
    *,
    raw: pd.DataFrame,
    prepared: pd.DataFrame,
    input_frame: pd.DataFrame,
    scored: pd.DataFrame,
    failed_symbols: list[str],
    short_symbols: list[str],
    config: dict[str, Any],
    universe_summary: dict[str, int] | None = None,
) -> dict[str, Any]:
    raw_symbols = int(raw["symbol"].astype(str).nunique())
    prepared_symbols = int(prepared["symbol"].nunique())
    input_symbols = int(input_frame["symbol"].nunique())
    universe_counts = universe_summary or {}
    return {
        "raw_symbols": raw_symbols,
        "input_symbols": input_symbols,
        "invalid_or_dropped_symbols": max(raw_symbols - prepared_symbols, 0),
        "universe_filtered_symbols": max(prepared_symbols - input_symbols, 0),
        "market_filtered_symbols": universe_counts.get("market_filtered_symbols", 0),
        "prefix_allow_filtered_symbols": universe_counts.get(
            "prefix_allow_filtered_symbols", 0
        ),
        "prefix_excluded_symbols": universe_counts.get("prefix_excluded_symbols", 0),
        "scored_symbols": len(scored),
        "failed_symbols": len(failed_symbols),
        "insufficient_history_symbols": len(short_symbols),
        "failed_symbol_examples": failed_symbols[:10],
        "insufficient_history_symbol_examples": short_symbols[:10],
        "threshold_failed_symbols": 0,
        "threshold_failures": {},
        "turnover_assumption": turnover_assumption_for(raw, config),
        "prediction_source": prediction_source_for(config),
    }


def add_threshold_summary(
    *,
    summary: dict[str, Any],
    scored: pd.DataFrame,
    thresholded: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        **summary,
        "threshold_failed_symbols": int(len(scored) - len(thresholded)),
        "threshold_failures": threshold_failure_counts(scored, config),
    }


def threshold_diagnostics(
    *,
    scored: pd.DataFrame,
    ranked: pd.DataFrame,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if scored.empty:
        return []
    masks = threshold_masks(scored, config["thresholds"])
    selected_symbols = set(ranked["symbol"].astype(str)) if not ranked.empty else set()
    rows = []
    for index, row in scored.iterrows():
        failed = [
            name for name, mask in masks.items() if not bool(mask.loc[index])
        ]
        selected = symbol_selected(row, selected_symbols)
        rows.append(diagnostic_row(row, failed, selected))
    return rows


def diagnostic_row(
    row: pd.Series,
    failed_thresholds: list[str],
    selected: bool,
) -> dict[str, Any]:
    symbol = str(row["symbol"])
    passed = not failed_thresholds
    return {
        "symbol": symbol,
        "name": row.get("name", symbol),
        "market": row.get("market", ""),
        "date": row.get("date", ""),
        "close": row.get("close"),
        "volume": row.get("volume"),
        "amount": row.get("amount"),
        "turn": row.get("turn"),
        "tradestatus": row.get("tradestatus"),
        "isST": row.get("isST"),
        "one_word_bar": row.get("one_word_bar"),
        "spot_price": row.get("spot_price"),
        "spot_pct_chg": row.get("spot_pct_chg"),
        "spot_amount": row.get("spot_amount"),
        "spot_industry": row.get("spot_industry"),
        "rsi": row.get("rsi"),
        "volatility": row.get("volatility"),
        "momentum_score": row.get("momentum_score"),
        "trend_score": row.get("trend_score"),
        "prediction_score": row.get("prediction_score"),
        "explosion_score": row.get("explosion_score"),
        "risk_score": row.get("risk_score"),
        "total_score": row.get("total_score"),
        "passed_thresholds": passed,
        "selected_candidate": selected,
        "failed_thresholds": ";".join(failed_thresholds),
        "failed_thresholds_zh": failed_thresholds_zh(failed_thresholds),
        "selection_status": selection_status(selected, passed),
        "short_reason": short_reason(selected, failed_thresholds),
    }


def symbol_selected(row: pd.Series, selected_symbols: set[str]) -> bool:
    return str(row["symbol"]) in selected_symbols


def is_st_series(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    return values.isin({"1", "true", "yes", "st"})


def write_threshold_diagnostics(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=DIAGNOSTIC_COLUMNS).to_csv(path, index=False)


def strict_gate_errors(
    summary: dict[str, Any],
    *,
    fail_on_skipped: bool,
    fail_on_empty_result: bool,
) -> list[str]:
    errors = []
    if fail_on_skipped and summary.get("failed_symbols", 0):
        errors.append(f"failed_symbols={summary['failed_symbols']}")
    if fail_on_skipped and summary.get("insufficient_history_symbols", 0):
        errors.append(
            f"insufficient_history_symbols={summary['insufficient_history_symbols']}"
        )
    if fail_on_empty_result and summary.get("effective_empty_result"):
        reason = summary.get("empty_result_reason", "unknown")
        errors.append(f"effective_empty_result=true empty_result_reason={reason}")
    return errors


def complete_summary(summary: dict[str, Any], candidates: int) -> dict[str, Any]:
    return {
        **summary,
        "candidates": int(candidates),
        "effective_empty_result": candidates == 0,
        "empty_result_reason": empty_result_reason(summary, candidates),
    }


def empty_result_reason(summary: dict[str, Any], candidates: int) -> str:
    if candidates:
        return "none"
    if summary.get("input_symbols", 0) == 0:
        return "universe_filtered_all"
    if summary.get("scored_symbols", 0) == 0:
        return "no_scored_symbols"
    if summary.get("threshold_failed_symbols", 0) == summary.get("scored_symbols", 0):
        return "threshold_filtered_all"
    return "none"
