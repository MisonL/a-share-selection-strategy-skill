"""Command builders for the local A-share selection runner."""

from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _SCRIPT_PATH = Path(__file__).resolve()
    _SCRIPTS_DIR = next(
        parent for parent in _SCRIPT_PATH.parents if parent.name == "scripts"
    )
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from lib.a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)


from pathlib import Path
import sys
from typing import Any

from lib.a_share_selection_config import load_config
from lib.a_share_selection_paths import SCRIPTS_DIR, resolve_config_path
from lib.selection_core.a_share_selection_command_safety import sanitize_text


SCRIPTS = SCRIPTS_DIR


def validate_command(args: Any, prices: Path) -> list[str]:
    return [
        sys.executable,
        str(SCRIPTS / "validate_ohlcv.py"),
        "--input",
        str(prices),
        "--min-history-rows",
        str(args.min_history_rows),
        "--config",
        str(run_config_path(args)),
    ]


def score_command(
    args: Any,
    prices: Path,
    candidates: Path,
    diagnostics: Path,
    spot: Path | None,
    profile: Path | None = None,
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
    if profile is not None:
        command.extend(["--profile-output", str(profile)])
    if spot is not None:
        command.extend(["--spot-input", str(spot)])
    if args.fail_on_empty_result:
        command.append("--fail-on-empty-result")
    if args.fail_on_skipped:
        command.append("--fail-on-skipped")
    return command


def fetch_spot_command(args: Any, spot: Path | None) -> list[str]:
    return fetch_spot_source_command(args, spot, args.fetch_spot)


def fetch_spot_fallback_command(args: Any, spot: Path | None) -> list[str]:
    return fetch_spot_source_command(args, spot, args.fetch_spot_fallback)


def fetch_spot_source_command(args: Any, spot: Path | None, source: str) -> list[str]:
    if spot is None:
        raise ValueError("unsupported spot fetch configuration")
    metadata = Path(args.output_dir) / "spot_metadata.json"
    if source == "baostock_universe":
        command = [
            sys.executable,
            str(SCRIPTS / "fetch_baostock_a_share_universe.py"),
            "--output",
            str(spot),
            "--metadata-output",
            str(metadata),
            "--lookback-days",
            str(args.spot_fallback_lookback_days),
            "--retries",
            str(args.spot_fallback_retries),
            "--retry-interval-seconds",
            str(args.spot_fallback_retry_interval_seconds),
        ]
        if args.fail_on_partial_spot:
            command.append("--fail-on-partial")
        return command
    if source != "eastmoney":
        raise ValueError("unsupported spot fetch configuration")
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


def fetch_history_command(
    args: Any,
    prices: Path,
    symbols: list[str],
) -> list[str]:
    sources = {
        "akshare",
        "akshare_hk_daily",
        "baostock",
        "pytdx",
        "zzshare",
        "yfinance",
    }
    if args.history_source not in sources:
        raise ValueError(
            "history-source must be akshare, akshare_hk_daily, baostock, "
            "pytdx, zzshare, or yfinance when prices-input is omitted"
        )
    if args.history_source == "yfinance":
        return fetch_yfinance_history_command(args, prices, symbols)
    if args.history_source == "akshare_hk_daily":
        return fetch_akshare_hk_daily_command(args, prices, symbols)
    symbol_args = history_symbol_command_args(args, symbols)
    command = [
        sys.executable,
        str(SCRIPTS / f"fetch_{args.history_source}_a_share.py"),
        *symbol_args,
        "--start-date",
        str(args.start_date),
        "--end-date",
        str(args.end_date),
        "--output",
        str(prices),
        "--metadata-output",
        str(Path(args.output_dir) / "history_metadata.json"),
    ]
    append_history_source_options(command, args)
    if not args.allow_partial_history:
        command.append("--fail-on-fetch-error")
    if args.drop_invalid_history_rows:
        command.append("--drop-invalid-rows")
    return command


def append_history_source_options(command: list[str], args: Any) -> None:
    if args.history_source == "zzshare":
        append_zzshare_history_options(command, args)
    elif args.history_source == "pytdx":
        append_optional_arg(command, "--timeout-seconds", args.history_timeout_seconds)
    elif args.history_source == "baostock":
        append_baostock_history_options(command, args)
    elif args.history_adjust is not None:
        command.extend(["--adjust", str(args.history_adjust)])


def append_zzshare_history_options(command: list[str], args: Any) -> None:
    if args.history_adjust is not None:
        command.extend(["--adjust", str(args.history_adjust)])
    command.extend(["--fields", "all"])
    option_values = (
        ("--http-url", args.history_http_url),
        ("--timeout-seconds", args.history_timeout_seconds),
        ("--request-interval-seconds", args.history_request_interval_seconds),
        (
            "--max-concurrent-symbol-requests",
            args.history_max_concurrent_symbol_requests,
        ),
        (
            "--max-rate-limit-sleep-seconds",
            args.history_max_rate_limit_sleep_seconds,
        ),
        ("--max-429-events", args.history_max_429_events),
        ("--max-runtime-seconds", args.history_max_runtime_seconds),
        ("--limit", args.history_limit),
        ("--max-pages", args.history_max_pages),
    )
    for flag, value in option_values:
        append_optional_arg(command, flag, value)
    command.extend(["--non-trading-policy", args.history_non_trading_policy])
    append_zzshare_checkpoint_options(command, args)


def append_zzshare_checkpoint_options(command: list[str], args: Any) -> None:
    if args.history_checkpoint_batch_size:
        command.extend(
            [
                "--checkpoint-dir",
                str(Path(args.output_dir) / "history_checkpoints"),
                "--checkpoint-batch-size",
                str(args.history_checkpoint_batch_size),
            ]
        )
    if args.history_resume_from_checkpoint:
        command.append("--resume-from-checkpoint")
    if args.history_progress_interval:
        command.extend(["--progress-interval", str(args.history_progress_interval)])


def append_baostock_history_options(command: list[str], args: Any) -> None:
    names_input = str(args.history_names_input or "")
    universe_sources = {args.fetch_spot, args.fetch_spot_fallback}
    if not names_input and "baostock_universe" in universe_sources:
        names_input = str(Path(args.output_dir) / "spot.csv")
    append_optional_arg(command, "--names-input", names_input)
    command.extend(
        [
            "--missing-name-policy",
            args.history_missing_name_policy,
            "--non-trading-policy",
            args.history_baostock_non_trading_policy,
        ]
    )
    if args.history_adjust is not None:
        command.extend(["--adjust", str(args.history_adjust)])


def history_symbol_command_args(args: Any, symbols: list[str]) -> list[str]:
    if args.history_source not in {"baostock", "zzshare"}:
        return ["--symbols", ",".join(symbols)]
    if planned_symbol_placeholder(symbols):
        return ["--symbols", ",".join(symbols)]
    symbols_file = getattr(args, "history_symbols_file", "") or getattr(
        args, "symbols_file", ""
    )
    if symbols_file:
        return ["--symbols-file", str(Path(symbols_file))]
    return ["--symbols", ",".join(symbols)]


def planned_symbol_placeholder(symbols: list[str]) -> bool:
    return any(str(symbol).startswith("<") and str(symbol).endswith(">") for symbol in symbols)


def fetch_akshare_hk_daily_command(
    args: Any,
    prices: Path,
    symbols: list[str],
) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPTS / "fetch_akshare_hk_daily.py"),
        "--symbols",
        ",".join(symbols),
        "--start-date",
        str(args.start_date),
        "--end-date",
        str(args.end_date),
        "--output",
        str(prices),
        "--metadata-output",
        str(Path(args.output_dir) / "history_metadata.json"),
    ]
    if args.history_adjust is not None:
        command.extend(["--adjust", str(args.history_adjust)])
    if not args.allow_partial_history:
        command.append("--fail-on-fetch-error")
    if args.drop_invalid_history_rows:
        command.append("--drop-invalid-rows")
    return command


