"""Summary JSON builder for today's A-share runner."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import date, datetime
from typing import Any

import run_today_a_share_selection_helpers as helpers
from a_share_selection_disclosure import (
    ADVICE_BOUNDARY,
    RECOMMENDATION_BOUNDARY,
)


def summary_view(manifest: dict[str, Any], status: str) -> dict[str, Any]:
    paths = summary_paths(manifest)
    score = helpers.score_summary(manifest)
    input_metadata = normalized_input_metadata(manifest)
    initialized = bool(manifest.get("run_outputs_initialized"))
    history_selection = history_selection_view(manifest) if initialized else {}
    return {
        **run_identity(manifest, status),
        **prediction_fields(manifest, score),
        "source_scope": manifest["source_scope"],
        "source_type": input_metadata.get("source_type", "unknown"),
        "real_market_data": input_metadata.get("real_market_data", "unknown"),
        "input_metadata": input_metadata,
        "advice_boundary": ADVICE_BOUNDARY,
        "recommendation_boundary": RECOMMENDATION_BOUNDARY,
        **row_count_fields(manifest, paths, score, history_selection, initialized),
        "score": score,
        **output_path_fields(paths, initialized),
        "boundary": helpers.boundary_for(manifest),
    }


def summary_paths(manifest: dict[str, Any]) -> dict[str, Path]:
    output_dir = Path(manifest["output_dir"])
    return {
        "prices": helpers.prices_output_path(manifest),
        "candidates": output_dir / "candidates.csv",
        "diagnostics": output_dir / "diagnostics.csv",
        "spot": helpers.spot_output_path(manifest),
        "spot_metadata": output_dir / "spot_metadata.json",
        "selected_symbols": output_dir / "selected_symbols.json",
        "history_metadata": output_dir / "history_metadata.json",
    }


def normalized_input_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    metadata = manifest.get("input_metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def run_identity(manifest: dict[str, Any], status: str) -> dict[str, Any]:
    failed = [
        step
        for step in manifest["steps"]
        if step["returncode"] not in step["allowed_returncodes"]
    ]
    return {
        "runner": manifest["runner"],
        "status": status,
        "requested_mode": manifest.get("requested_mode", manifest["mode"]),
        "mode": manifest["mode"],
        "mode_decision": manifest.get("mode_decision", ""),
        "mode_decision_reason": manifest.get("mode_decision_reason", ""),
        "missing_prediction_column_groups": manifest.get(
            "missing_prediction_column_groups",
            [],
        ),
        "missing_prediction_requirement": manifest.get("missing_prediction_requirement", ""),
        "steps": len(manifest["steps"]),
        "failed_steps": [step["step"] for step in failed],
        "run_error_type": manifest.get("run_error_type", ""),
        "run_error": manifest.get("run_error", ""),
    }


def prediction_fields(manifest: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    return {
        "prediction_mode": manifest["prediction_mode"],
        "consumes_prediction_columns": helpers.prediction_columns_consumed(manifest, score),
        "prediction_input_source": helpers.prediction_input_source(manifest),
        "requested_prediction_input_source": manifest.get(
            "requested_prediction_input_source",
            manifest.get("prediction_input_source", "unknown"),
        ),
        "prediction_model_executed_by_runner": (
            helpers.prediction_model_executed_by_runner(manifest)
        ),
        "lightgbm_not_used": manifest["lightgbm_not_used"],
        "lightgbm_output_source": manifest.get("lightgbm_output_source", "unknown"),
        "requested_lightgbm_output_source": manifest.get(
            "requested_lightgbm_output_source",
            manifest.get("lightgbm_output_source", "unknown"),
        ),
        "lightgbm_executed_by_runner": manifest.get("lightgbm_executed_by_runner", False),
    }


def row_count_fields(
    manifest: dict[str, Any],
    paths: dict[str, Path],
    score: dict[str, Any],
    history_selection: dict[str, Any],
    initialized: bool,
) -> dict[str, Any]:
    return {
        "spot_metadata": helpers.spot_metadata_view(manifest) if initialized else {},
        "spot_rows": helpers.spot_rows(manifest) if initialized else 0,
        "spot_matched_symbols": score.get("spot_matched_symbols", 0),
        "history_selection": history_selection,
        "history_symbol_count": history_symbol_count(manifest, history_selection),
        "prices_rows": row_count(paths["prices"], initialized),
        "candidate_rows": row_count(paths["candidates"], initialized),
        "diagnostic_rows": row_count(paths["diagnostics"], initialized),
        "spot_output": str(paths["spot"]) if paths["spot"] else "",
        "spot_output_written": initialized and paths["spot"] is not None and paths["spot"].exists(),
        "spot_metadata_output": str(paths["spot_metadata"]),
        "spot_metadata_output_written": initialized and paths["spot_metadata"].exists(),
    }


def row_count(path: Path, initialized: bool) -> int:
    return helpers.tabular_row_count(path) if initialized else 0


def output_path_fields(paths: dict[str, Path], initialized: bool) -> dict[str, Any]:
    return {
        "prices_output": str(paths["prices"]),
        "prices_output_written": initialized and paths["prices"].exists(),
        "candidates_output": str(paths["candidates"]),
        "candidates_output_written": initialized and paths["candidates"].exists(),
        "diagnostics_output": str(paths["diagnostics"]),
        "diagnostics_output_written": initialized and paths["diagnostics"].exists(),
        "selected_symbols_output": str(paths["selected_symbols"]),
        "selected_symbols_output_written": initialized and paths["selected_symbols"].exists(),
        "history_metadata_output": str(paths["history_metadata"]),
        "history_metadata_output_written": initialized and paths["history_metadata"].exists(),
    }


def history_selection_view(manifest: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(manifest["output_dir"])
    selected_path = output_dir / "selected_symbols.json"
    metadata_path = output_dir / "history_metadata.json"
    if not history_selection_available(manifest, selected_path, metadata_path):
        return {}
    selected_data = read_json_if_exists(selected_path)
    metadata = read_json_if_exists(metadata_path)
    selected_symbols = selected_symbol_values(selected_data, manifest)
    failed_symbols = metadata_list(metadata, "failed_symbols")
    fallback_errors = metadata_list(metadata, "fallback_errors")
    date_range = history_date_range_view(metadata, manifest)
    return {
        "source": selected_data.get("source", ""),
        "raw_spot_rows": selected_data.get("raw_spot_rows"),
        "filtered_spot_rows": selected_data.get("filtered_spot_rows"),
        "selected_symbol_count": selected_symbol_count(selected_data, selected_symbols),
        "max_history_symbols": selected_data.get(
            "max_history_symbols",
            manifest.get("max_history_symbols", 0),
        ),
        "allow_partial_history": bool(manifest.get("allow_partial_history", False)),
        "history_metadata_failed_symbol_count": len(failed_symbols),
        "history_metadata_failed_symbols": failed_symbols,
        "history_metadata_fallback_error_count": len(fallback_errors),
        "history_metadata_fallback_errors": fallback_errors,
        "history_metadata_symbol_providers": symbol_providers(metadata),
        **date_range,
        "selected_symbols_output": str(selected_path),
        "selected_symbols_output_written": selected_path.exists(),
        "history_metadata_output": str(metadata_path),
        "history_metadata_output_written": metadata_path.exists(),
    }


def history_selection_available(
    manifest: dict[str, Any],
    selected_path: Path,
    metadata_path: Path,
) -> bool:
    return (
        selected_path.exists()
        or metadata_path.exists()
        or bool(manifest.get("history_symbols"))
    )


def read_json_if_exists(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def selected_symbol_values(
    selected_data: dict[str, Any],
    manifest: dict[str, Any],
) -> list[Any]:
    for key in ("selected_symbols", "symbols"):
        value = selected_data.get(key)
        if isinstance(value, list):
            return value
    value = manifest.get("history_symbols", [])
    return value if isinstance(value, list) else []


def selected_symbol_count(selected_data: dict[str, Any], selected_symbols: list[Any]) -> int:
    value = selected_data.get("selected_symbol_count")
    if value is None:
        return len(selected_symbols)
    return int(value)


def metadata_list(metadata: dict[str, Any], key: str) -> list[Any]:
    value = metadata.get(key, [])
    return value if isinstance(value, list) else []


def history_date_range_view(
    metadata: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    requested = normalized_history_date(metadata.get("end_date") or manifest.get("end_date") or "")
    ranges = symbol_date_ranges(metadata)
    date_max_values = [item["date_max"] for item in ranges if item["date_max"]]
    actual_date_max = max(date_max_values) if date_max_values else ""
    reached = [item for item in ranges if item["date_max"] == requested and requested]
    return {
        "requested_end_date": requested,
        "history_metadata_actual_date_max": actual_date_max,
        "history_metadata_all_symbols_reached_end_date": bool(
            ranges and requested and len(reached) == len(ranges)
        ),
        "history_metadata_end_date_has_rows": bool(reached),
        "history_metadata_symbol_date_ranges": ranges,
    }


def symbol_date_ranges(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    symbols = metadata.get("symbols", [])
    if not isinstance(symbols, list):
        return []
    return [
        {
            "symbol": str(item.get("symbol", "")),
            "date_min": normalized_history_date(item.get("date_min", "")),
            "date_max": normalized_history_date(item.get("date_max", "")),
            "rows": int(item.get("rows", 0) or 0),
        }
        for item in symbols
        if isinstance(item, dict)
    ]


def symbol_providers(metadata: dict[str, Any]) -> list[dict[str, str]]:
    symbols = metadata.get("symbols", [])
    if not isinstance(symbols, list):
        return []
    return [
        {
            "symbol": str(item.get("symbol", "")),
            "provider": str(item.get("provider", "")),
        }
        for item in symbols
        if isinstance(item, dict) and item.get("provider")
    ]


def normalized_history_date(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    first = text.split()[0]
    try:
        if len(first) == 8 and first.isdigit():
            return datetime.strptime(first, "%Y%m%d").date().isoformat()
        return date.fromisoformat(first).isoformat()
    except ValueError:
        return text


def history_symbol_count(manifest: dict[str, Any], history_selection: dict[str, Any]) -> int:
    if "selected_symbol_count" in history_selection:
        return int(history_selection["selected_symbol_count"])
    symbols = manifest.get("history_symbols", [])
    return len(symbols) if isinstance(symbols, list) else 0
