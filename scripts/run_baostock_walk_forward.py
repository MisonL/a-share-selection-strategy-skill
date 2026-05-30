#!/usr/bin/env python3
"""Run the baostock QSSS walk-forward gate through existing CLIs."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from fetch_baostock_a_share import parse_symbols


SCRIPTS = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPTS / "qsss_profile_config.json"
TRADABILITY_MODEL = "tradestatus_entry_exit_only"
LIMIT_RULES_MODEL = "not_modeled"
Executor = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    allowed: tuple[int, ...] = (0,)


@dataclass
class RunContext:
    args: argparse.Namespace
    manifest: dict[str, Any]
    manifest_path: Path
    executor: Executor


@dataclass(frozen=True)
class SignalRun:
    signal_date: str
    prices: Path
    paths: dict[str, Path]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = initial_manifest(args)
    manifest_path = Path(args.output_dir) / "run_manifest.json"
    try:
        context = RunContext(
            args=args,
            manifest=manifest,
            manifest_path=manifest_path,
            executor=run_command,
        )
        run_pipeline(context)
    except StepFailure as exc:
        write_json(manifest, manifest_path)
        print(
            f"ERROR: strict gate failed; step={exc.step} returncode={exc.returncode} "
            f"output_written=true manifest={manifest_path}",
            file=sys.stderr,
        )
        return 3
    except Exception as exc:  # noqa: BLE001
        write_json(manifest, manifest_path)
        print(
            f"ERROR: code=run_failed output_written=true manifest={manifest_path} message={exc}",
            file=sys.stderr,
        )
        return 2
    write_json(manifest, manifest_path)
    print_summary(manifest, manifest_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run baostock QSSS walk-forward gates.")
    parser.add_argument("--symbols", required=True, help="Comma-separated six-digit symbols.")
    parser.add_argument("--start-date", required=True, help="Fetch start date.")
    parser.add_argument("--end-date", required=True, help="Fetch end date.")
    parser.add_argument("--signal-dates", nargs="+", required=True, help="Signal dates.")
    parser.add_argument("--output-dir", required=True, help="Output run directory.")
    parser.add_argument("--adjust", default="3", help="baostock adjustflag.")
    parser.add_argument("--cash-budget", type=float, required=True)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--max-open-positions", type=int, required=True)
    parser.add_argument("--max-gross-weight", type=float, required=True)
    parser.add_argument("--max-gross-notional", type=float, required=True)
    parser.add_argument("--max-cash-reserved", type=float, required=True)
    parser.add_argument("--fail-on-symbol-overlap", action="store_true")
    parser.add_argument("--expect-portfolio-violations", action="store_true")
    parser.add_argument("--drop-invalid-rows", action="store_true")
    return parser


class StepFailure(RuntimeError):
    def __init__(self, step: str, returncode: int) -> None:
        super().__init__(f"{step} failed with returncode {returncode}")
        self.step = step
        self.returncode = returncode


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(Path.cwd()), capture_output=True, text=True)


def run_pipeline(context: RunContext) -> None:
    args = context.args
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prices = output / "prices.csv"
    backtests = []
    run_step(context, Step("fetch", fetch_command(args, prices, output / "metadata.json")))
    for signal_date in args.signal_dates:
        signal_dir = output / "signals" / signal_date
        signal_dir.mkdir(parents=True, exist_ok=True)
        signal = SignalRun(signal_date=signal_date, prices=prices, paths=signal_paths(signal_dir))
        run_signal(context, signal)
        backtests.append(signal.paths["backtest"])
    run_step(context, Step("equity", equity_command(output, backtests)))
    overlap_allowed = (0, 3) if args.expect_portfolio_violations else (0,)
    run_step(context, Step("portfolio_overlap", overlap_command(args, output, backtests), overlap_allowed))
    run_step(context, Step("summary", summary_command(args, output)))


def run_signal(context: RunContext, signal: SignalRun) -> None:
    args = context.args
    paths = signal.paths
    name = signal.signal_date
    run_step(context, Step(f"{name}:slice", slice_command(signal.prices, paths["sliced"], name)))
    run_step(context, Step(f"{name}:predict", predict_command(paths)))
    run_step(context, Step(f"{name}:validate", validate_command(paths["predictions"])))
    run_step(context, Step(f"{name}:score", score_command(paths)))
    run_step(context, Step(f"{name}:allocate", allocate_command(args, signal.prices, paths)))
    run_step(context, Step(f"{name}:backtest", backtest_command(args, signal.prices, paths)))


def run_step(context: RunContext, step: Step) -> None:
    result = context.executor(step.command)
    context.manifest["steps"].append(step_record(step, result))
    write_json(context.manifest, context.manifest_path)
    if result.returncode not in step.allowed:
        raise StepFailure(step.name, result.returncode)


def step_record(step: Step, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "step": step.name,
        "command": step.command,
        "returncode": result.returncode,
        "allowed_returncodes": list(step.allowed),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def signal_paths(signal_dir: Path) -> dict[str, Path]:
    return {
        "sliced": signal_dir / "prices_signal_window.csv",
        "predictions": signal_dir / "predictions_signal_window.csv",
        "prediction_summary": signal_dir / "prediction_summary.json",
        "candidates": signal_dir / "qsss_candidates.csv",
        "sized": signal_dir / "qsss_sized_candidates.csv",
        "backtest": signal_dir / "qsss_backtest.csv",
    }


def fetch_command(args: argparse.Namespace, prices: Path, metadata: Path) -> list[str]:
    command = script_command("fetch_baostock_a_share.py", "--symbols", args.symbols, "--start-date", args.start_date, "--end-date", args.end_date, "--output", prices, "--metadata-output", metadata, "--adjust", args.adjust, "--fail-on-fetch-error")
    if args.drop_invalid_rows:
        command.append("--drop-invalid-rows")
    return command


def slice_command(prices: Path, output: Path, signal_date: str) -> list[str]:
    return script_command("slice_prices_as_of.py", "--input", prices, "--output", output, "--as-of-date", signal_date)


def predict_command(paths: dict[str, Path]) -> list[str]:
    return script_command("generate_lightgbm_predictions.py", "--input", paths["sliced"], "--output", paths["predictions"], "--summary-output", paths["prediction_summary"], "--fail-on-skipped")


def validate_command(predictions: Path) -> list[str]:
    return script_command("validate_ohlcv.py", "--input", predictions, "--config", CONFIG_PATH)


def score_command(paths: dict[str, Path]) -> list[str]:
    return script_command("score_candidates.py", "--input", paths["predictions"], "--config", CONFIG_PATH, "--output", paths["candidates"], "--fail-on-skipped", "--fail-on-empty-result")


def allocate_command(args: argparse.Namespace, prices: Path, paths: dict[str, Path]) -> list[str]:
    return script_command("allocate_candidate_capital.py", "--prices", prices, "--candidates", paths["candidates"], "--output", paths["sized"], "--cash-budget", args.cash_budget, "--lot-size", args.lot_size, "--fail-on-unallocated")


def backtest_command(args: argparse.Namespace, prices: Path, paths: dict[str, Path]) -> list[str]:
    return script_command("backtest_buy_hold.py", "--prices", prices, "--candidates", paths["sized"], "--output", paths["backtest"], "--hold-days", args.hold_days, "--cost-bps", args.cost_bps, "--slippage-bps", args.slippage_bps, "--require-tradable-bars", "--fail-on-incomplete")


def equity_command(output: Path, backtests: list[Path]) -> list[str]:
    return script_command("portfolio_equity_curve.py", "--backtests", *backtests, "--output", output / "qsss_equity_curve.csv", "--fail-on-incomplete")


def overlap_command(args: argparse.Namespace, output: Path, backtests: list[Path]) -> list[str]:
    command = script_command("portfolio_overlap_report.py", "--backtests", *backtests, "--daily-output", output / "qsss_daily_positions.csv", "--overlap-output", output / "qsss_overlap.csv", "--summary-output", output / "qsss_overlap_summary.json", "--max-open-positions", args.max_open_positions, "--max-gross-weight", args.max_gross_weight, "--max-gross-notional", args.max_gross_notional, "--max-cash-reserved", args.max_cash_reserved, "--require-capital-fields")
    if args.fail_on_symbol_overlap:
        command.append("--fail-on-symbol-overlap")
    return command


def summary_command(args: argparse.Namespace, output: Path) -> list[str]:
    command = script_command("summarize_walk_forward_run.py", "--run-dir", output, "--output", output / "qsss_run_summary.json", "--signal-dates", *args.signal_dates, "--expected-symbol-count", len(parse_symbols(args.symbols)), "--required-tradability-model", TRADABILITY_MODEL, "--required-limit-rules-model", LIMIT_RULES_MODEL, "--max-open-positions", args.max_open_positions, "--max-gross-weight", args.max_gross_weight, "--max-gross-notional", args.max_gross_notional, "--max-cash-reserved", args.max_cash_reserved)
    if args.fail_on_symbol_overlap:
        command.append("--fail-on-symbol-overlap")
    if args.expect_portfolio_violations:
        command.append("--expect-portfolio-violations")
    return command


def script_command(script: str, *parts: object) -> list[str]:
    return [sys.executable, str(SCRIPTS / script), *[str(part) for part in parts]]


def initial_manifest(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "runner": "run_baostock_walk_forward",
        "source": "baostock",
        "symbols": parse_symbols(args.symbols),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "signal_dates": list(args.signal_dates),
        "adjustflag": str(args.adjust),
        "limit_rules_model": LIMIT_RULES_MODEL,
        "tradability_model": TRADABILITY_MODEL,
        "steps": [],
    }


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def print_summary(manifest: dict[str, Any], manifest_path: Path) -> None:
    print(
        f"OK: runner=run_baostock_walk_forward symbols={len(manifest['symbols'])} "
        f"signals={len(manifest['signal_dates'])} steps={len(manifest['steps'])} "
        f"limit_rules_model={manifest['limit_rules_model']} manifest={manifest_path}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
