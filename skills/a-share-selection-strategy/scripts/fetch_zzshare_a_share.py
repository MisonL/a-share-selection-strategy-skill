#!/usr/bin/env python3
"""Fetch A-share OHLCV data through zzshare and save local gate files."""

from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime
from pathlib import Path

from lib.fetch.zzshare_a_share_data import (
    CLAIM_BOUNDARY,
    DEFAULT_FIELDS,
    DEFAULT_HTTP_URL,
    DEFAULT_LIMIT,
    DEFAULT_REQUEST_INTERVAL_SECONDS,
    collect_rows,
    fetch_prices,
    parse_symbols,
    ts_code,
    zzshare_date,
)
from lib.fetch.zzshare_a_share_quality import (
    apply_quality_policy,
    output_status,
    remove_output,
    strict_gate_errors,
    summary_prefix,
    write_metadata,
    write_outputs,
)
from lib.fetch.zzshare_rate_limit import (
    DEFAULT_MAX_429_EVENTS,
    DEFAULT_MAX_RATE_LIMIT_SLEEP_SECONDS,
    DEFAULT_MAX_RUNTIME_SECONDS,
)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output)
    metadata_output = Path(args.metadata_output)
    try:
        validate_arguments(args)
    except ValueError as exc:
        remove_output(output)
        remove_output(metadata_output)
        print(
            "ERROR: code=invalid_argument output_written=false "
            f"metadata_output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    try:
        frame, metadata = fetch_prices(args)
        frame, metadata = apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=args.drop_invalid_rows,
            non_trading_policy=args.non_trading_policy,
        )
        metadata = output_status(
            metadata, output_written=True, metadata_output_written=True
        )
        write_outputs(frame, metadata, output, metadata_output)
    except Exception as exc:  # noqa: BLE001
        remove_output(output)
        remove_output(metadata_output)
        print(
            "ERROR: code=fetch_failed output_written=false "
            f"metadata_output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    return finish(args, metadata, output, metadata_output)


def finish(
    args: argparse.Namespace,
    metadata: dict,
    output: Path,
    metadata_output: Path,
) -> int:
    strict_errors = strict_gate_errors(
        metadata, fail_on_fetch_error=args.fail_on_fetch_error
    )
    if strict_errors:
        metadata = output_status(
            metadata, output_written=False, metadata_output_written=True
        )
        remove_output(output)
        write_metadata(metadata, metadata_output)
        print_summary(metadata, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; "
            f"{'; '.join(strict_errors)} output_written=false metadata_output_written=true",
            file=sys.stderr,
        )
        return 3
    print_summary(metadata, prefix=summary_prefix(metadata))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=parser_description())
    add_required_options(parser)
    add_connection_options(parser)
    add_fetch_options(parser)
    add_gate_options(parser)
    return parser


def parser_description() -> str:
    return (
        "Fetch zzshare A-share daily data into local CSV and metadata. "
        "Most zzshare interfaces can be used without a token, but the optional "
        "ZZSHARE_TOKEN environment variable, request interval, pagination, empty "
        "symbols, and provider failures must be disclosed before candidate claims. "
        "Successful no-token fetches do not prove unlimited free quota or long-term "
        "stability."
    )


def add_required_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--symbols", help="Comma-separated six-digit symbols."
    )
    parser.add_argument(
        "--symbols-file",
        help="Text file containing comma-separated or newline-separated symbols.",
    )
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument(
        "--metadata-output", required=True, help="Output metadata JSON path."
    )


def add_connection_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--http-url",
        default=DEFAULT_HTTP_URL,
        help="zzshare API base URL. Default: https://api.zizizaizai.com.",
    )
    parser.add_argument(
        "--timeout-seconds",
        default=10.0,
        help="Per-request timeout passed to zzshare DataApi. Default: 10.",
    )
    parser.add_argument(
        "--request-interval-seconds",
        default=DEFAULT_REQUEST_INTERVAL_SECONDS,
        help="Sleep between per-symbol requests to respect free-tier rate limits. Default: 2.1.",
    )
    parser.add_argument(
        "--max-concurrent-symbol-requests",
        default=1,
        help=(
            "Maximum concurrent symbol fetches. Default: 1 preserves sequential "
            "behavior; larger values reduce wall time but increase upstream load."
        ),
    )
    parser.add_argument(
        "--max-rate-limit-sleep-seconds",
        default=DEFAULT_MAX_RATE_LIMIT_SLEEP_SECONDS,
        help="Maximum cumulative 429 sleep before a partial nonzero exit.",
    )
    parser.add_argument(
        "--max-429-events",
        default=DEFAULT_MAX_429_EVENTS,
        help="Maximum 429 responses before a partial nonzero exit.",
    )
    parser.add_argument(
        "--max-runtime-seconds",
        default=DEFAULT_MAX_RUNTIME_SECONDS,
        help="Maximum total fetch runtime before a partial nonzero exit.",
    )


