#!/usr/bin/env python3
"""Fetch A-share OHLCV data through baostock and save local gate files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


FIELDS = "date,code,open,high,low,close,volume,amount,turn"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch baostock A-share daily data.")
    parser.add_argument("--symbols", required=True, help="Comma-separated six-digit symbols.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--metadata-output", required=True, help="Output metadata JSON path.")
    parser.add_argument("--adjust", default="3", help="baostock adjustflag. Default: 3.")
    parser.add_argument("--fail-on-fetch-error", action="store_true")
    args = parser.parse_args(argv)
    try:
        frame, metadata = fetch_prices(args)
        write_outputs(frame, metadata, Path(args.output), Path(args.metadata_output))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: code=fetch_failed output_written=false message={exc}", file=sys.stderr)
        return 2
    if args.fail_on_fetch_error and metadata["failed_symbols"]:
        print_summary(metadata, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; "
            f"failed_symbols={len(metadata['failed_symbols'])} output_written=true",
            file=sys.stderr,
        )
        return 3
    print_summary(metadata)
    return 0


def fetch_prices(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        import baostock as bs
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("baostock is required for this fetch script") from exc
    login = bs.login()
    rows = []
    symbols_meta = []
    failed = []
    try:
        if login.error_code != "0":
            raise RuntimeError(f"baostock login failed: {login.error_code} {login.error_msg}")
        for symbol in parse_symbols(args.symbols):
            code = baostock_code(symbol)
            result = bs.query_history_k_data_plus(
                code,
                FIELDS,
                start_date=args.start_date,
                end_date=args.end_date,
                frequency="d",
                adjustflag=str(args.adjust),
            )
            if result.error_code != "0":
                failed.append({"symbol": symbol, "error": result.error_msg})
                continue
            symbol_rows = collect_rows(result, symbol)
            rows.extend(symbol_rows)
            symbols_meta.append(symbol_metadata(symbol, code, symbol_rows))
    finally:
        bs.logout()
    frame = pd.DataFrame(rows)
    metadata = build_metadata(args, frame, symbols_meta, failed)
    return frame, metadata


def parse_symbols(text: str) -> list[str]:
    symbols = [item.strip() for item in text.split(",") if item.strip()]
    invalid = [symbol for symbol in symbols if not symbol.isdigit() or len(symbol) != 6]
    if invalid:
        raise ValueError(f"symbols must be six digits: {','.join(invalid)}")
    return symbols


def baostock_code(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"sh.{symbol}"
    return f"sz.{symbol}"


def collect_rows(result: Any, symbol: str) -> list[dict[str, Any]]:
    rows = []
    while result.next():
        raw = dict(zip(result.fields, result.get_row_data()))
        rows.append(
            {
                "symbol": symbol,
                "name": symbol,
                "market": "A-share",
                "date": raw["date"],
                "open": raw["open"],
                "high": raw["high"],
                "low": raw["low"],
                "close": raw["close"],
                "volume": raw["volume"],
                "amount": raw["amount"],
                "turn": raw["turn"],
            }
        )
    return rows


def symbol_metadata(symbol: str, code: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [row["date"] for row in rows]
    return {
        "symbol": symbol,
        "source_code": code,
        "rows": len(rows),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
    }


def build_metadata(
    args: argparse.Namespace,
    frame: pd.DataFrame,
    symbols_meta: list[dict[str, Any]],
    failed: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source": "baostock",
        "requested_symbols": parse_symbols(args.symbols),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "adjustflag": str(args.adjust),
        "rows": int(len(frame)),
        "symbol_count": int(frame["symbol"].nunique()) if not frame.empty else 0,
        "symbols": symbols_meta,
        "failed_symbols": failed,
    }


def write_outputs(
    frame: pd.DataFrame,
    metadata: dict[str, Any],
    output: Path,
    metadata_output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def print_summary(metadata: dict[str, Any], prefix: str = "OK") -> None:
    print(
        f"{prefix}: source=baostock rows={metadata['rows']} "
        f"symbol_count={metadata['symbol_count']} "
        f"failed_symbols={len(metadata['failed_symbols'])} "
        f"start_date={metadata['start_date']} end_date={metadata['end_date']} "
        f"adjustflag={metadata['adjustflag']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
