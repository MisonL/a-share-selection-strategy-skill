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
    records: list[dict[str, str]],
    target_end_date: str,
    max_bucket_symbols: int = 200,
) -> list[dict[str, Any]]:
    if max_bucket_symbols < 1:
        raise ValueError("max_bucket_symbols must be positive")
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for record in records:
        key = (
            record["fetch_mode"],
            record["reason"],
            record["suggested_start_date"],
        )
        grouped.setdefault(key, []).append(record["symbol"])
    buckets = []
    index = 0
    for key, symbols in sorted(grouped.items()):
        mode, reason, start_date = key
        ordered = sorted(symbols)
        for offset in range(0, len(ordered), max_bucket_symbols):
            index += 1
            chunk = ordered[offset : offset + max_bucket_symbols]
            buckets.append(
                {
                    "bucket_id": f"fetch-{index:03d}-{mode}-{reason}",
                    "fetch_mode": mode,
                    "reason": reason,
                    "start_date": start_date,
                    "end_date": target_end_date,
                    "symbols": chunk,
                    "symbol_count": len(chunk),
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


def strict_raw_symbol_map(
    raw_records: Any,
    *,
    label: str,
) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_records, list):
        raise ValueError(f"{label} must be a list")
    result: dict[str, dict[str, Any]] = {}
    for record in raw_records:
        if not isinstance(record, dict):
            raise ValueError(f"{label} records must be objects")
        symbol = str(record.get("symbol", "")).strip()
        if not symbol:
            raise ValueError(f"{label} record requires symbol")
        if symbol in result:
            raise ValueError(f"{label} has duplicate symbol: {symbol}")
        result[symbol] = record
    return result


def reason_counts(records: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        reason = record["reason"]
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))
