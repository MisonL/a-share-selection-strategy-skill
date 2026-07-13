"""baostock A-share universe fetch helpers."""

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

from datetime import date, datetime, timedelta
import time
from typing import Any

from lib.fetch.baostock_a_share_universe_metadata import (
    CLAIM_BOUNDARY,
    CSV_COLUMNS,
    build_metadata,
    output_status,
    print_summary,
    strict_errors,
    utc_now,
)

SZ_A_SHARE_STOCK_PREFIXES = ("000", "001", "002", "003", "300", "301")
SH_A_SHARE_STOCK_PREFIXES = ("600", "601", "603", "605", "688", "689")


class BaostockUniverseFetchError(RuntimeError):
    def __init__(self, message: str, resolution: dict[str, Any]) -> None:
        super().__init__(message)
        self.resolution = resolution


def fetch_universe(args: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started_at = utc_now()
    started = time.monotonic()
    errors = []
    resolution = empty_resolution(args)
    try:
        import baostock as bs
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("baostock is required for this fetch script") from exc
    for attempt in range(fetch_attempt_count(args)):
        if attempt and float(args.retry_interval_seconds) > 0:
            time.sleep(float(args.retry_interval_seconds))
        try:
            rows, metadata = fetch_universe_once(args, bs, started_at, started)
            if errors:
                metadata = {
                    **metadata,
                    "fetch_errors": list(errors),
                    "fetch_error_count": len(errors),
                    "fetch_attempts": len(errors) + 1,
                }
            return rows, metadata
        except Exception as exc:  # noqa: BLE001
            resolution = getattr(exc, "resolution", resolution)
            errors.append(
                {
                    "attempt": attempt + 1,
                    "error": str(exc),
                    "attempted_dates": list(resolution.get("attempted_dates", [])),
                }
            )
    return [], build_failure_metadata(args, started_at, started, errors, resolution)


def fetch_attempt_count(args: Any) -> int:
    return int(args.retries) + 1


def fetch_universe_once(
    args: Any,
    bs: Any,
    started_at: str,
    started: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    login = bs.login()
    error = ""
    resolution = empty_resolution(args)
    collected: dict[str, Any] = empty_collection()
    try:
        if login.error_code != "0":
            raise RuntimeError(
                f"baostock login failed: {login.error_code} {login.error_msg}"
            )
        collected, error, resolution = query_universe_with_lookback(bs, args)
    finally:
        bs.logout()
    symbols = [str(symbol) for symbol in collected["symbols"]]
    names = collected.get("names", {})
    rows = [spot_row(symbol, str(names.get(symbol, ""))) for symbol in symbols]
    metadata = build_metadata(
        args,
        rows,
        collected,
        error=error,
        resolution=resolution,
        started_at=started_at,
        monotonic_started=started,
        fetch_errors=[],
        fetch_attempts=1,
    )
    return rows, metadata


def build_failure_metadata(
    args: Any,
    started_at: str,
    started: float,
    errors: list[dict[str, Any]],
    resolution: dict[str, Any],
) -> dict[str, Any]:
    return build_metadata(
        args,
        [],
        empty_collection(),
        error=errors[-1]["error"] if errors else "fetch failed",
        resolution=resolution,
        started_at=started_at,
        monotonic_started=started,
        fetch_errors=errors,
        fetch_attempts=len(errors),
    )


def empty_collection() -> dict[str, Any]:
    return {
        "symbols": [],
        "symbol_count": 0,
        "raw_row_count": 0,
        "names": {},
        "excluded": [],
        "excluded_count": 0,
    }


def query_universe_with_lookback(
    bs: Any,
    args: Any,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    attempts = []
    last_error = ""
    for day in candidate_dates(args):
        result = bs.query_all_stock(day=day)
        if result.error_code != "0":
            last_error = str(result.error_msg)
            attempts.append({"date": day, "error": last_error, "raw_rows": 0})
            raise BaostockUniverseFetchError(
                f"baostock query_all_stock failed for {day}: {last_error}",
                resolution_for(args, attempts, ""),
            )
        collected = collect_a_share_stock_symbols(result)
        raw_rows = int(collected.get("raw_row_count", 0) or 0)
        symbol_count = int(collected.get("symbol_count", 0) or 0)
        attempts.append(
            {
                "date": day,
                "error": "",
                "raw_rows": raw_rows,
                "symbol_count": symbol_count,
            }
        )
        if symbol_count:
            return collected, "", resolution_for(args, attempts, day)
    return empty_collection(), last_error, resolution_for(args, attempts, "")


def collect_a_share_stock_symbols(result: Any) -> dict[str, Any]:
    symbols = []
    excluded = []
    names = {}
    seen = set()
    raw_row_count = 0
    for raw in iter_all_stock_rows(result):
        raw_row_count += 1
        code = str(raw.get("code", "")).strip()
        symbol = baostock_a_share_stock_symbol(code)
        if symbol:
            if symbol not in seen:
                symbols.append(symbol)
                seen.add(symbol)
            name = str(raw.get("code_name") or raw.get("name") or "").strip()
            if name and symbol not in names:
                names[symbol] = name
            continue
        excluded.append({"code": code, "reason": "not_mainland_a_share_stock"})
    return {
        "source": "baostock_query_all_stock",
        "symbols": symbols,
        "symbol_count": len(symbols),
        "raw_row_count": raw_row_count,
        "names": names,
        "excluded": excluded,
        "excluded_count": len(excluded),
        "filter": "沪深A股股票前缀，不含指数、基金、ETF、B股或北交所代码",
    }


def iter_all_stock_rows(result: Any) -> Any:
    if hasattr(result, "next") and hasattr(result, "get_row_data"):
        fields = list(getattr(result, "fields", []))
        while result.next():
            yield dict(zip(fields, result.get_row_data()))
        return
    for row in result:
        if isinstance(row, dict):
            yield row
        else:
            yield {"code": str(row)}


def is_baostock_a_share_stock_code(code: str) -> bool:
    return bool(baostock_a_share_stock_symbol(code))


def baostock_a_share_stock_symbol(code: str) -> str:
    parts = str(code).strip().lower().split(".")
    if len(parts) != 2:
        return ""
    exchange, symbol = parts
    if len(symbol) != 6 or not symbol.isdigit():
        return ""
    if exchange == "sz" and symbol.startswith(SZ_A_SHARE_STOCK_PREFIXES):
        return symbol
    if exchange == "sh" and symbol.startswith(SH_A_SHARE_STOCK_PREFIXES):
        return symbol
    return ""


def candidate_dates(args: Any) -> list[str]:
    start = parse_snapshot_date(str(args.snapshot_date or ""))
    return [
        (start - timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in range(int(args.lookback_days) + 1)
    ]


def parse_snapshot_date(text: str) -> date:
    if not text:
        return date.today()
    normalized = text.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    raise ValueError("snapshot-date must be YYYY-MM-DD or YYYYMMDD")


def empty_resolution(args: Any) -> dict[str, Any]:
    dates = candidate_dates(args)
    return resolution_for(args, [], dates[0] if dates else "")


def resolution_for(
    args: Any,
    attempts: list[dict[str, Any]],
    resolved_date: str,
) -> dict[str, Any]:
    requested = candidate_dates(args)[0]
    return {
        "requested_snapshot_date": requested,
        "resolved_snapshot_date": resolved_date,
        "lookback_days": int(args.lookback_days),
        "attempted_dates": attempts,
        "date_resolution_mode": (
            "exact_date" if int(args.lookback_days) == 0 else "lookback_until_nonempty"
        ),
        "date_fallback_used": bool(resolved_date and resolved_date != requested),
    }


def spot_row(symbol: str, name: str = "") -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": name,
        "spot_price": "",
        "spot_pct_chg": "",
        "spot_amount": "",
        "spot_industry": "",
    }
