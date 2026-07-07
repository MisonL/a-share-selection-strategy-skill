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


def fetch_spot_command(args: Any, spot: Path | None) -> list[str]:
    if args.fetch_spot != "eastmoney" or spot is None:
        raise ValueError("unsupported spot fetch configuration")
    command = [
        sys.executable,
        str(SCRIPTS / "fetch_eastmoney_a_share_spot.py"),
        "--output",
        str(spot),
        "--metadata-output",
        str(Path(args.output_dir) / "spot_metadata.json"),
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
    sources = {"akshare", "akshare_hk_daily", "baostock", "zzshare", "yfinance"}
    if args.history_source not in sources:
        raise ValueError(
            "history-source must be akshare, akshare_hk_daily, baostock, "
            "zzshare, or yfinance when prices-input is omitted"
        )
    if args.history_source == "yfinance":
        return fetch_yfinance_history_command(args, prices, symbols)
    if args.history_source == "akshare_hk_daily":
        return fetch_akshare_hk_daily_command(args, prices, symbols)
    command = [
        sys.executable,
        str(SCRIPTS / f"fetch_{args.history_source}_a_share.py"),
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
    if args.history_source == "zzshare":
        if args.history_adjust is not None:
            command.extend(["--adjust", str(args.history_adjust)])
        command.extend(["--fields", "all"])
        append_optional_arg(command, "--http-url", args.history_http_url)
        append_optional_arg(command, "--timeout-seconds", args.history_timeout_seconds)
        append_optional_arg(
            command,
            "--request-interval-seconds",
            args.history_request_interval_seconds,
        )
        append_optional_arg(command, "--limit", args.history_limit)
        append_optional_arg(command, "--max-pages", args.history_max_pages)
    elif args.history_adjust is not None:
        command.extend(["--adjust", str(args.history_adjust)])
    if not args.allow_partial_history:
        command.append("--fail-on-fetch-error")
    if args.drop_invalid_history_rows:
        command.append("--drop-invalid-rows")
    return command


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
        "spot_input": str(Path(args.spot_input)) if args.spot_input else "",
        "fetch_spot": args.fetch_spot or "",
        "spot_pages": int(args.spot_pages),
        "history_source": args.history_source or "",
        "symbols": args.symbols or "",
        "symbols_file": str(Path(args.symbols_file))
        if getattr(args, "symbols_file", None)
        else "",
        "derive_symbols_from_spot": bool(args.derive_symbols_from_spot),
        "max_history_symbols": int(args.max_history_symbols),
        "max_history_symbols_supplied": bool(
            getattr(args, "max_history_symbols_supplied", False)
        ),
        "history_adjust": args.history_adjust or "",
        "history_http_url": sanitize_text(args.history_http_url or ""),
        "history_timeout_seconds": manifest_optional(args.history_timeout_seconds),
        "history_request_interval_seconds": manifest_optional(
            args.history_request_interval_seconds,
        ),
        "history_limit": manifest_optional(args.history_limit),
        "history_max_pages": manifest_optional(args.history_max_pages),
        "start_date": args.start_date or "",
        "end_date": args.end_date or "",
        "allow_partial_history": bool(args.allow_partial_history),
        "drop_invalid_history_rows": bool(args.drop_invalid_history_rows),
        "min_history_rows": args.min_history_rows,
        "fail_on_empty_result": bool(args.fail_on_empty_result),
        "fail_on_skipped": bool(args.fail_on_skipped),
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
