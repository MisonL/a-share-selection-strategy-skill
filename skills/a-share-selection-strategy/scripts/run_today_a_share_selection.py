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

import run_today_a_share_selection_helpers as helpers
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
    history_symbols,
    validate_history_inputs,
)
from run_today_a_share_selection_input_metadata import input_metadata_for_prices
from run_today_a_share_selection_modes import ModeResolution, resolve_mode
from run_today_a_share_selection_outputs import clear_stale_run_outputs, finalize_outputs
from run_today_a_share_selection_parser import build_parser


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

    def finish(status: str) -> None:
        finalize_outputs(
            args=args,
            manifest=manifest,
            manifest_path=manifest_path,
            output=output,
            status=status,
        )

    try:
        output.mkdir(parents=True, exist_ok=True)
        context = RunContext(args, manifest, manifest_path, run_command)
        run_pipeline(context)
    except StepFailure as exc:
        finish("failed")
        print(
            f"ERROR: strict gate failed; step={exc.step} returncode={exc.returncode} "
            f"summary_written=true manifest_written=true manifest={manifest_path} "
            f"step_stderr={exc.stderr_first_line}",
            file=sys.stderr,
        )
        return 3
    except Exception as exc:  # noqa: BLE001
        finish("failed")
        print(
            f"ERROR: code=run_failed summary_written=true manifest_written=true "
            f"manifest={manifest_path} "
            f"message={exc}",
            file=sys.stderr,
        )
        return 2
    finish("completed")
    helpers.print_summary(manifest, output)
    return 0


class StepFailure(RuntimeError):
    def __init__(self, step: str, returncode: int, stderr: str = "") -> None:
        super().__init__(f"{step} failed with returncode {returncode}")
        self.step = step
        self.returncode = returncode
        self.stderr_first_line = first_error_line(stderr)


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(Path.cwd()), capture_output=True, text=True)


def run_pipeline(context: RunContext) -> None:
    apply_mode_resolution(context, resolve_mode(context.args))
    output = Path(context.args.output_dir)
    prices = run_prices_path(context.args)
    candidates = output / "candidates.csv"
    diagnostics = output / "diagnostics.csv"
    spot = run_spot_path(context.args)
    context.manifest["input_metadata"] = input_metadata_for_prices(context.args.prices_input)
    validate_preflight_inputs(context.args, spot)
    clear_stale_run_outputs(context.args, output)
    context.manifest["run_outputs_initialized"] = True
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
    if args.prices_input:
        source = Path(args.prices_input)
        if not helpers.same_existing_path(source, prices):
            shutil.copyfile(source, prices)
    config = selected_config(args)
    target_config = output / config.name
    if config.resolve() != target_config.resolve():
        shutil.copyfile(config, target_config)
    if args.spot_input and spot is not None:
        source_spot = Path(args.spot_input)
        if not helpers.same_existing_path(source_spot, spot):
            shutil.copyfile(source_spot, spot)


def validate_preflight_inputs(args: argparse.Namespace, spot: Path | None) -> None:
    validate_history_inputs(args, spot)
    if args.prices_input and not Path(args.prices_input).exists():
        raise FileNotFoundError(f"prices input not found: {Path(args.prices_input)}")
    if args.spot_input and not Path(args.spot_input).exists():
        raise FileNotFoundError(f"spot input not found: {Path(args.spot_input)}")


def run_prices_path(args: argparse.Namespace) -> Path:
    if not args.prices_input:
        return Path(args.output_dir) / "prices.csv"
    return Path(args.output_dir) / f"prices{helpers.tabular_suffix(args.prices_input)}"


def run_spot_path(args: argparse.Namespace) -> Path | None:
    if not args.spot_input and not args.fetch_spot:
        return None
    return Path(args.output_dir) / f"spot{helpers.tabular_suffix(args.spot_input or '')}"


def apply_mode_resolution(context: RunContext, resolution: ModeResolution) -> None:
    context.args.resolved_mode = resolution.mode
    config = selected_config(context.args)
    consumes_prediction = resolution.mode == "prediction"
    context.manifest.update(
        {
            "mode": resolution.mode,
            "mode_decision": resolution.decision,
            "mode_decision_reason": resolution.reason,
            "missing_prediction_column_groups": list(
                resolution.missing_prediction_column_groups
            ),
            "missing_prediction_requirement": missing_prediction_requirement(resolution),
            "config_path": str(Path(context.args.output_dir) / config.name),
            "prediction_mode": consumes_prediction,
            "consumes_prediction_columns": consumes_prediction,
            "prediction_input_source": "external_input" if consumes_prediction else "not_used",
            "prediction_model_executed_by_runner": False,
            "lightgbm_not_used": not consumes_prediction,
            "lightgbm_output_source": "external_input" if consumes_prediction else "not_used",
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
    helpers.write_json(context.manifest, context.manifest_path)
    if result.returncode != 0:
        raise StepFailure(step.name, result.returncode, result.stderr)


def step_record(step: Step, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "step": step.name,
        "command": step.command,
        "returncode": result.returncode,
        "allowed_returncodes": [0],
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def first_error_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def missing_prediction_requirement(resolution: ModeResolution) -> str:
    missing = set(resolution.missing_prediction_column_groups)
    if "prediction" not in missing:
        return ""
    return "prediction_or_prediction_score"


if __name__ == "__main__":
    raise SystemExit(main())
