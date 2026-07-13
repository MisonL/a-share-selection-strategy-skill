"""Input metadata loading for today's A-share runner."""

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
    "license_claim_boundary",
    "adjustment",
    "adjust",
    "adjustflag",
    "fields",
    "token_configured",
    "request_interval_seconds",
    "max_concurrent_symbol_requests",
    "max_rate_limit_sleep_seconds",
    "max_429_events",
    "max_runtime_seconds",
    "limit",
    "max_pages",
    "timeout_seconds",
    "missing_provider_fields",
    "requested_symbols",
    "symbol_count",
    "rows",
    "raw_rows",
    "output_rows",
    "requested_raw_rows",
    "api_request_count",
    "overfetch_rows",
    "raw_to_output_ratio",
    "duration_seconds",
    "rate_limit_429_events",
    "rate_limit_sleep_seconds",
    "rate_limit_budget_exhausted",
    "rate_limit_exhaustion_reason",
    "network_retry_events",
    "network_retry_sleep_seconds",
    "failed_symbols",
    "empty_symbols",
    "possibly_truncated_symbols",
    "unprocessed_symbols",
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
    "clean_pool_generated_at",
    "clean_pool_source_prices",
    "clean_pool_removed_symbol_count",
    "clean_pool_reason_counts",
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
    prices_path = Path(prices_input)
    if prices_path.suffix.lower() in {".parquet", ".pq"}:
        sidecar_metadata = verified_sidecar_metadata(prices_path)
        if sidecar_metadata:
            return sidecar_metadata
    metadata_path = input_metadata_path(prices_input)
    if not metadata_path.is_file():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"input metadata must be a JSON object: {metadata_path}")
    return normalize_input_metadata(data, metadata_path.name)


def normalize_input_metadata(
    data: dict[str, Any], metadata_file: str
) -> dict[str, Any]:
    metadata = {key: data[key] for key in METADATA_KEYS if key in data}
    metadata["input_metadata_file"] = metadata_file
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
    if "unprocessed_symbols" in data:
        metadata["input_unprocessed_symbol_count"] = len(
            list_value(data, "unprocessed_symbols")
        )
    if "rate_limit_budget_exhausted" in data:
        metadata["input_rate_limit_budget_exhausted"] = (
            data.get("rate_limit_budget_exhausted") is True
        )
    if "rate_limit_exhaustion_reason" in data:
        metadata["input_rate_limit_exhaustion_reason"] = str(
            data.get("rate_limit_exhaustion_reason", "")
        )
    metadata.update(prefixed_quality_counts(data, "input_"))
    if "requested_symbols" in data:
        metadata["input_requested_symbol_count"] = len(
            list_value(data, "requested_symbols")
        )
    if "clean_pool_removed_symbol_count" in data:
        metadata["input_clean_pool_removed_symbol_count"] = integer_value(
            data.get("clean_pool_removed_symbol_count")
        )
    elif "clean_pool_removed_symbols" in data:
        metadata["input_clean_pool_removed_symbol_count"] = len(
            list_value(data, "clean_pool_removed_symbols")
        )
    if "clean_pool_reason_counts" in data:
        metadata["input_clean_pool_reason_counts"] = data[
            "clean_pool_reason_counts"
        ]
    return metadata


def verified_sidecar_metadata(prices: Path) -> dict[str, Any]:
    from lib.runner.run_today_a_share_selection_prices_sidecar import (
        load_verified_sidecar,
        sidecar_path,
    )

    path = sidecar_path(prices)
    if not path.exists():
        require_declared_filter_sidecar(prices)
        return {}
    sidecar = load_verified_sidecar(prices)
    source = sidecar["input_metadata"]
    metadata = normalize_input_metadata(source, path.name)
    metadata["input_metadata_sidecar_verified"] = True
    metadata["input_metadata_sidecar_claim_boundary"] = sidecar["claim_boundary"]
    metadata["input_metadata_sidecar_sha256"] = sidecar["artifact"]["sha256"]
    metadata["input_metadata_sidecar_rows"] = sidecar["rows"]
    metadata["input_metadata_sidecar_symbol_count"] = sidecar["symbol_count"]
    metadata["input_metadata_sidecar_date_min"] = sidecar["date_min"]
    metadata["input_metadata_sidecar_date_max"] = sidecar["date_max"]
    metadata["input_prices_filter_contract"] = dict(sidecar["filter_contract"])
    return metadata


def require_declared_filter_sidecar(prices: Path) -> None:
    from lib.runner.run_today_a_share_selection_prices_sidecar import sidecar_path

    filter_path = prices.parent / "prices_filter.json"
    if not filter_path.is_file():
        return
    data = json.loads(filter_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"prices filter metadata must be a JSON object: {filter_path}")
    declared = str(data.get("prices_filter_output_prices", "")).strip()
    if declared and Path(declared).resolve() == prices.resolve():
        raise ValueError(f"filtered prices sidecar not found: {sidecar_path(prices)}")


def input_metadata_path(prices_input: str) -> Path:
    root = Path(prices_input).parent
    primary = root / "metadata.json"
    if primary.is_file():
        return primary
    history = root / "history_metadata.json"
    if history.is_file():
        return history
    return primary


