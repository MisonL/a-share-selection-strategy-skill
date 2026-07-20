"""Pure shared run-state predicates for runner and HTML report consumers."""

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


from typing import Any


QUALITY_COUNT_KEYS = (
    "invalid_rows",
    "dropped_invalid_rows",
    "non_trading_rows",
    "tradestatus_missing_rows",
)


def list_value(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key, [])
    return value if isinstance(value, list) else []


def integer_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def quality_count_present(data: dict[str, Any]) -> bool:
    return any((integer_value(data.get(key)) or 0) > 0 for key in QUALITY_COUNT_KEYS)


def requested_symbol_count(data: dict[str, Any]) -> int | None:
    explicit_count = integer_value(data.get("input_requested_symbol_count"))
    if explicit_count is not None:
        return explicit_count
    requested = list_value(data, "requested_symbols")
    return len(requested) if requested else None


def history_partial_result(data: dict[str, Any]) -> bool:
    if data.get("partial_result") is True:
        return True
    if data.get("output_written") is False:
        return True
    if list_value(data, "failed_symbols"):
        return True
    if list_value(data, "empty_symbols"):
        return True
    if list_value(data, "possibly_truncated_symbols"):
        return True
    if list_value(data, "unprocessed_symbols"):
        return True
    if data.get("rate_limit_budget_exhausted") is True:
        return True
    if quality_count_present(data):
        return True
    if list_value(data, "fallback_errors"):
        return True
    requested = list_value(data, "requested_symbols")
    if requested and data.get("symbol_count") is not None:
        return int(data["symbol_count"]) != len(requested)
    return False


def history_selection_partial_result(selection: dict[str, Any]) -> bool:
    if selection.get("history_partial_result") is True:
        return True
    if selection.get("history_output_written") is False:
        return True
    count_keys = (
        "history_metadata_failed_symbol_count",
        "history_empty_symbol_count",
        "history_possibly_truncated_symbol_count",
        "history_unprocessed_symbol_count",
        "history_invalid_rows",
        "history_dropped_invalid_rows",
        "history_non_trading_rows",
        "history_tradestatus_missing_rows",
        "history_metadata_fallback_error_count",
    )
    return bool(
        selection.get("history_rate_limit_budget_exhausted") is True
        or any((integer_value(selection.get(key)) or 0) > 0 for key in count_keys)
    )


def local_input_partial_result(data: dict[str, Any]) -> bool:
    if data.get("partial_result") is True:
        return True
    if data.get("input_partial_result") is True:
        return True
    if data.get("output_written") is False:
        return True
    if list_value(data, "failed_symbols"):
        return True
    if list_value(data, "empty_symbols"):
        return True
    if list_value(data, "possibly_truncated_symbols"):
        return True
    if list_value(data, "unprocessed_symbols"):
        return True
    if data.get("rate_limit_budget_exhausted") is True:
        return True
    if quality_count_present(data):
        return True
    requested = requested_symbol_count(data)
    symbol_count = integer_value(data.get("symbol_count"))
    if requested is not None and symbol_count is not None:
        return symbol_count != requested
    return False


def is_synthetic_demo(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("source_type", "")) == "synthetic_demo"


def step_executed(step: dict[str, Any]) -> bool:
    return step.get("executed", True) is not False
