#!/usr/bin/env python3
"""Fetch yfinance OHLCV data and save local gate files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


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
]
YFINANCE_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch yfinance OHLCV data.")
    parser.add_argument("--symbols", required=True, help="Comma-separated ticker symbols.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument("--metadata-output", required=True, help="Output metadata JSON path.")
    parser.add_argument("--market", default="US", help="Market label to write. Default: US.")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Per-symbol yfinance history timeout. Default: 30.",
    )
    parser.add_argument("--fail-on-fetch-error", action="store_true")
    args = parser.parse_args(argv)
    try:
        frame, metadata = fetch_prices(args)
        write_outputs(frame, metadata, Path(args.output), Path(args.metadata_output))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: code=fetch_failed output_written=false message={exc}", file=sys.stderr)
        return 2
    strict_errors = strict_gate_errors(metadata, fail_on_fetch_error=args.fail_on_fetch_error)
    if strict_errors:
        print_summary(metadata, args.output, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; "
            f"{'; '.join(strict_errors)} output_written=true",
            file=sys.stderr,
        )
        return 3
    print_summary(metadata, args.output)
    return 0


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module

    globals().update({"pd": pandas_module})


def fetch_prices(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
    try:
        import yfinance as yf
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("yfinance is required for this fetch script") from exc
    rows = []
    symbols_meta = []
    failed = []
    for symbol in parse_symbols(args.symbols):
        symbol_rows = []
        try:
            history = yf.Ticker(symbol).history(
                start=args.start_date,
                end=args.end_date,
                auto_adjust=False,
                actions=False,
                timeout=args.timeout_seconds,
            )
            symbol_rows = history_rows(history, symbol, market=args.market)
        except Exception as exc:  # noqa: BLE001
            failed.append({"symbol": symbol, "error": str(exc)})
        rows.extend(symbol_rows)
        symbols_meta.append(symbol_metadata(symbol, symbol_rows))
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    return frame, build_metadata(args, frame, symbols_meta, failed)


def parse_symbols(text: str) -> list[str]:
    symbols = [item.strip().upper() for item in text.split(",") if item.strip()]
    if not symbols:
        raise ValueError("symbols must not be empty")
    invalid = [symbol for symbol in symbols if "," in symbol or symbol != symbol.strip()]
    if invalid:
        raise ValueError(f"invalid symbols: {','.join(invalid)}")
    return symbols


def history_rows(history: pd.DataFrame, symbol: str, *, market: str) -> list[dict[str, Any]]:
    ensure_runtime_dependencies()
    if history.empty:
        return []
    columns = resolve_columns(history)
    frame = history.copy()
    frame.index.name = "date"
    frame = frame.reset_index()
    rows = []
    for _, row in frame.iterrows():
        date = pd.to_datetime(row["date"], errors="coerce")
        rows.append(
            {
                "symbol": symbol,
                "name": symbol,
                "market": market,
                "date": date.date().isoformat() if not pd.isna(date) else "",
                "open": row[columns["Open"]],
                "high": row[columns["High"]],
                "low": row[columns["Low"]],
                "close": row[columns["Close"]],
                "volume": row[columns["Volume"]],
            }
        )
    return rows


def resolve_columns(frame: pd.DataFrame) -> dict[str, Any]:
    lookup = {str(column).lower(): column for column in frame.columns}
    result = {}
    missing = []
    for column in YFINANCE_COLUMNS:
        key = column.lower()
        if key not in lookup:
            missing.append(column)
        else:
            result[column] = lookup[key]
    if missing:
        raise ValueError(f"yfinance history missing columns: {', '.join(missing)}")
    return result


def symbol_metadata(symbol: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [row["date"] for row in rows if row["date"]]
    return {
        "symbol": symbol,
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
        "source": "yfinance",
        "requested_symbols": parse_symbols(args.symbols),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "market": args.market,
        "timeout_seconds": float(args.timeout_seconds),
        "adjustment": "auto_adjust_false_close",
        "rows": int(len(frame)),
        "symbol_count": int(frame["symbol"].nunique()) if not frame.empty else 0,
        "symbols": symbols_meta,
        "failed_symbols": failed,
        "empty_symbols": empty_symbols(symbols_meta),
    }


def empty_symbols(symbols_meta: list[dict[str, Any]]) -> list[str]:
    return [str(item["symbol"]) for item in symbols_meta if int(item["rows"]) == 0]


def strict_gate_errors(
    metadata: dict[str, Any],
    *,
    fail_on_fetch_error: bool,
) -> list[str]:
    errors = []
    if metadata["rows"] == 0:
        errors.append("rows=0")
    if fail_on_fetch_error and metadata["failed_symbols"]:
        errors.append(f"failed_symbols={len(metadata['failed_symbols'])}")
    if fail_on_fetch_error and metadata["empty_symbols"]:
        errors.append(f"empty_symbols={len(metadata['empty_symbols'])}")
    if fail_on_fetch_error:
        requested = len(metadata["requested_symbols"])
        if metadata["symbol_count"] != requested:
            errors.append(
                f"symbol_count={metadata['symbol_count']} requested_symbols={requested}"
            )
    return errors


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


def print_summary(
    metadata: dict[str, Any],
    output: str,
    prefix: str = "OK",
) -> None:
    print(
        f"{prefix}: source=yfinance rows={metadata['rows']} "
        f"symbol_count={metadata['symbol_count']} "
        f"failed_symbols={len(metadata['failed_symbols'])} "
        f"empty_symbols={len(metadata['empty_symbols'])} output={output}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
