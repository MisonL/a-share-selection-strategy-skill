"""Spot metadata fields for the local A-share HTML report."""

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


from typing import Any


SPOT_METADATA_KEYS = (
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
)


def spot_metadata_fields(summary: dict[str, Any]) -> list[tuple[str, Any]]:
    metadata = summary.get("spot_metadata", {})
    if not isinstance(metadata, dict) or not metadata:
        return []
    return [
        (f"spot_metadata.{key}", metadata.get(key, ""))
        for key in SPOT_METADATA_KEYS
        if key in metadata
    ]
