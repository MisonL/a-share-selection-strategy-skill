"""Metadata helpers for baostock A-share universe fetches."""

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

from pathlib import Path
import time
from typing import Any


CSV_COLUMNS = [
    "symbol",
    "name",
    "spot_price",
    "spot_pct_chg",
    "spot_amount",
    "spot_industry",
]
DATA_SOURCE_NOTE = (
    "baostock query_all_stock universe snapshot; symbol/name only; "
    "not a realtime quote, price, amount, industry, or full-market completion proof"
)
CLAIM_BOUNDARY = "baostock_universe_snapshot_not_realtime_spot_or_full_market_proof"


def build_metadata(
    args: Any,
    rows: list[dict[str, Any]],
    collected: dict[str, Any],
    *,
    error: str,
    resolution: dict[str, Any],
    started_at: str,
    monotonic_started: float,
    fetch_errors: list[dict[str, Any]],
    fetch_attempts: int,
) -> dict[str, Any]:
    finished_at = utc_now()
    partial = bool(error) or not rows
    return {
        "source": "baostock",
        "source_type": "external_fetch",
        "source_scope": "baostock_universe_snapshot",
        "real_market_data": True,
        "data_source_note": DATA_SOURCE_NOTE,
        "raw_items": len(rows),
        "filtered_items": len(rows),
        "symbol_count": len(rows),
        "raw_row_count": int(collected.get("raw_row_count", 0) or 0),
        "excluded_count": int(collected.get("excluded_count", 0) or 0),
        "excluded_examples": list(collected.get("excluded", []))[:10],
        "error": error,
        "fetch_errors": fetch_errors,
        "fetch_error_count": len(fetch_errors),
        "fetch_attempts": int(fetch_attempts),
        "retry_attempts": int(args.retries),
        "max_attempts": int(args.retries) + 1,
        "partial_result": partial,
        "coverage_claim": coverage_claim(partial),
        "source_claim_boundary": CLAIM_BOUNDARY,
        "allowed_failure_actions": allowed_failure_actions(partial, len(rows)),
        "snapshot_time": finished_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds(monotonic_started),
        "output": str(Path(args.output)),
        "metadata_output": str(Path(args.metadata_output)),
        **resolution,
    }


def coverage_claim(partial_result: bool) -> str:
    if partial_result:
        return "partial_universe_not_full_market"
    return "symbol_universe_snapshot_not_realtime_spot_proof"


def allowed_failure_actions(partial_result: bool, raw_items: int) -> list[str]:
    if raw_items == 0:
        return [
            "retry_baostock_universe_later",
            "switch_source_and_disclose_scope",
            "reuse_landed_snapshot_only_if_user_accepts_stale_scope",
        ]
    if partial_result:
        return [
            "rerun_with_fail_on_partial",
            "use_partial_universe_only_with_disclosure",
            "switch_source_and_compare_source_scope",
        ]
    return []


def strict_errors(metadata: dict[str, Any], args: Any) -> list[str]:
    errors = []
    if args.fail_on_partial and metadata["partial_result"]:
        errors.append("partial_result=true")
    if metadata["raw_items"] == 0:
        errors.append("raw_items=0")
    return errors


def output_status(
    metadata: dict[str, Any],
    *,
    output_written: bool,
    metadata_output_written: bool,
) -> dict[str, Any]:
    return {
        **metadata,
        "output_written": bool(output_written),
        "metadata_output_written": bool(metadata_output_written),
    }


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def duration_seconds(started: float) -> float:
    return round(max(time.monotonic() - started, 0.0), 6)


def print_summary(metadata: dict[str, Any], prefix: str = "OK") -> None:
    status = "PARTIAL" if prefix == "OK" and metadata["partial_result"] else prefix
    print(
        f"{status}: source=baostock source_scope={metadata['source_scope']} "
        f"raw_items={metadata['raw_items']} filtered_items={metadata['filtered_items']} "
        f"symbol_count={metadata['symbol_count']} "
        f"requested_snapshot_date={metadata['requested_snapshot_date']} "
        f"resolved_snapshot_date={metadata['resolved_snapshot_date']} "
        f"date_fallback_used={str(metadata['date_fallback_used']).lower()} "
        f"excluded_count={metadata['excluded_count']} "
        f"partial_result={str(metadata['partial_result']).lower()} "
        f"coverage_claim={metadata['coverage_claim']} "
        f"source_claim_boundary={metadata['source_claim_boundary']} "
        f"output_written={str(metadata.get('output_written', False)).lower()} "
        "metadata_output_written="
        f"{str(metadata.get('metadata_output_written', False)).lower()} "
        f"output={metadata['output']} metadata={metadata['metadata_output']}"
    )
