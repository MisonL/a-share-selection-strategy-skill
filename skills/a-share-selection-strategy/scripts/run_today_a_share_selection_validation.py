"""Preflight validation helpers for today's A-share runner."""

from __future__ import annotations

import math
from typing import Any


def normalize_zzshare_history_options(args: Any) -> None:
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


def sync_validated_history_options(
    manifest: dict[str, Any],
    args: Any,
) -> None:
    for name in [
        "history_timeout_seconds",
        "history_request_interval_seconds",
        "history_limit",
        "history_max_pages",
    ]:
        value = getattr(args, name)
        manifest[name] = "" if value is None else value


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


if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
