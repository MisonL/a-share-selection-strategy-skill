#!/usr/bin/env python3
"""Validate a walk-forward runner manifest without rerunning the pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SIGNAL_SUFFIXES = ("slice", "predict", "validate", "score", "allocate", "backtest")
PORTFOLIO_SIGNAL_SUFFIXES = ("slice", "predict", "validate", "score")
RUNNER = "run_baostock_walk_forward"
SOURCE = "baostock"
TRADABILITY_MODEL_HOLDING_PERIOD = "tradestatus_holding_period_bars"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output) if args.output else None
    try:
        manifest = load_json(Path(args.manifest))
        report = build_report(manifest, args)
        if output:
            write_json(report, output)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: code=bad_input output_written=false message={exc}", file=sys.stderr)
        return 2
    if report["errors"]:
        print_summary(report, output, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; " + "; ".join(report["errors"]),
            file=sys.stderr,
        )
        return 3
    print_summary(report, output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a walk-forward run manifest.")
    parser.add_argument("--manifest", required=True, help="run_manifest.json path.")
    parser.add_argument("--output", help="Optional JSON report path.")
    parser.add_argument("--signal-dates", nargs="+", required=True)
    parser.add_argument("--expected-symbol-count", type=int, required=True)
    parser.add_argument("--required-tradability-model", required=True)
    parser.add_argument("--required-limit-rules-model", required=True)
    parser.add_argument("--expected-max-candidates", type=int)
    parser.add_argument("--expect-portfolio-violations", action="store_true")
    return parser


def build_report(manifest: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    errors = []
    signal_dates = list(args.signal_dates)
    errors.extend(top_level_errors(manifest, args, signal_dates))
    steps = manifest.get("steps", [])
    step_list = steps if isinstance(steps, list) else []
    allocation_model = str(manifest.get("allocation_model", "equal_cash_budget_lot_floor"))
    errors.extend(step_order_errors(steps, signal_dates, allocation_model))
    errors.extend(step_record_errors(step_list, expect_overlap=args.expect_portfolio_violations))
    errors.extend(command_errors(step_list, signal_dates, args, allocation_model))
    return {
        "schema_version": 1,
        "validator": "validate_walk_forward_manifest",
        "manifest_runner": manifest.get("runner"),
        "signals": signal_dates,
        "steps_checked": len(steps) if isinstance(steps, list) else 0,
        "errors": errors,
    }


def top_level_errors(
    manifest: dict[str, Any],
    args: argparse.Namespace,
    signal_dates: list[str],
) -> list[str]:
    errors = []
    expected = {
        "schema_version": 1,
        "runner": RUNNER,
        "source": SOURCE,
        "signal_dates": signal_dates,
        "tradability_model": args.required_tradability_model,
        "limit_rules_model": args.required_limit_rules_model,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            errors.append(f"manifest_{key}={manifest.get(key)} expected={value}")
    if len(manifest.get("symbols", [])) != args.expected_symbol_count:
        errors.append(f"manifest_symbol_count={len(manifest.get('symbols', []))}")
    if args.expected_max_candidates is not None:
        actual = manifest.get("max_candidates")
        if actual != args.expected_max_candidates:
            errors.append(f"manifest_max_candidates={actual}")
    return errors


def step_order_errors(steps: Any, signal_dates: list[str], allocation_model: str) -> list[str]:
    if not isinstance(steps, list):
        return ["steps_not_list"]
    actual = [step.get("step") for step in steps if isinstance(step, dict)]
    expected = expected_steps(signal_dates, allocation_model)
    if actual != expected:
        return [f"step_order_mismatch expected={','.join(expected)}"]
    return []


def expected_steps(signal_dates: list[str], allocation_model: str) -> list[str]:
    names = ["fetch"]
    suffixes = PORTFOLIO_SIGNAL_SUFFIXES if allocation_model == "portfolio_cash_lot_floor" else SIGNAL_SUFFIXES
    for signal_date in signal_dates:
        names.extend(f"{signal_date}:{suffix}" for suffix in suffixes)
    if allocation_model == "portfolio_cash_lot_floor":
        names.append("portfolio_allocate")
        names.extend(f"{signal_date}:backtest" for signal_date in signal_dates)
    names.extend(["equity", "portfolio_overlap", "summary"])
    return names


def step_record_errors(steps: list[dict[str, Any]], *, expect_overlap: bool) -> list[str]:
    errors = []
    for item in steps:
        name = str(item.get("step"))
        allowed = item.get("allowed_returncodes")
        code = item.get("returncode")
        if not isinstance(item.get("command"), list) or len(item["command"]) < 2:
            errors.append(f"{name}_bad_command")
        if not isinstance(allowed, list):
            errors.append(f"{name}_bad_allowed_returncodes")
            allowed = []
        if code not in allowed:
            errors.append(f"{name}_returncode={code} allowed={allowed}")
        if name == "portfolio_overlap":
            errors.extend(overlap_errors(code, allowed, expect_overlap))
        elif code != 0:
            errors.append(f"{name}_unexpected_nonzero={code}")
    return errors


def overlap_errors(code: int, allowed: list[int], expect_overlap: bool) -> list[str]:
    if expect_overlap:
        return [] if allowed == [0, 3] and code in (0, 3) else ["portfolio_overlap_gate_mismatch"]
    if allowed != [0] or code != 0:
        return ["portfolio_overlap_unexpected_violation"]
    return []


def command_errors(
    steps: list[dict[str, Any]],
    signal_dates: list[str],
    args: argparse.Namespace,
    allocation_model: str,
) -> list[str]:
    errors = []
    by_name = {
        item["step"]: item["command"]
        for item in steps
        if isinstance(item, dict) and isinstance(item.get("command"), list)
    }
    errors.extend(requirements(by_name.get("fetch", []), "fetch", fetch_requirements()))
    for signal_date in signal_dates:
        errors.extend(
            signal_command_errors(
                by_name,
                signal_date,
                allocation_model,
                args.required_tradability_model,
            )
        )
    if allocation_model == "portfolio_cash_lot_floor":
        errors.extend(portfolio_allocate_errors(by_name.get("portfolio_allocate", [])))
    errors.extend(requirements(by_name.get("equity", []), "equity", ["portfolio_equity_curve.py", "--fail-on-incomplete"]))
    errors.extend(overlap_command_errors(by_name.get("portfolio_overlap", [])))
    errors.extend(summary_command_errors(by_name.get("summary", []), args))
    return errors


def signal_command_errors(
    by_name: dict[str, list[str]],
    signal_date: str,
    allocation_model: str,
    required_tradability_model: str,
) -> list[str]:
    checks = {
        "slice": ["slice_prices_as_of.py", "--as-of-date", signal_date],
        "predict": ["generate_lightgbm_predictions.py", "--summary-output", "--fail-on-skipped"],
        "validate": ["validate_ohlcv.py", "--config", "qsss_profile_config.json"],
        "score": ["score_candidates.py", "--fail-on-skipped", "--fail-on-empty-result"],
        "backtest": backtest_requirements(required_tradability_model),
    }
    if allocation_model != "portfolio_cash_lot_floor":
        checks["allocate"] = ["allocate_candidate_capital.py", "--cash-budget", "--lot-size", "--fail-on-unallocated"]
    errors = []
    for suffix, required in checks.items():
        errors.extend(requirements(by_name.get(f"{signal_date}:{suffix}", []), f"{signal_date}:{suffix}", required))
    return errors


def backtest_requirements(required_tradability_model: str) -> list[str]:
    required = ["backtest_buy_hold.py", "--require-tradable-bars", "--fail-on-incomplete"]
    if required_tradability_model == TRADABILITY_MODEL_HOLDING_PERIOD:
        required.append("--require-tradable-holding-period")
    return required


def fetch_requirements() -> list[str]:
    return [
        "fetch_baostock_a_share.py",
        "--symbols",
        "--start-date",
        "--end-date",
        "--metadata-output",
        "--adjust",
        "--fail-on-fetch-error",
    ]


def overlap_command_errors(command: list[str]) -> list[str]:
    required = [
        "portfolio_overlap_report.py",
        "--max-open-positions",
        "--max-gross-weight",
        "--max-gross-notional",
        "--max-cash-reserved",
        "--fail-on-symbol-overlap",
        "--require-capital-fields",
    ]
    return requirements(command, "portfolio_overlap", required)


def portfolio_allocate_errors(command: list[str]) -> list[str]:
    required = [
        "allocate_portfolio_candidate_capital.py",
        "--raw-candidates",
        "--candidate-outputs",
        "--sized-outputs",
        "--skipped-output",
        "--summary-output",
        "--max-open-positions",
        "--max-gross-weight",
        "--max-gross-notional",
        "--max-cash-reserved",
        "--fail-on-symbol-overlap",
    ]
    return requirements(command, "portfolio_allocate", required)


def summary_command_errors(command: list[str], args: argparse.Namespace) -> list[str]:
    required = [
        "summarize_walk_forward_run.py",
        "--expected-symbol-count",
        str(args.expected_symbol_count),
        "--required-tradability-model",
        args.required_tradability_model,
        "--required-limit-rules-model",
        args.required_limit_rules_model,
        "--fail-on-symbol-overlap",
    ]
    if args.expect_portfolio_violations:
        required.append("--expect-portfolio-violations")
    return requirements(command, "summary", required)


def requirements(command: list[str], step: str, required: list[str]) -> list[str]:
    if not isinstance(command, list):
        return [f"{step}_bad_command"]
    text = []
    for part in command:
        value = str(part)
        text.append(value)
        text.append(Path(value).name)
    return [f"{step}_missing_{item}" for item in required if item not in text]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def print_summary(report: dict[str, Any], output: Path | None, prefix: str = "OK") -> None:
    target = f" output={output}" if output else ""
    print(f"{prefix}: validator=validate_walk_forward_manifest steps={report['steps_checked']} errors={len(report['errors'])}{target}")


if __name__ == "__main__":
    raise SystemExit(main())
