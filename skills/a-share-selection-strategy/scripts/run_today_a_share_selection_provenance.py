"""Propagate runner provenance into run-scoped CSV artifacts."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from a_share_selection_provenance import (
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
    "mode_decision",
    "consumes_prediction_columns",
    "prediction_model_executed_by_runner",
    "lightgbm_executed_by_runner",
    "history_provider",
    "history_partial_result",
    "history_failed_symbol_count",
    "history_empty_symbol_count",
    "history_fallback_error_count",
    "history_output_written",
    "history_metadata_output_written",
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
        "source_scope": manifest.get("source_scope", "unknown"),
        "real_market_data": metadata.get("real_market_data", "unknown"),
        "mode_decision": manifest.get("mode_decision", ""),
        "consumes_prediction_columns": bool(manifest.get("consumes_prediction_columns", False)),
        "prediction_model_executed_by_runner": bool(
            manifest.get("prediction_model_executed_by_runner", False)
        ),
        "lightgbm_executed_by_runner": bool(manifest.get("lightgbm_executed_by_runner", False)),
        "history_provider": metadata.get("history_provider", ""),
        "history_partial_result": metadata.get("history_partial_result", ""),
        "history_failed_symbol_count": metadata.get("history_failed_symbol_count", ""),
        "history_empty_symbol_count": metadata.get("history_empty_symbol_count", ""),
        "history_fallback_error_count": metadata.get("history_fallback_error_count", ""),
        "history_output_written": metadata.get("history_output_written", ""),
        "history_metadata_output_written": metadata.get(
            "history_metadata_output_written",
            "",
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
        row[column] = value


def preserves_input_provenance(row: dict[str, Any], column: str) -> bool:
    return column in INPUT_PROVENANCE_COLUMNS and not missing_value(row.get(column))


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])
