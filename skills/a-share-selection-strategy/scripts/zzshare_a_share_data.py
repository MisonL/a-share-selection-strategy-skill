"""zzshare A-share fetch and field mapping helpers."""
from __future__ import annotations

import os
import time
from typing import Any

from a_share_selection_symbols import parse_a_share_symbols


OUTPUT_COLUMNS = "symbol name market date open high low close preclose pctChg volume amount turn tradestatus isST source source_type source_scope real_market_data metadata_source source_claim_boundary data_source_note".split()
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount", "turn"]
DEFAULT_HTTP_URL = "https://api.zizizaizai.com"
DEFAULT_FIELDS, DEFAULT_LIMIT = "all", 1000
DEFAULT_REQUEST_INTERVAL_SECONDS = 2.1
CLAIM_BOUNDARY = "zzshare_external_api_not_broker_order_or_long_term_stability_proof"
DATA_SOURCE_NOTE = "zzshare SDK endpoint; quota and stability require external verification"
FetchResult = tuple[list[dict[str, Any]], int, bool, dict[str, Any] | None]
EMPTY_QUALITY_FIELDS = {
    "invalid_rows": 0,
    "invalid_symbols": [],
    "invalid_row_examples": [],
    "dropped_invalid_rows": 0,
}
parse_symbols = parse_a_share_symbols


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import a_share_selection_tradability as tradability_module
    globals().update(
        {
            "pd": pandas_module,
            "prefixed_tradability_stats": tradability_module.prefixed_tradability_stats,
            "tradability_stats": tradability_module.tradability_stats,
        }
    )


def fetch_prices(args: Any) -> tuple[Any, dict[str, Any]]:
    ensure_runtime_dependencies()
    try:
        from zzshare.client import DataApi
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("zzshare is required for this fetch script") from exc
    api = DataApi(
        token=effective_token(args),
        timeout=float(args.timeout_seconds),
        http_url=args.http_url,
    )
    rows, symbols_meta, failed, truncated = [], [], [], []
    symbols = parse_symbols(args.symbols)
    for index, symbol in enumerate(symbols):
        if index and args.request_interval_seconds > 0:
            time.sleep(float(args.request_interval_seconds))
        try:
            symbol_rows, pages_used, possible_truncated, failure = fetch_symbol(api, args, symbol)
        except Exception as exc:  # noqa: BLE001
            symbol_rows = []
            pages_used = 0
            possible_truncated = False
            failure = {"symbol": symbol, "error": str(exc)}
        if failure:
            failed.append(failure)
        if possible_truncated:
            truncated.append(symbol)
        rows.extend(symbol_rows)
        symbols_meta.append(symbol_metadata(symbol, symbol_rows, pages_used, possible_truncated))
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    return frame, build_metadata(args, frame, symbols_meta, failed, truncated)


def effective_token(_args: Any) -> str:
    return str(os.environ.get("ZZSHARE_TOKEN", "")).strip()


def fetch_symbol(api: Any, args: Any, symbol: str) -> FetchResult:
    rows: list[dict[str, Any]] = []
    limit = int(args.limit)
    code = ts_code(symbol)
    start_date = zzshare_date(args.start_date)
    end_date = zzshare_date(args.end_date)
    for page in range(int(args.max_pages)):
        if page and float(args.request_interval_seconds) > 0:
            time.sleep(float(args.request_interval_seconds))
        offset = page * limit
        try:
            raw = api.daily(
                ts_code=code,
                start_date=start_date,
                end_date=end_date,
                fields=args.fields,
                adj=args.adjust,
                limit=limit,
                offset=offset,
            )
            page_rows = collect_rows(raw, symbol)
        except Exception as exc:  # noqa: BLE001
            failure = page_failure(symbol, code, start_date, end_date, page, offset, limit, exc)
            return rows, page, False, failure
        rows.extend(page_rows)
        if len(page_rows) < limit:
            return rows, page + 1, False, None
    possible_truncated = bool(rows and len(rows) >= limit * int(args.max_pages))
    return rows, int(args.max_pages), possible_truncated, None


def page_failure(symbol: str, code: str, start_date: str, end_date: str, page: int, offset: int, limit: int, exc: Exception) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "ts_code": code,
        "page": page + 1,
        "offset": offset,
        "limit": limit,
        "start_date": start_date,
        "end_date": end_date,
        "error": str(exc),
    }


def zzshare_date(text: str) -> str:
    compact = text.replace("-", "").strip()
    if not compact.isdigit() or len(compact) != 8:
        raise ValueError(f"date must be YYYY-MM-DD or YYYYMMDD: {text}")
    return compact


def ts_code(symbol: str) -> str:
    if symbol.startswith(("4", "8", "920")):
        suffix = "BJ"
    else:
        suffix = "SH" if symbol.startswith(("6", "9")) else "SZ"
    return f"{symbol}.{suffix}"


def collect_rows(frame: Any, requested_symbol: str) -> list[dict[str, Any]]:
    ensure_runtime_dependencies()
    if frame.empty:
        return []
    columns = resolve_columns(frame)
    rows = []
    for _, row in frame.iterrows():
        row_symbol = normalize_ts_code_symbol(row_value(row, columns["symbol"], requested_symbol))
        if row_symbol and row_symbol != requested_symbol:
            continue
        rows.append(row_record(row, columns, requested_symbol))
    return rows


