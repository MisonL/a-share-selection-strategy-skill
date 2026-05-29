"""Diagnostics and summary helpers for stock selection scoring."""

from __future__ import annotations

import sys
from typing import Any

import pandas as pd

from stock_selection_metrics import is_qsss_mode


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
    if is_qsss_mode(config):
        return ""
    if any(column in frame.columns for column in ["turn", "turnover"]):
        return ""
    return "neutral_series_missing_turnover"


def qsss_prediction_source(config: dict[str, Any]) -> str:
    return "external_unverified" if is_qsss_mode(config) else ""


def build_summary(
    *,
    raw: pd.DataFrame,
    prepared: pd.DataFrame,
    input_frame: pd.DataFrame,
    scored: pd.DataFrame,
    failed_symbols: list[str],
    short_symbols: list[str],
    config: dict[str, Any],
) -> dict[str, Any]:
    raw_symbols = int(raw["symbol"].astype(str).nunique())
    prepared_symbols = int(prepared["symbol"].nunique())
    input_symbols = int(input_frame["symbol"].nunique())
    return {
        "raw_symbols": raw_symbols,
        "input_symbols": input_symbols,
        "invalid_or_dropped_symbols": max(raw_symbols - prepared_symbols, 0),
        "universe_filtered_symbols": max(prepared_symbols - input_symbols, 0),
        "scored_symbols": len(scored),
        "failed_symbols": len(failed_symbols),
        "insufficient_history_symbols": len(short_symbols),
        "threshold_failed_symbols": 0,
        "threshold_failures": {},
        "turnover_assumption": turnover_assumption_for(raw, config),
        "prediction_source": qsss_prediction_source(config),
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


def complete_summary(summary: dict[str, Any], candidates: int) -> dict[str, Any]:
    return {
        **summary,
        "candidates": int(candidates),
        "effective_empty_result": candidates == 0,
    }


def print_summary(summary: dict[str, Any], output: str) -> None:
    parts = [
        f"raw_symbols={summary['raw_symbols']}",
        f"input_symbols={summary['input_symbols']}",
        f"invalid_or_dropped_symbols={summary['invalid_or_dropped_symbols']}",
        f"universe_filtered_symbols={summary['universe_filtered_symbols']}",
        f"insufficient_history_symbols={summary['insufficient_history_symbols']}",
        f"scored_symbols={summary['scored_symbols']}",
        f"failed_symbols={summary.get('failed_symbols', 0)}",
        f"threshold_failed_symbols={summary['threshold_failed_symbols']}",
        f"candidates={summary['candidates']}",
    ]
    if summary.get("effective_empty_result") is not None:
        parts.append(f"effective_empty_result={str(summary['effective_empty_result']).lower()}")
    if summary.get("input"):
        parts.append(f"input={summary['input']}")
    if summary.get("turnover_assumption"):
        parts.append(f"turnover_assumption={summary['turnover_assumption']}")
    parts.append(f"output={output}")
    print("OK: " + " ".join(parts))
    if summary.get("threshold_failures"):
        print(f"INFO: threshold_failures={format_counts(summary['threshold_failures'])}")
    if summary.get("turnover_assumption"):
        print(
            "WARNING: turn/turnover missing; turnover_ratio used a neutral series",
            file=sys.stderr,
        )
    if summary.get("prediction_source"):
        print(
            "INFO: prediction_source=external_unverified "
            "lightgbm_not_executed_by_this_script=true"
        )


def print_skipped_history_warning(
    short_symbols: list[str], config: dict[str, Any]
) -> None:
    min_history = int(config["thresholds"].get("min_history_rows", 120))
    examples = ", ".join(short_symbols[:10])
    print(
        "WARNING: skipped symbols with insufficient history "
        f"rows (< {min_history}): {examples}",
        file=sys.stderr,
    )


def no_scored_symbols_message(summary: dict[str, Any]) -> str:
    return (
        "no symbols could be scored; "
        f"insufficient_history_symbols={summary['insufficient_history_symbols']} "
        f"failed_symbols={summary['failed_symbols']}"
    )


def format_counts(counts: dict[str, int]) -> str:
    return ",".join(f"{name}:{count}" for name, count in sorted(counts.items()))
