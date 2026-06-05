"""Helpers for the local A-share selection runner."""

from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any


def summary_view(manifest: dict[str, Any], status: str) -> dict[str, Any]:
    failed = [step for step in manifest["steps"] if step["returncode"] not in step["allowed_returncodes"]]
    prices = prices_output_path(manifest)
    candidates = Path(manifest["output_dir"]) / "candidates.csv"
    diagnostics = Path(manifest["output_dir"]) / "diagnostics.csv"
    score = score_summary(manifest)
    run_outputs_initialized = bool(manifest.get("run_outputs_initialized"))
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
        "prediction_mode": manifest["prediction_mode"],
        "consumes_prediction_columns": prediction_columns_consumed(manifest, score),
        "prediction_input_source": prediction_input_source(manifest),
        "prediction_model_executed_by_runner": prediction_model_executed_by_runner(manifest),
        "lightgbm_not_used": manifest["lightgbm_not_used"],
        "lightgbm_output_source": manifest.get("lightgbm_output_source", "unknown"),
        "lightgbm_executed_by_runner": manifest.get("lightgbm_executed_by_runner", False),
        "source_scope": manifest["source_scope"],
        "input_metadata": manifest.get("input_metadata", {}),
        "steps": len(manifest["steps"]),
        "failed_steps": [step["step"] for step in failed],
        "spot_metadata": spot_metadata_view(manifest) if run_outputs_initialized else {},
        "spot_rows": spot_rows(manifest) if run_outputs_initialized else 0,
        "spot_matched_symbols": score.get("spot_matched_symbols", 0),
        "prices_rows": tabular_row_count(prices) if run_outputs_initialized else 0,
        "candidate_rows": tabular_row_count(candidates) if run_outputs_initialized else 0,
        "diagnostic_rows": tabular_row_count(diagnostics) if run_outputs_initialized else 0,
        "score": score,
        "prices_output": str(prices),
        "prices_output_written": run_outputs_initialized and prices.exists(),
        "candidates_output": str(candidates),
        "candidates_output_written": run_outputs_initialized and candidates.exists(),
        "diagnostics_output": str(diagnostics),
        "diagnostics_output_written": run_outputs_initialized and diagnostics.exists(),
        "boundary": boundary_for(manifest),
    }


def prices_output_path(manifest: dict[str, Any]) -> Path:
    source = str(manifest.get("prices_input", ""))
    suffix = tabular_suffix(source)
    return Path(manifest["output_dir"]) / f"prices{suffix}"


def prediction_input_source(manifest: dict[str, Any]) -> str:
    return str(manifest.get("prediction_input_source", manifest.get("lightgbm_output_source", "unknown")))


def prediction_model_executed_by_runner(manifest: dict[str, Any]) -> bool:
    return bool(
        manifest.get(
            "prediction_model_executed_by_runner",
            manifest.get("lightgbm_executed_by_runner", False),
        )
    )


def prediction_columns_consumed(
    manifest: dict[str, Any],
    score: dict[str, Any] | None = None,
) -> bool:
    if not manifest.get("prediction_mode"):
        return False
    summary = score if score is not None else score_summary(manifest)
    return str(summary.get("prediction_input_source", "")) == "external_input"


