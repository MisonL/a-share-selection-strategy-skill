"""Validate and publish incremental history bucket artifacts."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from lib.gates.incremental_history_plan import strict_raw_symbol_map


CLAIM_BOUNDARY = "bucket_fetch_execution_not_full_market_or_selection_proof"
FAILURE_LISTS = ("failed_symbols", "empty_symbols", "possibly_truncated_symbols")
PYTDX_ALLOWED_MERGE_FIELDS = ["open", "high", "low", "close", "volume", "amount"]
PARTIAL_RESULT_SEMANTICS = (
    "false_means_no_unaudited_gaps_"
    "audited_no_trading_updates_disclosed_separately"
)


def validate_bucket_artifacts(
    bucket: dict[str, Any],
    paths: dict[str, Path],
    provider: str,
    *,
    allow_non_trading_empty: bool = False,
) -> None:
    if not paths["prices"].is_file() or not paths["metadata"].is_file():
        raise ValueError(f"bucket artifacts missing: {bucket['bucket_id']}")
    metadata = read_json(paths["metadata"])
    artifact_provider = str(
        metadata.get("provider") or metadata.get("source") or ""
    ).strip()
    if artifact_provider != provider:
        raise ValueError(
            "bucket metadata provider does not match execution contract"
        )
    if metadata.get("output_written") is not True:
        raise ValueError("bucket metadata requires output_written=true")
    if metadata.get("metadata_output_written") is not True:
        raise ValueError("bucket metadata requires metadata_output_written=true")
    allowed_empty = validated_non_trading_empty_symbols(
        metadata,
        bucket,
        provider=provider,
        enabled=allow_non_trading_empty,
    )
    if provider == "baostock" and str(
        metadata.get("missing_name_policy", "query")
    ).strip().lower() != "blank":
        for key in ("name_lookup_failed_symbols", "name_lookup_missing_symbols"):
            if metadata_symbols(metadata.get(key, [])):
                raise ValueError(f"bucket metadata has {key}")
    for key in FAILURE_LISTS:
        values = metadata_symbols(metadata.get(key, []))
        if key == "empty_symbols":
            values = sorted(set(values) - allowed_empty)
        if values:
            raise ValueError(f"bucket metadata has {key}")
    invalid_rows = int(metadata.get("invalid_rows", 0) or 0)
    dropped_invalid_rows = int(metadata.get("dropped_invalid_rows", 0) or 0)
    if invalid_rows != dropped_invalid_rows:
        raise ValueError(
            "bucket metadata invalid_rows and dropped_invalid_rows do not match"
        )
    if metadata.get("partial_result") is True and not allowed_empty:
        raise ValueError("bucket metadata has partial_result=true")
    if metadata.get("rate_limit_budget_exhausted") is True:
        raise ValueError("bucket metadata exhausted its rate-limit budget")
    if metadata_symbols(metadata.get("unprocessed_symbols", [])):
        raise ValueError("bucket metadata has unprocessed_symbols")
    if int(metadata.get("tradestatus_missing_rows", 0) or 0) != 0:
        raise ValueError("bucket metadata has tradestatus_missing_rows")
    requested = metadata_symbols(metadata.get("requested_symbols", []))
    if requested != sorted(bucket["symbols"]):
        raise ValueError("bucket metadata requested_symbols do not match plan")
    prices = bucket_price_stats(paths["prices"], bucket, allowed_empty)
    validate_bucket_metadata_stats(metadata, prices, bucket, allowed_empty)


def validated_non_trading_empty_symbols(
    metadata: dict[str, Any],
    bucket: dict[str, Any],
    *,
    provider: str,
    enabled: bool,
) -> set[str]:
    empty = set(metadata_symbols(metadata.get("empty_symbols", [])))
    if not empty:
        return set()
    declared = set(
        metadata_symbols(metadata.get("non_trading_only_empty_symbols", []))
    )
    if not enabled or provider != "baostock":
        return set()
    if empty != declared:
        raise ValueError(
            "bucket empty_symbols must exactly match non_trading_only_empty_symbols"
        )
    raw_by_symbol = strict_raw_symbol_map(
        metadata.get("raw_symbols"),
        label="bucket metadata raw_symbols",
    )
    target = required_text(bucket, "end_date")
    for symbol in sorted(empty):
        record = raw_by_symbol.get(symbol)
        if record is None or int(record.get("rows", 0) or 0) <= 0:
            raise ValueError(
                f"bucket non-trading empty symbol lacks raw rows: {symbol}"
            )
        if normalize_bucket_date(record.get("date_max", "")) != target:
            raise ValueError(
                f"bucket non-trading empty symbol does not reach target: {symbol}"
            )
    return empty


def bucket_price_stats(
    path: Path,
    bucket: dict[str, Any],
    allowed_empty: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    allowed_empty = allowed_empty or set()
    stats: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = {"symbol", "date"}.difference(fields)
        if missing:
            raise ValueError(
                "bucket prices missing required columns: " + ", ".join(sorted(missing))
            )
        for row in reader:
            symbol = str(row.get("symbol", "")).strip()
            if len(symbol) != 6 or not symbol.isdigit():
                raise ValueError(f"bucket prices has invalid symbol: {symbol}")
            date = normalize_bucket_date(row.get("date", ""))
            key = (symbol, date)
            if key in seen:
                raise ValueError(
                    f"bucket prices has duplicate symbol/date: {symbol} {date}"
                )
            seen.add(key)
            item = stats.setdefault(
                symbol,
                {"rows": 0, "date_min": date, "date_max": date},
            )
            item["rows"] += 1
            item["date_min"] = min(item["date_min"], date)
            item["date_max"] = max(item["date_max"], date)
    expected_symbols = sorted(set(bucket["symbols"]) - allowed_empty)
    if not seen and expected_symbols:
        raise ValueError("bucket prices is empty")
    actual_symbols = sorted(stats)
    if actual_symbols != expected_symbols:
        raise ValueError("bucket prices symbols do not match plan")
    start = str(bucket.get("start_date", "")).strip()
    end = required_text(bucket, "end_date")
    for symbol, item in stats.items():
        if start and item["date_min"] < start:
            raise ValueError(f"bucket prices date precedes planned start: {symbol}")
        if item["date_max"] > end:
            raise ValueError(f"bucket prices date exceeds planned end: {symbol}")
    return stats


def validate_bucket_metadata_stats(
    metadata: dict[str, Any],
    prices: dict[str, dict[str, Any]],
    bucket: dict[str, Any],
    allowed_empty: set[str] | None = None,
) -> None:
    allowed_empty = allowed_empty or set()
    records = metadata.get("symbols")
    if not isinstance(records, list):
        raise ValueError("bucket metadata symbols must be a list")
    expected: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("bucket metadata symbol record must be an object")
        symbol = str(record.get("symbol", "")).strip()
        if symbol in expected:
            raise ValueError(f"bucket metadata has duplicate symbol record: {symbol}")
        expected[symbol] = record
    if sorted(expected) != sorted(bucket["symbols"]):
        raise ValueError("bucket metadata symbols do not match plan")
    for symbol in sorted(allowed_empty):
        if int(expected[symbol].get("rows", -1)) != 0:
            raise ValueError(
                f"bucket non-trading empty metadata rows must be zero: {symbol}"
            )
    for symbol, actual in prices.items():
        record = expected[symbol]
        try:
            rows = int(record.get("rows", -1))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"bucket metadata rows is invalid: {symbol}") from exc
        if rows != actual["rows"]:
            raise ValueError(f"bucket metadata rows do not match prices: {symbol}")
        for key in ("date_min", "date_max"):
            value = str(record.get(key, "")).strip()
            if not value:
                raise ValueError(f"bucket metadata {key} is missing: {symbol}")
            if normalize_bucket_date(value) != actual[key]:
                raise ValueError(
                    f"bucket metadata {key} does not match prices: {symbol}"
                )
    if "rows" in metadata:
        try:
            metadata_rows = int(metadata["rows"])
        except (TypeError, ValueError) as exc:
            raise ValueError("bucket metadata rows must be an integer") from exc
        actual_rows = sum(item["rows"] for item in prices.values())
        if metadata_rows != actual_rows:
            raise ValueError("bucket metadata total rows do not match prices")


def normalize_bucket_date(value: Any) -> str:
    text = str(value or "").strip()
    compact = text.replace("-", "")
    try:
        parsed = datetime.strptime(compact, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"bucket prices has invalid date: {text}") from exc
    return parsed.date().isoformat()


def staged_output_path(output: Path, token: str) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    return output.with_name(f".{output.name}.{token}.stage")


def publish_output_pair(
    outputs: list[tuple[Path, Path]],
    token: str,
) -> None:
    backups: list[tuple[Path, Path]] = []
    published: list[Path] = []
    try:
        for _staged, target in outputs:
            backup = target.with_name(f".{target.name}.{token}.previous")
            if target.exists() or target.is_symlink():
                target.replace(backup)
                backups.append((target, backup))
        for staged, target in outputs:
            staged.replace(target)
            published.append(target)
    except Exception:
        for target in published:
            target.unlink(missing_ok=True)
        for target, backup in reversed(backups):
            if backup.exists() or backup.is_symlink():
                backup.replace(target)
        raise
    else:
        for _target, backup in backups:
            backup.unlink(missing_ok=True)


def remove_staged_output(path: Path) -> None:
    path.unlink(missing_ok=True)
    path.with_suffix(path.suffix + ".tmp").unlink(missing_ok=True)


def combine_csv(inputs: list[Path], output: Path) -> int:
    if not inputs:
        raise ValueError("incremental aggregation requires bucket prices")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    header: list[str] | None = None
    rows = 0
    try:
        with temporary.open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target)
            for path in inputs:
                with path.open(encoding="utf-8", newline="") as source:
                    reader = csv.reader(source)
                    current = next(reader, None)
                    if not current:
                        raise ValueError(f"bucket prices has no header: {path}")
                    if header is None:
                        header = current
                        writer.writerow(header)
                    elif current != header:
                        raise ValueError(f"bucket prices columns differ: {path}")
                    for row in reader:
                        writer.writerow(row)
                        rows += 1
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return rows


def combine_metadata(
    plan: dict[str, Any], items: list[dict[str, Any]], provider: str, rows: int
) -> dict[str, Any]:
    symbols = [entry for item in items for entry in item.get("symbols", [])]
    raw_symbols = [entry for item in items for entry in item.get("raw_symbols", [])]
    empty_symbols = sorted(
        {
            symbol
            for item in items
            for symbol in metadata_symbols(item.get("empty_symbols", []))
        }
    )
    non_trading_empty = sorted(
        {
            symbol
            for item in items
            for symbol in metadata_symbols(
                item.get("non_trading_only_empty_symbols", [])
            )
        }
    )
    if set(empty_symbols) != set(non_trading_empty):
        raise ValueError(
            "aggregated empty_symbols must match non_trading_only_empty_symbols"
        )
    output_symbols = {
        str(entry.get("symbol", "")).strip()
        for entry in symbols
        if int(entry.get("rows", 0) or 0) > 0
    }
    output_symbols.discard("")
    combined = {
        "source": f"{provider}_incremental_bucket_execution",
        "source_claim_boundary": CLAIM_BOUNDARY,
        "generated_at": now_iso(),
        "provider": provider,
        "rows": rows,
        "symbol_count": len(output_symbols),
        "requested_symbol_count": len(plan["fetch_symbols"]),
        "requested_symbols": plan["fetch_symbols"],
        "symbols": symbols,
        "raw_symbols": raw_symbols,
        "failed_symbols": [],
        "empty_symbols": empty_symbols,
        "non_trading_only_empty_symbols": non_trading_empty,
        "no_trading_update_symbols": non_trading_empty,
        "possibly_truncated_symbols": [],
        "unprocessed_symbols": [],
        "invalid_rows": 0,
        "partial_result": False,
        "partial_result_semantics": PARTIAL_RESULT_SEMANTICS,
        "rate_limit_budget_exhausted": False,
        "rate_limit_exhaustion_reason": "",
        "output_written": True,
        "metadata_output_written": True,
        "bucket_count": len(items),
    }
    combined.update(combined_fetch_metrics(items, rows))
    combined.update(combined_quality_metrics(items))
    combined.update(combined_name_metrics(items))
    combined.update(provider_capabilities(items, provider))
    return combined


def combined_fetch_metrics(items: list[dict[str, Any]], rows: int) -> dict[str, Any]:
    has_raw_rows = any("raw_rows" in item for item in items)
    raw_rows = (
        sum(int(item.get("raw_rows", 0) or 0) for item in items)
        if has_raw_rows
        else rows
    )
    has_requested_rows = any("requested_raw_rows" in item for item in items)
    requested_rows = (
        sum(int(item.get("requested_raw_rows", 0) or 0) for item in items)
        if has_requested_rows
        else raw_rows
    )
    result = {
        "raw_rows": raw_rows,
        "output_rows": rows,
        "requested_raw_rows": requested_rows,
        "api_request_count": sum(
            int(item.get("api_request_count", 0) or 0) for item in items
        ),
        "overfetch_rows": raw_rows - rows,
        "raw_to_output_ratio": round(raw_rows / rows, 6) if rows else None,
    }
    for key in (
        "rate_limit_429_events",
        "network_retry_events",
        "checkpoint_symbols_skipped",
        "checkpoint_requests_executed",
        "checkpoint_integrity_issue_count",
    ):
        if any(key in item for item in items):
            result[key] = sum(int(item.get(key, 0) or 0) for item in items)
    for key in ("rate_limit_sleep_seconds", "network_retry_sleep_seconds"):
        if any(key in item for item in items):
            result[key] = round(
                sum(float(item.get(key, 0) or 0) for item in items), 6
            )
    return result


def combined_quality_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "invalid_rows",
        "raw_non_trading_rows",
        "raw_invalid_non_trading_overlap_rows",
        "non_trading_rows",
        "dropped_non_trading_rows",
        "retained_non_trading_rows",
        "dropped_invalid_rows",
        "tradestatus_missing_rows",
    ):
        if any(key in item for item in items):
            result[key] = sum(int(item.get(key, 0) or 0) for item in items)
    policies = {
        str(item.get("non_trading_policy", "")).strip()
        for item in items
        if str(item.get("non_trading_policy", "")).strip()
    }
    if len(policies) > 1:
        raise ValueError("bucket metadata non_trading_policy values differ")
    if policies:
        result["non_trading_policy"] = next(iter(policies))
    if any("invalid_symbols" in item for item in items):
        result["invalid_symbols"] = sorted(
            {
                str(symbol)
                for item in items
                for symbol in item.get("invalid_symbols", [])
                if str(symbol)
            }
        )
    if any("invalid_row_examples" in item for item in items):
        result["invalid_row_examples"] = [
            example
            for item in items
            for example in item.get("invalid_row_examples", [])
            if isinstance(example, dict)
        ][:10]
    semantics = {
        str(item.get("raw_quality_counter_semantics", "")).strip()
        for item in items
        if str(item.get("raw_quality_counter_semantics", "")).strip()
    }
    if len(semantics) > 1:
        raise ValueError("bucket metadata raw_quality_counter_semantics values differ")
    if semantics:
        result["raw_quality_counter_semantics"] = next(iter(semantics))
    return result


def combined_name_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("name_lookup_count", "names_input_count", "name_query_count"):
        if any(key in item for item in items):
            result[key] = sum(int(item.get(key, 0) or 0) for item in items)
    for key in ("name_lookup_failed_symbols", "name_lookup_missing_symbols"):
        if any(key in item for item in items):
            result[key] = sorted(
                {
                    str(symbol)
                    for item in items
                    for symbol in item.get(key, [])
                    if str(symbol)
                }
            )
    return result


def provider_capabilities(
    items: list[dict[str, Any]], provider: str
) -> dict[str, Any]:
    if provider != "pytdx":
        return {}
    first = items[0] if items else {}
    return {
        "allowed_merge_fields": first.get(
            "allowed_merge_fields", PYTDX_ALLOWED_MERGE_FIELDS
        ),
        "merge_join_keys": first.get("merge_join_keys", ["symbol", "date"]),
        "strict_fields_same_date_required": True,
        "selection_ready": False,
    }


def metadata_symbols(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    symbols = []
    for item in value:
        raw = item.get("symbol", "") if isinstance(item, dict) else item
        if str(raw).strip():
            symbols.append(str(raw).strip())
    return sorted(set(symbols))


def required_text(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key, "")).strip()
    if not value:
        raise ValueError(f"fetch bucket requires {key}")
    return value


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
