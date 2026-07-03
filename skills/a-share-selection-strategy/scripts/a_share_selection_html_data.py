"""Data loading helpers for the local A-share HTML report."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from a_share_selection_html_format import failure_reason, missing_key_disclosure_value
from a_share_selection_symbols import stock_symbol_key


HTML_REPORT_ROWS_LIMIT = 25
HTML_DIAGNOSTIC_ROWS_LIMIT = 80
HTML_MASTER_ROWS_LIMIT = 1000
HTML_CANDLE_ROWS_LIMIT = 80
HTML_CANDLE_SYMBOL_LIMIT = 100

PRICE_COLUMN_ALIASES = {
    "symbol": ("symbol", "code", "ticker", "ts_code"),
    "date": ("date", "trade_date"),
    "open": ("open", "open_price"),
    "high": ("high", "high_price"),
    "low": ("low", "low_price"),
    "close": ("close", "close_price"),
    "volume": ("volume", "vol"),
}
REQUIRED_PRICE_COLUMNS = ("symbol", "date", "open", "high", "low", "close")


def candidate_rows(summary: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    if not output_written(summary, "candidates_output_written"):
        return [], False
    return read_csv_rows(summary.get("candidates_output", ""), HTML_REPORT_ROWS_LIMIT)


def full_candidate_rows(summary: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    if not output_written(summary, "candidates_output_written"):
        return [], False
    return read_csv_rows(summary.get("candidates_output", ""), HTML_MASTER_ROWS_LIMIT)


def diagnostic_rows(summary: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    if not output_written(summary, "diagnostics_output_written"):
        return [], False
    rows, truncated = read_csv_rows(summary.get("diagnostics_output", ""), HTML_DIAGNOSTIC_ROWS_LIMIT)
    return [diagnostic_display_row(row) for row in rows], truncated


def candidate_candle_rows(summary: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, list[list[Any]]]:
    if not output_written(summary, "prices_output_written"):
        return {}
    path = Path(str(summary.get("prices_output", "")))
    if not path.is_file() or path.suffix.lower() != ".csv":
        return {}
    symbol_lookup = candidate_symbol_lookup(rows)
    if not symbol_lookup:
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = price_columns(reader.fieldnames or [])
        if not all(columns.get(column) for column in REQUIRED_PRICE_COLUMNS):
            return {}
        buckets = {symbol: [] for symbol in symbol_lookup.values()}
        for row in reader:
            symbol_key = stock_symbol_key(row.get(columns["symbol"], ""))
            symbol = symbol_lookup.get(symbol_key)
            if not symbol:
                continue
            candle = parse_candle_row(row, columns)
            if candle is not None:
                buckets[symbol].append(candle)
    return limited_candle_rows(buckets)


def candidate_symbol_lookup(rows: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in rows:
        symbol = str(row.get("symbol", "")).strip()
        key = stock_symbol_key(symbol)
        if symbol and key and key not in lookup:
            lookup[key] = symbol
        if len(lookup) >= HTML_CANDLE_SYMBOL_LIMIT:
            break
    return lookup


def price_columns(fieldnames: list[str]) -> dict[str, str]:
    lower = {name.lower(): name for name in fieldnames}
    columns = {}
    for key, aliases in PRICE_COLUMN_ALIASES.items():
        columns[key] = next((lower[alias.lower()] for alias in aliases if alias.lower() in lower), "")
    return columns


def parse_candle_row(row: dict[str, Any], columns: dict[str, str]) -> list[Any] | None:
    date = normalized_candle_date(row.get(columns["date"], ""))
    open_price = finite_float(row.get(columns["open"], ""))
    high_price = finite_float(row.get(columns["high"], ""))
    low_price = finite_float(row.get(columns["low"], ""))
    close_price = finite_float(row.get(columns["close"], ""))
    if (
        not date
        or open_price is None
        or high_price is None
        or low_price is None
        or close_price is None
        or min(open_price, high_price, low_price, close_price) <= 0
        or high_price < low_price
    ):
        return None
    volume = finite_float(row.get(columns.get("volume", ""), "")) if columns.get("volume") else None
    return [date, open_price, high_price, low_price, close_price, volume]


def limited_candle_rows(buckets: dict[str, list[list[Any]]]) -> dict[str, list[list[Any]]]:
    candles = {}
    for symbol, rows in buckets.items():
        if not rows:
            continue
        rows.sort(key=candle_sort_key)
        candles[symbol] = rows[-HTML_CANDLE_ROWS_LIMIT:]
    return candles


def candle_sort_key(row: list[Any]) -> str:
    return str(row[0]).replace("-", "")


def normalized_candle_date(value: Any) -> str:
    text = str(value).strip()
    digits = text.replace("-", "").replace("/", "")
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    return text


def finite_float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def output_written(summary: dict[str, Any], key: str) -> bool:
    return summary.get(key) is True


def diagnostic_display_row(row: dict[str, Any]) -> dict[str, Any]:
    display = dict(row)
    reason = failure_reason(row)
    display["failure_reason"] = reason or missing_key_disclosure_value("failure_reason")
    return display


def read_csv_rows(path_value: Any, limit: int | None) -> tuple[list[dict[str, Any]], bool]:
    path = Path(str(path_value)) if path_value else Path()
    if not path_value or not path.is_file() or path.suffix.lower() != ".csv":
        return [], False
    with path.open(encoding="utf-8", newline="") as handle:
        rows = []
        for index, row in enumerate(csv.DictReader(handle)):
            if limit is not None and index >= limit:
                return rows, True
            rows.append(row)
    return rows, False


def report_output_dir(summary: dict[str, Any]) -> Path | None:
    for key in ("html_report", "candidates_output", "diagnostics_output", "prices_output"):
        value = str(summary.get(key, ""))
        if value:
            return Path(value).parent
    return None


def evidence_path(value: Any, output_dir: Path | None) -> dict[str, str]:
    path_text = str(value) if value else ""
    if not path_text:
        return {"display": "", "title": ""}
    path = Path(path_text)
    display = relative_or_name(path, output_dir)
    return {"display": display, "title": path_text}


def relative_or_name(path: Path, output_dir: Path | None) -> str:
    if output_dir is not None:
        try:
            relative = path.resolve().relative_to(output_dir.resolve())
            return f"./{relative.as_posix()}"
        except (OSError, ValueError):
            pass
    return path.name or str(path)


def summary_path(summary: dict[str, Any]) -> str:
    output_dir = report_output_dir(summary)
    return str(output_dir / "summary.json") if output_dir is not None else ""


def manifest_path(summary: dict[str, Any]) -> str:
    output_dir = report_output_dir(summary)
    return str(output_dir / "run_manifest.json") if output_dir is not None else ""


def first_line(value: Any) -> str:
    for line in str(value).splitlines():
        if line.strip():
            return line.strip()
    return ""

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
