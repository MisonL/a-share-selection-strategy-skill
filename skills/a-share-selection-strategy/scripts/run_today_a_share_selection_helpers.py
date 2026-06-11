"""Helpers for the local A-share selection runner."""

from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any


def summary_view(manifest: dict[str, Any], status: str) -> dict[str, Any]:
    from run_today_a_share_selection_summary import summary_view as build_summary_view

    return build_summary_view(manifest, status)


def prices_output_path(manifest: dict[str, Any]) -> Path:
    source = str(manifest.get("prices_input", ""))
    suffix = tabular_suffix(source)
    return Path(manifest["output_dir"]) / f"prices{suffix}"


def spot_output_path(manifest: dict[str, Any]) -> Path | None:
    output_dir = Path(manifest["output_dir"])
    if (
        not manifest.get("spot_input")
        and not manifest.get("fetch_spot")
        and not (output_dir / "spot_metadata.json").exists()
    ):
        return None
    source = str(manifest.get("spot_input", ""))
    return output_dir / f"spot{tabular_suffix(source)}"


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


def prediction_claim_boundary(
    manifest: dict[str, Any],
    score: dict[str, Any] | None = None,
) -> str:
    if not manifest.get("prediction_mode"):
        return "not_prediction_derived"
    if prediction_columns_consumed(manifest, score):
        return "external_input_columns_consumed_runner_does_not_execute_prediction_model"
    return "prediction_columns_not_consumed_scoring_not_completed"


