#!/usr/bin/env python3
"""Run an auditable local A-share selection workflow through existing CLIs."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from run_today_a_share_selection_helpers import print_summary, summary_view, tabular_suffix, write_json
from run_today_a_share_selection_commands import (
    fetch_history_command,
    fetch_spot_command,
    initial_manifest,
    run_config_path,
    score_command,
    selected_config,
    validate_command,
)
from run_today_a_share_selection_history import (
    DEFAULT_HISTORY_SYMBOL_LIMIT,
    history_symbols,
    validate_history_inputs,
)
from run_today_a_share_selection_modes import ModeResolution, resolve_mode


SCRIPTS = Path(__file__).resolve().parent
DEFAULT_GENERIC_CONFIG = SCRIPTS / "ultra_short_low_price_config.json"
DEFAULT_PREDICTION_CONFIG = SCRIPTS / "prediction_profile_config.json"
Executor = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]


@dataclass
class RunContext:
    args: argparse.Namespace
    manifest: dict[str, Any]
    manifest_path: Path
    executor: Executor


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.default_generic_config = DEFAULT_GENERIC_CONFIG
    args.default_prediction_config = DEFAULT_PREDICTION_CONFIG
    output = Path(args.output_dir)
    manifest_path = output / "run_manifest.json"
    manifest = initial_manifest(args)
    try:
        output.mkdir(parents=True, exist_ok=True)
        context = RunContext(args, manifest, manifest_path, run_command)
        run_pipeline(context)
    except StepFailure as exc:
        write_json(manifest, manifest_path)
        write_json(summary_view(manifest, "failed"), output / "summary.json")
        print(
            f"ERROR: strict gate failed; step={exc.step} returncode={exc.returncode} "
            f"output_written=true manifest={manifest_path}",
            file=sys.stderr,
        )
        return 3
    except Exception as exc:  # noqa: BLE001
        write_json(manifest, manifest_path)
        write_json(summary_view(manifest, "failed"), output / "summary.json")
        print(
            f"ERROR: code=run_failed output_written=true manifest={manifest_path} "
            f"message={exc}",
            file=sys.stderr,
        )
        return 2
    write_json(manifest, manifest_path)
    write_json(summary_view(manifest, "completed"), output / "summary.json")
    print_summary(manifest, output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run local A-share selection gates. In --mode auto, inputs with "
            "market plus prediction/prediction_score plus turn/turnover use prediction-derived "
            "external-prediction scoring; otherwise the runner uses the generic "
            "low-price profile. This runner never executes LightGBM."
        )
    )
    parser.add_argument("--prices-input", help="Local CSV or Parquet prices.")
    parser.add_argument("--output-dir", required=True, help="Output run directory.")
    parser.add_argument("--mode", choices=["auto", "generic", "prediction"], default="auto")
    parser.add_argument("--config", help="Override scoring config path.")
    parser.add_argument("--spot-input", help="Optional local spot CSV or Parquet file.")
    parser.add_argument(
        "--fetch-spot",
        choices=["eastmoney"],
        help="Fetch spot snapshot before scoring.",
    )
    parser.add_argument("--spot-pages", type=positive_int, default=1)
    parser.add_argument("--fail-on-partial-spot", action="store_true")
    parser.add_argument("--history-source", choices=["akshare", "baostock"])
    parser.add_argument("--symbols", help="Comma-separated six-digit symbols for history fetch.")
    parser.add_argument("--start-date", help="History start date.")
    parser.add_argument("--end-date", help="History end date.")
    parser.add_argument(
        "--derive-symbols-from-spot",
        action="store_true",
        help="Derive history symbols from the local or fetched spot snapshot.",
    )
    parser.add_argument(
        "--max-history-symbols",
        type=positive_int,
        default=DEFAULT_HISTORY_SYMBOL_LIMIT,
    )
    parser.add_argument("--history-adjust", help="Forwarded adjust value for history fetch.")
    parser.add_argument("--allow-partial-history", action="store_true")
    parser.add_argument("--drop-invalid-history-rows", action="store_true")
    parser.add_argument("--min-history-rows", type=positive_int, default=120)
    parser.add_argument("--fail-on-empty-result", action="store_true")
    parser.add_argument("--fail-on-skipped", action="store_true")
    return parser


class StepFailure(RuntimeError):
    def __init__(self, step: str, returncode: int) -> None:
        super().__init__(f"{step} failed with returncode {returncode}")
        self.step = step
        self.returncode = returncode


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(Path.cwd()), capture_output=True, text=True)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def run_pipeline(context: RunContext) -> None:
    apply_mode_resolution(context, resolve_mode(context.args))
    output = Path(context.args.output_dir)
    prices = run_prices_path(context.args)
    candidates = output / "candidates.csv"
    diagnostics = output / "diagnostics.csv"
    spot = run_spot_path(context.args)
    prepare_inputs(context.args, output, prices, spot)
    if context.args.fetch_spot:
        run_step(context, Step("fetch_spot", fetch_spot_command(context.args, spot)))
    if not context.args.prices_input:
        symbols = history_symbols(context.args, spot, output, run_config_path(context.args))
        context.manifest["history_symbols"] = symbols
        run_step(
            context,
            Step("fetch_history", fetch_history_command(context.args, prices, symbols)),
        )
    run_step(context, Step("validate", validate_command(context.args, prices)))
    run_step(context, Step("score", score_command(context.args, prices, candidates, diagnostics, spot)))


def prepare_inputs(
    args: argparse.Namespace, output: Path, prices: Path, spot: Path | None
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    validate_history_inputs(args, spot)
    if args.prices_input:
        source = Path(args.prices_input)
        if not source.exists():
            raise FileNotFoundError(f"prices input not found: {source}")
        if source.resolve() != prices.resolve():
            shutil.copyfile(source, prices)
    config = selected_config(args)
    target_config = output / config.name
    if config.resolve() != target_config.resolve():
        shutil.copyfile(config, target_config)
    if args.spot_input and spot is not None:
        source_spot = Path(args.spot_input)
        if not source_spot.exists():
            raise FileNotFoundError(f"spot input not found: {source_spot}")
        if source_spot.resolve() != spot.resolve():
            shutil.copyfile(source_spot, spot)


def run_prices_path(args: argparse.Namespace) -> Path:
    if not args.prices_input:
        return Path(args.output_dir) / "prices.csv"
    return Path(args.output_dir) / f"prices{tabular_suffix(args.prices_input)}"


def run_spot_path(args: argparse.Namespace) -> Path | None:
    if not args.spot_input and not args.fetch_spot:
        return None
    return Path(args.output_dir) / f"spot{tabular_suffix(args.spot_input or '')}"


def apply_mode_resolution(context: RunContext, resolution: ModeResolution) -> None:
    context.args.resolved_mode = resolution.mode
    config = selected_config(context.args)
    context.manifest.update(
        {
            "mode": resolution.mode,
            "mode_decision": resolution.decision,
            "mode_decision_reason": resolution.reason,
            "config_path": str(Path(context.args.output_dir) / config.name),
            "prediction_mode": resolution.mode == "prediction",
            "lightgbm_not_used": resolution.mode != "prediction",
            "lightgbm_executed_by_runner": False,
            "source_scope": source_scope(context.args),
        }
    )


def source_scope(args: argparse.Namespace) -> str:
    scopes = []
    history = f"{args.history_source}_history_fetch" if args.history_source else "history_fetch"
    scopes.append("local_prices_input" if args.prices_input else history)
    if args.spot_input:
        scopes.append("local_spot_input")
    if args.fetch_spot:
        scopes.append("eastmoney_spot_snapshot")
    return "+".join(scopes)


def run_step(context: RunContext, step: Step) -> None:
    result = context.executor(step.command)
    context.manifest["steps"].append(step_record(step, result))
    write_json(context.manifest, context.manifest_path)
    if result.returncode != 0:
        raise StepFailure(step.name, result.returncode)


def step_record(step: Step, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "step": step.name,
        "command": step.command,
        "returncode": result.returncode,
        "allowed_returncodes": [0],
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


if __name__ == "__main__":
    raise SystemExit(main())