def history_metadata_for_output(output_dir: Path) -> dict[str, Any]:
    metadata_path = output_dir / "history_metadata.json"
    if not metadata_path.is_file():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"history metadata must be a JSON object: {metadata_path}")
    source = str(data.get("source", "external_fetch") or "external_fetch")
    unprocessed_symbols = list_value(data, "unprocessed_symbols")
    metadata = {
        "source_type": "external_fetch",
        "source": source,
        "source_scope": str(data.get("source_scope", f"{source}_history_fetch")),
        "source_claim_boundary": str(data.get("source_claim_boundary", "")),
        "data_source_note": str(data.get("data_source_note", "")),
        "history_provider": source,
        "real_market_data": history_real_market_data(data),
        "history_rows": integer_value(data.get("rows")) or 0,
        "history_metadata_symbol_count": integer_value(data.get("symbol_count")) or 0,
        "history_requested_symbol_count": len(list_value(data, "requested_symbols")),
        "history_partial_result": history_partial_result(data),
        "history_failed_symbol_count": len(list_value(data, "failed_symbols")),
        "history_empty_symbol_count": len(list_value(data, "empty_symbols")),
        "history_possibly_truncated_symbol_count": len(
            list_value(data, "possibly_truncated_symbols")
        ),
        "history_unprocessed_symbol_count": len(unprocessed_symbols),
        "history_unprocessed_symbols": unprocessed_symbols,
        "history_rate_limit_budget_exhausted": (
            data.get("rate_limit_budget_exhausted") is True
        ),
        "history_rate_limit_exhaustion_reason": str(
            data.get("rate_limit_exhaustion_reason", "")
        ),
        "history_fallback_error_count": len(list_value(data, "fallback_errors")),
        "history_output_written": bool(data.get("output_written", True)),
        "history_metadata_output_written": bool(
            data.get("metadata_output_written", True)
        ),
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
    if "max_concurrent_symbol_requests" in data:
        metadata["history_max_concurrent_symbol_requests"] = data[
            "max_concurrent_symbol_requests"
        ]
    if "max_rate_limit_sleep_seconds" in data:
        metadata["history_max_rate_limit_sleep_seconds"] = data[
            "max_rate_limit_sleep_seconds"
        ]
    if "max_429_events" in data:
        metadata["history_max_429_events"] = data["max_429_events"]
    if "max_runtime_seconds" in data:
        metadata["history_max_runtime_seconds"] = data["max_runtime_seconds"]
    if "timeout_seconds" in data:
        metadata["history_timeout_seconds"] = data["timeout_seconds"]
    if "market" in data:
        metadata["market"] = data["market"]
    if "market_label_only" in data:
        metadata["market_label_only"] = bool(data["market_label_only"])
    if "limit" in data:
        metadata["history_limit"] = data["limit"]
    if "max_pages" in data:
        metadata["history_max_pages"] = data["max_pages"]
    optional_keys = {
        "non_trading_policy": "history_non_trading_policy",
        "dropped_non_trading_rows": "history_dropped_non_trading_rows",
        "retained_non_trading_rows": "history_retained_non_trading_rows",
        "checkpoint_enabled": "history_checkpoint_enabled",
        "resume_from_checkpoint": "history_resume_from_checkpoint",
        "checkpoint_batch_size": "history_checkpoint_batch_size",
        "checkpoint_symbols_skipped": "history_checkpoint_symbols_skipped",
        "checkpoint_requests_executed": "history_checkpoint_requests_executed",
        "checkpoint_parts_written": "history_checkpoint_parts_written",
        "checkpoint_parts_available": "history_checkpoint_parts_available",
        "checkpoint_dir": "history_checkpoint_dir",
        "checkpoint_manifest": "history_checkpoint_manifest",
        "checkpoint_schema_version": "history_checkpoint_schema_version",
        "checkpoint_execution_contract_sha256": (
            "history_checkpoint_execution_contract_sha256"
        ),
        "license_claim_boundary": "history_license_claim_boundary",
        "missing_provider_fields": "history_missing_provider_fields",
        "page_size": "history_page_size",
        "category": "history_category",
        "duration_seconds": "history_duration_seconds",
        "raw_rows": "history_raw_rows",
        "output_rows": "history_output_rows",
        "requested_raw_rows": "history_requested_raw_rows",
        "api_request_count": "history_api_request_count",
        "overfetch_rows": "history_overfetch_rows",
        "raw_to_output_ratio": "history_raw_to_output_ratio",
        "rate_limit_429_events": "history_rate_limit_429_events",
        "rate_limit_sleep_seconds": "history_rate_limit_sleep_seconds",
        "network_retry_events": "history_network_retry_events",
        "network_retry_sleep_seconds": "history_network_retry_sleep_seconds",
    }
    for source_key, target_key in optional_keys.items():
        if source_key in data:
            metadata[target_key] = data[source_key]
    return metadata


def history_real_market_data(data: dict[str, Any]) -> Any:
    if "real_market_data" in data:
        return data["real_market_data"]
    if data.get("market_label_only") is True:
        return "unknown"
    return True


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
