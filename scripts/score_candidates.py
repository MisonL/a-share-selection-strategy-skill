#!/usr/bin/env python3
"""Score stock candidates from local OHLCV data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from stock_selection_config import load_config
from stock_selection_data import parse_dates, read_table
from stock_selection_diagnostics import (
    add_threshold_summary,
    build_summary,
    complete_summary,
    no_scored_symbols_message,
    print_skipped_history_warning,
    print_summary,
    threshold_masks,
)
from stock_selection_metrics import is_qsss_mode, score_symbol
from stock_selection_profile import profile_column_errors, qsss_value_errors
from stock_selection_universe import apply_universe_filter
from validate_ohlcv import validate_frame


BASE_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
OUTPUT_COLUMNS = [
    "rank",
    "symbol",
    "name",
    "market",
    "date",
    "close",
    "volume",
    "turn",
    "rsi",
    "volatility",
    "macd",
    "macd_status",
    "momentum_score",
    "trend_score",
    "prediction_score",
    "explosion_score",
    "risk_score",
    "total_score",
    "ma15",
    "low_ma15_flag",
    "explosion_focus_flag",
    "low_price_explosion_flag",
    "signal_tier",
    "recommendation",
    "key_reasons",
    "risk_notes",
    "data_window",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score stock candidates from local CSV or Parquet OHLCV data."
    )
    parser.add_argument("--input", required=True, help="Path to CSV or Parquet file.")
    parser.add_argument("--config", required=True, help="Path to JSON config file.")
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    parser.add_argument(
        "--fail-on-skipped",
        action="store_true",
        help="Return a non-zero exit code if any symbol is skipped.",
    )
    parser.add_argument(
        "--fail-on-empty-result",
        action="store_true",
        help="Return a non-zero exit code if scoring produces zero candidates.",
    )
    args = parser.parse_args(argv)
    try:
        config = load_config(Path(args.config))
        candidates, summary = score_candidates(read_table(Path(args.input)), config)
        summary["input"] = Path(args.input).name
        strict_errors = strict_gate_errors(
            summary,
            fail_on_skipped=args.fail_on_skipped,
            fail_on_empty_result=args.fail_on_empty_result,
        )
        if strict_errors:
            print_summary(summary, args.output, prefix="ERROR_SUMMARY")
            print(
                "ERROR: strict gate failed; "
                f"{'; '.join(strict_errors)} output_not_written=true",
                file=sys.stderr,
            )
            return 3
        write_output(candidates, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(
            "ERROR: code=bad_input "
            f"input={Path(args.input).name} output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(summary, args.output)
    return 0


def score_candidates(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    validate_input_frame(frame, config)
    validate_profile_requirements(frame, config)
    prepared = prepare_frame(frame)
    raw_symbols = int(frame["symbol"].astype(str).nunique())
    if prepared.empty and raw_symbols:
        raise ValueError("no valid rows after basic data cleaning")
    validate_qsss_symbols(prepared, config)
    input_frame, universe_summary = apply_universe_filter(prepared, config)
    validate_prediction_values(input_frame)
    scored_rows, failed_symbols, short_symbols = score_groups(input_frame, config)
    scored = pd.DataFrame(scored_rows)
    summary = build_summary(
        raw=frame,
        prepared=prepared,
        input_frame=input_frame,
        scored=scored,
        failed_symbols=failed_symbols,
        short_symbols=short_symbols,
        config=config,
        universe_summary=universe_summary,
    )
    if short_symbols:
        print_skipped_history_warning(short_symbols, config)
    if scored.empty:
        return empty_result(summary)
    thresholded = apply_thresholds(scored, config["thresholds"])
    summary = add_threshold_summary(
        summary=summary,
        scored=scored,
        thresholded=thresholded,
        config=config,
    )
    ranked = rank_and_limit(thresholded, config)
    return ranked_result(ranked, summary)


def empty_result(
    summary: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if summary["input_symbols"] and (
        summary["failed_symbols"] or summary["insufficient_history_symbols"]
    ):
        raise ValueError(no_scored_symbols_message(summary))
    return pd.DataFrame(columns=OUTPUT_COLUMNS), complete_summary(summary, 0)


def ranked_result(
    ranked: pd.DataFrame,
    summary: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    return ensure_output_columns(ranked), complete_summary(summary, len(ranked))


def score_groups(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    min_history = int(config["thresholds"].get("min_history_rows", 120))
    rows = []
    failed_symbols = []
    short_symbols = []
    for _, group in frame.groupby("symbol", sort=False):
        symbol = str(group["symbol"].iloc[-1])
        if len(group) >= min_history:
            try:
                rows.append(score_symbol(group, config))
            except Exception as exc:  # noqa: BLE001
                failed_symbols.append(symbol)
                print(f"WARNING: skipped symbol {symbol}: {exc}", file=sys.stderr)
        else:
            short_symbols.append(symbol)
    return rows, failed_symbols, short_symbols


def validate_input_frame(frame: pd.DataFrame, config: dict[str, Any]) -> None:
    errors = validate_frame(frame, min_history_rows=0)
    if errors:
        raise ValueError("; ".join(errors))


def validate_prediction_values(frame: pd.DataFrame) -> None:
    for column in ["prediction", "prediction_score"]:
        if column not in frame.columns:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        missing = int(values.isna().sum())
        invalid = int(((values < 0) | (values > 1)).sum())
        invalid_count = missing + invalid
        if invalid_count:
            raise ValueError(
                f"{column} has {invalid_count} invalid values; "
                "prediction values must be numbers between 0 and 1"
            )


def validate_profile_requirements(frame: pd.DataFrame, config: dict[str, Any]) -> None:
    errors = profile_column_errors(frame, config)
    if errors:
        raise ValueError("; ".join(errors))


def validate_qsss_symbols(frame: pd.DataFrame, config: dict[str, Any]) -> None:
    errors = qsss_value_errors(frame, config)
    if errors:
        raise ValueError("; ".join(errors))


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


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["symbol"] = result["symbol"].astype(str)
    result["date"] = parse_dates(result["date"])
    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
        "turn",
        "prediction",
        "prediction_score",
    ]
    for column in numeric_columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=BASE_COLUMNS)
    price_mask = (result[["open", "high", "low", "close"]] > 0).all(axis=1)
    result = result[price_mask & (result["volume"] >= 0)]
    return result.sort_values(["symbol", "date"]).reset_index(drop=True)


def rank_and_limit(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    ranked = frame.copy()
    sort_columns = ["total_score"]
    ascending = [False]
    if not is_qsss_mode(config):
        sort_columns.extend(["explosion_score", "momentum_score"])
        ascending.extend([False, False])
    ranked = ranked.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)
    max_candidates = int(config.get("output", {}).get("max_candidates", 50))
    if max_candidates > 0:
        ranked = ranked.head(max_candidates)
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    return ranked


def apply_thresholds(frame: pd.DataFrame, thresholds: dict[str, Any]) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    for threshold_mask in threshold_masks(frame, thresholds).values():
        mask &= threshold_mask
    return frame[mask].copy()


def ensure_output_columns(frame: pd.DataFrame) -> pd.DataFrame:
    for column in OUTPUT_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[OUTPUT_COLUMNS]


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


if __name__ == "__main__":
    raise SystemExit(main())