def add_fetch_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fields",
        default=DEFAULT_FIELDS,
        help=(
            "zzshare daily fields. Default: all, which exposes volume, turnover, "
            "turnover_rate, is_paused, and is_st when supported."
        ),
    )
    parser.add_argument("--adjust", default="", help="Forwarded zzshare adj value.")
    parser.add_argument(
        "--limit",
        default=DEFAULT_LIMIT,
        help="Per-page limit for zzshare daily. Default: 1000.",
    )
    parser.add_argument(
        "--max-pages",
        default=10,
        help="Maximum pages per symbol before reporting possible truncation. Default: 10.",
    )


def add_gate_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fail-on-fetch-error",
        action="store_true",
        help=(
            "Also fail on failed_symbols, empty_symbols, possibly_truncated_symbols, "
            "or missing symbols. "
            "Invalid or tradestatus-missing rows are always strict gates. "
            "Non-trading rows follow --non-trading-policy."
        ),
    )
    parser.add_argument(
        "--drop-invalid-rows",
        action="store_true",
        help="Explicitly drop invalid zzshare OHLCV, amount, or turn rows.",
    )
    parser.add_argument(
        "--non-trading-policy",
        choices=["fail", "drop", "keep"],
        default="fail",
        help=(
            "How to handle rows whose tradestatus is not 1. "
            "fail preserves the legacy strict gate, drop filters them with metadata, "
            "and keep retains them with an audit warning."
        ),
    )
    parser.add_argument(
        "--checkpoint-dir",
        help=(
            "Optional directory for zzshare batch checkpoints. Checkpoints are "
            "raw/audit artifacts and do not prove selection readiness."
        ),
    )
    parser.add_argument(
        "--checkpoint-batch-size",
        default=0,
        help="Symbols per checkpoint part. Use 0 to disable checkpointing.",
    )
    parser.add_argument(
        "--resume-from-checkpoint",
        action="store_true",
        help="Reuse completed symbols from --checkpoint-dir and retry the rest.",
    )
    parser.add_argument(
        "--progress-interval",
        default=0,
        help="Emit a PROGRESS line every N processed symbols. Use 0 to disable.",
    )


def positive_int(value: object, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer: {value}") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be positive")
    return parsed


def non_negative_float(value: object, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number: {value}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def validate_arguments(args: argparse.Namespace) -> None:
    validate_date_arguments(args)
    validate_numeric_arguments(args)
    normalize_symbol_arguments(args)
    parse_symbols(args.symbols)


def normalize_symbol_arguments(args: argparse.Namespace) -> None:
    if args.symbols and args.symbols_file:
        raise ValueError("use either --symbols or --symbols-file, not both")
    if args.symbols_file:
        args.symbols = read_symbols_file(Path(args.symbols_file))
    if not str(args.symbols or "").strip():
        raise ValueError("provide --symbols or --symbols-file")


def read_symbols_file(path: Path) -> str:
    if not path.exists():
        raise ValueError(f"symbols file not found: {path}")
    if path.is_dir():
        raise ValueError(f"symbols file is a directory: {path}")
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"symbols file is not valid UTF-8 or UTF-8-BOM: {path}"
        ) from exc
    text = ",".join(part.strip() for part in raw_text.replace("\r", "\n").splitlines())
    text = ",".join(part.strip() for part in text.split(",") if part.strip())
    if not text:
        raise ValueError(f"symbols file is empty or contains no symbols: {path}")
    return text


