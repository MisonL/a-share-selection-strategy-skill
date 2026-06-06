#!/usr/bin/env python3
"""Validate walk-forward artifact contents without rerunning the pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from walk_forward_artifact_checks import build_artifact_report, write_json


VALIDATOR = "validate_walk_forward_artifacts"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output)
    try:
        report = build_artifact_report(Path(args.run_dir), args, VALIDATOR)
        write_json(report, output)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: code=bad_input output_written=false message={exc}", file=sys.stderr)
        return 2
    if report["errors"]:
        print_summary(report, output, prefix="ERROR_SUMMARY")
        print("ERROR: strict gate failed; " + "; ".join(report["errors"]), file=sys.stderr)
        return 3
    print_summary(report, output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate walk-forward artifacts. Without --manifest-validation the manifest is not checked; "
            "portfolio_violations > 0 is not a capacity pass."
        )
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--signal-dates", nargs="+", required=True)
    parser.add_argument("--expected-symbols", nargs="+", required=True)
    parser.add_argument("--expected-candidates", nargs="+", type=int, required=True)
    parser.add_argument("--expected-final-equity", type=float, required=True)
    parser.add_argument("--final-equity-tolerance", type=float, default=1e-12)
    parser.add_argument("--expected-portfolio-violations", type=int, required=True)
    parser.add_argument("--required-allocation-model", default="equal_cash_budget_lot_floor")
    parser.add_argument("--required-tradability-model", required=True)
    parser.add_argument("--required-limit-rules-model", required=True)
    parser.add_argument("--manifest-validation")
    parser.add_argument("--cash-budget", type=float, default=1000000.0)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--allow-dropped-invalid-rows", action="store_true")
    return parser


def print_summary(report: dict[str, object], output: Path, prefix: str = "OK") -> None:
    print(
        f"{prefix}: validator={VALIDATOR} signals={report['signals_checked']} "
        f"candidates={report['total_candidates']} "
        f"completed_trades={report['total_completed_trades']} "
        f"manifest_checked={report['manifest_checked']} "
        f"portfolio_violations={report['portfolio_violations']} "
        f"expected_portfolio_violations={report['expected_portfolio_violations']} "
        f"capacity_gate_pass={report['capacity_gate_pass']} "
        f"errors={len(report['errors'])} claim_boundary=artifact_validation_not_external_gate "
        f"output={output}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
