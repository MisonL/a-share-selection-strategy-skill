#!/usr/bin/env python3
"""Fetch A-share daily OHLCV data through pytdx and save gate files."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from lib.fetch.pytdx_a_share import (
    CLAIM_BOUNDARY,
    DEFAULT_HOST,
    DEFAULT_PORT,
    fetch_prices,
    validate_arguments,
)
from lib.fetch.pytdx_a_share_quality import (
    apply_quality_policy,
    output_status,
    print_summary,
    strict_gate_errors,
    summary_prefix,
)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output)
    metadata_output = Path(args.metadata_output)
    try:
        validate_arguments(args)
    except ValueError as exc:
        remove_output(output)
        remove_output(metadata_output)
        print(
            "ERROR: code=invalid_argument output_written=false "
            "metadata_output_written=false "
            f"source_claim_boundary={CLAIM_BOUNDARY} message={exc}",
            file=sys.stderr,
        )
        return 2
    try:
        frame, metadata = fetch_prices(args)
        frame, metadata = apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=args.drop_invalid_rows,
        )
        metadata = output_status(
            metadata,
            output_written=True,
            metadata_output_written=True,
        )
        write_outputs(frame, metadata, output, metadata_output)
    except Exception as exc:  # noqa: BLE001
        remove_output(output)
        remove_output(metadata_output)
        print(
            "ERROR: code=fetch_failed output_written=false "
            "metadata_output_written=false "
            f"source_claim_boundary={CLAIM_BOUNDARY} message={exc}",
            file=sys.stderr,
        )
        return 2
    errors = strict_gate_errors(metadata, args.fail_on_fetch_error)
    if errors:
        metadata = output_status(
            metadata,
            output_written=False,
            metadata_output_written=True,
        )
        remove_output(output)
        try:
            write_metadata(metadata, metadata_output)
        except Exception as exc:  # noqa: BLE001
            remove_output(output)
            remove_output(metadata_output)
            print(
                "ERROR: code=fetch_failed output_written=false "
                "metadata_output_written=false "
                f"source_claim_boundary={CLAIM_BOUNDARY} message={exc}",
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
    print_summary(metadata, prefix=summary_prefix(metadata))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Fetch pytdx A-share daily OHLCV into local CSV and metadata. "
            "pytdx is a no token supplemental source; it does not provide "
            "turnover, tradestatus, isST, official license, or stability proof."
        )
    )
    parser.add_argument("--symbols", required=True, help="Comma-separated six-digit symbols.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--metadata-output", required=True, help="Output metadata JSON path.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="TDX quote server host.")
    parser.add_argument("--port", type=positive_int, default=DEFAULT_PORT)
    parser.add_argument("--timeout-seconds", type=positive_float, default=10.0)
    parser.add_argument("--page-size", type=positive_int, default=800)
    parser.add_argument("--max-pages", type=positive_int, default=2)
    parser.add_argument("--fail-on-fetch-error", action="store_true")
    parser.add_argument("--drop-invalid-rows", action="store_true")
    return parser


def positive_int(value: object) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"value must be an integer: {value}") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def positive_float(value: object) -> float:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"value must be a number: {value}") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a finite positive number")
    return parsed


def write_outputs(
    frame: Any,
    metadata: dict[str, Any],
    output: Path,
    metadata_output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    write_metadata(metadata, metadata_output)


def write_metadata(metadata: dict[str, Any], metadata_output: Path) -> None:
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def remove_output(output: Path) -> None:
    if not output.exists() and not output.is_symlink():
        return
    if output.is_dir() and not output.is_symlink():
        return
    output.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