def spot_metadata_view(manifest: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(manifest["output_dir"])
    metadata_path = output_dir / "spot_metadata.json"
    if not metadata_path.exists():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    keys = [
        "source",
        "source_scope",
        "requested_pages",
        "retry_attempts_per_page",
        "successful_pages",
        "pages_successful",
        "failed_pages",
        "pages_failed",
        "raw_items",
        "filtered_items",
        "partial_result",
        "allowed_failure_actions",
    ]
    return {key: data.get(key) for key in keys if key in data}


def spot_rows(manifest: dict[str, Any]) -> int:
    metadata = spot_metadata_view(manifest)
    if metadata:
        filtered_items = metadata.get("filtered_items")
        raw_items = metadata.get("raw_items")
        if filtered_items is not None:
            return int(filtered_items)
        if raw_items is not None:
            return int(raw_items)
        return 0
    output_dir = Path(manifest["output_dir"])
    if not manifest.get("spot_input"):
        return 0
    spot_path = output_dir / f"spot{tabular_suffix(str(manifest['spot_input']))}"
    if not spot_path.exists():
        return 0
    return tabular_row_count(spot_path)


def tabular_suffix(source: str | Path) -> str:
    suffix = Path(source).suffix.lower()
    return suffix if suffix in {".csv", ".parquet", ".pq"} else ".csv"


def tabular_row_count(path: Path) -> int:
    if not path.is_file():
        return 0
    if path.suffix.lower() in {".parquet", ".pq"}:
        return parquet_row_count(path)
    if path.suffix.lower() != ".csv":
        return 0
    with path.open(encoding="utf-8") as handle:
        return max(sum(1 for _row in csv.reader(handle)) - 1, 0)


def parquet_row_count(path: Path) -> int:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        import pandas as pd

        return int(len(pd.read_parquet(path)))
    return int(pq.ParquetFile(path).metadata.num_rows)


def boundary_for(manifest: dict[str, Any]) -> str:
    decision = manifest.get("mode_decision", "")
    reason = manifest.get("mode_decision_reason", "")
    if manifest["prediction_mode"]:
        if not prediction_columns_consumed(manifest):
            return (
                "Prediction mode was requested, but the runner did not consume prediction "
                "columns because scoring did not complete. "
                f"prediction_input_source={prediction_input_source(manifest)} "
                f"prediction_model_executed_by_runner={str(prediction_model_executed_by_runner(manifest)).lower()} "
                "lightgbm_executed_by_runner=false "
                f"mode_decision={decision} reason={reason}"
            )
        return (
            "prediction-derived mode requires external prediction or prediction_score in the input. "
            "The runner consumes prediction columns from input and does not execute a prediction model. "
            f"prediction_input_source={prediction_input_source(manifest)} "
            f"prediction_model_executed_by_runner={str(prediction_model_executed_by_runner(manifest)).lower()} "
            f"lightgbm_output_source={manifest.get('lightgbm_output_source', 'unknown')} "
            f"lightgbm_executed_by_runner=false mode_decision={decision} reason={reason}"
        )
    return (
        "Generic technical mode; not prediction-derived and not LightGBM-backed. "
        f"consumes_prediction_columns={str(manifest.get('consumes_prediction_columns', False)).lower()} "
        f"prediction_input_source={prediction_input_source(manifest)} "
        f"prediction_model_executed_by_runner={str(prediction_model_executed_by_runner(manifest)).lower()} "
        f"lightgbm_executed_by_runner=false mode_decision={decision} reason={reason}"
    )


def score_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    for step in reversed(manifest["steps"]):
        if step["step"] == "score":
            return parse_score_stdout(step.get("stdout", ""))
    return {}


def parse_score_stdout(stdout: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for line in stdout.splitlines():
        if line.startswith("OK: ") or line.startswith("ERROR_SUMMARY: "):
            parsed.update(parse_key_values(line.split(": ", 1)[1]))
        elif line.startswith("INFO: threshold_failures="):
            counts_text = line.split("=", 1)[1]
            parsed["threshold_failures"] = counts_text
            parsed["threshold_failures_by_rule"] = parse_count_pairs(counts_text)
    return parsed


def parse_key_values(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in text.split():
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parsed[key] = parse_value(value)
    return parsed


def parse_value(value: str) -> Any:
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def parse_count_pairs(text: str) -> dict[str, int]:
    counts = {}
    for item in text.split(","):
        if not item or ":" not in item:
            continue
        name, count = item.split(":", 1)
        try:
            counts[name] = int(count)
        except ValueError:
            continue
    return counts


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def same_existing_path(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return False


def print_summary(manifest: dict[str, Any], output: Path) -> None:
    from run_today_a_share_selection_outputs import (
        html_report_error_stdout,
        html_report_stdout_value,
    )

    view = summary_view(manifest, "completed")
    paths = f"manifest={output / 'run_manifest.json'} summary={output / 'summary.json'}"
    html_report = html_report_stdout_value(manifest, output)
    html_error = html_report_error_stdout(manifest)
    print(
        "OK: runner=run_today_a_share_selection "
        f"mode={manifest['mode']} steps={len(manifest['steps'])} "
        f"prediction_mode={str(manifest['prediction_mode']).lower()} "
        f"consumes_prediction_columns={str(manifest.get('consumes_prediction_columns', False)).lower()} "
        f"prediction_input_source={prediction_input_source(manifest)} "
        f"prediction_model_executed_by_runner={str(prediction_model_executed_by_runner(manifest)).lower()} "
        f"lightgbm_not_used={str(manifest['lightgbm_not_used']).lower()} "
        f"lightgbm_output_source={manifest.get('lightgbm_output_source', 'unknown')} "
        "lightgbm_executed_by_runner=false "
        f"prices_rows={view['prices_rows']} "
        f"candidate_rows={view['candidate_rows']} "
        f"diagnostic_rows={view['diagnostic_rows']} "
        f"spot_matched_symbols={view['spot_matched_symbols']} "
        f"{paths} html_report={html_report}{html_error}"
    )
