"""Summary JSON builder for today's A-share runner."""

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
from datetime import date, datetime
from typing import Any

import lib.runner.run_today_a_share_selection_helpers as helpers
from lib.a_share_selection_run_state import history_partial_result, step_executed
from lib.selection_core.a_share_selection_candidate_fields import (
    OPTIONAL_CANDIDATE_FIELD_ALIASES,
    candidate_field_value_present,
)
from lib.selection_core.a_share_selection_provenance import (
    PROVENANCE_COLUMNS as INPUT_CSV_PROVENANCE_COLUMNS,
)
from lib.selection_core.a_share_selection_disclosure import (
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
        "source": summary_source(input_metadata, manifest),
        "source_scope": summary_source_scope(input_metadata, manifest),
        "runner_source_scope": manifest["source_scope"],
        "source_type": input_metadata.get("source_type", "unknown"),
        "real_market_data": input_metadata.get("real_market_data", "unknown"),
        "source_claim_boundary": input_metadata.get("source_claim_boundary", ""),
        "input_metadata": input_metadata,
        "input_csv_provenance": input_csv_provenance(score),
        "source_provenance": source_provenance(input_metadata, score, manifest),
        "advice_boundary": ADVICE_BOUNDARY,
        "recommendation_boundary": RECOMMENDATION_BOUNDARY,
        **row_count_fields(manifest, paths, score, history_selection, initialized),
        **full_a_provenance_fields(manifest),
        **selection_failure_fields(manifest, status, history_selection),
        "candidate_field_coverage": candidate_field_coverage(
            paths["candidates"], initialized
        ),
        **empty_result_fields(score),
        "score": score,
        **output_path_fields(paths, initialized),
        "boundary": helpers.boundary_for(manifest),
    }


