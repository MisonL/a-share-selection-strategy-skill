"""Input metadata loading for today's A-share runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


METADATA_KEYS = (
    "source_type",
    "source",
    "source_scope",
    "scenario",
    "days",
    "prices",
    "market",
    "market_label_only",
    "source_claim_boundary",
    "data_source_note",
    "adjustment",
    "adjust",
    "adjustflag",
    "fields",
    "token_configured",
    "request_interval_seconds",
    "limit",
    "max_pages",
    "timeout_seconds",
    "requested_symbols",
    "symbol_count",
    "rows",
    "failed_symbols",
    "empty_symbols",
    "possibly_truncated_symbols",
    "invalid_rows",
    "invalid_symbols",
    "invalid_row_examples",
    "dropped_invalid_rows",
    "non_trading_rows",
    "non_trading_symbols",
    "non_trading_row_examples",
    "tradestatus_missing_rows",
    "output_written",
    "metadata_output_written",
    "synthetic_prediction_input",
    "synthetic_prediction_proves_real_model",
    "real_market_data",
)

QUALITY_COUNT_KEYS = (
    "invalid_rows",
    "dropped_invalid_rows",
    "non_trading_rows",
    "tradestatus_missing_rows",
)


def input_metadata_for_prices(prices_input: str | None) -> dict[str, Any]:
    if not prices_input:
        return {}
    metadata_path = Path(prices_input).parent / "metadata.json"
    if not metadata_path.is_file():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"input metadata must be a JSON object: {metadata_path}")
    metadata = {key: data[key] for key in METADATA_KEYS if key in data}
    if local_input_partial_result(data):
        metadata["input_partial_result"] = True
    if "failed_symbols" in data:
        metadata["input_failed_symbol_count"] = len(list_value(data, "failed_symbols"))
    if "empty_symbols" in data:
        metadata["input_empty_symbol_count"] = len(list_value(data, "empty_symbols"))
    if "possibly_truncated_symbols" in data:
        metadata["input_possibly_truncated_symbol_count"] = len(
            list_value(data, "possibly_truncated_symbols")
        )
    metadata.update(prefixed_quality_counts(data, "input_"))
    if "requested_symbols" in data:
        metadata["input_requested_symbol_count"] = len(list_value(data, "requested_symbols"))
    return metadata


def history_metadata_for_output(output_dir: Path) -> dict[str, Any]:
    metadata_path = output_dir / "history_metadata.json"
    if not metadata_path.is_file():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"history metadata must be a JSON object: {metadata_path}")
    source = str(data.get("source", "external_fetch") or "external_fetch")
    metadata = {
        "source_type": "external_fetch",
        "source": source,
        "source_scope": str(data.get("source_scope", f"{source}_history_fetch")),
        "source_claim_boundary": str(data.get("source_claim_boundary", "")),
        "data_source_note": str(data.get("data_source_note", "")),
        "history_provider": source,
        "real_market_data": True,
        "history_partial_result": history_partial_result(data),
        "history_failed_symbol_count": len(list_value(data, "failed_symbols")),
        "history_empty_symbol_count": len(list_value(data, "empty_symbols")),
        "history_possibly_truncated_symbol_count": len(
            list_value(data, "possibly_truncated_symbols")
        ),
        "history_fallback_error_count": len(list_value(data, "fallback_errors")),
        "history_output_written": bool(data.get("output_written", True)),
        "history_metadata_output_written": bool(data.get("metadata_output_written", True)),
    }
    metadata.update(prefixed_quality_counts(data, "history_"))
    for key in QUALITY_COUNT_KEYS:
        metadata.setdefault(f"history_{key}", 0)
    if "adjust" in data:
        metadata["history_adjust"] = data["adjust"]
    if "adjustflag" in data:
        metadata["history_adjustflag"] = str(data["adjustflag"])
    if "fields" in data:
        metadata["history_fields"] = str(data["fields"])
    if "token_configured" in data:
        metadata["history_token_configured"] = bool(data["token_configured"])
    if "request_interval_seconds" in data:
        metadata["history_request_interval_seconds"] = data["request_interval_seconds"]
    if "timeout_seconds" in data:
        metadata["history_timeout_seconds"] = data["timeout_seconds"]
    if "limit" in data:
        metadata["history_limit"] = data["limit"]
    if "max_pages" in data:
        metadata["history_max_pages"] = data["max_pages"]
    return metadata


def list_value(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key, [])
    return value if isinstance(value, list) else []


def prefixed_quality_counts(data: dict[str, Any], prefix: str) -> dict[str, int]:
    result = {}
    for key in QUALITY_COUNT_KEYS:
        if key in data:
            result[f"{prefix}{key}"] = quality_count_value(data.get(key), key)
    return result


def quality_count_value(value: Any, key: str) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"metadata {key} must be an integer: {value}") from exc


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
        "history_invalid_rows",
        "history_dropped_invalid_rows",
        "history_non_trading_rows",
        "history_tradestatus_missing_rows",
        "history_metadata_fallback_error_count",
    )
    return any((integer_value(selection.get(key)) or 0) > 0 for key in count_keys)


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
    if quality_count_present(data):
        return True
    requested = requested_symbol_count(data)
    symbol_count = integer_value(data.get("symbol_count"))
    if requested is not None and symbol_count is not None:
        return symbol_count != requested
    return False


def requested_symbol_count(data: dict[str, Any]) -> int | None:
    explicit_count = integer_value(data.get("input_requested_symbol_count"))
    if explicit_count is not None:
        return explicit_count
    requested = list_value(data, "requested_symbols")
    return len(requested) if requested else None


def quality_count_present(data: dict[str, Any]) -> bool:
    return any((integer_value(data.get(key)) or 0) > 0 for key in QUALITY_COUNT_KEYS)


def integer_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_synthetic_demo(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("source_type", "")) == "synthetic_demo"

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
