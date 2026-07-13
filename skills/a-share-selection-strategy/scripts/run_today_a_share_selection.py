#!/usr/bin/env python3
"""Run an auditable local A-share selection workflow through existing CLIs."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import lib.runner.run_today_a_share_selection_helpers as helpers
from lib.a_share_selection_paths import config_path
from lib.selection_core.a_share_selection_command_safety import (
    sanitize_command,
    sanitize_text,
)
from prepare_history_retry_symbols import build_retry_plan
from lib.runner.run_today_a_share_selection_commands import (
    fetch_history_command,
    fetch_spot_fallback_command,
    fetch_spot_command,
    history_market,
    initial_manifest,
    run_config_path,
    score_command,
    selected_config,
    validate_command,
)
from lib.runner.run_today_a_share_selection_history import (
    history_symbols,
    validate_history_inputs,
)
from lib.runner.run_today_a_share_selection_input_metadata import (
    history_metadata_for_output,
    input_metadata_for_prices,
)
from lib.runner.run_today_a_share_selection_modes import ModeResolution, resolve_mode
from lib.runner.run_today_a_share_selection_outputs import (
    clear_stale_run_outputs,
    finalize_outputs,
)
from lib.runner.run_today_a_share_selection_parser import build_parser
from lib.runner.run_today_a_share_selection_prices_filter import (
    PricesFilterError,
    filter_local_prices,
)
from lib.runner.run_today_a_share_selection_prices_sidecar import (
    build_sidecar,
    write_sidecar,
)
from lib.runner.run_today_a_share_selection_provenance import annotate_run_csv_outputs
from lib.runner.run_today_a_share_selection_validation import (
    normalize_zzshare_history_options,
    sync_validated_history_options,
)


DEFAULT_GENERIC_CONFIG = config_path("ultra_short_low_price_config.json")
DEFAULT_PREDICTION_CONFIG = config_path("prediction_profile_config.json")
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
    run_started = time.monotonic()
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
            run_started_monotonic=run_started,
        )

    try:
        output.mkdir(parents=True, exist_ok=True)
        apply_resume_from(args)
        validate_symbols_file_static_output_collision(args, output)
        clear_stale_run_outputs(args, output)
        manifest.clear()
        manifest.update(initial_manifest(args))
        manifest["run_outputs_initialized"] = True
        context = RunContext(args, manifest, manifest_path, run_command)
        if args.plan_only:
            run_plan(context)
        else:
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
        message = sanitize_text(str(exc))
        clear_stale_outputs_after_preflight_error(args, output, manifest)
        manifest["run_error_type"] = exc.__class__.__name__
        manifest["run_error"] = message
        finish("failed")
        print(
            f"ERROR: code=run_failed summary_written=true manifest_written=true "
            f"manifest={manifest_path} "
            f"message={message}",
            file=sys.stderr,
        )
        return 2
    finish("planned" if args.plan_only else "completed")
    helpers.print_summary(manifest, output)
    return 0


class StepFailure(RuntimeError):
    def __init__(self, step: str, returncode: int, stderr: str = "") -> None:
        super().__init__(f"{step} failed with returncode {returncode}")
        self.step = step
        self.returncode = returncode
        self.stderr_first_line = sanitize_text(first_error_line(stderr))


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=str(Path.cwd()),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    threads = [
        threading.Thread(
            target=collect_stream,
            args=(process.stdout, stdout_lines, False),
            daemon=True,
        ),
        threading.Thread(
            target=collect_stream,
            args=(process.stderr, stderr_lines, True),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    returncode = process.wait()
    for thread in threads:
        thread.join()
    result = subprocess.CompletedProcess(
        command,
        int(returncode),
        "".join(stdout_lines),
        "".join(stderr_lines),
    )
    result.duration_seconds = round(max(time.monotonic() - started, 0.0), 6)
    return result


def collect_stream(stream: Any, lines: list[str], echo_progress: bool) -> None:
    if stream is None:
        return
    try:
        for line in stream:
            lines.append(line)
            if echo_progress and line.startswith("PROGRESS:"):
                print(line, file=sys.stderr, end="", flush=True)
    finally:
        stream.close()


def clear_stale_outputs_after_preflight_error(
    args: argparse.Namespace,
    output: Path,
    manifest: dict[str, Any],
) -> None:
    if manifest.get("run_outputs_initialized"):
        return
    try:
        clear_stale_run_outputs(args, output)
    except Exception as exc:  # noqa: BLE001
        manifest["stale_cleanup_error_type"] = exc.__class__.__name__
        manifest["stale_cleanup_error"] = sanitize_text(str(exc))
        return
    manifest["run_outputs_initialized"] = True


def run_pipeline(context: RunContext) -> None:
    apply_mode_resolution(context, resolve_mode(context.args))
    output = Path(context.args.output_dir)
    prices = run_prices_path(context.args)
    candidates = output / "candidates.csv"
    diagnostics = output / "diagnostics.csv"
    score_profile = score_profile_path(context.args)
    spot = run_spot_path(context.args)
    context.manifest["input_metadata"] = input_metadata_for_prices(
        context.args.prices_input
    )
    context.manifest["run_outputs_initialized"] = True
    if not context.args.prices_input:
        context.args.history_market = history_market(context.args)
    validate_preflight_inputs(context.args, spot)
    sync_validated_history_options(context.manifest, context.args)
    apply_execution_path(context)
    validate_symbols_file_output_collision(
        context.args, output, prices, candidates, diagnostics, spot
    )
    prepare_inputs(context.args, output, prices, spot)
    if context.args.fetch_spot:
        run_fetch_spot_step(context, spot)
    prices = apply_optional_prices_filter(context, prices, spot)
    if not context.args.prices_input:
        symbol_derivation_started = time.monotonic()
        symbols = history_symbols(
            context.args, spot, output, run_config_path(context.args)
        )
        context.manifest["symbol_derivation_duration_seconds"] = round(
            max(time.monotonic() - symbol_derivation_started, 0.0), 6
        )
        context.manifest["history_symbols"] = symbols
        prepare_history_symbols_file(context.args, context.manifest, symbols)
        run_step(
            context,
            Step("fetch_history", fetch_history_command(context.args, prices, symbols)),
        )
    run_step(context, Step("validate", validate_command(context.args, prices)))
    run_step(
        context,
        Step(
            "score",
            score_command(
                context.args,
                prices,
                candidates,
                diagnostics,
                spot,
                score_profile,
            ),
        ),
    )
    annotate_run_csv_outputs(context.manifest, candidates, diagnostics)


def run_plan(context: RunContext) -> None:
    apply_mode_resolution(context, resolve_mode(context.args))
    output = Path(context.args.output_dir)
    prices = run_prices_path(context.args)
    candidates = output / "candidates.csv"
    diagnostics = output / "diagnostics.csv"
    score_profile = score_profile_path(context.args)
    spot = run_spot_path(context.args)
    context.manifest["input_metadata"] = input_metadata_for_prices(
        context.args.prices_input
    )
    context.manifest["run_outputs_initialized"] = True
    context.manifest["execution_mode"] = "plan_only"
    context.manifest["commands_executed"] = False
    if not context.args.prices_input:
        context.args.history_market = history_market(context.args)
    validate_preflight_inputs(context.args, spot)
    sync_validated_history_options(context.manifest, context.args)
    apply_execution_path(context)
    validate_symbols_file_output_collision(
        context.args, output, prices, candidates, diagnostics, spot
    )
    prepare_inputs(context.args, output, prices, spot)
    if context.args.fetch_spot:
        plan_step(context, Step("fetch_spot", fetch_spot_command(context.args, spot)))
        if context.args.fetch_spot_fallback:
            plan_step(
                context,
                Step(
                    "fetch_spot_fallback",
                    fetch_spot_fallback_command(context.args, spot),
                ),
            )
    if not context.args.prices_input:
        symbols = planned_history_symbols(context.args, spot)
        context.manifest["history_symbols"] = symbols
        prepare_history_symbols_file(context.args, context.manifest, symbols)
        plan_step(
            context,
            Step("fetch_history", fetch_history_command(context.args, prices, symbols)),
        )
    plan_step(context, Step("validate", validate_command(context.args, prices)))
    plan_step(
        context,
        Step(
            "score",
            score_command(
                context.args,
                prices,
                candidates,
                diagnostics,
                spot,
                score_profile,
            ),
        ),
    )


def planned_history_symbols(args: argparse.Namespace, spot: Path | None) -> list[str]:
    if args.symbols or getattr(args, "symbols_file", None):
        return history_symbols(args, spot, Path(args.output_dir), run_config_path(args))
    if args.derive_symbols_from_spot and spot is not None and args.spot_input:
        return history_symbols(args, spot, Path(args.output_dir), run_config_path(args))
    if args.derive_symbols_from_spot:
        return ["<derived_from_spot_snapshot>"]
    raise ValueError("plan-only history fetch requires a symbol source")


def prepare_history_symbols_file(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    symbols: list[str],
) -> None:
    args.history_symbols_file = ""
    manifest["history_symbols_file"] = ""
    if args.history_source != "zzshare":
        return
    if getattr(args, "plan_only", False):
        return
    if any(str(symbol).startswith("<") and str(symbol).endswith(">") for symbol in symbols):
        return
    if getattr(args, "symbols_file", None):
        args.history_symbols_file = str(Path(args.symbols_file))
        manifest["history_symbols_file"] = args.history_symbols_file
        return
    path = Path(args.output_dir) / "history_symbols.txt"
    path.write_text("\n".join(symbols) + "\n", encoding="utf-8")
    args.history_symbols_file = str(path)
    manifest["history_symbols_file"] = str(path)


def prepare_inputs(
    args: argparse.Namespace, output: Path, prices: Path, spot: Path | None
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    if args.prices_input:
        source = Path(args.prices_input)
        if should_copy_prices_input(args, source, prices):
            shutil.copyfile(source, prices)
    config = selected_config(args)
    target_config = output / config.name
    if config.resolve() != target_config.resolve():
        shutil.copyfile(config, target_config)
    if args.spot_input and spot is not None:
        source_spot = Path(args.spot_input)
        if not helpers.same_existing_path(source_spot, spot):
            shutil.copyfile(source_spot, spot)


def apply_optional_prices_filter(
    context: RunContext,
    prices: Path,
    spot: Path | None,
) -> Path:
    if not prices_filter_requested(context.args):
        return prices
    if not context.args.prices_input:
        raise ValueError("prices filters require --prices-input")
    if context.args.filter_prices_to_spot_universe and (
        spot is None or not spot.is_file()
    ):
        raise ValueError(
            "--filter-prices-to-spot-universe requires --spot-input or --fetch-spot"
        )
    source = prices_filter_source_path(context.args, prices)
    target = prices_filter_output_path(context.args, prices)
    filter_started = time.monotonic()
    try:
        filtered_prices, metadata = filter_local_prices(
            prices=source,
            spot=spot,
            output_dir=Path(context.args.output_dir),
            filter_spot_universe=bool(context.args.filter_prices_to_spot_universe),
            min_symbol_latest_date=context.args.min_symbol_latest_date,
        )
    except PricesFilterError as exc:
        exc.metadata["prices_filter_duration_seconds"] = round(
            max(time.monotonic() - filter_started, 0.0), 6
        )
        exc.metadata["prices_filter_output_prices"] = str(target)
        exc.metadata["prices_filter_output_format"] = prices_output_format_label(target)
        record_prices_filter_metadata(context, exc.metadata)
        raise
    metadata["prices_filter_output_prices"] = str(target)
    metadata["prices_filter_output_format"] = prices_output_format_label(target)
    passthrough_copy = can_copy_filtered_source(source, target, metadata)
    metadata["prices_filter_passthrough_copy"] = passthrough_copy
    if passthrough_copy:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    else:
        write_tabular_output(filtered_prices, target)
    if target.suffix.lower() in {".parquet", ".pq"}:
        sidecar = build_sidecar(
            prices=target,
            frame=filtered_prices,
            filter_metadata=metadata,
            input_metadata=context.manifest.get("input_metadata", {}),
        )
        metadata["prices_filter_sidecar_output"] = str(write_sidecar(sidecar, target))
        metadata["prices_filter_sidecar_sha256"] = sidecar["artifact"]["sha256"]
    metadata["prices_filter_duration_seconds"] = round(
        max(time.monotonic() - filter_started, 0.0), 6
    )
    record_prices_filter_metadata(context, metadata)
    context.manifest["prices_output_path"] = str(target)
    return target


def record_prices_filter_metadata(
    context: RunContext,
    metadata: dict[str, Any],
) -> None:
    helpers.write_json(metadata, Path(metadata["prices_filter_metadata_output"]))
    for key in [
        "prices_filter_spot_universe",
        "prices_filter_min_symbol_latest_date",
        "prices_filter_metadata_output",
        "prices_filter_source_prices",
        "prices_filter_source_spot",
        "prices_filter_output_prices",
        "prices_filter_output_format",
        "prices_filter_passthrough_copy",
        "prices_filter_sidecar_output",
        "prices_filter_sidecar_sha256",
        "prices_filter_input_rows",
        "prices_filter_output_rows",
        "prices_filter_spot_symbol_count",
        "prices_filter_input_symbol_count",
        "prices_filter_kept_symbol_count",
        "prices_filter_removed_symbol_count",
        "prices_filter_removed_symbols",
        "prices_filter_removed_stale_symbol_count",
        "prices_filter_removed_stale_symbols",
        "prices_filter_output_written",
        "prices_filter_failure_reason",
        "prices_filter_error",
        "prices_filter_duration_seconds",
    ]:
        if key in metadata:
            context.manifest[key] = metadata[key]
    context.manifest["prices_filter_claim_boundary"] = metadata["source_claim_boundary"]
    context.manifest["input_metadata"].update(metadata)


def prices_filter_requested(args: argparse.Namespace) -> bool:
    return bool(args.filter_prices_to_spot_universe or args.min_symbol_latest_date)


def prices_filter_source_path(args: argparse.Namespace, prepared_prices: Path) -> Path:
    if explicit_prices_filter_output_format(args) and args.prices_input:
        return Path(args.prices_input)
    return prepared_prices


def should_copy_prices_input(
    args: argparse.Namespace, source: Path, prepared_prices: Path
) -> bool:
    if helpers.same_existing_path(source, prepared_prices):
        return False
    return not explicit_prices_filter_output_format(args)


def explicit_prices_filter_output_format(args: argparse.Namespace) -> bool:
    return bool(
        prices_filter_requested(args)
        and getattr(args, "prices_filter_output_format", "input") != "input"
    )


def prices_filter_output_path(args: argparse.Namespace, prepared_prices: Path) -> Path:
    output_format = getattr(args, "prices_filter_output_format", "input") or "input"
    suffix = prices_filter_output_suffix(output_format, prepared_prices)
    return Path(args.output_dir) / f"prices{suffix}"


def can_copy_filtered_source(
    source: Path,
    target: Path,
    metadata: dict[str, Any],
) -> bool:
    if source.suffix.lower() != target.suffix.lower():
        return False
    if helpers.same_existing_path(source, target):
        return False
    return (
        int(metadata.get("prices_filter_removed_symbol_count", 0) or 0) == 0
        and int(metadata.get("prices_filter_input_rows", 0) or 0)
        == int(metadata.get("prices_filter_output_rows", 0) or 0)
    )


def prices_filter_output_suffix(output_format: str, prepared_prices: Path) -> str:
    if output_format == "input":
        return helpers.tabular_suffix(str(prepared_prices))
    suffixes = {"csv": ".csv", "parquet": ".parquet", "pq": ".pq"}
    return suffixes[output_format]


def prices_output_format_label(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".parquet":
        return "parquet"
    if suffix == ".pq":
        return "pq"
    raise ValueError("unsupported prices output format; use .csv, .parquet, or .pq")


def write_tabular_output(frame: Any, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame.to_csv(path, index=False)
        return
    if suffix in {".parquet", ".pq"}:
        frame.to_parquet(path, index=False)
        return
    raise ValueError("unsupported prices output format; use .csv, .parquet, or .pq")


def validate_symbols_file_output_collision(
    args: argparse.Namespace,
    output: Path,
    prices: Path,
    candidates: Path,
    diagnostics: Path,
    spot: Path | None,
) -> None:
    symbols_file = getattr(args, "symbols_file", None)
    if not symbols_file:
        return
    source = Path(symbols_file)
    blocked = [
        output / "run_manifest.json",
        output / "summary.json",
        output / "report.html",
        output / "selected_symbols.json",
        output / "history_metadata.json",
        output / "spot_metadata.json",
        output / selected_config(args).name,
        prices,
        candidates,
        diagnostics,
    ]
    if prices_filter_requested(args):
        blocked.append(prices_filter_output_path(args, prices))
    if spot is not None:
        blocked.append(spot)
    for path in blocked:
        if helpers.same_path_or_existing_file(path, source):
            raise ValueError(
                f"--symbols-file must not point to runner output path: {source}"
            )


def validate_symbols_file_static_output_collision(
    args: argparse.Namespace, output: Path
) -> None:
    symbols_file = getattr(args, "symbols_file", None)
    if not symbols_file:
        return
    source = Path(symbols_file)
    blocked = [
        output / "run_manifest.json",
        output / "summary.json",
        output / "report.html",
        output / "selected_symbols.json",
        output / "history_metadata.json",
        output / "spot_metadata.json",
        output / "candidates.csv",
        output / "diagnostics.csv",
        run_prices_path(args),
    ]
    if prices_filter_requested(args):
        blocked.append(prices_filter_output_path(args, run_prices_path(args)))
    spot = run_spot_path(args)
    if spot is not None:
        blocked.append(spot)
    for config in [
        getattr(args, "default_generic_config", None),
        getattr(args, "default_prediction_config", None),
        Path(args.config) if getattr(args, "config", None) else None,
    ]:
        if config:
            blocked.append(output / Path(config).name)
    for path in blocked:
        if helpers.same_path_or_existing_file(path, source):
            raise ValueError(
                f"--symbols-file must not point to runner output path: {source}"
            )


def validate_preflight_inputs(args: argparse.Namespace, spot: Path | None) -> None:
    validate_history_inputs(args, spot)
    if prices_filter_requested(args) and not args.prices_input:
        raise ValueError("prices filters require --prices-input")
    if args.filter_prices_to_spot_universe and not (args.spot_input or args.fetch_spot):
        raise ValueError(
            "--filter-prices-to-spot-universe requires --spot-input or --fetch-spot"
        )
    if not args.prices_input and args.history_source in {"pytdx", "zzshare", "yfinance"}:
        normalize_zzshare_history_options(args)
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
    return (
        Path(args.output_dir) / f"spot{helpers.tabular_suffix(args.spot_input or '')}"
    )


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
            "missing_prediction_requirement": missing_prediction_requirement(
                resolution
            ),
            "config_path": str(Path(context.args.output_dir) / config.name),
            "prediction_mode": consumes_prediction,
            "consumes_prediction_columns": False,
            "prediction_input_source": "not_used",
            "requested_prediction_input_source": (
                "external_input" if consumes_prediction else "not_used"
            ),
            "prediction_model_executed_by_runner": False,
            "lightgbm_not_used": not consumes_prediction,
            "lightgbm_output_source": "not_used",
            "requested_lightgbm_output_source": (
                "external_input" if consumes_prediction else "not_used"
            ),
            "lightgbm_executed_by_runner": False,
            "source_scope": source_scope(context.args),
        }
    )


def apply_execution_path(context: RunContext) -> None:
    args = context.args
    mode = getattr(args, "resolved_mode", args.mode)
    if args.prices_input:
        path = f"local_prices_{mode}"
        reason = "prices_input_provided"
        coverage_class = "local_input"
        full_market_boundary = "local_prices_input_not_full_market_scan"
        if args.spot_input:
            path += "_with_local_spot"
            reason += "+spot_input"
        elif args.fetch_spot:
            path += "_with_fetched_spot"
            reason += "+fetch_spot"
    else:
        if args.derive_symbols_from_spot:
            max_history_symbols_is_default = not bool(
                getattr(args, "max_history_symbols_supplied", False)
            )
            spot_source_suffix = (
                "_with_local_spot" if args.spot_input else "_with_fetched_spot"
            )
            spot_source_reason = "+spot_input" if args.spot_input else "+fetch_spot"
            path = (
                "history_fetch_spot_derived_sample"
                if max_history_symbols_is_default
                else "history_fetch_spot_derived_explicit_limit"
            )
            reason = (
                "derive_symbols_from_spot+default_small_sample_cap"
                if max_history_symbols_is_default
                else "derive_symbols_from_spot+explicit_history_limit"
            )
            coverage_class = (
                "spot_derived_sample"
                if max_history_symbols_is_default
                else "spot_derived_limited_pool"
            )
            full_market_boundary = (
                "default_small_sample_cap_not_full_market"
                if max_history_symbols_is_default
                else "spot_derived_explicit_limit_requires_artifact_review"
            )
            path += spot_source_suffix
            reason += spot_source_reason
        else:
            explicit_limit = bool(getattr(args, "max_history_symbols_supplied", False))
            input_label = explicit_history_input_label(args)
            path = (
                f"history_fetch_{input_label}_explicit_limit"
                if explicit_limit
                else f"history_fetch_{input_label}"
            )
            reason = (
                f"{input_label}+explicit_history_limit"
                if explicit_limit
                else input_label
            )
            coverage_class = (
                "explicit_symbol_limited_pool"
                if explicit_limit
                else "explicit_symbol_pool"
            )
            full_market_boundary = (
                "explicit_symbols_explicit_limit_requires_artifact_review"
                if explicit_limit
                else "explicit_symbols_not_full_market_scan"
            )
        path += f"_{mode}"
    context.manifest.update(
        {
            "execution_path": path,
            "execution_path_reason": reason,
            "coverage_class": coverage_class,
            # The runner reports breadth evidence but does not prove full-market closure by itself.
            "full_market_claim_allowed": False,
            "full_market_claim_boundary": full_market_boundary,
        }
    )


def explicit_history_input_label(args: argparse.Namespace) -> str:
    if getattr(args, "resume_from", None):
        return "resume_retry_symbols"
    if getattr(args, "symbols_file", None):
        return "explicit_symbols_file"
    return "explicit_symbols"


def source_scope(args: argparse.Namespace) -> str:
    return source_scope_for_spot_source(args, args.fetch_spot)


def source_scope_for_spot_source(args: argparse.Namespace, spot_source: str) -> str:
    scopes = []
    history = (
        f"{args.history_source}_history_fetch"
        if args.history_source
        else "history_fetch"
    )
    scopes.append("local_prices_input" if args.prices_input else history)
    if args.spot_input:
        scopes.append("local_spot_input")
    if spot_source:
        scopes.append(fetch_spot_source_scope(spot_source))
    return "+".join(scopes)


def fetch_spot_source_scope(source: str) -> str:
    if source == "baostock_universe":
        return "baostock_universe_snapshot"
    if source == "eastmoney":
        return "eastmoney_spot_snapshot"
    return f"{source}_spot_snapshot"


def run_fetch_spot_step(context: RunContext, spot: Path | None) -> None:
    step = Step("fetch_spot", fetch_spot_command(context.args, spot))
    result = run_step_result(context, step)
    if result.returncode == 0:
        return
    fallback = context.args.fetch_spot_fallback
    if not fallback:
        raise StepFailure(step.name, result.returncode, result.stderr)
    mark_last_step_as_handled_fallback(context, result.returncode)
    context.manifest["fetch_spot_primary_failure"] = step_record(step, result)
    context.manifest["fetch_spot_fallback_used"] = True
    context.manifest["source_scope"] = source_scope_for_spot_source(
        context.args,
        fallback,
    )
    fallback_step = Step(
        "fetch_spot_fallback",
        fetch_spot_fallback_command(context.args, spot),
    )
    fallback_result = run_step_result(context, fallback_step)
    if fallback_result.returncode != 0:
        raise StepFailure(
            fallback_step.name,
            fallback_result.returncode,
            fallback_result.stderr,
        )


def mark_last_step_as_handled_fallback(
    context: RunContext,
    returncode: int,
) -> None:
    if not context.manifest["steps"]:
        return
    latest = context.manifest["steps"][-1]
    latest["allowed_returncodes"] = sorted({0, int(returncode)})
    latest["handled_failure"] = True
    latest["fallback_step"] = "fetch_spot_fallback"


def run_step(context: RunContext, step: Step) -> None:
    result = run_step_result(context, step)
    if result.returncode != 0:
        raise StepFailure(step.name, result.returncode, result.stderr)


def run_step_result(
    context: RunContext,
    step: Step,
) -> subprocess.CompletedProcess[str]:
    result = context.executor(step.command)
    context.manifest["commands_executed"] = True
    context.manifest["steps"].append(step_record(step, result))
    if step.name == "fetch_history":
        update_history_input_metadata(context.manifest)
    if step.name == "validate" and result.returncode != 0:
        write_short_history_artifacts(context.manifest, context.args)
    if step.name == "score":
        update_prediction_consumption(context.manifest)
        if context.args.score_profile:
            update_score_profile_metadata(context.manifest, context.args)
    helpers.write_json(context.manifest, context.manifest_path)
    return result


def plan_step(context: RunContext, step: Step) -> None:
    context.manifest["steps"].append(plan_step_record(step))
    if step.name == "score" and context.args.score_profile:
        update_score_profile_metadata(context.manifest, context.args)
    helpers.write_json(context.manifest, context.manifest_path)


def step_record(step: Step, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    record = {
        "step": step.name,
        "command": sanitize_command(step.command),
        "returncode": result.returncode,
        "allowed_returncodes": [0],
        "stdout": sanitize_text(result.stdout),
        "stderr": sanitize_text(result.stderr),
    }
    duration = getattr(result, "duration_seconds", None)
    if duration is not None:
        record["duration_seconds"] = float(duration)
    return record


def plan_step_record(step: Step) -> dict[str, Any]:
    return {
        "step": step.name,
        "command": sanitize_command(step.command),
        "returncode": None,
        "allowed_returncodes": [0],
        "stdout": "",
        "stderr": "",
        "planned": True,
        "executed": False,
    }


def update_score_profile_metadata(
    manifest: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    profile = Path(args.output_dir) / "score_profile.json"
    manifest["score_profile_output"] = str(profile)
    if profile.is_file():
        profile_data = json.loads(profile.read_text(encoding="utf-8"))
        manifest["score_profile_output_written"] = True
        manifest["score_profile_rows"] = int(profile_data.get("candidate_rows", 0) or 0)
        manifest["score_profile_duration_seconds"] = profile_data.get(
            "duration_seconds", 0.0
        )
        manifest["score_profile_input_rows_per_second"] = profile_data.get(
            "input_rows_per_second"
        )
        manifest["score_profile_scored_symbols_per_second"] = profile_data.get(
            "scored_symbols_per_second"
        )
    else:
        manifest["score_profile_output_written"] = False
        manifest["score_profile_rows"] = 0
        manifest["score_profile_duration_seconds"] = 0.0
        manifest["score_profile_input_rows_per_second"] = None
        manifest["score_profile_scored_symbols_per_second"] = None


def score_profile_path(args: argparse.Namespace) -> Path | None:
    if not args.score_profile:
        return None
    return Path(args.output_dir) / "score_profile.json"


def apply_resume_from(args: argparse.Namespace) -> None:
    if not args.resume_from:
        args.resume_symbol_source = ""
        args.resume_retry_symbol_count = 0
        args.resume_inherited_options = []
        args.resume_sensitive_options_requiring_explicit_input = []
        args.resume_prior_output_dir = ""
        return
    if args.prices_input:
        raise ValueError("--resume-from cannot be combined with --prices-input")
    if (
        args.symbols
        or getattr(args, "symbols_file", None)
        or args.derive_symbols_from_spot
    ):
        raise ValueError(
            "--resume-from cannot be combined with --symbols, --symbols-file, "
            "or --derive-symbols-from-spot"
        )
    manifest_path = resolve_resume_manifest_path(Path(args.resume_from))
    manifest = load_resume_manifest(manifest_path)
    prior_output = resume_output_dir(manifest, manifest_path)
    symbols = retry_symbols_from_prior_run(prior_output)
    if not symbols:
        raise ValueError(
            "--resume-from did not produce retry symbols; expected failed, empty, "
            "possibly truncated, or unprocessed history symbols in the prior artifacts"
        )
    args.symbols = ",".join(symbols)
    args.resume_from = str(manifest_path)
    args.resume_symbol_source = "prior_history_retry_plan"
    args.resume_retry_symbol_count = len(symbols)
    args.resume_prior_output_dir = str(prior_output)
    apply_resume_defaults(args, manifest)


def resolve_resume_manifest_path(path: Path) -> Path:
    if path.is_dir():
        return path / "run_manifest.json"
    return path


def load_resume_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"resume manifest not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"resume manifest must be a JSON object: {path}")
    return data


def resume_output_dir(manifest: dict[str, Any], manifest_path: Path) -> Path:
    output = str(manifest.get("output_dir", "")).strip()
    if not output:
        return manifest_path.parent
    output_path = Path(output)
    if output_path.is_absolute():
        return output_path
    if path_has_suffix(manifest_path.parent, output_path):
        return manifest_path.parent
    return manifest_path.parent / output_path


def path_has_suffix(path: Path, suffix: Path) -> bool:
    path_parts = path.parts
    suffix_parts = suffix.parts
    return bool(suffix_parts) and path_parts[-len(suffix_parts) :] == suffix_parts


def retry_symbols_from_prior_run(output: Path) -> list[str]:
    selected = read_json_object(output / "selected_symbols.json")
    metadata = read_json_object(output / "history_metadata.json")
    plan = build_retry_plan(
        selected_data=selected,
        metadata=metadata,
        include_clean_selected=False,
    )
    return list(plan["retry_symbols"])


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"resume artifact not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"resume artifact must be a JSON object: {path}")
    return data


def apply_resume_defaults(args: argparse.Namespace, manifest: dict[str, Any]) -> None:
    inherited = []
    for name in ["history_source", "start_date", "end_date"]:
        inherit_resume_option(args, manifest, inherited, name)
    prior_source = str(manifest.get("history_source", "") or "")
    current_source = str(getattr(args, "history_source", "") or "")
    sensitive_options = []
    if current_source != prior_source:
        args.resume_inherited_options = inherited
        args.resume_sensitive_options_requiring_explicit_input = sensitive_options
        return
    if current_source in {"akshare", "akshare_hk_daily", "baostock", "zzshare"}:
        inherit_resume_option(args, manifest, inherited, "history_adjust")
    if current_source == "zzshare":
        note_sensitive_resume_option(
            args, manifest, sensitive_options, "history_http_url"
        )
        for name in [
            "history_timeout_seconds",
            "history_request_interval_seconds",
            "history_max_concurrent_symbol_requests",
            "history_max_rate_limit_sleep_seconds",
            "history_max_429_events",
            "history_max_runtime_seconds",
            "history_limit",
            "history_max_pages",
            "history_non_trading_policy",
        ]:
            inherit_resume_option(args, manifest, inherited, name)
    elif current_source in {"pytdx", "yfinance"}:
        inherit_resume_option(args, manifest, inherited, "history_timeout_seconds")
    args.resume_inherited_options = inherited
    args.resume_sensitive_options_requiring_explicit_input = sensitive_options


def inherit_resume_option(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    inherited: list[str],
    name: str,
) -> None:
    if helpers.option_configured(getattr(args, name, None)):
        return
    value = manifest.get(name, "")
    if helpers.option_configured(value):
        setattr(args, name, str(value))
        inherited.append(name)


def note_sensitive_resume_option(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    sensitive_options: list[str],
    name: str,
) -> None:
    if helpers.option_configured(getattr(args, name, None)):
        return
    if helpers.option_configured(manifest.get(name, "")):
        sensitive_options.append(name)


def update_prediction_consumption(manifest: dict[str, Any]) -> None:
    consumed = helpers.prediction_columns_consumed(manifest)
    manifest["consumes_prediction_columns"] = consumed
    manifest["prediction_input_source"] = "external_input" if consumed else "not_used"
    manifest["lightgbm_output_source"] = "external_input" if consumed else "not_used"


def update_history_input_metadata(manifest: dict[str, Any]) -> None:
    metadata = history_metadata_for_output(Path(manifest["output_dir"]))
    if metadata:
        manifest["input_metadata"] = metadata


def write_short_history_artifacts(
    manifest: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    output = Path(manifest["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    metadata_path = output / "history_metadata.json"
    metadata = read_json_object(metadata_path) if metadata_path.is_file() else {}
    if not isinstance(metadata.get("symbols"), list):
        prices_path = short_history_prices_path(manifest, args)
        if prices_path is None:
            return
        try:
            metadata = metadata_from_prices(prices_path)
        except Exception as exc:  # noqa: BLE001
            manifest["short_history_artifacts_error"] = (
                f"{exc.__class__.__name__}: {sanitize_text(str(exc))}"
            )
            return
    symbols = short_history_symbols(metadata, int(args.min_history_rows))
    if not symbols:
        return
    txt_path = output / "short_history_symbols.txt"
    json_path = output / "short_history_symbols.json"
    txt_path.write_text(
        "\n".join(str(item["symbol"]) for item in symbols) + "\n",
        encoding="utf-8",
    )
    helpers.write_json(
        {
            "source": "history_metadata_rows",
            "min_history_rows": int(args.min_history_rows),
            "short_history_symbol_count": len(symbols),
            "symbols": symbols,
            "next_action": (
                "review these symbols, then rerun with a cleaned symbols file or "
                "extend the history window"
            ),
        },
        json_path,
    )
    manifest["short_history_symbols_output"] = str(txt_path)
    manifest["short_history_symbols_metadata_output"] = str(json_path)
    manifest["short_history_symbol_count"] = len(symbols)


def short_history_prices_path(
    manifest: dict[str, Any], args: argparse.Namespace
) -> Path | None:
    raw_path = str(
        manifest.get("prices_filter_output_prices")
        or args.prices_input
        or ""
    ).strip()
    if not raw_path:
        return None
    path = Path(raw_path)
    return path if path.is_file() else None


def metadata_from_prices(path: Path) -> dict[str, Any]:
    from lib.selection_core.a_share_selection_data import parse_dates, read_table

    frame = read_table(path)
    if "symbol" not in frame or "date" not in frame:
        return {"symbols": []}
    dates = parse_dates(frame["date"])
    if dates.isna().any():
        raise ValueError(f"prices input has invalid dates: {path}")
    symbols = []
    for symbol, group in frame.assign(_date=dates).groupby(
        frame["symbol"].astype(str), sort=True
    ):
        series = group["_date"]
        symbols.append(
            {
                "symbol": str(symbol),
                "rows": int(len(group)),
                "date_min": str(series.min().date()),
                "date_max": str(series.max().date()),
            }
        )
    return {"symbols": symbols}


def short_history_symbols(
    metadata: dict[str, Any],
    min_history_rows: int,
) -> list[dict[str, Any]]:
    records = metadata.get("symbols", [])
    if not isinstance(records, list):
        return []
    symbols: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        rows = int(record.get("rows", 0) or 0)
        symbol = str(record.get("symbol", "")).strip()
        if symbol and rows < min_history_rows:
            symbols.append(
                {
                    "symbol": symbol,
                    "rows": rows,
                    "min_history_rows": min_history_rows,
                    "date_min": str(record.get("date_min", "") or ""),
                    "date_max": str(record.get("date_max", "") or ""),
                }
            )
    return symbols


def first_error_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("PROGRESS:"):
            continue
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
