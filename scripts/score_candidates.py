#!/usr/bin/env python3
"""Score stock candidates from local OHLCV data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from stock_selection_metrics import is_qsss_mode, score_symbol


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
        write_output(candidates, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print_summary(summary, args.output)
    return 0


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    for key in ["windows", "weights", "explosion_weights", "thresholds", "output"]:
        if key not in config:
            raise ValueError(f"config missing section: {key}")
    thresholds = config["thresholds"]
    if not any(key in thresholds for key in ["min_prediction_score", "min_trend_score"]):
        raise ValueError(
            "config thresholds require min_prediction_score or min_trend_score"
        )
    return config


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
) -> tuple[pd.DataFrame, dict[str, int]]:
    validate_columns(frame)
    validate_profile_requirements(frame, config)
    prepared = prepare_frame(frame)
    prepared = apply_universe_filter(prepared, config)
    scored_rows, failed_symbols = score_groups(prepared, config)
    scored = pd.DataFrame(scored_rows)
    summary = {
        "input_symbols": int(prepared["symbol"].nunique()),
        "scored_symbols": len(scored),
        "failed_symbols": len(failed_symbols),
    }
    if scored.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS), {**summary, "candidates": 0}
    filtered = filter_and_rank(scored, config)
    return ensure_output_columns(filtered), {**summary, "candidates": int(len(filtered))}


def score_groups(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    min_history = int(config["thresholds"].get("min_history_rows", 120))
    rows = []
    failed_symbols = []
    for _, group in frame.groupby("symbol", sort=False):
        if len(group) >= min_history:
            symbol = str(group["symbol"].iloc[-1])
            try:
                rows.append(score_symbol(group, config))
            except Exception as exc:  # noqa: BLE001
                failed_symbols.append(symbol)
                print(f"WARNING: skipped symbol {symbol}: {exc}", file=sys.stderr)
    return rows, failed_symbols


def validate_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in BASE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def validate_profile_requirements(frame: pd.DataFrame, config: dict[str, Any]) -> None:
    if str(config.get("score_mode", "")).lower() != "qsss-derived":
        return
    if not any(column in frame.columns for column in ["prediction", "prediction_score"]):
        raise ValueError("qsss-derived score mode requires prediction or prediction_score")
    if not any(column in frame.columns for column in ["turn", "turnover"]):
        raise ValueError("qsss-derived score mode requires turn or turnover column")


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["symbol"] = result["symbol"].astype(str)
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
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
    allow_regex = universe.get("symbol_prefix_allow_regex")
    if allow_regex:
        result = result[result["symbol"].str.match(str(allow_regex))]
    exclude = tuple(str(value) for value in universe.get("symbol_prefix_exclude", []))
    if exclude:
        result = result[~result["symbol"].str.startswith(exclude)]
    return result.reset_index(drop=True)


def filter_and_rank(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    filtered = apply_thresholds(frame, config["thresholds"])
    sort_columns = ["total_score"]
    ascending = [False]
    if not is_qsss_mode(config):
        sort_columns.extend(["explosion_score", "momentum_score"])
        ascending.extend([False, False])
    filtered = filtered.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)
    max_candidates = int(config.get("output", {}).get("max_candidates", 50))
    if max_candidates > 0:
        filtered = filtered.head(max_candidates)
    filtered.insert(0, "rank", range(1, len(filtered) + 1))
    return filtered


def apply_thresholds(frame: pd.DataFrame, thresholds: dict[str, Any]) -> pd.DataFrame:
    mask = (
        (frame["total_score"] >= float(thresholds["min_total_score"]))
        & (frame["momentum_score"] >= float(thresholds["min_momentum_score"]))
        & (frame["rsi"] >= float(thresholds["min_rsi"]))
        & (frame["rsi"] <= float(thresholds["max_rsi"]))
        & (frame["volatility"] <= float(thresholds["max_volatility"]))
        & (frame["volume"] >= float(thresholds["min_volume"]))
        & (frame["close"] >= float(thresholds["min_close"]))
    )
    if "min_prediction_score" in thresholds:
        mask &= frame["prediction_score"] >= float(thresholds["min_prediction_score"])
    else:
        mask &= frame["trend_score"] >= float(thresholds["min_trend_score"])
    return frame[mask].copy()


def ensure_output_columns(frame: pd.DataFrame) -> pd.DataFrame:
    for column in OUTPUT_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[OUTPUT_COLUMNS]


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def print_summary(summary: dict[str, int], output: str) -> None:
    print(
        "OK: "
        f"input_symbols={summary['input_symbols']} "
        f"scored_symbols={summary['scored_symbols']} "
        f"failed_symbols={summary.get('failed_symbols', 0)} "
        f"candidates={summary['candidates']} "
        f"output={output}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
