"""Propagate runner provenance into run-scoped CSV artifacts."""

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


import csv
import json
from pathlib import Path
from typing import Any

from lib.selection_core.a_share_selection_provenance import (
    PROVENANCE_COLUMNS as INPUT_PROVENANCE_COLUMNS,
    missing_value,
)

RUN_PROVENANCE_COLUMNS = (
    "source_type",
    "source",
    "source_scope",
    "real_market_data",
    "market_label_only",
    "source_claim_boundary",
    "execution_path",
    "execution_path_reason",
    "coverage_class",
    "full_market_claim_allowed",
    "full_market_claim_boundary",
    "mode_decision",
    "consumes_prediction_columns",
    "prediction_model_executed_by_runner",
    "lightgbm_executed_by_runner",
    "history_provider",
    "history_token_configured",
    "input_token_configured",
    "history_fields",
    "history_request_interval_seconds",
    "history_max_concurrent_symbol_requests",
    "history_max_rate_limit_sleep_seconds",
    "history_max_429_events",
    "history_max_runtime_seconds",
    "history_limit",
    "history_max_pages",
    "history_partial_result",
    "input_partial_result",
    "history_failed_symbol_count",
    "history_empty_symbol_count",
    "history_possibly_truncated_symbol_count",
    "history_unprocessed_symbol_count",
    "history_rate_limit_budget_exhausted",
    "history_rate_limit_exhaustion_reason",
    "history_invalid_rows",
    "history_dropped_invalid_rows",
    "history_non_trading_rows",
    "history_non_trading_policy",
    "history_dropped_non_trading_rows",
    "history_retained_non_trading_rows",
    "history_tradestatus_missing_rows",
    "input_possibly_truncated_symbol_count",
    "input_unprocessed_symbol_count",
    "input_rate_limit_budget_exhausted",
    "input_rate_limit_exhaustion_reason",
    "input_invalid_rows",
    "input_dropped_invalid_rows",
    "input_non_trading_rows",
    "input_tradestatus_missing_rows",
    "history_fallback_error_count",
    "history_adjust",
    "history_adjustflag",
    "history_output_written",
    "history_metadata_output_written",
    "history_checkpoint_enabled",
    "history_resume_from_checkpoint",
    "history_checkpoint_batch_size",
    "history_checkpoint_symbols_skipped",
    "clean_pool_removed_symbol_count",
    "clean_pool_reason_counts",
    "input_clean_pool_removed_symbol_count",
    "input_clean_pool_reason_counts",
    "filter_prices_to_spot_universe",
    "prices_filter_spot_universe",
    "prices_filter_min_symbol_latest_date",
    "prices_filter_output_format",
    "prices_filter_output_prices",
    "prices_filter_sidecar_output",
    "prices_filter_sidecar_sha256",
    "prices_filter_metadata_output",
    "prices_filter_input_rows",
    "prices_filter_output_rows",
    "prices_filter_spot_symbol_count",
    "prices_filter_input_symbol_count",
    "prices_filter_kept_symbol_count",
    "prices_filter_removed_symbol_count",
    "prices_filter_removed_stale_symbol_count",
    "prices_filter_output_written",
    "prices_filter_failure_reason",
    "prices_filter_claim_boundary",
)
OPTIONAL_METADATA_COLUMNS = ("source", "market_label_only", "source_claim_boundary")


def annotate_run_csv_outputs(
    manifest: dict[str, Any],
    candidates: Path,
    diagnostics: Path,
) -> None:
    fields = provenance_fields(manifest)
    for path in (candidates, diagnostics):
        annotate_csv(path, fields)


