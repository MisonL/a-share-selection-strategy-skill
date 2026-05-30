#!/usr/bin/env python3
"""Fetch A-share OHLCV data through akshare and save local gate files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


OUTPUT_COLUMNS = ["symbol", "name", "market", "date", "open", "high", "low", "close", "volume", "amount", "turn"]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount", "turn"]
SCHEMAS = [
    dict(date="日期", symbol="股票代码", open="开盘", high="最高", low="最低", close="收盘", volume="成交量", amount="成交额", turn="换手率"),
    dict(date="date", symbol="", open="open", high="high", low="low", close="close", volume="volume", amount="amount", turn="turnover"),
]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        frame, metadata = fetch_prices(args)
        frame, metadata = apply_quality_policy(frame, metadata, args.drop_invalid_rows)
        write_outputs(frame, metadata, Path(args.output), Path(args.metadata_output))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: code=fetch_failed output_written=false message={exc}", file=sys.stderr)
        return 2
    strict_errors = strict_gate_errors(metadata, args.fail_on_fetch_error)
    if strict_errors:
        print_summary(metadata, prefix="ERROR_SUMMARY")
        print(f"ERROR: strict gate failed; {'; '.join(strict_errors)} output_written=true", file=sys.stderr)
        return 3
    print_summary(metadata)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch akshare A-share daily data.")
    parser.add_argument("--symbols", required=True, help="Comma-separated six-digit symbols.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--metadata-output", required=True, help="Output metadata JSON path.")
    parser.add_argument("--adjust", default="", help="akshare adjust value. Default: empty.")
    parser.add_argument("--fail-on-fetch-error", action="store_true")
    parser.add_argument("--drop-invalid-rows", action="store_true")
    return parser


def fetch_prices(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        import akshare as ak
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("akshare is required for this fetch script") from exc
    rows: list[dict[str, Any]] = []
    symbols_meta: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    fallbacks: list[dict[str, str]] = []
    for symbol in parse_symbols(args.symbols):
        try:
            symbol_rows, provider, fallback_error = fetch_symbol(ak, args, symbol)
        except Exception as exc:  # noqa: BLE001
            symbol_rows, provider, fallback_error = [], "", ""
            failed.append({"symbol": symbol, "error": str(exc)})
        rows.extend(symbol_rows)
        if fallback_error:
            fallbacks.append({"symbol": symbol, "error": fallback_error})
        symbols_meta.append(symbol_metadata(symbol, symbol_rows, provider))
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    return frame, build_metadata(args, frame, symbols_meta, failed, fallbacks)


def fetch_symbol(ak: Any, args: argparse.Namespace, symbol: str) -> tuple[list[dict[str, Any]], str, str]:
    error = ""
    try:
        raw = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=akshare_date(args.start_date),
            end_date=akshare_date(args.end_date),
            adjust=args.adjust,
        )
        rows = collect_rows(raw, symbol)
        if rows:
            return rows, "stock_zh_a_hist", ""
        error = "stock_zh_a_hist returned empty data"
    except Exception as exc:  # noqa: BLE001
        error = f"stock_zh_a_hist failed: {exc}"
    raw = ak.stock_zh_a_daily(
        symbol=akshare_daily_symbol(symbol),
        start_date=akshare_date(args.start_date),
        end_date=akshare_date(args.end_date),
        adjust=args.adjust,
    )
    rows = collect_rows(raw, symbol)
    if not rows:
        raise ValueError(f"stock_zh_a_daily returned empty data after fallback: {error}")
    return rows, "stock_zh_a_daily", error


def parse_symbols(text: str) -> list[str]:
    symbols = [item.strip() for item in text.split(",") if item.strip()]
    invalid = [symbol for symbol in symbols if not symbol.isdigit() or len(symbol) != 6]
    if invalid:
        raise ValueError(f"symbols must be six digits: {','.join(invalid)}")
    if not symbols:
        raise ValueError("symbols must not be empty")
    return symbols


def akshare_date(text: str) -> str:
    compact = text.replace("-", "").strip()
    if not compact.isdigit() or len(compact) != 8:
        raise ValueError(f"date must be YYYY-MM-DD or YYYYMMDD: {text}")
    return compact


def akshare_daily_symbol(symbol: str) -> str:
    return ("sh" if symbol.startswith(("6", "9")) else "sz") + symbol


def collect_rows(frame: pd.DataFrame, requested_symbol: str) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    columns = resolve_columns(frame)
    return [row_record(row, columns, requested_symbol) for _, row in frame.iterrows()]


def row_record(row: pd.Series, columns: dict[str, str], requested_symbol: str) -> dict[str, Any]:
    symbol = row_symbol(row, columns, requested_symbol)
    return {
        "symbol": symbol,
        "name": symbol,
        "market": "A-share",
        "date": row[columns["date"]],
        "open": row[columns["open"]],
        "high": row[columns["high"]],
        "low": row[columns["low"]],
        "close": row[columns["close"]],
        "volume": row[columns["volume"]],
        "amount": row[columns["amount"]],
        "turn": row[columns["turn"]],
    }


def resolve_columns(frame: pd.DataFrame) -> dict[str, str]:
    for schema in SCHEMAS:
        required = [source for key, source in schema.items() if key != "symbol"]
        if all(source in frame.columns for source in required):
            return {key: source for key, source in schema.items() if source}
    raise ValueError("akshare history missing required OHLCV columns")


def row_symbol(row: pd.Series, columns: dict[str, str], fallback: str) -> str:
    symbol = str(row[columns["symbol"]]).strip() if "symbol" in columns else fallback
    return symbol.zfill(6) if symbol.isdigit() else symbol


def symbol_metadata(symbol: str, rows: list[dict[str, Any]], provider: str) -> dict[str, Any]:
    dates = [str(row["date"]) for row in rows if str(row["date"])]
    return {
        "symbol": symbol,
        "provider": provider,
        "rows": len(rows),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
    }


def build_metadata(
    args: argparse.Namespace,
    frame: pd.DataFrame,
    symbols_meta: list[dict[str, Any]],
    failed: list[dict[str, str]],
    fallbacks: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "source": "akshare",
        "requested_symbols": parse_symbols(args.symbols),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "adjust": args.adjust,
        "rows": int(len(frame)),
        "raw_rows": int(len(frame)),
        "symbol_count": int(frame["symbol"].nunique()) if not frame.empty else 0,
        "symbols": symbols_meta,
        "failed_symbols": failed,
        "fallback_errors": fallbacks,
        "empty_symbols": empty_symbols(symbols_meta),
        "invalid_rows": 0,
        "invalid_symbols": [],
        "invalid_row_examples": [],
        "dropped_invalid_rows": 0,
    }


def apply_quality_policy(
    frame: pd.DataFrame,
    metadata: dict[str, Any],
    drop_invalid_rows: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    invalid = invalid_row_details(frame)
    metadata = dict(metadata)
    metadata["invalid_rows"] = len(invalid)
    metadata["invalid_symbols"] = sorted({item["symbol"] for item in invalid})
    metadata["invalid_row_examples"] = invalid[:10]
    metadata["dropped_invalid_rows"] = len(invalid) if drop_invalid_rows else 0
    result = frame.drop(index=[item["index"] for item in invalid]) if drop_invalid_rows else frame
    result = result.reset_index(drop=True)
    metadata["rows"] = int(len(result))
    metadata["symbol_count"] = int(result["symbol"].nunique()) if not result.empty else 0
    providers = {str(item["symbol"]): str(item["provider"]) for item in metadata["symbols"]}
    metadata["symbols"] = [symbol_metadata_for_frame(symbol, result, providers.get(symbol, "")) for symbol in metadata["requested_symbols"]]
    metadata["empty_symbols"] = empty_symbols(metadata["symbols"])
    return result, metadata


def invalid_row_details(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "index": int(index),
            "symbol": str(row.get("symbol", "")),
            "date": str(row.get("date", "")),
            "invalid_columns": invalid_columns,
        }
        for index, row in frame.iterrows()
        if (invalid_columns := invalid_numeric_columns(row))
    ]


def invalid_numeric_columns(row: pd.Series) -> list[str]:
    invalid = []
    for column in NUMERIC_COLUMNS:
        value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
        if pd.isna(value):
            invalid.append(column)
    return invalid


def symbol_metadata_for_frame(symbol: str, frame: pd.DataFrame, provider: str) -> dict[str, Any]:
    rows = [] if frame.empty else frame[frame["symbol"].astype(str) == symbol].to_dict("records")
    return symbol_metadata(symbol, rows, provider)


def empty_symbols(symbols_meta: list[dict[str, Any]]) -> list[str]:
    return [str(item["symbol"]) for item in symbols_meta if int(item["rows"]) == 0]


def strict_gate_errors(metadata: dict[str, Any], fail_on_fetch_error: bool) -> list[str]:
    errors = []
    if metadata["invalid_rows"] != metadata["dropped_invalid_rows"]:
        errors.append(f"invalid_rows={metadata['invalid_rows']}")
    if not fail_on_fetch_error:
        return errors
    if metadata["failed_symbols"]:
        errors.append(f"failed_symbols={len(metadata['failed_symbols'])}")
    if metadata["empty_symbols"]:
        errors.append(f"empty_symbols={len(metadata['empty_symbols'])}")
    if metadata["symbol_count"] != len(metadata["requested_symbols"]):
        errors.append(f"symbol_count={metadata['symbol_count']} requested_symbols={len(metadata['requested_symbols'])}")
    return errors


def write_outputs(frame: pd.DataFrame, metadata: dict[str, Any], output: Path, meta: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def print_summary(metadata: dict[str, Any], prefix: str = "OK") -> None:
    print(
        f"{prefix}: source=akshare rows={metadata['rows']} symbol_count={metadata['symbol_count']} "
        f"failed_symbols={len(metadata['failed_symbols'])} empty_symbols={len(metadata['empty_symbols'])} "
        f"invalid_rows={metadata['invalid_rows']} dropped_invalid_rows={metadata['dropped_invalid_rows']} "
        f"fallback_errors={len(metadata['fallback_errors'])} start_date={metadata['start_date']} "
        f"end_date={metadata['end_date']} adjust={metadata['adjust']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
