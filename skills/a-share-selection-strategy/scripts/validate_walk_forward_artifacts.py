#!/usr/bin/env python3
"""Validate walk-forward artifact contents without rerunning the pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from typing import Any

from lib.gates.a_share_selection_output_safety import (
    prepare_output_paths,
    remove_output_files,
)
from lib.selection_core.a_share_selection_model_contracts import (
    EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
)
from lib.selection_core.a_share_selection_cli_numeric import (
    integer_or_non_finite,
    normalize_negative_non_finite_option_values,
)
from lib.selection_core.a_share_selection_sizing_contracts import (
    require_finite_non_negative_number,
    require_finite_number,
    require_integer_at_least,
    require_positive_number,
)
from lib.walk_forward.artifact_checks import (
    build_artifact_report,
    manifest_validation_path,
)


VALIDATOR = "validate_walk_forward_artifacts"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(
        normalize_negative_non_finite_option_values(argv, NUMERIC_OPTIONS)
    )
    run_dir = Path(args.run_dir)
    output = Path(args.output)
    output_prepared = False
    try:
        prepare_output_paths([output], artifact_input_paths(run_dir, args))
        output_prepared = True
        validate_numeric_args(args)
        report = build_artifact_report(run_dir, args, VALIDATOR)
        write_json(report, output)
    except Exception as exc:  # noqa: BLE001
        if output_prepared:
            remove_output_files([output])
        print(
            f"ERROR: code=bad_input output_written=false message={exc}", file=sys.stderr
        )
        return 2
    if report["errors"]:
        print_summary(report, output, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; " + "; ".join(report["errors"]), file=sys.stderr
        )
        return 3
    print_summary(report, output)
    return 0


NUMERIC_OPTIONS = (
    "--expected-candidates",
    "--expected-final-equity",
    "--final-equity-tolerance",
    "--expected-portfolio-violations",
    "--cash-budget",
    "--lot-size",
    "--hold-days",
    "--cost-bps",
    "--slippage-bps",
    "--backtest-value-tolerance",
)


def validate_numeric_args(args: argparse.Namespace) -> None:
    args.expected_candidates = [
        require_integer_at_least(value, "expected-candidates", 0)
        for value in args.expected_candidates
    ]
    args.expected_final_equity = require_finite_number(
        args.expected_final_equity,
        "expected-final-equity",
    )
    args.final_equity_tolerance = require_finite_non_negative_number(
        args.final_equity_tolerance,
        "final-equity-tolerance",
    )
    args.backtest_value_tolerance = require_finite_non_negative_number(
        args.backtest_value_tolerance,
        "backtest-value-tolerance",
    )
    args.expected_portfolio_violations = require_integer_at_least(
        args.expected_portfolio_violations,
        "expected-portfolio-violations",
        0,
    )
    args.cash_budget = require_positive_number(args.cash_budget, "cash-budget")
    args.lot_size = require_integer_at_least(args.lot_size, "lot-size", 1)
    args.hold_days = require_integer_at_least(args.hold_days, "hold-days", 1)
    args.cost_bps = require_finite_non_negative_number(args.cost_bps, "cost-bps")
    args.slippage_bps = require_finite_non_negative_number(
        args.slippage_bps,
        "slippage-bps",
    )


def artifact_input_paths(run_dir: Path, args: argparse.Namespace) -> list[Path]:
    paths = [
        run_dir / "metadata.json",
        run_dir / "prediction_run_summary.json",
        run_dir / "prediction_overlap_summary.json",
        run_dir / "prediction_equity_curve.csv",
        run_dir / "prices.csv",
    ]
    manifest_path = manifest_validation_path(run_dir, args)
    if manifest_path is not None:
        paths.append(manifest_path)
    for date in args.signal_dates:
        signal_dir = run_dir / "signals" / date
        paths.extend(
            [
                signal_dir / "prediction_summary.json",
                signal_dir / "prices_signal_window.csv",
                signal_dir / "prediction_candidates.csv",
                signal_dir / "prediction_sized_candidates.csv",
                signal_dir / "prediction_backtest.csv",
            ]
        )
    if args.required_allocation_model == "portfolio_cash_lot_floor":
        paths.extend(
            [
                run_dir / "prediction_allocation_summary.json",
                run_dir / "prediction_skipped_candidates.csv",
            ]
        )
        for date in args.signal_dates:
            paths.append(run_dir / "signals" / date / "prediction_raw_candidates.csv")
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate walk-forward artifacts. Existing run_manifest_validation.json is checked automatically; "
            "portfolio_violations > 0 is not a capacity pass."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--output",
        required=True,
        help="JSON report path; must differ from all read run artifacts.",
    )
    parser.add_argument("--signal-dates", nargs="+", required=True)
    parser.add_argument("--expected-symbols", nargs="+", required=True)
    parser.add_argument(
        "--expected-candidates",
        nargs="+",
        type=integer_or_non_finite,
        required=True,
    )
    parser.add_argument("--expected-final-equity", type=float, required=True)
    parser.add_argument("--final-equity-tolerance", type=float, default=1e-12)
    parser.add_argument(
        "--expected-portfolio-violations",
        type=integer_or_non_finite,
        required=True,
        help="Expected known violation count; known violations only, not a capacity pass.",
    )
    parser.add_argument(
        "--required-allocation-model", default="equal_cash_budget_lot_floor"
    )
    parser.add_argument("--required-tradability-model", required=True)
    parser.add_argument("--required-limit-rules-model", required=True)
    parser.add_argument(
        "--required-execution-model",
        choices=[EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE],
        default=EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
    )
    parser.add_argument("--manifest-validation")
    parser.add_argument("--cash-budget", type=float, default=1000000.0)
    parser.add_argument("--lot-size", type=integer_or_non_finite, default=100)
    parser.add_argument("--hold-days", type=integer_or_non_finite, default=5)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--backtest-value-tolerance", type=float, default=1e-9)
    parser.add_argument("--allow-dropped-invalid-rows", action="store_true")
    return parser


def print_summary(report: dict[str, object], output: Path, prefix: str = "OK") -> None:
    print(
        f"{prefix}: validator={VALIDATOR} signals={report['signals_checked']} "
        f"candidates={report['total_candidates']} "
        f"completed_trades={report['total_completed_trades']} "
        f"execution_model={report['execution_model']} "
        f"manifest_checked={report['manifest_checked']} "
        f"portfolio_violations={report['portfolio_violations']} "
        f"expected_portfolio_violations={report['expected_portfolio_violations']} "
        f"capacity_gate_pass={report['capacity_gate_pass']} "
        f"capacity_gate_status={report['capacity_gate_status']} "
        f"errors={len(report['errors'])} verdict={report['verdict']} "
        f"claim_boundary=artifact_validation_not_external_gate "
        f"output={output}"
    )


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
