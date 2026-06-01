#!/usr/bin/env python3
"""Slice local OHLCV rows to an as-of date to prevent future leakage."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Slice local OHLCV data by date.")
    parser.add_argument("--input", required=True, help="Path to CSV or Parquet file.")
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    parser.add_argument("--as-of-date", required=True, help="Inclusive YYYY-MM-DD date.")
    args = parser.parse_args(argv)
    try:
        ensure_runtime_dependencies()
        sliced = slice_prices(read_table(Path(args.input)), as_of_date=args.as_of_date)
        write_output(sliced, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(
            "ERROR: code=bad_input "
            f"input={Path(args.input).name} output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(sliced, args.as_of_date, args.output)
    return 0


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import stock_selection_data as data_module
    import validate_ohlcv as validator_module

    globals().update(
        {
            "pd": pandas_module,
            "parse_dates": data_module.parse_dates,
            "read_table": data_module.read_table,
            "validate_frame": validator_module.validate_frame,
        }
    )


def slice_prices(frame: pd.DataFrame, *, as_of_date: str) -> pd.DataFrame:
    ensure_runtime_dependencies()
    errors = validate_frame(frame, min_history_rows=0)
    if errors:
        raise ValueError("; ".join(errors))
    cutoff = parse_cutoff(as_of_date)
    result = frame.copy()
    result["symbol"] = result["symbol"].astype(str)
    result["_parsed_date"] = parse_dates(result["date"])
    result = result.dropna(subset=["_parsed_date"])
    result = result[result["_parsed_date"] <= cutoff]
    if result.empty:
        raise ValueError(f"no rows on or before as-of-date {as_of_date}")
    result = result.sort_values(["symbol", "_parsed_date"]).drop(columns=["_parsed_date"])
    return result.reset_index(drop=True)


def parse_cutoff(value: str) -> pd.Timestamp:
    ensure_runtime_dependencies()
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError("as-of-date must be parseable")
    return parsed


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def print_summary(frame: pd.DataFrame, as_of_date: str, output: str) -> None:
    ensure_runtime_dependencies()
    dates = parse_dates(frame["date"])
    print(
        f"OK: rows={len(frame)} symbols={frame['symbol'].nunique()} "
        f"date_min={dates.min().date()} date_max={dates.max().date()} "
        f"as_of_date={as_of_date} output={output}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