def provenance_fields(manifest: dict[str, Any]) -> dict[str, Any]:
    metadata = manifest.get("input_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    fields = {
        "source_type": metadata.get("source_type", "unknown"),
        "source_scope": metadata.get(
            "source_scope", manifest.get("source_scope", "unknown")
        ),
        "real_market_data": metadata.get("real_market_data", "unknown"),
        "execution_path": manifest.get("execution_path", "unresolved"),
        "execution_path_reason": manifest.get("execution_path_reason", ""),
        "coverage_class": manifest.get("coverage_class", "unknown"),
        "full_market_claim_allowed": bool(
            manifest.get("full_market_claim_allowed", False)
        ),
        "full_market_claim_boundary": manifest.get(
            "full_market_claim_boundary",
            "not_evaluated",
        ),
        "mode_decision": manifest.get("mode_decision", ""),
        "consumes_prediction_columns": bool(
            manifest.get("consumes_prediction_columns", False)
        ),
        "prediction_model_executed_by_runner": bool(
            manifest.get("prediction_model_executed_by_runner", False)
        ),
        "lightgbm_executed_by_runner": bool(
            manifest.get("lightgbm_executed_by_runner", False)
        ),
        "history_provider": metadata.get("history_provider", ""),
        "history_token_configured": metadata.get("history_token_configured", ""),
        "input_token_configured": metadata.get("token_configured", ""),
        "history_fields": metadata.get("history_fields", ""),
        "history_request_interval_seconds": metadata.get(
            "history_request_interval_seconds",
            "",
        ),
        "history_max_concurrent_symbol_requests": metadata.get(
            "history_max_concurrent_symbol_requests",
            "",
        ),
        "history_max_rate_limit_sleep_seconds": metadata.get(
            "history_max_rate_limit_sleep_seconds",
            "",
        ),
        "history_max_429_events": metadata.get("history_max_429_events", ""),
        "history_max_runtime_seconds": metadata.get(
            "history_max_runtime_seconds",
            "",
        ),
        "history_limit": metadata.get("history_limit", ""),
        "history_max_pages": metadata.get("history_max_pages", ""),
        "history_partial_result": metadata.get("history_partial_result", ""),
        "input_partial_result": metadata.get("input_partial_result", ""),
        "history_failed_symbol_count": metadata.get("history_failed_symbol_count", ""),
        "history_empty_symbol_count": metadata.get("history_empty_symbol_count", ""),
        "history_possibly_truncated_symbol_count": metadata.get(
            "history_possibly_truncated_symbol_count",
            "",
        ),
        "history_unprocessed_symbol_count": metadata.get(
            "history_unprocessed_symbol_count",
            "",
        ),
        "history_rate_limit_budget_exhausted": metadata.get(
            "history_rate_limit_budget_exhausted",
            "",
        ),
        "history_rate_limit_exhaustion_reason": metadata.get(
            "history_rate_limit_exhaustion_reason",
            "",
        ),
        "history_invalid_rows": metadata.get("history_invalid_rows", ""),
        "history_dropped_invalid_rows": metadata.get(
            "history_dropped_invalid_rows", ""
        ),
        "history_non_trading_rows": metadata.get("history_non_trading_rows", ""),
        "history_non_trading_policy": metadata.get(
            "history_non_trading_policy",
            "",
        ),
        "history_dropped_non_trading_rows": metadata.get(
            "history_dropped_non_trading_rows",
            "",
        ),
        "history_retained_non_trading_rows": metadata.get(
            "history_retained_non_trading_rows",
            "",
        ),
        "history_tradestatus_missing_rows": metadata.get(
            "history_tradestatus_missing_rows",
            "",
        ),
        "input_possibly_truncated_symbol_count": metadata.get(
            "input_possibly_truncated_symbol_count",
            "",
        ),
        "input_unprocessed_symbol_count": metadata.get(
            "input_unprocessed_symbol_count",
            "",
        ),
        "input_rate_limit_budget_exhausted": metadata.get(
            "input_rate_limit_budget_exhausted",
            "",
        ),
        "input_rate_limit_exhaustion_reason": metadata.get(
            "input_rate_limit_exhaustion_reason",
            "",
        ),
        "input_invalid_rows": metadata.get("input_invalid_rows", ""),
        "input_dropped_invalid_rows": metadata.get("input_dropped_invalid_rows", ""),
        "input_non_trading_rows": metadata.get("input_non_trading_rows", ""),
        "input_tradestatus_missing_rows": metadata.get(
            "input_tradestatus_missing_rows",
            "",
        ),
        "history_fallback_error_count": metadata.get(
            "history_fallback_error_count", ""
        ),
        "history_adjust": metadata.get("history_adjust", ""),
        "history_adjustflag": metadata.get("history_adjustflag", ""),
        "history_output_written": metadata.get("history_output_written", ""),
        "history_metadata_output_written": metadata.get(
            "history_metadata_output_written",
            "",
        ),
        "history_checkpoint_enabled": metadata.get("history_checkpoint_enabled", ""),
        "history_resume_from_checkpoint": metadata.get(
            "history_resume_from_checkpoint",
            "",
        ),
        "history_checkpoint_batch_size": metadata.get(
            "history_checkpoint_batch_size",
            "",
        ),
        "history_checkpoint_symbols_skipped": metadata.get(
            "history_checkpoint_symbols_skipped",
            "",
        ),
        "clean_pool_removed_symbol_count": metadata.get(
            "clean_pool_removed_symbol_count",
            "",
        ),
        "clean_pool_reason_counts": metadata.get("clean_pool_reason_counts", ""),
        "input_clean_pool_removed_symbol_count": metadata.get(
            "input_clean_pool_removed_symbol_count",
            "",
        ),
        "input_clean_pool_reason_counts": metadata.get(
            "input_clean_pool_reason_counts",
            "",
        ),
        "filter_prices_to_spot_universe": bool(
            manifest.get("filter_prices_to_spot_universe", False)
        ),
        "prices_filter_spot_universe": bool(
            manifest.get("prices_filter_spot_universe", False)
        ),
        "prices_filter_min_symbol_latest_date": manifest.get(
            "prices_filter_min_symbol_latest_date", ""
        ),
        "prices_filter_output_format": manifest.get(
            "prices_filter_output_format", ""
        ),
        "prices_filter_output_prices": manifest.get(
            "prices_filter_output_prices", ""
        ),
        "prices_filter_sidecar_output": manifest.get(
            "prices_filter_sidecar_output", ""
        ),
        "prices_filter_sidecar_sha256": manifest.get(
            "prices_filter_sidecar_sha256", ""
        ),
        "prices_filter_metadata_output": manifest.get(
            "prices_filter_metadata_output", ""
        ),
        "prices_filter_input_rows": manifest.get("prices_filter_input_rows", ""),
        "prices_filter_output_rows": manifest.get("prices_filter_output_rows", ""),
        "prices_filter_spot_symbol_count": manifest.get(
            "prices_filter_spot_symbol_count", ""
        ),
        "prices_filter_input_symbol_count": manifest.get(
            "prices_filter_input_symbol_count", ""
        ),
        "prices_filter_kept_symbol_count": manifest.get(
            "prices_filter_kept_symbol_count", ""
        ),
        "prices_filter_removed_symbol_count": manifest.get(
            "prices_filter_removed_symbol_count", ""
        ),
        "prices_filter_removed_stale_symbol_count": manifest.get(
            "prices_filter_removed_stale_symbol_count", ""
        ),
        "prices_filter_output_written": bool(
            manifest.get("prices_filter_output_written", False)
        ),
        "prices_filter_failure_reason": manifest.get(
            "prices_filter_failure_reason", ""
        ),
        "prices_filter_claim_boundary": manifest.get(
            "prices_filter_claim_boundary", ""
        ),
    }
    for column in OPTIONAL_METADATA_COLUMNS:
        if column in metadata:
            fields[column] = metadata[column]
    return fields


def annotate_csv(path: Path, fields: dict[str, Any]) -> None:
    if not path.is_file() or path.suffix.lower() != ".csv":
        return
    rows, fieldnames = read_csv(path)
    columns = [
        *fieldnames,
        *(column for column in RUN_PROVENANCE_COLUMNS if column not in fieldnames),
    ]
    for row in rows:
        merge_provenance_fields(row, fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def merge_provenance_fields(row: dict[str, Any], fields: dict[str, Any]) -> None:
    for column, value in fields.items():
        if preserves_input_provenance(row, column):
            continue
        row[column] = provenance_csv_value(value)


def provenance_csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return value


def preserves_input_provenance(row: dict[str, Any], column: str) -> bool:
    return column in INPUT_PROVENANCE_COLUMNS and not missing_value(row.get(column))


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])
