#!/usr/bin/env python3
"""Validate local OHLCV data for stock selection workflows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

from stock_selection_config import load_config
from stock_selection_data import parse_dates
from stock_selection_metrics import is_qsss_mode


REQUIRED_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate local CSV or Parquet OHLCV data."
    )
    parser.add_argument("--input", required=True, help="Path to CSV or Parquet file.")
    parser.add_argument(
        "--min-history-rows",
        type=int,
        default=120,
        help="Minimum rows required for each symbol. Default: 120.",
    )
    parser.add_argument(
        "--config",
        help="Optional scoring config used to validate profile-specific input columns.",
    )
    args = parser.parse_args(argv)

    try:
        frame = read_table(Path(args.input))
        config = load_config(Path(args.config)) if args.config else None
        errors = validate_frame(frame, min_history_rows=args.min_history_rows)
        if config is not None:
            errors.extend(validate_profile_columns(frame, config))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc} [input={Path(args.input).name}]", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(f"ERROR: {error} [input={Path(args.input).name}]", file=sys.stderr)
        return 1

    symbols = frame["symbol"].nunique()
    print(f"OK: validated {len(frame)} rows across {symbols} symbols")
    return 0


def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype={"symbol": str})
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("unsupported input format; use .csv, .parquet, or .pq")


def validate_frame(frame: pd.DataFrame, min_history_rows: int) -> list[str]:
    errors: list[str] = []
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        return [f"missing required columns: {', '.join(missing)}"]
    if frame.empty:
        return ["input data is empty"]

    errors.extend(validate_required_values(frame))
    errors.extend(validate_symbols(frame))
    errors.extend(validate_numeric_values(frame))
    errors.extend(validate_dates(frame))
    errors.extend(validate_duplicates(frame))
    errors.extend(validate_history(frame, min_history_rows=min_history_rows))
    return errors


def validate_required_values(frame: pd.DataFrame) -> Iterable[str]:
    for column in REQUIRED_COLUMNS:
        missing_count = int(frame[column].isna().sum())
        if missing_count:
            yield f"column {column} has {missing_count} missing values"


def validate_symbols(frame: pd.DataFrame) -> Iterable[str]:
    symbols = frame["symbol"].astype(str).str.strip()
    empty_count = int((symbols == "").sum())
    if empty_count:
        yield f"column symbol has {empty_count} empty values"
    damaged = symbols.str.fullmatch(r"\d{1,3}", na=False)
    damaged_count = int(damaged.sum())
    if damaged_count:
        yield (
            f"column symbol has {damaged_count} values that look numeric-damaged; "
            "preserve leading zeros as text"
        )


def validate_numeric_values(frame: pd.DataFrame) -> Iterable[str]:
    for column in [*PRICE_COLUMNS, "volume"]:
        values = pd.to_numeric(frame[column], errors="coerce")
        invalid_count = int(values.isna().sum())
        if invalid_count:
            yield f"column {column} has {invalid_count} non-numeric values"
        if column in PRICE_COLUMNS:
            non_positive = int((values <= 0).sum())
            if non_positive:
                yield f"column {column} has {non_positive} non-positive values"
        else:
            negative = int((values < 0).sum())
            if negative:
                yield f"column {column} has {negative} negative values"


def validate_dates(frame: pd.DataFrame) -> Iterable[str]:
    dates = parse_dates(frame["date"])
    invalid_count = int(dates.isna().sum())
    if invalid_count:
        yield f"column date has {invalid_count} invalid values"


def validate_duplicates(frame: pd.DataFrame) -> Iterable[str]:
    checked = frame[["symbol"]].copy()
    checked["date"] = parse_dates(frame["date"])
    checked = checked.dropna(subset=["date"])
    duplicate_count = int(checked.duplicated(subset=["symbol", "date"]).sum())
    if duplicate_count:
        yield f"found {duplicate_count} duplicate symbol/date rows"


def validate_history(frame: pd.DataFrame, min_history_rows: int) -> Iterable[str]:
    counts = frame.groupby("symbol", dropna=False).size()
    short = counts[counts < min_history_rows]
    if not short.empty:
        examples = ", ".join(f"{symbol}:{count}" for symbol, count in short.head(10).items())
        yield (
            f"{len(short)} symbols have fewer than {min_history_rows} rows"
            f" ({examples})"
        )


def validate_profile_columns(
    frame: pd.DataFrame, config: dict
) -> Iterable[str]:
    if not is_qsss_mode(config):
        return []
    errors = []
    if config.get("universe", {}).get("market") and "market" not in frame.columns:
        errors.append("qsss-derived profile requires market column")
    if not any(column in frame.columns for column in ["prediction", "prediction_score"]):
        errors.append("qsss-derived profile requires prediction or prediction_score column")
    if not any(column in frame.columns for column in ["turn", "turnover"]):
        errors.append("qsss-derived profile requires turn or turnover column")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
