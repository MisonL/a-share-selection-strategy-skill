#!/usr/bin/env python3
"""Allocate candidate capital with portfolio-aware capacity gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ensure_runtime_dependencies()
        selected, sized, skipped, summary = allocate_portfolio(
            read_table(Path(args.prices)),
            [read_table(Path(path)) for path in args.raw_candidates],
            expected_signal_dates=args.expected_signal_dates,
            cash_budget=args.cash_budget,
            lot_size=args.lot_size,
            hold_days=args.hold_days,
            max_open_positions=args.max_open_positions,
            max_gross_weight=args.max_gross_weight,
            max_gross_notional=args.max_gross_notional,
            max_cash_reserved=args.max_cash_reserved,
            fail_on_symbol_overlap=args.fail_on_symbol_overlap,
            close_tolerance=args.close_tolerance,
        )
        write_signal_outputs(selected, args.candidate_outputs)
        write_signal_outputs(sized, args.sized_outputs)
        write_output(skipped, Path(args.skipped_output))
        write_json(summary, Path(args.summary_output))
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: code=bad_input output_written=false message={exc}", file=sys.stderr
        )
        return 2
    print_summary(summary, args.summary_output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Allocate candidates with portfolio capacity."
    )
    parser.add_argument("--prices", required=True)
    parser.add_argument("--raw-candidates", nargs="+", required=True)
    parser.add_argument("--expected-signal-dates", nargs="+")
    parser.add_argument("--candidate-outputs", nargs="+", required=True)
    parser.add_argument("--sized-outputs", nargs="+", required=True)
    parser.add_argument("--skipped-output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--cash-budget", type=float, required=True)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--hold-days", type=int, required=True)
    parser.add_argument("--max-open-positions", type=int, required=True)
    parser.add_argument("--max-gross-weight", type=float, required=True)
    parser.add_argument("--max-gross-notional", type=float, required=True)
    parser.add_argument("--max-cash-reserved", type=float, required=True)
    parser.add_argument("--fail-on-symbol-overlap", action="store_true")
    parser.add_argument("--close-tolerance", type=float, default=0.000001)
    return parser


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import lib.selection_core.a_share_selection_data as data_module
    import lib.gates.portfolio_candidate_allocation as allocation_module

    globals().update(
        {
            "pd": pandas_module,
            "allocate_portfolio": allocation_module.allocate_portfolio,
            "read_table": data_module.read_table,
        }
    )


def write_signal_outputs(frames: list[pd.DataFrame], paths: list[str]) -> None:
    if len(frames) != len(paths):
        raise ValueError("output path count must match candidate file count")
    for frame, path in zip(frames, paths, strict=True):
        write_output(frame, Path(path))


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def print_summary(summary: dict[str, Any], output: str) -> None:
    print(
        f"OK: allocation_model={summary['allocation_model']} "
        f"raw_candidates={summary['raw_candidates']} "
        f"allocated_candidates={summary['allocated_candidates']} "
        f"skipped_candidates={summary['skipped_candidates']} "
        f"claim_boundary={summary['claim_boundary']} output={output}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
