"""Pure contracts for incremental history fetch plans."""

from __future__ import annotations

from typing import Any


def metadata_history_is_empty(record: dict[str, Any], date_max: str) -> bool:
    if not date_max:
        return True
    if "rows" not in record:
        return False
    try:
        return int(record["rows"]) <= 0
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid history metadata rows: {record['rows']}") from exc


def build_fetch_buckets(
    records: list[dict[str, str]], target_end_date: str
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for record in records:
        key = (
            record["fetch_mode"],
            record["reason"],
            record["suggested_start_date"],
        )
        grouped.setdefault(key, []).append(record["symbol"])
    buckets = []
    for index, (key, symbols) in enumerate(sorted(grouped.items()), start=1):
        mode, reason, start_date = key
        buckets.append(
            {
                "bucket_id": f"fetch-{index:03d}-{mode}-{reason}",
                "fetch_mode": mode,
                "reason": reason,
                "start_date": start_date,
                "end_date": target_end_date,
                "symbols": sorted(symbols),
                "symbol_count": len(symbols),
            }
        )
    return buckets


def validate_bucket_coverage(
    fetch_symbols: list[str], buckets: list[dict[str, Any]]
) -> None:
    bucket_symbols = [symbol for bucket in buckets for symbol in bucket["symbols"]]
    if len(bucket_symbols) != len(set(bucket_symbols)):
        raise ValueError("fetch buckets contain duplicate symbols")
    if sorted(fetch_symbols) != sorted(bucket_symbols):
        raise ValueError("fetch buckets do not cover fetch_symbols exactly")


def reason_counts(records: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        reason = record["reason"]
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))
