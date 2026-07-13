"""pytdx A-share history fetch helpers."""

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


from datetime import date, datetime
from typing import Any

from lib.selection_core.a_share_selection_symbols import parse_six_digit_symbols


CLAIM_BOUNDARY = "pytdx_external_fetch_not_turnover_tradability_or_stability_proof"
DATA_SOURCE_NOTE = (
    "pytdx TDX-compatible quote server; no token is configured, but package "
    "license metadata is UNKNOWN and provider stability/commercial-use rights "
    "are not proven"
)
DEFAULT_HOST = "218.6.170.47"
DEFAULT_PORT = 7709
TDX_DAILY_CATEGORY = 9
OUTPUT_COLUMNS = [
    "symbol",
    "name",
    "market",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]
ALLOWED_MERGE_FIELDS = ["open", "high", "low", "close", "volume", "amount"]
MERGE_JOIN_KEYS = ["symbol", "date"]
RECENT_WINDOW_SAFETY_ROWS = 8
MINIMUM_FIRST_REQUEST_ROWS = 16


def validate_arguments(args: Any) -> None:
    parse_symbols(args.symbols)
    start = pytdx_date(args.start_date)
    end = pytdx_date(args.end_date)
    if start > end:
        raise ValueError("start-date must be earlier than or equal to end-date")
    if int(args.page_size) > 800:
        raise ValueError("page-size must not exceed pytdx get_security_bars count 800")
    if not str(args.host).strip():
        raise ValueError("host must not be empty")


def parse_symbols(text: str) -> list[str]:
    return parse_six_digit_symbols(text)


def pytdx_date(text: str) -> str:
    normalized = str(text).replace("-", "").strip()
    if not normalized.isdigit() or len(normalized) != 8:
        raise ValueError(f"date must be YYYY-MM-DD or YYYYMMDD: {text}")
    try:
        parsed = datetime.strptime(normalized, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"date must be a real calendar date: {text}") from exc
    return parsed.date().isoformat()


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import importlib.metadata as importlib_metadata
    import pandas as pandas_module
    from pytdx.hq import TdxHq_API

    globals().update(
        {
            "importlib_metadata": importlib_metadata,
            "pd": pandas_module,
            "TdxHq_API": TdxHq_API,
        }
    )


def fetch_prices(args: Any) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
    rows: list[dict[str, Any]] = []
    symbols_meta: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    api = TdxHq_API(auto_retry=True, raise_exception=True)
    connected = api.connect(
        str(args.host),
        int(args.port),
        time_out=float(args.timeout_seconds),
    )
    if not connected:
        raise RuntimeError(f"pytdx connect failed: {args.host}:{args.port}")
    try:
        for symbol in parse_symbols(args.symbols):
            symbol_rows: list[dict[str, Any]] = []
            observation = empty_fetch_observation()
            try:
                symbol_rows, observation = fetch_symbol_rows(api, args, symbol)
            except Exception as exc:  # noqa: BLE001
                failed.append({"symbol": symbol, "error": str(exc)})
            rows.extend(symbol_rows)
            symbols_meta.append(symbol_metadata(symbol, symbol_rows, observation))
    finally:
        api.disconnect()
    frame = pd.DataFrame(unique_sorted_rows(rows), columns=OUTPUT_COLUMNS)
    return frame, build_metadata(args, frame, symbols_meta, failed)


def fetch_symbol_rows(
    api: Any,
    args: Any,
    symbol: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start_date = pytdx_date(args.start_date)
    end_date = pytdx_date(args.end_date)
    rows: list[dict[str, Any]] = []
    observation = empty_fetch_observation()
    offset = 0
    request_count = initial_request_count(start_date, int(args.page_size))
    raw_dates: list[str] = []
    for _request_index in range(int(args.max_pages)):
        observation["request_counts"].append(request_count)
        observation["request_offsets"].append(offset)
        observation["requested_raw_rows"] += request_count
        observation["api_request_count"] += 1
        raw_rows = api.get_security_bars(
            TDX_DAILY_CATEGORY,
            pytdx_market_code(symbol),
            symbol,
            offset,
            request_count,
        )
        if not raw_rows:
            observation["provider_exhausted"] = True
            break
        observation["raw_rows"] += len(raw_rows)
        page_rows = [normalize_bar(symbol, raw) for raw in raw_rows]
        rows.extend(row for row in page_rows if start_date <= row["date"] <= end_date)
        page_dates = [row["date"] for row in page_rows if row["date"]]
        raw_dates.extend(page_dates)
        if page_dates and min(page_dates) <= start_date:
            observation["reached_start_boundary"] = True
            break
        if len(raw_rows) < request_count:
            observation["provider_exhausted"] = True
            break
        offset += len(raw_rows)
        request_count = int(args.page_size)
    observation["oldest_raw_date"] = min(raw_dates) if raw_dates else ""
    observation["newest_raw_date"] = max(raw_dates) if raw_dates else ""
    observation["window_complete"] = bool(
        observation["reached_start_boundary"] or observation["provider_exhausted"]
    )
    observation["output_rows"] = len(rows)
    observation["overfetch_rows"] = observation["raw_rows"] - len(rows)
    observation["raw_to_output_ratio"] = (
        round(observation["raw_rows"] / len(rows), 6) if rows else None
    )
    return rows, observation


def initial_request_count(
    start_date: str,
    page_size: int,
    *,
    today: date | None = None,
) -> int:
    start = datetime.strptime(pytdx_date(start_date), "%Y-%m-%d").date()
    current = today or date.today()
    calendar_rows = max((current - start).days + 1, 1)
    estimated = max(
        MINIMUM_FIRST_REQUEST_ROWS,
        calendar_rows + RECENT_WINDOW_SAFETY_ROWS,
    )
    return min(page_size, estimated)


def empty_fetch_observation() -> dict[str, Any]:
    return {
        "api_request_count": 0,
        "requested_raw_rows": 0,
        "request_counts": [],
        "request_offsets": [],
        "raw_rows": 0,
        "output_rows": 0,
        "overfetch_rows": 0,
        "raw_to_output_ratio": None,
        "oldest_raw_date": "",
        "newest_raw_date": "",
        "reached_start_boundary": False,
        "provider_exhausted": False,
        "window_complete": False,
    }


def pytdx_market_code(symbol: str) -> int:
    return 1 if str(symbol).startswith(("5", "6", "9")) else 0


def normalize_bar(symbol: str, raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": "",
        "market": "A-share",
        "date": bar_date(raw),
        "open": raw.get("open", ""),
        "high": raw.get("high", ""),
        "low": raw.get("low", ""),
        "close": raw.get("close", ""),
        "volume": raw.get("volume", raw.get("vol", "")),
        "amount": raw.get("amount", ""),
    }


def bar_date(raw: dict[str, Any]) -> str:
    if raw.get("date"):
        return pytdx_date(str(raw["date"]).split()[0])
    if raw.get("datetime"):
        return pytdx_date(str(raw["datetime"]).split()[0])
    parts = [raw.get("year"), raw.get("month"), raw.get("day")]
    if all(part not in (None, "") for part in parts):
        return pytdx_date(f"{int(parts[0]):04d}{int(parts[1]):02d}{int(parts[2]):02d}")
    return ""


def unique_sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(str(row["symbol"]), str(row["date"])): row for row in rows}
    return [indexed[key] for key in sorted(indexed)]


