"""Preflight validation helpers for today's A-share runner."""

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


import math
from typing import Any


def normalize_zzshare_history_options(args: Any) -> None:
    if args.history_source == "zzshare":
        if not args.history_non_trading_policy:
            args.history_non_trading_policy = "drop"
        if args.history_max_concurrent_symbol_requests in (None, ""):
            args.history_max_concurrent_symbol_requests = "1"
        if args.history_checkpoint_batch_size in (None, ""):
            args.history_checkpoint_batch_size = "100"
        if args.history_progress_interval in (None, ""):
            args.history_progress_interval = "100"
    args.history_timeout_seconds = positive_float_or_none(
        args.history_timeout_seconds,
        "history-timeout-seconds",
    )
    args.history_request_interval_seconds = non_negative_float_or_none(
        args.history_request_interval_seconds,
        "history-request-interval-seconds",
    )
    args.history_limit = positive_int_or_none(args.history_limit, "history-limit")
    args.history_max_pages = positive_int_or_none(
        args.history_max_pages,
        "history-max-pages",
    )
    if args.history_source == "zzshare":
        args.history_max_concurrent_symbol_requests = positive_int_or_none(
            args.history_max_concurrent_symbol_requests,
            "history-max-concurrent-symbol-requests",
        )
        args.history_max_rate_limit_sleep_seconds = non_negative_float_or_none(
            args.history_max_rate_limit_sleep_seconds,
            "history-max-rate-limit-sleep-seconds",
        )
        args.history_max_429_events = positive_int_or_none(
            args.history_max_429_events,
            "history-max-429-events",
        )
        args.history_max_runtime_seconds = positive_float_or_none(
            args.history_max_runtime_seconds,
            "history-max-runtime-seconds",
        )
        args.history_checkpoint_batch_size = non_negative_int_or_none(
            args.history_checkpoint_batch_size,
            "history-checkpoint-batch-size",
        )
        args.history_progress_interval = non_negative_int_or_none(
            args.history_progress_interval,
            "history-progress-interval",
        )


def sync_validated_history_options(
    manifest: dict[str, Any],
    args: Any,
) -> None:
    for name in [
        "history_timeout_seconds",
        "history_request_interval_seconds",
        "history_max_concurrent_symbol_requests",
        "history_max_rate_limit_sleep_seconds",
        "history_max_429_events",
        "history_max_runtime_seconds",
        "history_limit",
        "history_max_pages",
        "history_checkpoint_batch_size",
        "history_progress_interval",
    ]:
        value = getattr(args, name)
        manifest[name] = "" if value is None else value
    manifest["history_non_trading_policy"] = args.history_non_trading_policy
    manifest["history_resume_from_checkpoint"] = bool(
        args.history_resume_from_checkpoint
    )


def positive_int_or_none(value: object, name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(str(value))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be positive")
    return parsed


def non_negative_int_or_none(value: object, name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(str(value))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def positive_float_or_none(value: object, name: str) -> float | None:
    parsed = float_or_none(value, name)
    if parsed is not None and parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def non_negative_float_or_none(value: object, name: str) -> float | None:
    parsed = float_or_none(value, name)
    if parsed is not None and parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def float_or_none(value: object, name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(str(value))
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    return parsed