def fetch_yfinance_history_command(
    args: Any,
    prices: Path,
    symbols: list[str],
) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPTS / "fetch_yfinance_ohlcv.py"),
        "--symbols",
        ",".join(symbols),
        "--start-date",
        str(args.start_date),
        "--end-date",
        str(args.end_date),
        "--output",
        str(prices),
        "--metadata-output",
        str(Path(args.output_dir) / "history_metadata.json"),
        "--market",
        history_market(args),
    ]
    append_optional_arg(command, "--timeout-seconds", args.history_timeout_seconds)
    if not args.allow_partial_history:
        command.append("--fail-on-fetch-error")
    return command


def history_market(args: Any) -> str:
    config = load_config(selected_config(args))
    market = str(config.get("universe", {}).get("market", "")).strip()
    return market or "US"


def append_optional_arg(command: list[str], flag: str, value: Any) -> None:
    if value is None or value == "":
        return
    command.extend([flag, str(value)])


def run_config_path(args: Any) -> Path:
    return Path(args.output_dir) / selected_config(args).name


def initial_manifest(args: Any) -> dict[str, Any]:
    return {
        **manifest_identity_fields(args),
        **manifest_spot_fields(args),
        **manifest_filter_fields(args),
        **manifest_history_fields(args),
        **manifest_output_fields(args),
    }


