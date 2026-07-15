#!/usr/bin/env python3
"""Execute incremental history fetch buckets and optionally merge them."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

from lib.gates.incremental_history_execution import (
    default_python,
    default_scripts_dir,
    execute_plan,
    load_plan,
    run_command,
)


PROVIDERS = ("zzshare", "baostock", "pytdx")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute auditable incremental history fetch buckets. Provider failures "
            "stop the run; no source fallback is implicit."
        )
    )
    parser.add_argument("--plan", required=True)
    parser.add_argument("--provider", choices=PROVIDERS, required=True)
    parser.add_argument("--full-start-date")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--checkpoint-batch-size", type=positive_int, default=100)
    parser.add_argument(
        "--zzshare-non-trading-policy",
        choices=("fail", "drop", "keep"),
        default="fail",
        help=(
            "Explicit zzshare non-trading row policy for bucket fetches. "
            "Default: fail. Other providers reject this option."
        ),
    )
    parser.add_argument("--zzshare-request-interval-seconds", type=non_negative_float)
    parser.add_argument("--zzshare-max-concurrent-symbol-requests", type=positive_int)
    parser.add_argument("--zzshare-max-rate-limit-sleep-seconds", type=non_negative_float)
    parser.add_argument("--zzshare-max-429-events", type=positive_int)
    parser.add_argument("--zzshare-max-runtime-seconds", type=positive_float)
    parser.add_argument("--zzshare-progress-interval", type=non_negative_int)
    parser.add_argument(
        "--baostock-names-input",
        help="Optional CSV or Parquet symbol/name artifact for Baostock buckets.",
    )
    parser.add_argument(
        "--baostock-missing-name-policy",
        choices=("query", "fail", "blank"),
        help="Explicit Baostock policy for symbols absent from --baostock-names-input.",
    )
    parser.add_argument(
        "--baostock-non-trading-policy",
        choices=("reject", "drop", "keep"),
        help="Explicit Baostock policy for tradestatus values other than 1.",
    )
    parser.add_argument(
        "--baostock-drop-invalid-rows",
        action="store_true",
        help="Explicitly drop invalid Baostock rows instead of failing the bucket.",
    )
    parser.add_argument(
        "--baostock-allow-non-trading-empty",
        action="store_true",
        help=(
            "Allow only explicitly audited Baostock symbols with no trading row "
            "through the target date to retain their base history."
        ),
    )
    parser.add_argument("--base-prices")
    parser.add_argument("--base-metadata")
    parser.add_argument("--merged-output")
    parser.add_argument("--merged-metadata-output")
    parser.add_argument("--merge-report-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan_path = Path(args.plan).resolve()
        plan = load_plan(plan_path)
        config = build_config(args, plan_path, plan)
        manifest = execute_plan(plan, config, run_command)
        if manifest["status"] != "complete":
            failure = manifest.get("failed_bucket_id") or manifest.get(
                "failed_stage", ""
            )
            print(
                f"ERROR: incremental bucket execution partial; "
                f"failed_at={failure} error={manifest.get('error', '')}",
                file=sys.stderr,
            )
            return 2
        if merge_requested(args):
            run_verified_merge(args, config)
        print(
            f"OK: buckets={manifest['planned_bucket_count']} "
            f"symbols={manifest['planned_symbol_count']} provider={args.provider} "
            f"manifest={config['manifest_output']}"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: incremental history execution failed: {exc}", file=sys.stderr)
        return 2


def build_config(
    args: argparse.Namespace, plan_path: Path, plan: dict[str, object]
) -> dict[str, object]:
    output_dir = Path(args.output_dir).resolve()
    requires_full = any(
        bucket.get("fetch_mode") == "full" for bucket in plan["fetch_buckets"]
    )
    if requires_full and not str(args.full_start_date or "").strip():
        raise ValueError("--full-start-date is required when plan has full buckets")
    validate_merge_arguments(args)
    if not plan["fetch_buckets"] and merge_requested(args):
        raise ValueError(
            "verified merge is not valid when the plan has no fetch buckets"
        )
    baostock_names_input = validate_provider_options(args)
    return {
        "plan_path": plan_path,
        "provider": args.provider,
        "full_start_date": str(args.full_start_date or ""),
        "output_dir": output_dir,
        "prices_output": output_dir / "incremental_prices.csv",
        "metadata_output": output_dir / "incremental_metadata.json",
        "manifest_output": output_dir / "execution_manifest.json",
        "resume": bool(args.resume),
        "checkpoint_batch_size": args.checkpoint_batch_size,
        **provider_config_fields(args, baostock_names_input),
        "python_executable": default_python(),
        "scripts_dir": default_scripts_dir(),
    }


def validate_provider_options(args: argparse.Namespace) -> Path | None:
    validate_zzshare_options(args)
    return validate_baostock_options(args)


def validate_zzshare_options(args: argparse.Namespace) -> None:
    zzshare_options_supplied = args.zzshare_non_trading_policy != "fail" or any(
        value is not None
        for value in (
            args.zzshare_request_interval_seconds,
            args.zzshare_max_concurrent_symbol_requests,
            args.zzshare_max_rate_limit_sleep_seconds,
            args.zzshare_max_429_events,
            args.zzshare_max_runtime_seconds,
            args.zzshare_progress_interval,
        )
    )
    if args.provider != "zzshare" and zzshare_options_supplied:
        raise ValueError(
            "zzshare-specific options are only valid with --provider zzshare"
        )


def validate_baostock_options(args: argparse.Namespace) -> Path | None:
    baostock_options_supplied = bool(args.baostock_names_input) or any(
        value is not None
        for value in (
            args.baostock_missing_name_policy,
            args.baostock_non_trading_policy,
        )
    ) or bool(args.baostock_drop_invalid_rows)
    baostock_options_supplied = baostock_options_supplied or bool(
        args.baostock_allow_non_trading_empty
    )
    if args.provider != "baostock" and baostock_options_supplied:
        raise ValueError(
            "baostock-specific options are only valid with --provider baostock"
        )
    if args.baostock_missing_name_policy and not args.baostock_names_input:
        raise ValueError(
            "--baostock-missing-name-policy requires --baostock-names-input"
        )
    if args.baostock_allow_non_trading_empty:
        if args.baostock_non_trading_policy != "drop":
            raise ValueError(
                "--baostock-allow-non-trading-empty requires "
                "--baostock-non-trading-policy drop"
            )
        if not args.baostock_drop_invalid_rows:
            raise ValueError(
                "--baostock-allow-non-trading-empty requires "
                "--baostock-drop-invalid-rows"
            )
    baostock_names_input = (
        Path(args.baostock_names_input).resolve()
        if args.baostock_names_input
        else None
    )
    if baostock_names_input is not None and not baostock_names_input.is_file():
        raise FileNotFoundError(
            f"baostock names input not found: {baostock_names_input}"
        )
    return baostock_names_input


def provider_config_fields(
    args: argparse.Namespace,
    baostock_names_input: Path | None,
) -> dict[str, object]:
    return {
        "zzshare_non_trading_policy": args.zzshare_non_trading_policy,
        "zzshare_request_interval_seconds": args.zzshare_request_interval_seconds,
        "zzshare_max_concurrent_symbol_requests": args.zzshare_max_concurrent_symbol_requests,
        "zzshare_max_rate_limit_sleep_seconds": args.zzshare_max_rate_limit_sleep_seconds,
        "zzshare_max_429_events": args.zzshare_max_429_events,
        "zzshare_max_runtime_seconds": args.zzshare_max_runtime_seconds,
        "zzshare_progress_interval": args.zzshare_progress_interval,
        "baostock_names_input": baostock_names_input,
        "baostock_missing_name_policy": args.baostock_missing_name_policy,
        "baostock_non_trading_policy": args.baostock_non_trading_policy,
        "baostock_drop_invalid_rows": bool(args.baostock_drop_invalid_rows),
        "baostock_allow_non_trading_empty": bool(
            args.baostock_allow_non_trading_empty
        ),
    }


def validate_merge_arguments(args: argparse.Namespace) -> None:
    values = [
        args.base_prices,
        args.base_metadata,
        args.merged_output,
        args.merged_metadata_output,
        args.merge_report_output,
    ]
    if any(values) and not all(values):
        raise ValueError("all verified merge arguments must be provided together")


def merge_requested(args: argparse.Namespace) -> bool:
    return bool(args.base_prices)


def run_verified_merge(args: argparse.Namespace, config: dict[str, object]) -> None:
    command = [
        default_python(),
        str(default_scripts_dir() / "prepare_clean_history_pool.py"),
        "--prices-input",
        args.base_prices,
        "--history-metadata",
        args.base_metadata,
        "--incremental-plan",
        str(config["plan_path"]),
        "--incremental-prices",
        str(config["prices_output"]),
        "--incremental-metadata",
        str(config["metadata_output"]),
        "--output",
        args.merged_output,
        "--metadata-output",
        args.merged_metadata_output,
        "--report-output",
        args.merge_report_output,
    ]
    result = subprocess.run(command, cwd=Path.cwd(), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"verified incremental merge failed: {result.returncode}")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("value must be finite and non-negative")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("value must be finite and positive")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
