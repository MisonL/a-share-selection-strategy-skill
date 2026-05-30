"""Allocation artifact checks for walk-forward validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def allocation_errors(run_dir: Path, summary: dict[str, Any], args: Any, load_json, read_csv) -> list[str]:
    if args.required_allocation_model != "portfolio_cash_lot_floor":
        return ["unexpected_allocation_summary"] if summary.get("allocation") not in (None, {}) else []
    errors = []
    allocation = load_json(run_dir / "qsss_allocation_summary.json")
    skipped = read_csv(run_dir / "qsss_skipped_candidates.csv")
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
        errors.append(f"allocation_raw={raw} selected={selected} skipped={skipped_count}")
    if len(skipped) != skipped_count:
        errors.append(f"skipped_rows={len(skipped)} expected={skipped_count}")
    if skipped and "skip_reason" not in skipped[0]:
        errors.append("skipped_missing_skip_reason")
    return errors
