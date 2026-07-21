"""Build compact source-level summaries for external source probes."""

from __future__ import annotations

import json
import math
from typing import Any

from lib.selection_core.a_share_selection_command_safety import sanitize_text


def command_elapsed_seconds(started: float, finished: float) -> float:
    elapsed = finished - started
    if not math.isfinite(elapsed):
        raise ValueError("command elapsed seconds must be finite")
    return round(max(elapsed, 0.0), 6)


def build_summary(
    manifest: dict[str, Any],
    *,
    short_window_claim_boundary: str,
) -> dict[str, Any]:
    results = manifest["results"]
    by_source = {
        source: [item for item in results if item["source"] == source]
        for source in sorted({item["source"] for item in results})
    }
    return {
        "iterations": manifest["iterations"],
        "total_runs": len(results),
        "passed_runs": sum(1 for item in results if item["passed"]),
        "sources": {
            source: source_summary(items)
            for source, items in by_source.items()
        },
        "all_sources_all_iterations_passed": bool(results)
        and all(item["passed"] for item in results),
        "long_term_stability_claim": "not_proven",
        "short_window_claim_boundary": short_window_claim_boundary,
        "interpretation": "Repeated success only describes this run window, parameters, and network environment.",
    }


def source_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    latest = items[-1]
    return {
        "runs": len(items),
        "passed_runs": sum(1 for item in items if item["passed"]),
        "all_passed": all(item["passed"] for item in items),
        "observation_failed_checks": observation_failures(items),
        **latest_source_projection(latest),
    }


def latest_source_projection(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "latest_source_returncode": optional_returncode(result.get("returncode")),
        "latest_command_elapsed_seconds": optional_seconds(
            result.get("command_elapsed_seconds")
        ),
        "latest_command_timeout_seconds": optional_seconds(
            result.get("command_timeout_seconds")
        ),
        "latest_command_timed_out": result.get("command_timed_out") is True,
        "latest_first_required_failure": first_required_failure(result.get("checks")),
        "latest_metadata_output": sanitized_optional_text(
            result.get("metadata_output")
        ),
        "latest_stderr_nonempty": bool(result.get("stderr")),
    }


def optional_returncode(value: object) -> int | None:
    if type(value) is int:
        return value
    return None


def optional_seconds(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        return None
    return parsed


def sanitized_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return sanitize_text(value)


def first_required_failure(checks: object) -> str | None:
    if not isinstance(checks, list):
        return None
    for item in checks:
        if not isinstance(item, dict) or item.get("required", True) is False:
            continue
        if item.get("passed") is True:
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            return "unnamed_required_check"
        return sanitize_text(name)
    return None


def observation_failures(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for check_item in item["checks"]:
            if check_item.get("required", True) or check_item["passed"]:
                continue
            name = str(check_item["name"])
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def strict_errors(summary: dict[str, Any]) -> list[str]:
    errors = []
    for source, data in summary.get("sources", {}).items():
        if not data.get("all_passed"):
            errors.append(
                f"{source}_passed_runs={data.get('passed_runs')} runs={data.get('runs')}"
            )
    return errors


def strict_failure_diagnostics(
    results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> list[str]:
    by_source = {
        source: [item for item in results if item.get("source") == source]
        for source in summary.get("sources", {})
    }
    diagnostics = []
    for source, data in summary.get("sources", {}).items():
        if data.get("all_passed"):
            continue
        failed = latest_failed_result(by_source.get(source, []))
        diagnostics.append(strict_failure_diagnostic(source, failed))
    return diagnostics


def latest_failed_result(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in reversed(items):
        if item.get("passed") is not True:
            return item
    return None


def strict_failure_diagnostic(source: object, result: dict[str, Any] | None) -> str:
    if result is None:
        return f"source={sanitize_text(str(source))} failed_result=unavailable"
    projection = latest_source_projection(result)
    return " ".join(
        [
            f"source={sanitize_text(str(source))}",
            "failed_source_returncode="
            f"{diagnostic_value(projection['latest_source_returncode'])}",
            "failed_first_required_failure="
            f"{diagnostic_value(projection['latest_first_required_failure'])}",
            "failed_metadata_output="
            f"{diagnostic_text(projection['latest_metadata_output'])}",
            "failed_command_timed_out="
            f"{str(projection['latest_command_timed_out']).lower()}",
            "failed_command_timeout_seconds="
            f"{diagnostic_value(projection['latest_command_timeout_seconds'])}",
        ]
    )


def diagnostic_value(value: object) -> str:
    if value is None:
        return "null"
    return sanitize_text(str(value))


def diagnostic_text(value: object) -> str:
    if value is None:
        return "null"
    return json.dumps(sanitize_text(str(value)), ensure_ascii=True)