def resolve_columns(frame: Any) -> dict[str, str]:
    lookup = {str(column).strip().lower(): str(column) for column in frame.columns}
    required = {
        "symbol": first_present(lookup, ["ts_code", "symbol", "code"]),
        "date": first_present(lookup, ["trade_date", "date"]),
        "open": first_present(lookup, ["open"]),
        "high": first_present(lookup, ["high"]),
        "low": first_present(lookup, ["low"]),
        "close": first_present(lookup, ["close"]),
        "volume": first_present(lookup, ["volume", "vol"]),
        "amount": first_present(lookup, ["turnover", "amount"]),
    }
    missing = [name for name, source in required.items() if not source]
    if missing:
        raise ValueError(f"zzshare daily missing required columns: {', '.join(missing)}")
    return optional_columns(lookup, required)


def optional_columns(lookup: dict[str, str], required: dict[str, str]) -> dict[str, str]:
    return {
        **required,
        "turn": first_present(lookup, ["turnover_rate", "turn", "turnoverrate"]),
        "name": first_present(lookup, ["name"]),
        "preclose": first_present(lookup, ["prev_close", "pre_close", "preclose"]),
        "pctChg": first_present(lookup, ["quote_rate", "pct_chg", "pctChg"]),
        "tradestatus": first_present(lookup, ["tradestatus", "trade_status", "is_paused"]),
        "isST": first_present(lookup, ["is_st", "isST"]),
    }


def first_present(lookup: dict[str, str], names: list[str]) -> str:
    for name in names:
        key = name.lower()
        if key in lookup:
            return lookup[key]
    return ""


def row_record(row: Any, columns: dict[str, str], requested_symbol: str) -> dict[str, Any]:
    paused = row_value(row, columns["tradestatus"])
    source = columns["tradestatus"].lower() == "is_paused" if columns["tradestatus"] else False
    return {
        "symbol": requested_symbol,
        "name": row_value(row, columns["name"]),
        "market": "A-share",
        "date": output_date(row_value(row, columns["date"])),
        "open": row_value(row, columns["open"]),
        "high": row_value(row, columns["high"]),
        "low": row_value(row, columns["low"]),
        "close": row_value(row, columns["close"]),
        "preclose": row_value(row, columns["preclose"]),
        "pctChg": row_value(row, columns["pctChg"]),
        "volume": row_value(row, columns["volume"]),
        "amount": row_value(row, columns["amount"]),
        "turn": row_value(row, columns["turn"]),
        "tradestatus": tradestatus_value(paused, source),
        "isST": row_value(row, columns["isST"]),
        "source": "zzshare",
        "source_type": "external_fetch",
        "source_scope": "zzshare_history_fetch",
        "real_market_data": True,
        "metadata_source": "zzshare",
        "source_claim_boundary": CLAIM_BOUNDARY,
        "data_source_note": DATA_SOURCE_NOTE,
    }


def row_value(row: Any, column: str, default: Any = "") -> Any:
    return row.get(column, default) if column else default


def output_date(value: Any) -> str:
    text = str(value).strip()
    compact = text.replace("-", "")
    if compact.isdigit() and len(compact) == 8:
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
    return text


def normalize_ts_code_symbol(value: Any) -> str:
    text = str(value).strip()
    if "." in text:
        return text.split(".", 1)[0].zfill(6)
    return text.zfill(6) if text.isdigit() else text


def tradestatus_value(value: Any, is_paused_source: bool) -> str:
    if not is_paused_source:
        return str(value).strip() if str(value).strip() else ""
    text = str(value).strip().lower()
    if text in {"0", "0.0", "false"}:
        return "1"
    if text in {"1", "1.0", "true"}:
        return "0"
    return ""


def symbol_metadata(symbol: str, rows: list[dict[str, Any]], pages_used: int, possible_truncated: bool) -> dict[str, Any]:
    dates = [str(row["date"]) for row in rows if str(row["date"])]
    return {
        "symbol": symbol,
        "ts_code": ts_code(symbol),
        "rows": len(rows),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
        "pages_used": int(pages_used),
        "possibly_truncated": bool(possible_truncated),
    }


def build_metadata(args: Any, frame: Any, symbols_meta: list[dict[str, Any]], failed: list[dict[str, Any]], truncated: list[str]) -> dict[str, Any]:
    return {
        "source": "zzshare",
        "source_type": "external_fetch",
        "source_scope": "zzshare_history_fetch",
        "real_market_data": True,
        "source_claim_boundary": CLAIM_BOUNDARY,
        "data_source_note": DATA_SOURCE_NOTE,
        "requested_symbols": parse_symbols(args.symbols),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "adjust": args.adjust,
        "fields": args.fields,
        "limit": int(args.limit),
        "max_pages": int(args.max_pages),
        "http_url": str(args.http_url).rstrip("/"),
        "timeout_seconds": float(args.timeout_seconds),
        "request_interval_seconds": float(args.request_interval_seconds),
        "token_configured": bool(effective_token(args)),
        "rows": int(len(frame)),
        "raw_rows": int(len(frame)),
        "symbol_count": int(frame["symbol"].nunique()) if not frame.empty else 0,
        "symbols": symbols_meta,
        "failed_symbols": failed,
        "empty_symbols": empty_symbols(symbols_meta),
        "possibly_truncated_symbols": truncated,
        **dict(EMPTY_QUALITY_FIELDS),
        **prefixed_tradability_stats(frame, "raw_"),
        **tradability_stats(frame),
    }


def empty_symbols(symbols_meta: list[dict[str, Any]]) -> list[str]:
    return [str(item["symbol"]) for item in symbols_meta if int(item["rows"]) == 0]


if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli
    fail_not_cli(__file__)
