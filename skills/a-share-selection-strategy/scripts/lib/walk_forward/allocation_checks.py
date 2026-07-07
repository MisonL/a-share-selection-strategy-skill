"""Allocation artifact checks for walk-forward validation."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


CAPACITY_FIELDS = (
    "max_open_positions",
    "max_gross_weight",
    "max_gross_notional",
    "max_cash_reserved",
)
FLOAT_TOLERANCE = 0.000000001


def allocation_errors(
    *,
    run_dir: Path,
    summary: dict[str, Any],
    overlap: dict[str, Any],
    args: Any,
    load_json,
    read_csv,
) -> list[str]:
    if args.required_allocation_model != "portfolio_cash_lot_floor":
        return (
            ["unexpected_allocation_summary"]
            if summary.get("allocation") not in (None, {})
            else []
        )
    errors = []
    allocation = load_json(run_dir / "prediction_allocation_summary.json")
    skipped = read_csv(run_dir / "prediction_skipped_candidates.csv")
    if summary.get("allocation") != allocation:
        errors.append("allocation_summary_mismatch")
    if allocation.get("allocation_model") != args.required_allocation_model:
        errors.append(f"allocation_model={allocation.get('allocation_model')}")
    selected = sum(args.expected_candidates)
    raw = int(allocation.get("raw_candidates", 0))
    skipped_count = int(allocation.get("skipped_candidates", 0))
    if int(allocation.get("allocated_candidates", 0)) != selected:
        errors.append(f"allocation_allocated={allocation.get('allocated_candidates')}")
    if raw != selected + skipped_count:
        errors.append(
            f"allocation_raw={raw} selected={selected} skipped={skipped_count}"
        )
    errors += allocation_overlap_errors(allocation, overlap)
    if len(skipped) != skipped_count:
        errors.append(f"skipped_rows={len(skipped)} expected={skipped_count}")
    if skipped and "skip_reason" not in skipped[0]:
        errors.append("skipped_missing_skip_reason")
    return errors


def allocation_overlap_errors(
    allocation: dict[str, Any], overlap: dict[str, Any]
) -> list[str]:
    errors = []
    for field in CAPACITY_FIELDS:
        allocation_value, allocation_error = capacity_value(
            allocation, field, "allocation"
        )
        overlap_value, overlap_error = capacity_value(overlap, field, "overlap")
        errors += [error for error in (allocation_error, overlap_error) if error]
        if allocation_value is None or overlap_value is None:
            continue
        if abs(allocation_value - overlap_value) > FLOAT_TOLERANCE:
            errors.append(f"allocation_overlap_{field}_mismatch")
    return errors


def capacity_value(
    source: dict[str, Any], field: str, label: str
) -> tuple[float | None, str | None]:
    value = source.get(field)
    if field not in source or value in (None, ""):
        return None, f"allocation_overlap_{label}_{field}_missing"
    if isinstance(value, bool):
        return None, f"allocation_overlap_{label}_{field}_non_numeric"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, f"allocation_overlap_{label}_{field}_non_numeric"
    if not math.isfinite(number):
        return None, f"allocation_overlap_{label}_{field}_non_finite"
    if number < 0:
        return None, f"allocation_overlap_{label}_{field}_negative"
    return number, None
