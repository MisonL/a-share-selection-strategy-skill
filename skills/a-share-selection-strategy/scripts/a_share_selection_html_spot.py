"""Spot metadata fields for the local A-share HTML report."""

from __future__ import annotations

from typing import Any


SPOT_METADATA_KEYS = (
    "partial_result",
    "coverage_claim",
    "failed_pages",
    "allowed_failure_actions",
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
