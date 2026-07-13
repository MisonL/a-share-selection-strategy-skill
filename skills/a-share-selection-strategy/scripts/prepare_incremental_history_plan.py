#!/usr/bin/env python3
"""Prepare an auditable incremental history fetch plan."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lib.gates.incremental_history_plan import (
    build_fetch_buckets,
    metadata_history_is_empty,
    reason_counts,
    validate_bucket_coverage,
)


CLAIM_BOUNDARY = "incremental_history_plan_only_not_history_fetch_success"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a symbol-level incremental history plan from a current universe "
            "and existing history metadata. This helper does not fetch data."
        )
    )
    parser.add_argument("--spot-input", required=True, help="Current universe CSV.")
    parser.add_argument(
        "--prices-input",
        required=True,
        help="Existing clean CSV or Parquet prices used to verify metadata.",
    )
    parser.add_argument("--history-metadata", required=True)
    parser.add_argument("--min-history-rows", type=positive_int, default=120)
    parser.add_argument("--target-end-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--output", required=True, help="Plan JSON output.")
    parser.add_argument(
        "--symbols-output",
        help="Optional newline-separated symbols needing history fetch.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    started = time.monotonic()
    args = build_parser().parse_args(argv)
    spot_input = Path(args.spot_input)
    prices_input = Path(args.prices_input)
    metadata_input = Path(args.history_metadata)
    output = Path(args.output)
    symbols_output = Path(args.symbols_output) if args.symbols_output else None
    validate_paths(
        inputs=[spot_input, prices_input, metadata_input],
        outputs=[path for path in [output, symbols_output] if path is not None],
    )
    target = normalize_date(args.target_end_date)
    universe = read_universe_symbols(spot_input)
    price_stats = read_price_stats(prices_input)
    metadata = read_json(metadata_input)
    plan = build_incremental_plan(
        universe,
        metadata,
        target,
        price_stats=price_stats,
        min_history_rows=args.min_history_rows,
    )
    plan["prices_input"] = str(prices_input.resolve())
    plan["history_metadata_input"] = str(metadata_input.resolve())
    plan["plan_duration_seconds"] = round(
        max(time.monotonic() - started, 0.0), 6
    )
    plan["plan_symbols_per_second"] = (
        round(len(universe) / plan["plan_duration_seconds"], 6)
        if plan["plan_duration_seconds"]
        else None
    )
    write_json(plan, output)
    if symbols_output:
        symbols_output.parent.mkdir(parents=True, exist_ok=True)
        symbols_output.write_text("\n".join(plan["fetch_symbols"]) + "\n", encoding="utf-8")
    print(
        "OK: fetch_symbols="
        f"{plan['fetch_symbol_count']} up_to_date_symbols={plan['up_to_date_symbol_count']} "
        f"target_end_date={target} output={output} claim_boundary={CLAIM_BOUNDARY}"
    )
    return 0


def build_incremental_plan(
    universe: list[str],
    metadata: dict[str, Any],
    target_end_date: str,
    *,
    price_stats: dict[str, dict[str, Any]] | None = None,
    min_history_rows: int = 1,
) -> dict[str, Any]:
    if min_history_rows < 1:
        raise ValueError("min_history_rows must be positive")
    validate_history_metadata_quality(metadata)
    existing = metadata_symbol_map(metadata)
    validate_price_metadata_consistency(universe, existing, price_stats)
    failed = metadata_symbols(metadata.get("failed_symbols", []))
    empty_metadata = metadata_symbols(metadata.get("empty_symbols", []))
    truncated = metadata_symbols(metadata.get("possibly_truncated_symbols", []))
    unprocessed = metadata_symbols(metadata.get("unprocessed_symbols", []))
    fetch_records: list[dict[str, Any]] = []
    categories: dict[str, list[str]] = {
        "up_to_date": [],
        "stale": [],
        "missing": [],
        "empty": [],
        "short": [],
    }
    for symbol in universe:
        category, record = classify_history_symbol(
            symbol,
            metadata=existing,
            price_stats=price_stats,
            failed=failed,
            empty=empty_metadata,
            truncated=truncated,
            unprocessed=unprocessed,
            target_end_date=target_end_date,
            min_history_rows=min_history_rows,
        )
        categories[category].append(symbol)
        if record is not None:
            fetch_records.append(record)
    fetch_symbols = [record["symbol"] for record in fetch_records]
    refresh = refresh_summary(fetch_records, target_end_date)
    buckets = build_fetch_buckets(fetch_records, target_end_date)
    validate_bucket_coverage(fetch_symbols, buckets)
    return {
        "source": "incremental_history_plan",
        "claim_boundary": CLAIM_BOUNDARY,
        "generated_at": now_iso(),
        "target_end_date": target_end_date,
        "min_history_rows": min_history_rows,
        "universe_symbol_count": len(universe),
        "metadata_symbol_count": len(existing),
        "prices_extra_symbols": sorted(
            set(price_stats or {}).difference(universe)
        ),
        "prices_extra_symbol_count": len(
            set(price_stats or {}).difference(universe)
        ),
        "fetch_symbols": fetch_symbols,
        "fetch_symbol_count": len(fetch_symbols),
        "fetch_records": fetch_records,
        "fetch_buckets": buckets,
        "fetch_bucket_count": len(buckets),
        "fetch_reason_counts": reason_counts(fetch_records),
        **refresh,
        "missing_symbols": categories["missing"],
        "missing_symbol_count": len(categories["missing"]),
        "empty_history_symbols": categories["empty"],
        "empty_history_symbol_count": len(categories["empty"]),
        "short_history_symbols": categories["short"],
        "short_history_symbol_count": len(categories["short"]),
        "stale_symbols": categories["stale"],
        "stale_symbol_count": len(categories["stale"]),
        "up_to_date_symbols": categories["up_to_date"],
        "up_to_date_symbol_count": len(categories["up_to_date"]),
        "next_action": incremental_next_action(refresh),
    }


def classify_history_symbol(
    symbol: str,
    *,
    metadata: dict[str, dict[str, Any]],
    price_stats: dict[str, dict[str, Any]] | None,
    failed: set[str],
    empty: set[str],
    truncated: set[str],
    unprocessed: set[str],
    target_end_date: str,
    min_history_rows: int,
) -> tuple[str, dict[str, Any] | None]:
    history = metadata.get(symbol)
    if not history:
        return "missing", fetch_record(
            symbol, reason="missing_history", fetch_mode="full"
        )
    actual = price_stats.get(symbol) if price_stats is not None else None
    date_max = normalize_optional_date(
        actual.get("date_max") if actual is not None else history.get("date_max")
    )
    rows = history_rows(actual if actual is not None else history)
    metadata_reason = metadata_failure_reason(
        symbol, failed, empty, truncated, unprocessed
    )
    if metadata_reason:
        return "empty", fetch_record(
            symbol, reason=metadata_reason, fetch_mode="full"
        )
    if metadata_history_is_empty(history, date_max):
        return "empty", fetch_record(
            symbol, reason="empty_or_missing_history", fetch_mode="full"
        )
    if rows is not None and rows < min_history_rows:
        return "short", fetch_record(
            symbol,
            reason="short_history_recovery",
            fetch_mode="full",
            current_rows=rows,
        )
    if date_max > target_end_date:
        raise ValueError(
            f"history date_max exceeds target_end_date: {symbol} {date_max}"
        )
    if date_max < target_end_date:
        return "stale", fetch_record(
            symbol,
            reason="stale_history",
            current_date_max=date_max,
            fetch_mode="delta",
        )
    return "up_to_date", None


def fetch_record(
    symbol: str,
    *,
    reason: str,
    fetch_mode: str,
    current_date_max: str = "",
    current_rows: int | None = None,
) -> dict[str, Any]:
    suggested_start = next_calendar_date(current_date_max) if current_date_max else ""
    return {
        "symbol": symbol,
        "reason": reason,
        "fetch_mode": fetch_mode,
        "current_date_max": current_date_max,
        "suggested_start_date": suggested_start,
        "current_rows": current_rows,
    }


def refresh_summary(
    fetch_records: list[dict[str, str]],
    target_end_date: str,
) -> dict[str, Any]:
    delta_records = [
        record for record in fetch_records if record.get("suggested_start_date")
    ]
    full_records = [
        record for record in fetch_records if not record.get("suggested_start_date")
    ]
    starts = sorted({record["suggested_start_date"] for record in delta_records})
    single_delta_start = starts[0] if starts and not full_records else ""
    return {
        "history_refresh_mode": history_refresh_mode(delta_records, full_records),
        "delta_fetch_symbol_count": len(delta_records),
        "full_fetch_symbol_count": len(full_records),
        "suggested_fetch_start_date": single_delta_start,
        "suggested_fetch_start_dates": starts,
        "suggested_fetch_end_date": target_end_date,
        "suggested_history_window_claim_boundary": (
            "incremental_dates_are_plan_hints_not_fetch_success"
        ),
    }


def history_refresh_mode(
    delta_records: list[dict[str, str]],
    full_records: list[dict[str, str]],
) -> str:
    if not delta_records and not full_records:
        return "none"
    if delta_records and not full_records:
        return "delta_only"
    if full_records and not delta_records:
        return "full_for_missing_only"
    return "mixed_delta_and_missing"


def incremental_next_action(refresh: dict[str, Any]) -> str:
    mode = refresh["history_refresh_mode"]
    if mode == "delta_only":
        return "fetch delta date window for fetch_symbols then merge and revalidate"
    if mode == "none":
        return "no history fetch needed; artifacts are already up to date"
    return "fetch missing symbols with full window and stale symbols with delta window"


def read_universe_symbols(path: Path) -> list[str]:
    pd = pandas_module()
    frame = pd.read_csv(path, dtype={"symbol": str})
    if "symbol" not in frame:
        raise ValueError(f"spot input missing symbol column: {path}")
    return unique_symbols(frame["symbol"].tolist())


def metadata_symbol_map(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = metadata.get("symbols", [])
    if not isinstance(items, list):
        raise ValueError("history metadata symbols must be a list")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).strip()
        if symbol:
            if symbol in result:
                raise ValueError(f"duplicate symbol metadata: {symbol}")
            result[symbol] = item
    return result


def validate_history_metadata_quality(metadata: dict[str, Any]) -> None:
    if metadata.get("output_written") is False:
        raise ValueError("history metadata declares output_written=false")
    if metadata.get("metadata_output_written") is False:
        raise ValueError("history metadata declares metadata_output_written=false")
    invalid_rows = metadata_count(metadata, "invalid_rows")
    dropped_invalid_rows = metadata_count(metadata, "dropped_invalid_rows")
    if invalid_rows != dropped_invalid_rows:
        raise ValueError(
            "history metadata invalid_rows and dropped_invalid_rows do not match"
        )
    if metadata_count(metadata, "tradestatus_missing_rows"):
        raise ValueError("history metadata has tradestatus_missing_rows")
    non_trading_rows = metadata_count(metadata, "non_trading_rows")
    dropped_non_trading_rows = metadata_count(
        metadata, "dropped_non_trading_rows"
    )
    retained_non_trading_rows = metadata_count(
        metadata, "retained_non_trading_rows"
    )
    non_trading_policy = str(metadata.get("non_trading_policy", "")).strip()
    if non_trading_rows:
        if non_trading_policy == "drop":
            valid_accounting = (
                dropped_non_trading_rows == non_trading_rows
                and retained_non_trading_rows == 0
            )
        elif non_trading_policy == "keep":
            valid_accounting = (
                retained_non_trading_rows == non_trading_rows
                and dropped_non_trading_rows == 0
            )
        else:
            valid_accounting = False
        if not valid_accounting:
            raise ValueError(
                "history metadata non-trading row accounting is inconsistent"
            )

    recovery_symbols = set().union(
        *(metadata_symbols(metadata.get(key, [])) for key in (
            "failed_symbols",
            "empty_symbols",
            "possibly_truncated_symbols",
            "unprocessed_symbols",
        ))
    )
    clean_pool_removal = audited_clean_pool_removal(metadata)
    explained_quality = bool(
        recovery_symbols
        or invalid_rows
        or non_trading_rows
        or clean_pool_removal
    )
    if (
        metadata.get("rate_limit_budget_exhausted") is True
        and not recovery_symbols
        and not clean_pool_removal
    ):
        raise ValueError(
            "history metadata rate-limit budget exhausted without affected symbols"
        )
    if metadata.get("partial_result") is True and not explained_quality:
        raise ValueError("history metadata partial_result has no auditable cause")


def audited_clean_pool_removal(metadata: dict[str, Any]) -> bool:
    if str(metadata.get("source_scope", "")) != "clean_history_pool":
        return False
    removed = metadata_count(metadata, "clean_pool_removed_symbol_count")
    if removed < 1:
        return False
    reasons = metadata.get("clean_pool_reason_counts")
    if not isinstance(reasons, dict):
        return False
    return any(metadata_count(reasons, str(key)) > 0 for key in reasons)


def metadata_count(metadata: dict[str, Any], key: str) -> int:
    value = metadata.get(key, 0)
    try:
        count = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"history metadata {key} must be an integer") from exc
    if count < 0:
        raise ValueError(f"history metadata {key} must be non-negative")
    return count


def validate_price_metadata_consistency(
    universe: list[str],
    metadata: dict[str, dict[str, Any]],
    price_stats: dict[str, dict[str, Any]] | None,
) -> None:
    if price_stats is None:
        return
    for symbol in universe:
        record = metadata.get(symbol)
        actual = price_stats.get(symbol)
        if record is None:
            if actual is not None:
                raise ValueError(
                    f"history prices symbol is missing from metadata: {symbol}"
                )
            continue
        if actual is None:
            rows = history_rows(record)
            date_max = normalize_optional_date(record.get("date_max"))
            if (rows is not None and rows > 0) or date_max:
                raise ValueError(
                    f"history metadata symbol is missing from prices: {symbol}"
                )
            continue
        expected_rows = history_rows(record)
        if expected_rows is not None and expected_rows != int(actual["rows"]):
            raise ValueError(
                f"history prices rows do not match metadata: {symbol} "
                f"prices={actual['rows']} metadata={expected_rows}"
            )
        for key in ("date_min", "date_max"):
            expected = normalize_optional_date(record.get(key))
            if expected and expected != actual[key]:
                raise ValueError(
                    f"history prices {key} does not match metadata: {symbol}"
                )


def history_rows(record: dict[str, Any] | None) -> int | None:
    if record is None or "rows" not in record:
        return None
    try:
        rows = int(record["rows"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid history metadata rows: {record['rows']}") from exc
    if rows < 0:
        raise ValueError(f"invalid history metadata rows: {record['rows']}")
    return rows


def metadata_symbols(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        str(item.get("symbol", "") if isinstance(item, dict) else item).strip()
        for item in value
        if str(item.get("symbol", "") if isinstance(item, dict) else item).strip()
    }


def metadata_failure_reason(
    symbol: str,
    failed: set[str],
    empty: set[str],
    truncated: set[str],
    unprocessed: set[str],
) -> str:
    if symbol in failed:
        return "metadata_failed_fetch"
    if symbol in empty:
        return "metadata_empty_history"
    if symbol in truncated:
        return "metadata_possibly_truncated"
    if symbol in unprocessed:
        return "metadata_unprocessed_fetch"
    return ""


def read_price_stats(path: Path) -> dict[str, dict[str, Any]]:
    pd = pandas_module()
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, usecols=["symbol", "date"], dtype={"symbol": str})
    elif suffix in {".parquet", ".pq"}:
        frame = pd.read_parquet(path, columns=["symbol", "date"])
        if not pd.api.types.is_string_dtype(frame["symbol"].dtype):
            raise ValueError("prices symbol column must be text")
    else:
        raise ValueError("prices input must be CSV or Parquet")
    symbols = frame["symbol"].astype(str).str.strip()
    if symbols.eq("").any() or not symbols.str.fullmatch(r"\d{6}").all():
        raise ValueError("prices input contains invalid symbol values")
    compact_dates = frame["date"].astype(str).str.strip().str.replace("-", "", regex=False)
    dates = pd.to_datetime(compact_dates, format="%Y%m%d", errors="coerce")
    if dates.isna().any():
        raise ValueError("prices input contains invalid date values")
    normalized = pd.DataFrame({"symbol": symbols, "date": dates})
    if normalized.duplicated(["symbol", "date"]).any():
        raise ValueError("prices input contains duplicate symbol/date rows")
    grouped = normalized.groupby("symbol", sort=True)["date"].agg(
        rows="size", date_min="min", date_max="max"
    )
    return {
        str(symbol): {
            "rows": int(row.rows),
            "date_min": row.date_min.date().isoformat(),
            "date_max": row.date_max.date().isoformat(),
        }
        for symbol, row in grouped.iterrows()
    }


def unique_symbols(values: Any) -> list[str]:
    seen = set()
    result = []
    for value in values:
        symbol = str(value).strip()
        if symbol and symbol not in seen:
            result.append(symbol)
            seen.add(symbol)
    return sorted(result)


def normalize_date(text: str) -> str:
    raw = str(text).strip()
    compact = raw.replace("-", "")
    if not compact.isdigit() or len(compact) != 8:
        raise ValueError(f"date must be YYYY-MM-DD or YYYYMMDD: {text}")
    try:
        parsed = datetime.strptime(compact, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"date must be YYYY-MM-DD or YYYYMMDD: {text}") from exc
    return parsed.strftime("%Y-%m-%d")


def normalize_optional_date(value: Any) -> str:
    text = str(value or "").strip()
    return normalize_date(text) if text else ""


def next_calendar_date(value: str) -> str:
    parsed = datetime.strptime(normalize_date(value), "%Y-%m-%d")
    return (parsed + timedelta(days=1)).strftime("%Y-%m-%d")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def validate_paths(*, inputs: list[Path], outputs: list[Path]) -> None:
    input_paths = {resolved_path(path) for path in inputs}
    seen_outputs = set()
    for output in outputs:
        output_path = resolved_path(output)
        if output_path in input_paths:
            raise ValueError(f"output path must not overwrite input: {output}")
        if output_path in seen_outputs:
            raise ValueError(f"duplicate output path: {output}")
        seen_outputs.add(output_path)


def resolved_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def pandas_module() -> Any:
    import pandas as pandas  # noqa: PLC0415

    return pandas


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
