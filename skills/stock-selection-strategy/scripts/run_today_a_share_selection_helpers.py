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
    return {
        "runner": manifest["runner"],
        "status": status,
        "requested_mode": manifest.get("requested_mode", manifest["mode"]),
        "mode": manifest["mode"],
        "mode_decision": manifest.get("mode_decision", ""),
        "mode_decision_reason": manifest.get("mode_decision_reason", ""),
        "prediction_mode": manifest["prediction_mode"],
        "consumes_prediction_columns": manifest.get("consumes_prediction_columns", False),
        "prediction_input_source": prediction_input_source(manifest),
        "prediction_model_executed_by_runner": prediction_model_executed_by_runner(manifest),
        "lightgbm_not_used": manifest["lightgbm_not_used"],
        "lightgbm_output_source": manifest.get("lightgbm_output_source", "unknown"),
        "lightgbm_executed_by_runner": manifest.get("lightgbm_executed_by_runner", False),
        "source_scope": manifest["source_scope"],
        "steps": len(manifest["steps"]),
        "failed_steps": [step["step"] for step in failed],
        "spot_metadata": spot_metadata_view(manifest),
        "spot_rows": spot_rows(manifest),
        "prices_rows": tabular_row_count(prices),
        "candidate_rows": tabular_row_count(candidates),
        "diagnostic_rows": tabular_row_count(diagnostics),
        "score": score_summary(manifest),
        "prices_output": str(prices),
        "candidates_output": str(candidates),
        "diagnostics_output": str(diagnostics),
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
    if not path.exists():
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
            parsed["threshold_failures"] = line.split("=", 1)[1]
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


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_summary(manifest: dict[str, Any], output: Path) -> None:
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
        f"manifest={output / 'run_manifest.json'} summary={output / 'summary.json'}"
    )
