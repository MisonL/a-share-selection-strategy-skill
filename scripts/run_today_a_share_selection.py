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

from run_today_a_share_selection_helpers import print_summary, summary_view, write_json


SCRIPTS = Path(__file__).resolve().parent
DEFAULT_GENERIC_CONFIG = SCRIPTS / "ultra_short_low_price_config.json"
DEFAULT_QSSS_CONFIG = SCRIPTS / "qsss_profile_config.json"
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
    parser = argparse.ArgumentParser(description="Run local A-share selection gates.")
    parser.add_argument("--prices-input", required=True, help="Local CSV or Parquet prices.")
    parser.add_argument("--output-dir", required=True, help="Output run directory.")
    parser.add_argument("--mode", choices=["generic", "qsss"], default="generic")
    parser.add_argument("--config", help="Override scoring config path.")
    parser.add_argument("--spot-input", help="Optional local spot CSV or Parquet file.")
    parser.add_argument(
        "--fetch-spot",
        choices=["eastmoney"],
        help="Fetch spot snapshot before scoring.",
    )
    parser.add_argument("--spot-pages", type=int, default=1)
    parser.add_argument("--fail-on-partial-spot", action="store_true")
    parser.add_argument("--min-history-rows", type=int, default=120)
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


def run_pipeline(context: RunContext) -> None:
    output = Path(context.args.output_dir)
    prices = run_prices_path(context.args)
    candidates = output / "candidates.csv"
    diagnostics = output / "diagnostics.csv"
    spot = run_spot_path(context.args)
    prepare_inputs(context.args, output, prices, spot)
    run_step(context, Step("validate", validate_command(context.args, prices)))
    if context.args.fetch_spot:
        run_step(context, Step("fetch_spot", fetch_spot_command(context.args, spot)))
    run_step(context, Step("score", score_command(context.args, prices, candidates, diagnostics, spot)))


def prepare_inputs(
    args: argparse.Namespace, output: Path, prices: Path, spot: Path | None
) -> None:
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
    source = Path(args.prices_input)
    suffix = source.suffix if source.suffix in {".csv", ".parquet"} else ".csv"
    return Path(args.output_dir) / f"prices{suffix}"


def run_spot_path(args: argparse.Namespace) -> Path | None:
    if not args.spot_input and not args.fetch_spot:
        return None
    suffix = Path(args.spot_input).suffix if args.spot_input else ".csv"
    suffix = suffix if suffix in {".csv", ".parquet"} else ".csv"
    return Path(args.output_dir) / f"spot{suffix}"


def selected_config(args: argparse.Namespace) -> Path:
    if args.config:
        return Path(args.config)
    return DEFAULT_QSSS_CONFIG if args.mode == "qsss" else DEFAULT_GENERIC_CONFIG


def validate_command(args: argparse.Namespace, prices: Path) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPTS / "validate_ohlcv.py"),
        "--input",
        str(prices),
        "--min-history-rows",
        str(args.min_history_rows),
        "--config",
        str(run_config_path(args)),
    ]
    return command


def score_command(
    args: argparse.Namespace,
    prices: Path,
    candidates: Path,
    diagnostics: Path,
    spot: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPTS / "score_candidates.py"),
        "--input",
        str(prices),
        "--config",
        str(run_config_path(args)),
        "--output",
        str(candidates),
        "--diagnostics-output",
        str(diagnostics),
    ]
    if spot is not None:
        command.extend(["--spot-input", str(spot)])
    if args.fail_on_empty_result:
        command.append("--fail-on-empty-result")
    if args.fail_on_skipped:
        command.append("--fail-on-skipped")
    return command


def fetch_spot_command(args: argparse.Namespace, spot: Path | None) -> list[str]:
    if args.fetch_spot != "eastmoney" or spot is None:
        raise ValueError("unsupported spot fetch configuration")
    metadata = Path(args.output_dir) / "spot_metadata.json"
    command = [
        sys.executable,
        str(SCRIPTS / "fetch_eastmoney_a_share_spot.py"),
        "--output",
        str(spot),
        "--metadata-output",
        str(metadata),
        "--pages",
        str(args.spot_pages),
    ]
    if args.fail_on_partial_spot:
        command.append("--fail-on-partial")
    return command


def run_config_path(args: argparse.Namespace) -> Path:
    return Path(args.output_dir) / selected_config(args).name


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


def initial_manifest(args: argparse.Namespace) -> dict[str, Any]:
    config = selected_config(args)
    return {
        "runner": "run_today_a_share_selection",
        "mode": args.mode,
        "prices_input": str(Path(args.prices_input)),
        "output_dir": str(Path(args.output_dir)),
        "config_path": str(Path(args.output_dir) / config.name),
        "spot_input": str(Path(args.spot_input)) if args.spot_input else "",
        "fetch_spot": args.fetch_spot or "",
        "spot_pages": int(args.spot_pages),
        "min_history_rows": args.min_history_rows,
        "fail_on_empty_result": bool(args.fail_on_empty_result),
        "fail_on_skipped": bool(args.fail_on_skipped),
        "qsss_mode": args.mode == "qsss",
        "lightgbm_not_used": args.mode != "qsss",
        "source_scope": "local_prices_input",
        "steps": [],
    }


if __name__ == "__main__":
    raise SystemExit(main())