def symbol_metadata(
    symbol: str,
    rows: list[dict[str, Any]],
    observation: dict[str, Any],
) -> dict[str, Any]:
    dates = [row["date"] for row in rows if row["date"]]
    fetch_metrics = dict(observation)
    fetch_metrics["output_rows"] = len(rows)
    fetch_metrics["overfetch_rows"] = int(fetch_metrics.get("raw_rows", 0)) - len(rows)
    fetch_metrics["raw_to_output_ratio"] = (
        round(int(fetch_metrics.get("raw_rows", 0)) / len(rows), 6) if rows else None
    )
    return {
        **fetch_metrics,
        "symbol": symbol,
        "market_code": pytdx_market_code(symbol),
        "rows": len(rows),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
    }


def build_metadata(
    args: Any,
    frame: pd.DataFrame,
    symbols_meta: list[dict[str, Any]],
    failed: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "source": "pytdx",
        "source_type": "external_fetch",
        "source_scope": "pytdx_history_fetch",
        "metadata_source": "pytdx",
        "real_market_data": True,
        "partial_result": bool(
            failed or empty_symbols(symbols_meta) or truncated_symbols(symbols_meta)
        ),
        "source_claim_boundary": CLAIM_BOUNDARY,
        "data_source_note": DATA_SOURCE_NOTE,
        "token_configured": False,
        "license_claim_boundary": "pypi_license_unknown_readme_personal_research_boundary",
        "pytdx_version": provider_version(),
        "host": str(args.host),
        "port": int(args.port),
        "timeout_seconds": float(args.timeout_seconds),
        "category": TDX_DAILY_CATEGORY,
        "page_size": int(args.page_size),
        "max_pages": int(args.max_pages),
        "requested_symbols": parse_symbols(args.symbols),
        "start_date": pytdx_date(args.start_date),
        "end_date": pytdx_date(args.end_date),
        "market": "A-share",
        "rows": int(len(frame)),
        "raw_rows": int(sum(int(item["raw_rows"]) for item in symbols_meta)),
        "output_rows": int(len(frame)),
        "requested_raw_rows": int(
            sum(int(item["requested_raw_rows"]) for item in symbols_meta)
        ),
        "api_request_count": int(
            sum(int(item["api_request_count"]) for item in symbols_meta)
        ),
        "overfetch_rows": int(
            sum(int(item["overfetch_rows"]) for item in symbols_meta)
        ),
        "raw_to_output_ratio": (
            round(
                sum(int(item["raw_rows"]) for item in symbols_meta) / len(frame), 6
            )
            if len(frame)
            else None
        ),
        "symbol_count": int(frame["symbol"].nunique()) if not frame.empty else 0,
        "symbols": symbols_meta,
        "failed_symbols": failed,
        "empty_symbols": empty_symbols(symbols_meta),
        "possibly_truncated_symbols": truncated_symbols(symbols_meta),
        "allowed_merge_fields": ALLOWED_MERGE_FIELDS,
        "merge_join_keys": MERGE_JOIN_KEYS,
        "strict_fields_same_date_required": True,
        "selection_ready": False,
        "missing_provider_fields": ["turn", "tradestatus", "isST", "name"],
        "name_value_policy": "blank_missing_provider_name",
        "invalid_rows": 0,
        "invalid_symbols": [],
        "invalid_row_examples": [],
        "dropped_invalid_rows": 0,
    }


def provider_version() -> str:
    try:
        return str(importlib_metadata.version("pytdx"))
    except Exception:  # noqa: BLE001
        return ""


def empty_symbols(symbols_meta: list[dict[str, Any]]) -> list[str]:
    return [str(item["symbol"]) for item in symbols_meta if int(item["rows"]) == 0]


def truncated_symbols(symbols_meta: list[dict[str, Any]]) -> list[str]:
    return [
        str(item["symbol"])
        for item in symbols_meta
        if int(item.get("raw_rows", 0)) > 0 and not item.get("window_complete")
    ]
