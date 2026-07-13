#!/usr/bin/env python3
"""Fetch baostock A-share universe into a spot-compatible CSV snapshot."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

from lib.fetch.baostock_a_share_universe import (
    CLAIM_BOUNDARY,
    CSV_COLUMNS,
    fetch_universe,
    output_status,
    print_summary,
    strict_errors,
)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output)
    metadata_output = Path(args.metadata_output)
    try:
        rows, metadata = fetch_universe(args)
        metadata = output_status(
            metadata,
            output_written=True,
            metadata_output_written=True,
        )
        write_csv(output, rows)
        write_json(metadata, metadata_output)
    except Exception as exc:  # noqa: BLE001
        remove_output(output)
        remove_output(metadata_output)
        print(
            "ERROR: code=fetch_failed output_written=false "
            f"metadata_output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    errors = strict_errors(metadata, args)
    if errors:
        metadata = output_status(
            metadata,
            output_written=False,
            metadata_output_written=True,
        )
        remove_output(output)
        try:
            write_json(metadata, metadata_output)
        except Exception as exc:  # noqa: BLE001
            remove_output(output)
            remove_output(metadata_output)
            print(
                "ERROR: code=fetch_failed output_written=false "
                f"metadata_output_written=false message={exc}",
                file=sys.stderr,
            )
            return 2
        print_summary(metadata, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; "
            f"{'; '.join(errors)} output_written=false metadata_output_written=true",
            file=sys.stderr,
        )
        return 3
    print_summary(metadata)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch baostock query_all_stock A-share universe into a spot-compatible "
            "CSV. The output can seed --derive-all-spot-symbols, but it is not a "
            "realtime spot quote snapshot."
        )
    )
    parser.add_argument("--output", required=True, help="Output spot-compatible CSV.")
    parser.add_argument(
        "--metadata-output",
        required=True,
        help="Output metadata JSON path.",
    )
    parser.add_argument(
        "--fail-on-partial",
        action="store_true",
        help="Fail if baostock query_all_stock reports an error or returns zero rows.",
    )
    parser.add_argument(
        "--snapshot-date",
        default="",
        help="Universe date in YYYY-MM-DD or YYYYMMDD. Omitted uses today.",
    )
    parser.add_argument(
        "--lookback-days",
        type=non_negative_int,
        default=0,
        help=(
            "Try earlier calendar dates after an empty successful response. "
            "Default 0 disables date fallback."
        ),
    )
    parser.add_argument(
        "--retries",
        type=non_negative_int,
        default=1,
        help="Retry failed baostock login or query attempts before writing failure metadata.",
    )
    parser.add_argument(
        "--retry-interval-seconds",
        type=non_negative_float,
        default=1.0,
        help="Sleep between retry attempts. Default 1.0.",
    )
    return parser


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0 or not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("value must be a finite non-negative number")
    return parsed


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def remove_output(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        return
    path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