def manifest_identity_fields(args: Any) -> dict[str, Any]:
    return {
        "runner": "run_today_a_share_selection",
        "requested_mode": args.mode,
        "mode": "unresolved" if args.mode == "auto" else args.mode,
        "mode_decision": "unresolved",
        "mode_decision_reason": "",
        "prices_input": str(Path(args.prices_input)) if args.prices_input else "",
        "output_dir": str(Path(args.output_dir)),
        "execution_mode": "plan_only"
        if getattr(args, "plan_only", False)
        else "execute",
        "commands_executed": False,
        "plan_only": bool(getattr(args, "plan_only", False)),
        "resume_from": str(Path(args.resume_from))
        if getattr(args, "resume_from", None)
        else "",
        "resume_symbol_source": getattr(args, "resume_symbol_source", ""),
        "resume_retry_symbol_count": int(getattr(args, "resume_retry_symbol_count", 0)),
        "resume_inherited_options": list(getattr(args, "resume_inherited_options", [])),
        "resume_sensitive_options_requiring_explicit_input": list(
            getattr(args, "resume_sensitive_options_requiring_explicit_input", [])
        ),
        "resume_prior_output_dir": getattr(args, "resume_prior_output_dir", ""),
        "config_path": "",
    }


def manifest_spot_fields(args: Any) -> dict[str, Any]:
    return {
        "spot_input": str(Path(args.spot_input)) if args.spot_input else "",
        "fetch_spot": args.fetch_spot or "",
        "fetch_spot_fallback": args.fetch_spot_fallback or "",
        "spot_fallback_lookback_days": int(args.spot_fallback_lookback_days),
        "spot_fallback_retries": int(args.spot_fallback_retries),
        "spot_fallback_retry_interval_seconds": float(
            args.spot_fallback_retry_interval_seconds
        ),
        "spot_metadata_origin": "",
        "spot_input_metadata_source": "",
        "spot_input_metadata_output": "",
        "spot_input_metadata_output_exists": False,
        "spot_input_metadata_output_written": False,
        "spot_input_metadata_sha256": "",
        "spot_input_metadata_size_bytes": 0,
        "spot_input_metadata_claim_boundary": "",
        "fetch_spot_fallback_used": False,
        "fetch_spot_primary_failure": {},
        "spot_pages": int(args.spot_pages),
        "fail_on_partial_spot": bool(args.fail_on_partial_spot),
        "history_source": args.history_source or "",
        "symbols": args.symbols or "",
        "symbols_file": str(Path(args.symbols_file))
        if getattr(args, "symbols_file", None)
        else "",
        "derive_symbols_from_spot": bool(args.derive_symbols_from_spot),
        "derive_all_spot_symbols": bool(args.derive_all_spot_symbols),
    }


def manifest_filter_fields(args: Any) -> dict[str, Any]:
    return {
        **full_a_manifest_fields(args),
        "filter_prices_to_spot_universe": bool(args.filter_prices_to_spot_universe),
        "prices_filter_output_format": args.prices_filter_output_format,
        "prices_filter_output_prices": "",
        "prices_filter_sidecar_output": "",
        "prices_filter_sidecar_sha256": "",
        "prices_filter_spot_universe": False,
        "prices_filter_min_symbol_latest_date": args.min_symbol_latest_date or "",
        "prices_filter_metadata_output": "",
        "prices_filter_source_prices": "",
        "prices_filter_source_spot": "",
        "prices_filter_input_rows": 0,
        "prices_filter_output_rows": 0,
        "prices_filter_spot_symbol_count": 0,
        "prices_filter_spot_symbol_set_sha256": "",
        "prices_filter_input_symbol_count": 0,
        "prices_filter_input_symbol_set_sha256": "",
        "prices_filter_kept_symbol_count": 0,
        "prices_filter_kept_symbol_set_sha256": "",
        "prices_filter_removed_symbol_count": 0,
        "prices_filter_removed_symbols": [],
        "prices_filter_removed_symbol_set_sha256": "",
        "prices_filter_removed_stale_symbol_count": 0,
        "prices_filter_removed_stale_symbols": [],
        "prices_filter_output_written": False,
        "prices_filter_failure_reason": "",
        "prices_filter_error": "",
        "prices_filter_claim_boundary": "",
        "score_profile_output": (
            str(Path(args.output_dir) / "score_profile.json")
            if bool(getattr(args, "score_profile", False))
            else ""
        ),
        "score_profile_enabled": bool(getattr(args, "score_profile", False)),
        "score_profile_output_written": False,
        "score_profile_rows": 0,
    }


