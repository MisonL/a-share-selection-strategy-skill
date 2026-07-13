"""Optional profiling helpers for score_candidates.py."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def start_profile(
    input_path: Path,
    config_path: Path,
    spot_path: Path | None,
    profile_output: Path | None,
) -> dict[str, Any] | None:
    if profile_output is None:
        return None
    now = time.monotonic()
    return {
        "profile_schema": "score_candidates_profile_v1",
        "input": input_path.name,
        "config": config_path.name,
        "spot_input": spot_path.name if spot_path else "",
        "profile_output_requested": profile_output is not None,
        "stages": [],
        "started_monotonic": now,
        "last_monotonic": now,
    }


def tick(profile: dict[str, Any] | None, stage: str) -> None:
    if profile is None:
        return
    now = time.monotonic()
    last = float(profile["last_monotonic"])
    started = float(profile["started_monotonic"])
    profile["stages"].append(
        {
            "stage": stage,
            "elapsed_since_previous_seconds": round(max(now - last, 0.0), 6),
            "elapsed_total_seconds": round(max(now - started, 0.0), 6),
        }
    )
    profile["last_monotonic"] = now


def record_count(
    profile: dict[str, Any] | None,
    key: str,
    value: int,
) -> None:
    if profile is None:
        return
    profile[key] = int(value)


def update_from_summary(
    profile: dict[str, Any] | None,
    summary: dict[str, Any],
    candidate_rows: int,
) -> None:
    if profile is None:
        return
    for key in summary_profile_keys():
        if key in summary:
            profile[f"summary_{key}"] = summary[key]
    profile["candidate_rows"] = int(candidate_rows)
    profile["diagnostic_rows"] = int(len(summary.get("threshold_diagnostics", [])))


def finalize(
    profile: dict[str, Any] | None,
    summary: dict[str, Any],
) -> dict[str, Any] | None:
    if profile is None:
        return None
    finalized = {**profile, "stages": list(profile["stages"])}
    tick(finalized, "profile_write_started")
    total = max(time.monotonic() - float(finalized["started_monotonic"]), 0.0)
    finalized["duration_seconds"] = round(total, 6)
    input_rows = int(finalized.get("input_rows", 0) or 0)
    scored_symbols = int(finalized.get("summary_scored_symbols", 0) or 0)
    finalized["input_rows_per_second"] = (
        round(input_rows / total, 6) if input_rows and total else None
    )
    finalized["scored_symbols_per_second"] = (
        round(scored_symbols / total, 6) if scored_symbols and total else None
    )
    finalized["effective_empty_result"] = bool(
        summary.get("effective_empty_result", False)
    )
    finalized["empty_result_reason"] = summary.get("empty_result_reason", "none")
    finalized.pop("started_monotonic", None)
    finalized.pop("last_monotonic", None)
    return finalized


def summary_profile_keys() -> tuple[str, ...]:
    return (
        "raw_rows",
        "raw_symbols",
        "prepared_rows",
        "input_rows",
        "input_symbols",
        "scored_symbols",
        "failed_symbols",
        "insufficient_history_symbols",
        "candidates",
    )
