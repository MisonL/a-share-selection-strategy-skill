"""Helpers for the local A-share selection runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def summary_view(manifest: dict[str, Any], status: str) -> dict[str, Any]:
    failed = [step for step in manifest["steps"] if step["returncode"] not in step["allowed_returncodes"]]
    return {
        "runner": manifest["runner"],
        "status": status,
        "mode": manifest["mode"],
        "qsss_mode": manifest["qsss_mode"],
        "lightgbm_not_used": manifest["lightgbm_not_used"],
        "source_scope": manifest["source_scope"],
        "steps": len(manifest["steps"]),
        "failed_steps": [step["step"] for step in failed],
        "spot_metadata": spot_metadata_view(manifest),
        "score": score_summary(manifest),
        "candidates_output": str(Path(manifest["output_dir"]) / "candidates.csv"),
        "diagnostics_output": str(Path(manifest["output_dir"]) / "diagnostics.csv"),
        "boundary": boundary_for(manifest),
    }


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
        "failed_pages",
        "raw_items",
        "filtered_items",
        "partial_result",
        "allowed_failure_actions",
    ]
    return {key: data.get(key) for key in keys if key in data}


def boundary_for(manifest: dict[str, Any]) -> str:
    if manifest["qsss_mode"]:
        return "QSSS mode requires real prediction or prediction_score in the input."
    return "Generic technical mode; not QSSS-derived and not LightGBM-backed."


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
        f"qsss_mode={str(manifest['qsss_mode']).lower()} "
        f"lightgbm_not_used={str(manifest['lightgbm_not_used']).lower()} "
        f"manifest={output / 'run_manifest.json'} summary={output / 'summary.json'}"
    )
