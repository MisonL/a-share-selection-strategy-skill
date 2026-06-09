"""Input provenance helpers for A-share selection scoring."""

from __future__ import annotations

import math
from typing import Any


PROVENANCE_COLUMNS = [
    "source_type",
    "source_scope",
    "real_market_data",
    "metadata_source",
    "source_claim_boundary",
    "data_source_note",
]


def aggregate_input_provenance(frame: Any) -> dict[str, Any]:
    return {
        column: aggregate_column_value(frame[column])
        for column in PROVENANCE_COLUMNS
        if column in frame
    }


def aggregate_column_value(series: Any) -> Any:
    values = []
    for value in series:
        if missing_value(value):
            continue
        normalized = normalized_value(value)
        if normalized not in values:
            values.append(normalized)
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return "mixed"


def normalized_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    text = str(value).strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    return text


def missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "nat", "<na>"}


def add_provenance_to_frame(frame: Any, provenance: dict[str, Any]) -> Any:
    result = frame.copy()
    for column, value in provenance.items():
        result[column] = value
    return result


def add_provenance_to_rows(
    rows: list[dict[str, Any]], provenance: dict[str, Any]
) -> list[dict[str, Any]]:
    return [{**row, **provenance} for row in rows]

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