def full_a_manifest_fields(args: Any) -> dict[str, Any]:
    if not args.full_a_provenance:
        return {}
    return {
        "full_a_provenance_requested": True,
        "full_a_provenance_input": str(Path(args.full_a_provenance)),
        "full_a_provenance_file_sha256": "",
        "full_a_provenance_validation_status": "pending",
        "full_a_provenance_validation_error": "",
        "full_a_provenance_closure_eligible": False,
        "full_a_provenance_boundary": "",
        "full_a_provenance_as_of_date": "",
        "full_a_provenance_universe_symbol_count": 0,
        "full_a_provenance_clean_symbol_count": 0,
        "full_a_provenance_clean_pool_removed_symbol_count": 0,
        "full_a_provenance_final_prices_symbol_count": 0,
        "full_a_provenance_final_prices_symbol_set_sha256": "",
        "full_a_provenance_final_filter_removed_symbol_count": 0,
        "full_a_provenance_final_filter_removed_symbols": [],
        "full_a_provenance_final_scoring_validated": False,
        "full_a_provenance_candidate_symbol_count": 0,
        "full_a_provenance_diagnostic_symbol_count": 0,
        "full_a_provenance_output_cleanup_errors": [],
    }


def manifest_history_fields(args: Any) -> dict[str, Any]:
    return {
        "history_symbols_file": "",
        "history_symbols_file_origin": "not_applicable",
        "history_symbols_file_exists": False,
        "history_symbols_file_output_written": False,
        "history_symbols_file_symbol_count": 0,
        "history_symbols_file_sha256": "",
        "history_symbols_file_size_bytes": 0,
        "max_history_symbols": int(args.max_history_symbols),
        "max_history_symbols_supplied": bool(
            getattr(args, "max_history_symbols_supplied", False)
        ),
        "history_adjust": args.history_adjust or "",
        "history_output_format": args.history_output_format
        or ("csv" if not args.prices_input else ""),
        "history_http_url": sanitize_text(args.history_http_url or ""),
        "history_timeout_seconds": manifest_optional(args.history_timeout_seconds),
        "history_request_interval_seconds": manifest_optional(
            args.history_request_interval_seconds,
        ),
        "history_max_concurrent_symbol_requests": manifest_optional(
            args.history_max_concurrent_symbol_requests,
        ),
        "history_max_rate_limit_sleep_seconds": manifest_optional(
            args.history_max_rate_limit_sleep_seconds,
        ),
        "history_max_429_events": manifest_optional(args.history_max_429_events),
        "history_max_runtime_seconds": manifest_optional(
            args.history_max_runtime_seconds,
        ),
        "history_limit": manifest_optional(args.history_limit),
        "history_max_pages": manifest_optional(args.history_max_pages),
        "history_non_trading_policy": args.history_non_trading_policy,
        "history_checkpoint_batch_size": manifest_optional(
            args.history_checkpoint_batch_size
        ),
        "history_checkpoint_dir": (
            str(Path(args.output_dir) / "history_checkpoints")
            if args.history_checkpoint_batch_size
            else ""
        ),
        "history_resume_from_checkpoint": bool(args.history_resume_from_checkpoint),
        "history_progress_interval": manifest_optional(args.history_progress_interval),
        "start_date": args.start_date or "",
        "end_date": args.end_date or "",
        "allow_partial_history": bool(args.allow_partial_history),
        "drop_invalid_history_rows": bool(args.drop_invalid_history_rows),
    }


def manifest_output_fields(args: Any) -> dict[str, Any]:
    return {
        "min_history_rows": args.min_history_rows,
        "fail_on_empty_result": bool(args.fail_on_empty_result),
        "fail_on_skipped": bool(args.fail_on_skipped),
        "no_html_report": bool(args.no_html_report),
        "html_report_enabled": not bool(args.no_html_report),
        "html_report_language": args.html_report_language,
        "html_report_initial_language": "",
        "run_outputs_initialized": False,
        "input_metadata": {},
        "prediction_mode": args.mode == "prediction",
        "consumes_prediction_columns": False,
        "prediction_input_source": "not_used",
        "requested_prediction_input_source": (
            "external_input" if args.mode == "prediction" else "not_used"
        ),
        "prediction_model_executed_by_runner": False,
        "lightgbm_not_used": args.mode != "prediction",
        "lightgbm_output_source": "not_used",
        "requested_lightgbm_output_source": (
            "external_input" if args.mode == "prediction" else "not_used"
        ),
        "lightgbm_executed_by_runner": False,
        "source_scope": "unresolved",
        "history_symbols": [],
        "steps": [],
    }


def selected_config(args: Any) -> Path:
    if args.config:
        return resolve_config_path(Path(args.config))
    mode = getattr(args, "resolved_mode", args.mode)
    return (
        args.default_prediction_config
        if mode == "prediction"
        else args.default_generic_config
    )


def manifest_optional(value: Any) -> Any:
    return "" if value is None else value
