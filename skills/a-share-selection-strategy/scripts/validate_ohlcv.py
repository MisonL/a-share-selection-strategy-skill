#!/usr/bin/env python3
"""Validate local OHLCV data for A-share selection workflows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.a_share_selection_validation import (
    REQUIRED_COLUMNS,
    VOLUME_UNIT_VERIFICATION,
    validate_frame,
    validate_profile_columns,
)


RUNTIME_DEPENDENCIES_READY = False


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
        ensure_runtime_dependencies()
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
    print(
        f"OK: validated {len(frame)} rows across {symbols} symbols "
        f"volume_unit_verification={VOLUME_UNIT_VERIFICATION} "
        "volume_must_not_be_amount_or_mixed_units"
    )
    return 0


def ensure_runtime_dependencies() -> None:
    global RUNTIME_DEPENDENCIES_READY
    if RUNTIME_DEPENDENCIES_READY:
        return
    global load_config, read_table, _parse_dates
    from lib.a_share_selection_config import load_config as load_config_fn
    from lib.selection_core.a_share_selection_data import parse_dates as parse_dates_fn
    from lib.selection_core.a_share_selection_data import read_table as read_table_fn

    load_config = load_config_fn
    _parse_dates = parse_dates_fn
    read_table = read_table_fn
    RUNTIME_DEPENDENCIES_READY = True


def parse_dates(series):
    ensure_runtime_dependencies()
    return _parse_dates(series)


if __name__ == "__main__":
    raise SystemExit(main())