def spot_metadata_view(manifest: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(manifest["output_dir"])
    metadata_path = output_dir / "spot_metadata.json"
    if not metadata_path.exists():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    keys = [
        "source",
        "source_scope",
        "snapshot_time",
        "requested_pages",
        "retry_attempts_per_page",
        "successful_pages",
        "pages_successful",
        "failed_pages",
        "pages_failed",
        "raw_items",
        "filtered_items",
        "partial_result",
        "coverage_claim",
        "allowed_failure_actions",
        "output_written",
        "metadata_output_written",
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
    spot_path = spot_output_path(manifest)
    if spot_path is None:
        return 0
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
                "requested_prediction_input_source="
                f"{manifest.get('requested_prediction_input_source', 'unknown')} "
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
        "requested_prediction_input_source="
        f"{manifest.get('requested_prediction_input_source', 'unknown')} "
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
        elif line.startswith("INFO: failed_symbol_examples="):
            parsed["failed_symbol_examples"] = parse_csv_values(line.split("=", 1)[1])
        elif line.startswith("INFO: insufficient_history_symbol_examples="):
            parsed["insufficient_history_symbol_examples"] = parse_csv_values(
                line.split("=", 1)[1]
            )
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


def parse_csv_values(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


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
    metadata = manifest.get("input_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    paths = f"manifest={output / 'run_manifest.json'} summary={output / 'summary.json'}"
    html_report = html_report_stdout_value(manifest, output)
    html_error = html_report_error_stdout(manifest)
    disclosure = runner_disclosure_stdout(view)
    runner_metadata = runner_metadata_stdout(view, metadata)
    input_csv = input_csv_provenance_stdout(view.get("input_csv_provenance", {}))
    print(
        "OK: runner=run_today_a_share_selection "
        f"mode={manifest['mode']} steps={len(manifest['steps'])} "
        f"prediction_mode={str(manifest['prediction_mode']).lower()} "
        f"consumes_prediction_columns={str(manifest.get('consumes_prediction_columns', False)).lower()} "
        f"prediction_input_source={prediction_input_source(manifest)} "
        f"prediction_model_executed_by_runner={str(prediction_model_executed_by_runner(manifest)).lower()} "
        f"prediction_claim_boundary={view['prediction_claim_boundary']} "
        f"lightgbm_not_used={str(manifest['lightgbm_not_used']).lower()} "
        f"lightgbm_output_source={manifest.get('lightgbm_output_source', 'unknown')} "
        "lightgbm_executed_by_runner=false "
        f"metadata_source={metadata_stdout_value(metadata.get('source_type'))} "
        f"real_market_data={metadata_stdout_value(metadata.get('real_market_data'))} "
        f"source={metadata_stdout_value(metadata.get('source'))} "
        f"market_label_only={metadata_stdout_value(metadata.get('market_label_only'))} "
        "source_claim_boundary="
        f"{metadata_stdout_value(metadata.get('source_claim_boundary'))} "
        f"{runner_metadata} "
        f"{input_csv} "
        f"prices_rows={view['prices_rows']} "
        f"candidate_rows={view['candidate_rows']} "
        f"diagnostic_rows={view['diagnostic_rows']} "
        f"spot_matched_symbols={view['spot_matched_symbols']} "
        f"effective_empty_result={str(view.get('effective_empty_result', False)).lower()} "
        f"empty_result_reason={view.get('empty_result_reason', 'none')} "
        f"{disclosure} "
        f"{paths} html_report={html_report}{html_error}"
    )


def runner_metadata_stdout(view: dict[str, Any], metadata: dict[str, Any]) -> str:
    parts = [
        f"runner_metadata_source={metadata_stdout_value(metadata.get('source_type'))}",
        f"runner_real_market_data={metadata_stdout_value(metadata.get('real_market_data'))}",
        f"source_scope={metadata_stdout_value(view.get('source_scope'))}",
        f"runner_source_scope={metadata_stdout_value(view.get('runner_source_scope'))}",
    ]
    if not history_metadata_stdout_available(metadata):
        parts.extend(input_metadata_stdout(metadata))
    return " ".join(parts)


def history_metadata_stdout_available(metadata: dict[str, Any]) -> bool:
    return any(str(key).startswith("history_") for key in metadata)


def input_metadata_stdout(metadata: dict[str, Any]) -> list[str]:
    return [
        f"input_token_configured={metadata_stdout_value(metadata.get('token_configured'))}",
        f"input_partial_result={metadata_stdout_value(metadata.get('input_partial_result'))}",
        "input_failed_symbol_count="
        f"{metadata_stdout_value(metadata.get('input_failed_symbol_count'))}",
        "input_empty_symbol_count="
        f"{metadata_stdout_value(metadata.get('input_empty_symbol_count'))}",
        "input_possibly_truncated_symbol_count="
        f"{metadata_stdout_value(metadata.get('input_possibly_truncated_symbol_count'))}",
        *quality_counter_stdout("input", metadata),
        f"input_symbol_count={input_symbol_count_stdout(metadata)}",
        f"input_requested_symbols={metadata_list_stdout(metadata.get('requested_symbols'))}",
        f"input_failed_symbols={metadata_list_stdout(metadata.get('failed_symbols'))}",
        f"input_empty_symbols={metadata_list_stdout(metadata.get('empty_symbols'))}",
        f"input_output_written={metadata_stdout_value(metadata.get('output_written'))}",
        "input_metadata_output_written="
        f"{metadata_stdout_value(metadata.get('metadata_output_written'))}",
    ]


def quality_counter_stdout(prefix: str, metadata: dict[str, Any]) -> list[str]:
    return [
        f"{prefix}_invalid_rows={metadata_stdout_value(metadata.get(f'{prefix}_invalid_rows'))}",
        (
            f"{prefix}_dropped_invalid_rows="
            f"{metadata_stdout_value(metadata.get(f'{prefix}_dropped_invalid_rows'))}"
        ),
        f"{prefix}_non_trading_rows={metadata_stdout_value(metadata.get(f'{prefix}_non_trading_rows'))}",
        (
            f"{prefix}_tradestatus_missing_rows="
            f"{metadata_stdout_value(metadata.get(f'{prefix}_tradestatus_missing_rows'))}"
        ),
    ]


def input_csv_provenance_stdout(value: Any) -> str:
    provenance = value if isinstance(value, dict) else {}
    parts = [
        f"input_csv_source_type={metadata_stdout_value(provenance.get('source_type'))}",
        f"input_csv_real_market_data={metadata_stdout_value(provenance.get('real_market_data'))}",
        f"input_csv_source_scope={metadata_stdout_value(provenance.get('source_scope'))}",
        "input_csv_source_claim_boundary="
        f"{metadata_stdout_value(provenance.get('source_claim_boundary'))}",
    ]
    return " ".join(parts)


def metadata_stdout_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    text = str(value).strip() if value is not None else ""
    return text or "unknown"


def input_symbol_count_stdout(metadata: dict[str, Any]) -> str:
    symbol_count = metadata.get("symbol_count")
    requested = metadata.get("input_requested_symbol_count")
    if requested is None and isinstance(metadata.get("requested_symbols"), list):
        requested = len(metadata["requested_symbols"])
    if symbol_count is None:
        return "unknown"
    if requested is None:
        return str(symbol_count)
    return f"{symbol_count}/{requested}"


def metadata_list_stdout(value: Any) -> str:
    if not isinstance(value, list):
        return "unknown"
    tokens = [metadata_item_stdout(item) for item in value]
    tokens = [token for token in tokens if token]
    return ",".join(tokens) if tokens else "none"


def metadata_item_stdout(item: Any) -> str:
    if isinstance(item, dict):
        symbol = stdout_token(item.get("symbol"))
        error = stdout_token(item.get("error"))
        if symbol != "unknown" and error != "unknown":
            return f"{symbol}:{error}"
        if symbol != "unknown":
            return symbol
    return stdout_token(item)


def stdout_token(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        return "unknown"
    for source, target in ((" ", "_"), ("\t", "_"), ("\n", "_"), (",", "_"), (";", "_")):
        text = text.replace(source, target)
    return text


def runner_disclosure_stdout(view: dict[str, Any]) -> str:
    spot = view.get("spot_metadata", {})
    if not isinstance(spot, dict):
        spot = {}
    history = view.get("history_selection", {})
    if not isinstance(history, dict):
        history = {}
    parts = [
        f"spot_partial_result={metadata_stdout_value(spot.get('partial_result'))}",
        f"spot_failed_pages={metadata_stdout_value(spot_failed_pages(spot))}",
        f"history_symbols={view.get('history_symbol_count', 0)}",
    ]
    if history:
        parts.extend(
            [
                f"raw_spot_rows={metadata_stdout_value(history.get('raw_spot_rows'))}",
                f"filtered_spot_rows={metadata_stdout_value(history.get('filtered_spot_rows'))}",
                f"max_history_symbols={metadata_stdout_value(history.get('max_history_symbols'))}",
                "allow_partial_history="
                f"{metadata_stdout_value(history.get('allow_partial_history'))}",
                "history_requested_end_date="
                f"{metadata_stdout_value(history.get('requested_end_date'))}",
                "history_actual_date_max="
                f"{metadata_stdout_value(history.get('history_metadata_actual_date_max'))}",
                "history_partial_result="
                f"{metadata_stdout_value(history.get('history_partial_result'))}",
                "history_output_written="
                f"{metadata_stdout_value(history.get('history_output_written'))}",
                "history_token_configured="
                f"{metadata_stdout_value(history.get('history_token_configured'))}",
                f"history_fields={metadata_stdout_value(history.get('history_fields'))}",
                "history_request_interval_seconds="
                f"{metadata_stdout_value(history.get('history_request_interval_seconds'))}",
                f"history_limit={metadata_stdout_value(history.get('history_limit'))}",
                f"history_max_pages={metadata_stdout_value(history.get('history_max_pages'))}",
                "history_empty_symbol_count="
                f"{metadata_stdout_value(history.get('history_empty_symbol_count'))}",
                "history_possibly_truncated_symbol_count="
                f"{metadata_stdout_value(history.get('history_possibly_truncated_symbol_count'))}",
                *quality_counter_stdout("history", history),
                "history_failed_symbol_count="
                f"{metadata_stdout_value(history.get('history_metadata_failed_symbol_count'))}",
                "history_fallback_error_count="
                f"{metadata_stdout_value(history.get('history_metadata_fallback_error_count'))}",
                f"history_adjust={metadata_stdout_value(history.get('history_adjust'))}",
                f"history_adjustflag={metadata_stdout_value(history.get('history_adjustflag'))}",
                "history_symbols_reached_end_date_count="
                f"{metadata_stdout_value(history.get('history_metadata_symbols_reached_end_date_count'))}",
                "history_all_symbols_reached_end_date="
                f"{metadata_stdout_value(history.get('history_metadata_all_symbols_reached_end_date'))}",
                "history_end_date_has_rows="
                f"{metadata_stdout_value(history.get('history_metadata_end_date_has_rows'))}",
            ]
        )
    return " ".join(parts)


def spot_failed_pages(spot_metadata: dict[str, Any]) -> int | None:
    failed = spot_metadata.get("failed_pages")
    if isinstance(failed, list):
        return len(failed)
    pages_failed = spot_metadata.get("pages_failed")
    return int(pages_failed) if isinstance(pages_failed, int) else None

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