def summary_paths(manifest: dict[str, Any]) -> dict[str, Path]:
    output_dir = Path(manifest["output_dir"])
    return {
        "summary": output_dir / "summary.json",
        "manifest": output_dir / "run_manifest.json",
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


def full_a_provenance_fields(manifest: dict[str, Any]) -> dict[str, Any]:
    if not manifest.get("full_a_provenance_requested"):
        return {}
    keys = (
        "full_a_provenance_input",
        "full_a_provenance_file_sha256",
        "full_a_provenance_validation_status",
        "full_a_provenance_validation_error",
        "full_a_provenance_closure_eligible",
        "full_a_provenance_boundary",
        "full_a_provenance_as_of_date",
        "full_a_provenance_universe_symbol_count",
        "full_a_provenance_clean_symbol_count",
        "full_a_provenance_clean_pool_removed_symbol_count",
        "full_a_provenance_final_prices_symbol_count",
        "full_a_provenance_final_prices_symbol_set_sha256",
        "full_a_provenance_final_filter_removed_symbol_count",
        "full_a_provenance_final_filter_removed_symbols",
        "full_a_provenance_final_scoring_validated",
        "full_a_provenance_candidate_symbol_count",
        "full_a_provenance_diagnostic_symbol_count",
        "full_a_provenance_output_cleanup_errors",
    )
    return {key: manifest.get(key) for key in keys}


def summary_source(input_metadata: dict[str, Any], manifest: dict[str, Any]) -> str:
    source = input_metadata.get("source")
    if source:
        return str(source)
    history_source = manifest.get("history_source")
    if history_source:
        return str(history_source)
    return "unknown"


def summary_source_scope(
    input_metadata: dict[str, Any], manifest: dict[str, Any]
) -> str:
    source_scope = input_metadata.get("source_scope")
    if source_scope:
        return str(source_scope)
    return str(manifest["source_scope"])


def input_csv_provenance(score: dict[str, Any]) -> dict[str, Any]:
    return {key: score[key] for key in INPUT_CSV_PROVENANCE_COLUMNS if key in score}


def source_provenance(
    input_metadata: dict[str, Any],
    score: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "source_type": input_metadata.get(
            "source_type", score.get("source_type", "unknown")
        ),
        "source_scope": summary_source_scope(input_metadata, manifest),
        "real_market_data": input_metadata.get(
            "real_market_data",
            score.get("real_market_data", "unknown"),
        ),
        "source": summary_source(input_metadata, manifest),
        "source_claim_boundary": input_metadata.get(
            "source_claim_boundary",
            score.get("source_claim_boundary", ""),
        ),
        "input_csv_source_type": score.get("source_type", "unknown"),
        "input_csv_source_scope": score.get("source_scope", "unknown"),
        "input_csv_real_market_data": score.get("real_market_data", "unknown"),
    }
    if "market_label_only" in input_metadata:
        fields["market_label_only"] = input_metadata["market_label_only"]
    return fields


def run_identity(manifest: dict[str, Any], status: str) -> dict[str, Any]:
    failed = [
        step
        for step in manifest["steps"]
        if step_executed(step)
        and step.get("returncode") not in step.get("allowed_returncodes", [])
    ]
    return {
        **run_status_fields(manifest, status),
        **history_request_fields(manifest),
        **prices_filter_artifact_fields(manifest),
        **prices_filter_coverage_fields(manifest),
        **prices_filter_status_fields(manifest),
        **score_runtime_fields(manifest),
        **spot_fetch_fields(manifest),
        **execution_decision_fields(manifest, failed),
    }


def run_status_fields(manifest: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "runner": manifest["runner"],
        "status": status,
        "execution_mode": manifest.get("execution_mode", "execute"),
        "commands_executed": bool(manifest.get("commands_executed", False)),
        "plan_only": bool(manifest.get("plan_only", False)),
        **plan_only_fields(manifest, status),
        "resume_from": manifest.get("resume_from", ""),
        "resume_symbol_source": manifest.get("resume_symbol_source", ""),
        "resume_retry_symbol_count": manifest.get("resume_retry_symbol_count", 0),
        "resume_sensitive_options_requiring_explicit_input": manifest.get(
            "resume_sensitive_options_requiring_explicit_input",
            [],
        ),
    }


def history_request_fields(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "history_source": manifest.get("history_source", ""),
        "history_limit": manifest.get("history_limit", ""),
        "history_max_pages": manifest.get("history_max_pages", ""),
        "history_max_concurrent_symbol_requests": manifest.get(
            "history_max_concurrent_symbol_requests",
            "",
        ),
        "history_max_rate_limit_sleep_seconds": manifest.get(
            "history_max_rate_limit_sleep_seconds", ""
        ),
        "history_max_429_events": manifest.get("history_max_429_events", ""),
        "history_max_runtime_seconds": manifest.get(
            "history_max_runtime_seconds", ""
        ),
        "history_non_trading_policy": manifest.get("history_non_trading_policy", ""),
        "history_checkpoint_batch_size": manifest.get(
            "history_checkpoint_batch_size",
            "",
        ),
        "history_checkpoint_dir": manifest.get("history_checkpoint_dir", ""),
        "history_resume_from_checkpoint": bool(
            manifest.get("history_resume_from_checkpoint", False)
        ),
        "history_progress_interval": manifest.get("history_progress_interval", ""),
    }


def prices_filter_artifact_fields(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
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
        "prices_filter_source_prices": manifest.get(
            "prices_filter_source_prices", ""
        ),
        "prices_filter_source_spot": manifest.get("prices_filter_source_spot", ""),
        "prices_filter_input_rows": int(
            manifest.get("prices_filter_input_rows", 0) or 0
        ),
        "prices_filter_output_rows": int(
            manifest.get("prices_filter_output_rows", 0) or 0
        ),
    }


def prices_filter_coverage_fields(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "prices_filter_spot_symbol_count": int(
            manifest.get("prices_filter_spot_symbol_count", 0) or 0
        ),
        "prices_filter_spot_symbol_set_sha256": manifest.get(
            "prices_filter_spot_symbol_set_sha256", ""
        ),
        "prices_filter_input_symbol_count": int(
            manifest.get("prices_filter_input_symbol_count", 0) or 0
        ),
        "prices_filter_input_symbol_set_sha256": manifest.get(
            "prices_filter_input_symbol_set_sha256", ""
        ),
        "prices_filter_kept_symbol_count": int(
            manifest.get("prices_filter_kept_symbol_count", 0) or 0
        ),
        "prices_filter_kept_symbol_set_sha256": manifest.get(
            "prices_filter_kept_symbol_set_sha256", ""
        ),
        "prices_filter_removed_symbol_count": int(
            manifest.get("prices_filter_removed_symbol_count", 0) or 0
        ),
        "prices_filter_removed_symbols": manifest.get(
            "prices_filter_removed_symbols", []
        ),
        "prices_filter_removed_symbol_set_sha256": manifest.get(
            "prices_filter_removed_symbol_set_sha256", ""
        ),
        "prices_filter_removed_stale_symbol_count": int(
            manifest.get("prices_filter_removed_stale_symbol_count", 0) or 0
        ),
        "prices_filter_removed_stale_symbols": manifest.get(
            "prices_filter_removed_stale_symbols", []
        ),
    }


def prices_filter_status_fields(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "prices_filter_output_written": bool(
            manifest.get("prices_filter_output_written", False)
        ),
        "prices_filter_failure_reason": manifest.get(
            "prices_filter_failure_reason", ""
        ),
        "prices_filter_error": manifest.get("prices_filter_error", ""),
        "prices_filter_duration_seconds": manifest.get(
            "prices_filter_duration_seconds", 0.0
        ),
        "prices_filter_claim_boundary": manifest.get(
            "prices_filter_claim_boundary", ""
        ),
    }


def score_runtime_fields(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "score_profile_output": manifest.get("score_profile_output", ""),
        "score_profile_enabled": bool(manifest.get("score_profile_enabled", False)),
        "score_profile_output_written": bool(
            manifest.get("score_profile_output_written", False)
        ),
        "score_profile_rows": int(manifest.get("score_profile_rows", 0) or 0),
        "score_profile_duration_seconds": manifest.get(
            "score_profile_duration_seconds", 0.0
        ),
        "score_profile_input_rows_per_second": manifest.get(
            "score_profile_input_rows_per_second"
        ),
        "score_profile_scored_symbols_per_second": manifest.get(
            "score_profile_scored_symbols_per_second"
        ),
        "symbol_derivation_duration_seconds": manifest.get(
            "symbol_derivation_duration_seconds", 0.0
        ),
        "html_report_duration_seconds": manifest.get(
            "html_report_duration_seconds", 0.0
        ),
        "finalize_duration_seconds": manifest.get("finalize_duration_seconds", 0.0),
        "run_duration_seconds": manifest.get("run_duration_seconds", 0.0),
        "history_request_interval_seconds": manifest.get(
            "history_request_interval_seconds",
            "",
        ),
        "history_timeout_seconds": manifest.get("history_timeout_seconds", ""),
    }


def spot_fetch_fields(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "fetch_spot": manifest.get("fetch_spot", ""),
        "fetch_spot_fallback": manifest.get("fetch_spot_fallback", ""),
        "spot_fallback_lookback_days": manifest.get("spot_fallback_lookback_days", ""),
        "spot_fallback_retries": manifest.get("spot_fallback_retries", ""),
        "spot_fallback_retry_interval_seconds": manifest.get(
            "spot_fallback_retry_interval_seconds",
            "",
        ),
        "fetch_spot_fallback_used": bool(
            manifest.get("fetch_spot_fallback_used", False)
        ),
        "fetch_spot_primary_failure": manifest.get("fetch_spot_primary_failure", {}),
        "spot_pages": manifest.get("spot_pages", ""),
        "spot_page_size": manifest.get("spot_page_size", ""),
    }


def execution_decision_fields(
    manifest: dict[str, Any], failed: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "planned_parameters": planned_parameters(manifest),
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
        "requested_mode": manifest.get("requested_mode", manifest["mode"]),
        "mode": manifest["mode"],
        "mode_decision": manifest.get("mode_decision", ""),
        "mode_decision_reason": manifest.get("mode_decision_reason", ""),
        "missing_prediction_column_groups": manifest.get(
            "missing_prediction_column_groups",
            [],
        ),
        "missing_prediction_requirement": manifest.get(
            "missing_prediction_requirement", ""
        ),
        "steps": len(manifest["steps"]),
        "failed_steps": [step["step"] for step in failed],
        "step_summary": step_summary(manifest),
        "failed_step_details": [failed_step_detail(step) for step in failed],
        "run_error_type": manifest.get("run_error_type", ""),
        "run_error": manifest.get("run_error", ""),
    }


def plan_only_fields(manifest: dict[str, Any], status: str) -> dict[str, Any]:
    if not bool(manifest.get("plan_only", False)):
        return {
            "plan_only_reason": "",
            "plan_only_next_action": "",
        }
    if status == "planned":
        return {
            "plan_only_reason": "plan_only_no_commands_executed",
            "plan_only_next_action": "execute_planned_workflow_to_collect_artifacts",
        }
    return {
        "plan_only_reason": "plan_only_failed_before_execution_completed",
        "plan_only_next_action": "inspect_run_error_and_fix_plan_options",
    }


def planned_parameters(manifest: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if manifest.get("fetch_spot"):
        add_planned_values(
            result,
            manifest,
            ("fetch_spot", "spot_pages"),
        )
        if manifest.get("fetch_spot") == "baostock_universe":
            add_planned_values(
                result,
                manifest,
                (
                    "spot_fallback_lookback_days",
                    "spot_fallback_retries",
                    "spot_fallback_retry_interval_seconds",
                ),
            )
        if manifest.get("fetch_spot_fallback"):
            add_planned_values(
                result,
                manifest,
                (
                    "fetch_spot_fallback",
                    "spot_fallback_lookback_days",
                    "spot_fallback_retries",
                    "spot_fallback_retry_interval_seconds",
                ),
            )
    if manifest.get("filter_prices_to_spot_universe"):
        result["filter_prices_to_spot_universe"] = True
    if manifest.get("prices_filter_min_symbol_latest_date"):
        result["min_symbol_latest_date"] = manifest[
            "prices_filter_min_symbol_latest_date"
        ]
    if manifest.get("history_source"):
        add_planned_values(
            result,
            manifest,
            (
                "history_source",
                "history_limit",
                "history_max_pages",
                "history_max_concurrent_symbol_requests",
                "history_max_rate_limit_sleep_seconds",
                "history_max_429_events",
                "history_max_runtime_seconds",
                "history_request_interval_seconds",
                "history_timeout_seconds",
                "history_non_trading_policy",
                "history_checkpoint_batch_size",
                "history_progress_interval",
                "start_date",
                "end_date",
            ),
        )
        if manifest.get("derive_symbols_from_spot"):
            if manifest.get("derive_all_spot_symbols"):
                result["derive_all_spot_symbols"] = True
            add_planned_values(result, manifest, ("max_history_symbols",))
    return result


def add_planned_values(
    result: dict[str, Any],
    manifest: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    for key in keys:
        value = manifest.get(key)
        if value not in ("", None):
            result[key] = value


def step_summary(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [step_summary_record(step) for step in manifest["steps"]]


def step_summary_record(step: dict[str, Any]) -> dict[str, Any]:
    record = {
        "step": step.get("step", ""),
        "planned": bool(step.get("planned", False)),
        "executed": step_executed(step),
        "returncode": step.get("returncode"),
    }
    if "duration_seconds" in step:
        record["duration_seconds"] = step.get("duration_seconds")
    return record


def failed_step_detail(step: dict[str, Any]) -> dict[str, Any]:
    stderr = str(step.get("stderr", "") or "")
    stdout = str(step.get("stdout", "") or "")
    return {
        "step": step.get("step", ""),
        "returncode": step.get("returncode"),
        "allowed_returncodes": step.get("allowed_returncodes", []),
        "stderr_first_line": first_nonempty_line(stderr),
        "stdout_first_line": first_nonempty_line(stdout),
        "stderr_line_count": nonempty_line_count(stderr),
    }


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def nonempty_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def prediction_fields(
    manifest: dict[str, Any], score: dict[str, Any]
) -> dict[str, Any]:
    return {
        "prediction_mode": manifest["prediction_mode"],
        "consumes_prediction_columns": helpers.prediction_columns_consumed(
            manifest, score
        ),
        "prediction_input_source": helpers.prediction_input_source(manifest),
        "requested_prediction_input_source": manifest.get(
            "requested_prediction_input_source",
            manifest.get("prediction_input_source", "unknown"),
        ),
        "prediction_model_executed_by_runner": (
            helpers.prediction_model_executed_by_runner(manifest)
        ),
        "prediction_claim_boundary": helpers.prediction_claim_boundary(manifest, score),
        "lightgbm_not_used": manifest["lightgbm_not_used"],
        "lightgbm_output_source": manifest.get("lightgbm_output_source", "unknown"),
        "requested_lightgbm_output_source": manifest.get(
            "requested_lightgbm_output_source",
            manifest.get("lightgbm_output_source", "unknown"),
        ),
        "lightgbm_executed_by_runner": manifest.get(
            "lightgbm_executed_by_runner", False
        ),
    }


def row_count_fields(
    manifest: dict[str, Any],
    paths: dict[str, Path],
    score: dict[str, Any],
    history_selection: dict[str, Any],
    initialized: bool,
) -> dict[str, Any]:
    history_count = history_symbol_count(manifest, history_selection)
    return {
        "spot_metadata": helpers.spot_metadata_view(manifest) if initialized else {},
        "spot_rows": helpers.spot_rows(manifest) if initialized else 0,
        "spot_matched_symbols": score.get("spot_matched_symbols", 0),
        "history_selection": history_selection,
        "history_symbol_count": history_count,
        "history_symbol_count_label": history_symbol_count_label(
            manifest,
            history_count,
        ),
        **history_metadata_summary_fields(history_selection),
        **short_history_artifact_fields(manifest),
        "prices_rows": row_count(paths["prices"], initialized),
        "candidate_rows": row_count(paths["candidates"], initialized),
        "diagnostic_rows": row_count(paths["diagnostics"], initialized),
        "spot_output": str(paths["spot"]) if paths["spot"] else "",
        "spot_output_written": output_file_written(paths["spot"], initialized),
        "spot_metadata_output": str(paths["spot_metadata"]),
        "spot_metadata_output_written": output_file_written(
            paths["spot_metadata"], initialized
        ),
    }


def short_history_artifact_fields(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "short_history_symbol_count": int(
            manifest.get("short_history_symbol_count", 0) or 0
        ),
        "short_history_symbols_output": str(
            manifest.get("short_history_symbols_output", "") or ""
        ),
        "short_history_symbols_metadata_output": str(
            manifest.get("short_history_symbols_metadata_output", "") or ""
        ),
    }


def empty_result_fields(score: dict[str, Any]) -> dict[str, Any]:
    return {
        "effective_empty_result": score.get("effective_empty_result", False),
        "empty_result_reason": score.get("empty_result_reason", ""),
    }


def row_count(path: Path, initialized: bool) -> int:
    return helpers.tabular_row_count(path) if initialized else 0


def output_path_fields(paths: dict[str, Path], initialized: bool) -> dict[str, Any]:
    return {
        "prices_output": str(paths["prices"]),
        "prices_output_written": output_file_written(paths["prices"], initialized),
        "candidates_output": str(paths["candidates"]),
        "candidates_output_written": output_file_written(
            paths["candidates"], initialized
        ),
        "diagnostics_output": str(paths["diagnostics"]),
        "diagnostics_output_written": output_file_written(
            paths["diagnostics"], initialized
        ),
        "selected_symbols_output": str(paths["selected_symbols"]),
        "selected_symbols_output_written": output_file_written(
            paths["selected_symbols"], initialized
        ),
        "history_metadata_output": str(paths["history_metadata"]),
        "history_metadata_file_exists": output_file_written(
            paths["history_metadata"], initialized
        ),
        "summary_output": str(paths["summary"]),
        "summary_output_written": output_file_written(paths["summary"], initialized),
        "manifest_output": str(paths["manifest"]),
        "manifest_output_written": output_file_written(paths["manifest"], initialized),
    }


def output_file_written(path: Path | None, initialized: bool) -> bool:
    return bool(initialized and path is not None and path.is_file())


def history_selection_view(manifest: dict[str, Any]) -> dict[str, Any]:
    if not manifest.get("run_outputs_initialized"):
        return {}
    output_dir = Path(manifest["output_dir"])
    selected_path = output_dir / "selected_symbols.json"
    metadata_path = output_dir / "history_metadata.json"
    if not history_selection_available(manifest, selected_path, metadata_path):
        return {}
    selected_data = read_json_if_exists(selected_path)
    metadata = read_json_if_exists(metadata_path)
    metadata_exists = metadata_path.is_file()
    selected_symbols = selected_symbol_values(selected_data, manifest)
    view = {
        **history_selection_source_fields(
            selected_data,
            selected_symbols,
            manifest,
        ),
        **history_performance_fields(metadata, manifest),
        **history_quality_fields(metadata, metadata_exists),
        **history_date_range_view(metadata, manifest),
        **history_selection_path_fields(selected_path, metadata_path),
    }
    add_optional_history_fields(view, metadata)
    return view


def history_selection_source_fields(
    selected_data: dict[str, Any],
    selected_symbols: list[str],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source": selected_data.get("source", ""),
        "preflight_stage": selected_data.get("preflight_stage", ""),
        "selection_failed": bool(selected_data.get("selection_failed", False)),
        "selection_failed_reason": selected_data.get("selection_failed_reason", ""),
        "selection_failed_next_action": selected_data.get(
            "selection_failed_next_action",
            selected_data.get("next_action", ""),
        ),
        "raw_spot_rows": selected_data.get("raw_spot_rows"),
        "filtered_spot_rows": selected_data.get("filtered_spot_rows"),
        "selected_symbol_count": selected_symbol_count(selected_data, selected_symbols),
        "max_history_symbols": history_limit_value(selected_data, manifest),
        "history_symbol_limit_source": history_limit_source(selected_data, manifest),
        "allow_partial_history": bool(manifest.get("allow_partial_history", False)),
    }


def history_performance_fields(
    metadata: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    fetch_duration = executed_step_duration(manifest, "fetch_history")
    history_rows = int(metadata.get("rows", 0) or 0)
    history_symbols = int(metadata.get("symbol_count", 0) or 0)
    return {
        "history_partial_result": history_partial_result(metadata),
        "history_rows": history_rows,
        "history_fetch_duration_seconds": fetch_duration,
        "history_rows_per_second": (
            round(history_rows / fetch_duration, 6)
            if history_rows and fetch_duration
            else None
        ),
        "history_symbols_per_second": (
            round(history_symbols / fetch_duration, 6)
            if history_symbols and fetch_duration
            else None
        ),
        "history_raw_rows": int(metadata.get("raw_rows", 0) or 0),
        "history_output_rows": int(
            metadata.get("output_rows", metadata.get("rows", 0)) or 0
        ),
        "history_requested_raw_rows": int(
            metadata.get("requested_raw_rows", 0) or 0
        ),
        "history_api_request_count": int(metadata.get("api_request_count", 0) or 0),
        "history_overfetch_rows": int(metadata.get("overfetch_rows", 0) or 0),
        "history_raw_to_output_ratio": metadata.get("raw_to_output_ratio"),
        "history_duration_seconds": metadata.get("duration_seconds"),
        "history_rate_limit_429_events": int(
            metadata.get("rate_limit_429_events", 0) or 0
        ),
        "history_rate_limit_sleep_seconds": float(
            metadata.get("rate_limit_sleep_seconds", 0) or 0
        ),
        "history_network_retry_events": int(
            metadata.get("network_retry_events", 0) or 0
        ),
        "history_network_retry_sleep_seconds": float(
            metadata.get("network_retry_sleep_seconds", 0) or 0
        ),
    }


def history_quality_fields(
    metadata: dict[str, Any], metadata_exists: bool
) -> dict[str, Any]:
    failed_symbols = metadata_list(metadata, "failed_symbols")
    empty_symbols = metadata_list(metadata, "empty_symbols")
    truncated_symbols = metadata_list(metadata, "possibly_truncated_symbols")
    unprocessed_symbols = metadata_list(metadata, "unprocessed_symbols")
    fallback_errors = metadata_list(metadata, "fallback_errors")
    return {
        "history_metadata_symbol_count": int(metadata.get("symbol_count", 0) or 0),
        "history_requested_symbol_count": len(
            metadata_list(metadata, "requested_symbols")
        ),
        "history_output_written": metadata_bool(
            metadata,
            "output_written",
            missing_default=False,
        ),
        "history_metadata_output_written": metadata_bool(
            metadata,
            "metadata_output_written",
            missing_default=metadata_exists,
        ),
        "history_artifact_status": history_artifact_status(metadata, metadata_exists),
        "history_failed_symbol_count": len(failed_symbols),
        "history_metadata_failed_symbol_count": len(failed_symbols),
        "history_metadata_failed_symbols": failed_symbols,
        "history_empty_symbol_count": len(empty_symbols),
        "history_empty_symbols": empty_symbols,
        "history_possibly_truncated_symbol_count": len(truncated_symbols),
        "history_possibly_truncated_symbols": truncated_symbols,
        "history_unprocessed_symbol_count": len(unprocessed_symbols),
        "history_unprocessed_symbols": unprocessed_symbols,
        "history_rate_limit_budget_exhausted": (
            metadata.get("rate_limit_budget_exhausted") is True
        ),
        "history_rate_limit_exhaustion_reason": str(
            metadata.get("rate_limit_exhaustion_reason", "")
        ),
        "history_invalid_rows": int(metadata.get("invalid_rows", 0) or 0),
        "history_dropped_invalid_rows": int(
            metadata.get("dropped_invalid_rows", 0) or 0
        ),
        "history_raw_non_trading_rows": int(
            metadata.get("raw_non_trading_rows", 0) or 0
        ),
        "history_raw_invalid_non_trading_overlap_rows": int(
            metadata.get("raw_invalid_non_trading_overlap_rows", 0) or 0
        ),
        "history_raw_quality_counter_semantics": str(
            metadata.get("raw_quality_counter_semantics", "")
        ),
        "history_non_trading_rows": int(metadata.get("non_trading_rows", 0) or 0),
        "history_tradestatus_missing_rows": int(
            metadata.get("tradestatus_missing_rows", 0) or 0
        ),
        "history_metadata_fallback_error_count": len(fallback_errors),
        "history_metadata_fallback_errors": fallback_errors,
        "history_metadata_symbol_providers": symbol_providers(metadata),
    }


def history_selection_path_fields(
    selected_path: Path, metadata_path: Path
) -> dict[str, Any]:
    return {
        "selected_symbols_output": str(selected_path),
        "selected_symbols_output_written": selected_path.is_file(),
        "history_metadata_output": str(metadata_path),
        "history_metadata_file_exists": metadata_path.is_file(),
    }


def add_optional_history_fields(
    view: dict[str, Any], metadata: dict[str, Any]
) -> None:
    if "adjust" in metadata:
        view["history_adjust"] = metadata["adjust"]
    if "adjustflag" in metadata:
        view["history_adjustflag"] = str(metadata["adjustflag"])
    if "token_configured" in metadata:
        view["history_token_configured"] = bool(metadata["token_configured"])
    for source_key, view_key in (
        ("fields", "history_fields"),
        ("request_interval_seconds", "history_request_interval_seconds"),
        (
            "max_concurrent_symbol_requests",
            "history_max_concurrent_symbol_requests",
        ),
        ("max_rate_limit_sleep_seconds", "history_max_rate_limit_sleep_seconds"),
        ("max_429_events", "history_max_429_events"),
        ("max_runtime_seconds", "history_max_runtime_seconds"),
        ("limit", "history_limit"),
        ("max_pages", "history_max_pages"),
        ("non_trading_policy", "history_non_trading_policy"),
        ("dropped_non_trading_rows", "history_dropped_non_trading_rows"),
        ("retained_non_trading_rows", "history_retained_non_trading_rows"),
        ("checkpoint_enabled", "history_checkpoint_enabled"),
        ("resume_from_checkpoint", "history_resume_from_checkpoint"),
        ("checkpoint_batch_size", "history_checkpoint_batch_size"),
        ("checkpoint_symbols_skipped", "history_checkpoint_symbols_skipped"),
        ("checkpoint_requests_executed", "history_checkpoint_requests_executed"),
        ("checkpoint_parts_written", "history_checkpoint_parts_written"),
        ("checkpoint_parts_available", "history_checkpoint_parts_available"),
        ("checkpoint_dir", "history_checkpoint_dir"),
        ("checkpoint_manifest", "history_checkpoint_manifest"),
    ):
        if source_key in metadata:
            view[view_key] = metadata[source_key]


def candidate_field_coverage(path: Path, initialized: bool) -> dict[str, Any]:
    if not initialized or not path.is_file() or path.suffix.lower() != ".csv":
        return {}
    present_rows = {key: 0 for key in OPTIONAL_CANDIDATE_FIELD_ALIASES}
    total_rows = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_rows += 1
            update_candidate_field_counts(row, present_rows)
    fields = {
        key: candidate_field_counts(present, total_rows)
        for key, present in present_rows.items()
    }
    return {
        "rows_evaluated": total_rows,
        "all_fields_present": total_rows > 0
        and all(field["present_rows"] == total_rows for field in fields.values()),
        "fields": fields,
    }


def update_candidate_field_counts(
    row: dict[str, str],
    present_rows: dict[str, int],
) -> None:
    for key, aliases in OPTIONAL_CANDIDATE_FIELD_ALIASES.items():
        if any(candidate_field_value_present(row.get(alias)) for alias in aliases):
            present_rows[key] += 1


def candidate_field_counts(present_rows: int, total_rows: int) -> dict[str, Any]:
    missing_rows = max(total_rows - present_rows, 0)
    ratio = round((present_rows / total_rows), 4) if total_rows else 0.0
    return {
        "present_rows": present_rows,
        "missing_rows": missing_rows,
        "coverage_ratio": ratio,
    }


def history_selection_available(
    manifest: dict[str, Any],
    selected_path: Path,
    metadata_path: Path,
) -> bool:
    return (
        selected_path.is_file()
        or metadata_path.is_file()
        or bool(manifest.get("history_symbols"))
    )


def read_json_if_exists(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def selected_symbol_values(
    selected_data: dict[str, Any],
    manifest: dict[str, Any],
) -> list[Any]:
    for key in ("selected_symbols", "symbols"):
        value = selected_data.get(key)
        if isinstance(value, list):
            return value
    value = manifest.get("history_symbols", [])
    if isinstance(value, list) and value == ["<derived_from_spot_snapshot>"]:
        return []
    return value if isinstance(value, list) else []


def selected_symbol_count(
    selected_data: dict[str, Any], selected_symbols: list[Any]
) -> int:
    value = selected_data.get("selected_symbol_count")
    if value is None:
        return len(selected_symbols)
    return int(value)


def history_limit_value(selected_data: dict[str, Any], manifest: dict[str, Any]) -> Any:
    if explicit_history_symbols(selected_data, manifest):
        return selected_data.get("max_history_symbols", "")
    return selected_data.get(
        "max_history_symbols", manifest.get("max_history_symbols", 0)
    )


def history_limit_source(
    selected_data: dict[str, Any], manifest: dict[str, Any]
) -> str:
    source = selected_data.get("history_symbol_limit_source")
    if source:
        return str(source)
    if explicit_history_symbols(selected_data, manifest):
        return "explicit_symbols_no_spot_limit"
    if not bool(manifest.get("max_history_symbols_supplied", False)):
        return "small_sample_default_cap"
    return "explicit_user_input"


def explicit_history_symbols(
    selected_data: dict[str, Any], manifest: dict[str, Any]
) -> bool:
    return (
        selected_data.get("source") == "explicit_symbols"
        or manifest.get("execution_path_reason") == "explicit_symbols"
    )


def metadata_list(metadata: dict[str, Any], key: str) -> list[Any]:
    value = metadata.get(key, [])
    return value if isinstance(value, list) else []


def history_date_range_view(
    metadata: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    requested = normalized_history_date(
        metadata.get("end_date") or manifest.get("end_date") or ""
    )
    ranges = symbol_date_ranges(metadata)
    date_max_values = [item["date_max"] for item in ranges if item["date_max"]]
    actual_date_max = max(date_max_values) if date_max_values else ""
    reached = [item for item in ranges if item["date_max"] == requested and requested]
    return {
        "requested_end_date": requested,
        "history_metadata_actual_date_max": actual_date_max,
        "history_metadata_symbols_reached_end_date_count": len(reached),
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


def history_symbol_count(
    manifest: dict[str, Any], history_selection: dict[str, Any]
) -> int:
    if spot_derivation_placeholder(manifest):
        return 0
    if "selected_symbol_count" in history_selection:
        return int(history_selection["selected_symbol_count"])
    symbols = manifest.get("history_symbols", [])
    return len(symbols) if isinstance(symbols, list) else 0


def history_symbol_count_label(manifest: dict[str, Any], count: int) -> str:
    if spot_derivation_placeholder(manifest):
        return "planned_placeholder"
    return str(count)


def spot_derivation_placeholder(manifest: dict[str, Any]) -> bool:
    symbols = manifest.get("history_symbols", [])
    return (
        bool(manifest.get("plan_only", False))
        and isinstance(symbols, list)
        and symbols == ["<derived_from_spot_snapshot>"]
    )


def history_metadata_summary_fields(history_selection: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "history_rows",
        "history_fetch_duration_seconds",
        "history_rows_per_second",
        "history_symbols_per_second",
        "history_raw_rows",
        "history_output_rows",
        "history_requested_raw_rows",
        "history_api_request_count",
        "history_overfetch_rows",
        "history_raw_to_output_ratio",
        "history_duration_seconds",
        "history_rate_limit_429_events",
        "history_rate_limit_sleep_seconds",
        "history_network_retry_events",
        "history_network_retry_sleep_seconds",
        "history_max_rate_limit_sleep_seconds",
        "history_max_429_events",
        "history_max_runtime_seconds",
        "history_metadata_symbol_count",
        "history_requested_symbol_count",
        "history_partial_result",
        "history_output_written",
        "history_metadata_output_written",
        "history_artifact_status",
        "history_failed_symbol_count",
        "history_metadata_failed_symbol_count",
        "history_empty_symbol_count",
        "history_possibly_truncated_symbol_count",
        "history_unprocessed_symbol_count",
        "history_rate_limit_budget_exhausted",
        "history_rate_limit_exhaustion_reason",
        "history_invalid_rows",
        "history_dropped_invalid_rows",
        "history_raw_non_trading_rows",
        "history_raw_invalid_non_trading_overlap_rows",
        "history_raw_quality_counter_semantics",
        "history_non_trading_rows",
        "history_non_trading_policy",
        "history_dropped_non_trading_rows",
        "history_retained_non_trading_rows",
        "history_tradestatus_missing_rows",
        "history_metadata_fallback_error_count",
        "history_checkpoint_enabled",
        "history_resume_from_checkpoint",
        "history_checkpoint_batch_size",
        "history_checkpoint_symbols_skipped",
        "history_checkpoint_requests_executed",
        "history_checkpoint_parts_written",
        "history_checkpoint_parts_available",
        "history_checkpoint_schema_version",
        "history_checkpoint_execution_contract_sha256",
    )
    return {key: history_selection.get(key, default_history_value(key)) for key in keys}


def executed_step_duration(manifest: dict[str, Any], step_name: str) -> float:
    for step in manifest.get("steps", []):
        if (
            step.get("step") == step_name
            and step.get("planned") is not True
            and step.get("returncode") is not None
        ):
            return float(step.get("duration_seconds", 0.0) or 0.0)
    return 0.0


def selection_failure_fields(
    manifest: dict[str, Any],
    status: str,
    history_selection: dict[str, Any],
) -> dict[str, str]:
    reason = str(history_selection.get("selection_failed_reason", "") or "").strip()
    action = str(
        history_selection.get("selection_failed_next_action", "") or ""
    ).strip()
    if reason:
        return {
            "selection_failed_reason": reason,
            "selection_failed_next_action": action,
        }
    if status != "failed":
        return {
            "selection_failed_reason": "",
            "selection_failed_next_action": "",
        }
    reason, action = failed_run_reason(manifest)
    return {
        "selection_failed_reason": reason,
        "selection_failed_next_action": action,
    }


def failed_run_reason(manifest: dict[str, Any]) -> tuple[str, str]:
    failed_steps = [
        step
        for step in manifest["steps"]
        if step_executed(step)
        and step.get("returncode") not in step.get("allowed_returncodes", [])
    ]
    if manifest.get("missing_prediction_column_groups"):
        return (
            "missing_prediction_columns",
            "provide_prediction_or_prediction_score_or_use_generic_mode",
        )
    if failed_steps:
        first_step = str(failed_steps[0].get("step", "") or "unknown")
        if first_step == "validate":
            return (
                "validation_failed_before_scoring",
                "fix_input_columns_or_config_before_rerun",
            )
        if first_step == "score":
            return (
                "scoring_failed",
                "inspect_score_stderr_and_fix_input_or_config",
            )
        return (
            f"{first_step}_failed",
            "inspect_failed_step_details_and_rerun",
        )
    if manifest.get("run_error_type"):
        return (
            str(manifest.get("run_error_type")),
            "inspect_run_error_and_fix_command_options",
        )
    return (
        f"runner_failed_status_{manifest.get('status', 'unknown')}",
        "inspect_failed_step_details_and_rerun",
    )


def default_history_value(key: str) -> Any:
    if key in {
        "history_partial_result",
        "history_output_written",
        "history_metadata_output_written",
        "history_checkpoint_enabled",
        "history_resume_from_checkpoint",
        "history_rate_limit_budget_exhausted",
    }:
        return False
    if key == "history_artifact_status":
        return "not_written"
    if key == "history_non_trading_policy":
        return ""
    if key == "history_rate_limit_exhaustion_reason":
        return ""
    return 0


def history_artifact_status(metadata: dict[str, Any], metadata_exists: bool) -> str:
    if not metadata_exists:
        return "not_written"
    output_written = metadata_bool(
        metadata,
        "output_written",
        missing_default=False,
    )
    metadata_written = metadata_bool(
        metadata,
        "metadata_output_written",
        missing_default=metadata_exists,
    )
    if output_written and metadata_written:
        return "written"
    if output_written:
        return "inconsistent_metadata"
    if metadata_written:
        return "metadata_only"
    return "not_written"


def metadata_bool(
    metadata: dict[str, Any],
    key: str,
    *,
    missing_default: bool,
) -> bool:
    if key not in metadata:
        return missing_default
    value = metadata.get(key)
    return value if isinstance(value, bool) else False