def validate_numeric_arguments(args: argparse.Namespace) -> None:
    args.timeout_seconds = non_negative_float(args.timeout_seconds, "timeout-seconds")
    if args.timeout_seconds <= 0:
        raise ValueError("timeout-seconds must be positive")
    args.request_interval_seconds = non_negative_float(
        args.request_interval_seconds,
        "request-interval-seconds",
    )
    args.max_concurrent_symbol_requests = positive_int(
        args.max_concurrent_symbol_requests,
        "max-concurrent-symbol-requests",
    )
    args.max_rate_limit_sleep_seconds = non_negative_float(
        args.max_rate_limit_sleep_seconds,
        "max-rate-limit-sleep-seconds",
    )
    args.max_429_events = positive_int(args.max_429_events, "max-429-events")
    args.max_runtime_seconds = non_negative_float(
        args.max_runtime_seconds,
        "max-runtime-seconds",
    )
    if args.max_runtime_seconds <= 0:
        raise ValueError("max-runtime-seconds must be positive")
    args.limit = positive_int(args.limit, "limit")
    args.max_pages = positive_int(args.max_pages, "max-pages")
    args.checkpoint_batch_size = non_negative_int(
        args.checkpoint_batch_size,
        "checkpoint-batch-size",
    )
    args.progress_interval = non_negative_int(
        args.progress_interval,
        "progress-interval",
    )
    if args.resume_from_checkpoint and not str(args.checkpoint_dir or "").strip():
        raise ValueError("resume-from-checkpoint requires checkpoint-dir")
    if str(args.checkpoint_dir or "").strip() and args.checkpoint_batch_size < 1:
        raise ValueError("checkpoint-batch-size must be positive when checkpoint-dir is set")


def non_negative_int(value: object, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer: {value}") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def validate_date_arguments(args: argparse.Namespace) -> None:
    start = calendar_date(args.start_date)
    end = calendar_date(args.end_date)
    if start > end:
        raise ValueError("start-date must be earlier than or equal to end-date")


def calendar_date(text: str) -> datetime:
    compact = zzshare_date(text)
    try:
        return datetime.strptime(compact, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"date must be a real calendar date: {text}") from exc


def print_summary(metadata: dict, prefix: str = "OK") -> None:
    unprocessed = metadata.get("unprocessed_symbols", [])
    if not isinstance(unprocessed, list):
        unprocessed = []
    unprocessed_examples = ",".join(str(symbol) for symbol in unprocessed[:10]) or "none"
    print(
        f"{prefix}: source=zzshare rows={metadata['rows']} "
        f"symbol_count={metadata['symbol_count']} "
        f"failed_symbols={len(metadata['failed_symbols'])} "
        f"empty_symbols={len(metadata['empty_symbols'])} "
        f"source_scope={metadata.get('source_scope', 'zzshare_history_fetch')} "
        f"invalid_rows={metadata['invalid_rows']} "
        f"dropped_invalid_rows={metadata['dropped_invalid_rows']} "
        f"possibly_truncated_symbols={len(metadata.get('possibly_truncated_symbols', []))} "
        f"non_trading_rows={metadata.get('non_trading_rows', 0)} "
        f"non_trading_policy={metadata.get('non_trading_policy', 'fail')} "
        f"dropped_non_trading_rows={metadata.get('dropped_non_trading_rows', 0)} "
        f"checkpoint_enabled={str(metadata.get('checkpoint_enabled', False)).lower()} "
        f"checkpoint_symbols_skipped={metadata.get('checkpoint_symbols_skipped', 0)} "
        f"checkpoint_integrity_issues={metadata.get('checkpoint_integrity_issue_count', 0)} "
        f"tradestatus_missing_rows={metadata.get('tradestatus_missing_rows', 0)} "
        f"fields={metadata['fields']} "
        f"limit={metadata['limit']} "
        f"max_pages={metadata['max_pages']} "
        f"request_interval_seconds={metadata['request_interval_seconds']} "
        f"max_concurrent_symbol_requests={metadata.get('max_concurrent_symbol_requests', 1)} "
        f"rate_limit_429_events={metadata.get('rate_limit_429_events', 0)} "
        f"rate_limit_sleep_seconds={metadata.get('rate_limit_sleep_seconds', 0)} "
        f"rate_limit_budget_exhausted={str(metadata.get('rate_limit_budget_exhausted', False)).lower()} "
        f"unprocessed_symbols={len(unprocessed)} "
        f"unprocessed_symbol_examples={unprocessed_examples} "
        f"token_configured={str(metadata['token_configured']).lower()} "
        f"source_claim_boundary={metadata.get('source_claim_boundary', CLAIM_BOUNDARY)}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
