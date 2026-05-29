#!/usr/bin/env python3
"""Score stock candidates from local OHLCV data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from stock_selection_config import load_config
from stock_selection_data import parse_dates
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
    args = parser.parse_args(argv)
    try:
        config = load_config(Path(args.config))
        candidates, summary = score_candidates(read_table(Path(args.input)), config)
        summary["input"] = Path(args.input).name
        write_output(candidates, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc} [input={Path(args.input).name}]", file=sys.stderr)
        return 2
    print_summary(summary, args.output)
    return 0


def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype={"symbol": str})
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("unsupported input format; use .csv, .parquet, or .pq")


def score_candidates(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    validate_input_frame(frame, config)
    validate_prediction_values(frame)
    validate_profile_requirements(frame, config)
    prepared = prepare_frame(frame)
    raw_symbols = int(frame["symbol"].astype(str).nunique())
    if prepared.empty and raw_symbols:
        raise ValueError("no valid rows after basic data cleaning")
    input_frame = apply_universe_filter(prepared, config)
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
    min_history = int(config["thresholds"].get("min_history_rows", 120))
    errors = validate_frame(frame, min_history_rows=min_history)
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
    if not is_qsss_mode(config):
        return
    if config.get("universe", {}).get("market") and "market" not in frame.columns:
        raise ValueError("qsss-derived score mode requires market column")
    prediction_column = next(
        (column for column in ["prediction", "prediction_score"] if column in frame.columns),
        None,
    )
    if prediction_column is None:
        raise ValueError("qsss-derived score mode requires prediction or prediction_score")
    if not any(column in frame.columns for column in ["turn", "turnover"]):
        raise ValueError("qsss-derived score mode requires turn or turnover column")


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
    result = result.drop_duplicates(subset=["symbol", "date"], keep="last")
    return result.sort_values(["symbol", "date"]).reset_index(drop=True)


def apply_universe_filter(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    universe = config.get("universe", {})
    result = frame.copy()
    market = universe.get("market")
    if market and "market" in result.columns:
        result = result[result["market"].astype(str) == str(market)]
    allow_regex = universe.get("symbol_prefix_allow_regex")
    if allow_regex:
        result = result[result["symbol"].str.match(str(allow_regex))]
    exclude = tuple(str(value) for value in universe.get("symbol_prefix_exclude", []))
    if exclude:
        result = result[~result["symbol"].str.startswith(exclude)]
    return result.reset_index(drop=True)


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
