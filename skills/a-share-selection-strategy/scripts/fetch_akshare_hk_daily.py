#!/usr/bin/env python3
"""Fetch Hong Kong OHLCV data through akshare stock_hk_daily."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lib.selection_core.a_share_selection_symbols import (
    normalize_hk_symbol,
    valid_hk_symbol_text,
)


SOURCE = "akshare_stock_hk_daily"
CLAIM_BOUNDARY = "akshare_stock_hk_daily_not_exchange_calendar_or_tradability_proof"
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
REQUIRED_COLUMNS = ["date", *NUMERIC_COLUMNS]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output)
    metadata_output = Path(args.metadata_output)
    try:
        frame, metadata = fetch_prices(args)
        frame, metadata = apply_quality_policy(frame, metadata, args.drop_invalid_rows)
        metadata = output_status(
            metadata, output_written=True, metadata_output_written=True
        )
        write_outputs(frame, metadata, output, metadata_output)
    except Exception as exc:  # noqa: BLE001
        remove_output(output)
        remove_output(metadata_output)
        print(
            "ERROR: code=fetch_failed output_written=false "
            f"metadata_output_written=false source_claim_boundary={CLAIM_BOUNDARY} "
            f"message={exc}",
            file=sys.stderr,
        )
        return 2
    strict_errors = strict_gate_errors(
        metadata, fail_on_fetch_error=args.fail_on_fetch_error
    )
    if strict_errors:
        metadata = output_status(
            metadata, output_written=False, metadata_output_written=True
        )
        remove_output(output)
        write_metadata(metadata, metadata_output)
        print_summary(metadata, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; "
            f"{'; '.join(strict_errors)} output_written=false metadata_output_written=true",
            file=sys.stderr,
        )
        return 3
    print_summary(metadata, prefix=summary_prefix(metadata))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch akshare stock_hk_daily OHLCV into local CSV and metadata. "
            "This does not prove HKEX calendar, real-time coverage, tradability, "
            "or long-term source stability."
        )
    )
    parser.add_argument("--symbols", required=True, help="Comma-separated HK symbols.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument(
        "--metadata-output", required=True, help="Output metadata JSON path."
    )
    parser.add_argument(
        "--adjust", default="", help="akshare adjust value. Default: empty."
    )
    parser.add_argument("--fail-on-fetch-error", action="store_true")
    parser.add_argument(
        "--drop-invalid-rows",
        action="store_true",
        help="Explicitly drop invalid OHLCV rows and disclose dropped counts.",
    )
    return parser


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module

    globals().update({"pd": pandas_module})


def fetch_prices(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
    try:
        import akshare as ak
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("akshare is required for this fetch script") from exc
    rows: list[dict[str, Any]] = []
    symbols_meta: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for symbol in parse_symbols(args.symbols):
        try:
            symbol_rows = fetch_symbol(ak, args, symbol)
        except Exception as exc:  # noqa: BLE001
            symbol_rows = []
            failed.append({"symbol": symbol, "error": str(exc)})
        rows.extend(symbol_rows)
        symbols_meta.append(symbol_metadata(symbol, symbol_rows))
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    return frame, build_metadata(args, frame, symbols_meta, failed)


def fetch_symbol(
    ak: Any, args: argparse.Namespace, symbol: str
) -> list[dict[str, Any]]:
    raw = ak.stock_hk_daily(symbol=symbol, adjust=args.adjust)
    return collect_rows(filter_date_range(raw, args.start_date, args.end_date), symbol)


def parse_symbols(text: str) -> list[str]:
    raw_symbols = [item.strip() for item in text.split(",") if item.strip()]
    symbols = []
    invalid = []
    for raw_symbol in raw_symbols:
        normalized = normalize_hk_symbol(raw_symbol)
        if not valid_hk_symbol_text(normalized):
            invalid.append(raw_symbol)
            continue
        symbols.append(normalized.zfill(5))
    if invalid:
        raise ValueError(
            f"HK symbols must be 1 to 5 digits or HK-prefixed/suffixed: {','.join(invalid)}"
        )
    if not symbols:
        raise ValueError("symbols must not be empty")
    return symbols


def akshare_date(text: str) -> str:
    compact = text.replace("-", "").strip()
    if not compact.isdigit() or len(compact) != 8:
        raise ValueError(f"date must be YYYY-MM-DD or YYYYMMDD: {text}")
    return compact


def filter_date_range(
    frame: pd.DataFrame, start_date: str, end_date: str
) -> pd.DataFrame:
    ensure_runtime_dependencies()
    if frame.empty:
        return frame
    if "date" not in frame.columns:
        raise ValueError("akshare stock_hk_daily missing date column")
    start = pd.to_datetime(akshare_date(start_date), format="%Y%m%d")
    end = pd.to_datetime(akshare_date(end_date), format="%Y%m%d")
    dates = pd.to_datetime(frame["date"], errors="coerce")
    return frame[(dates >= start) & (dates <= end)].copy()


def collect_rows(frame: pd.DataFrame, symbol: str) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            f"akshare stock_hk_daily missing required columns: {', '.join(missing)}"
        )
    return [row_record(row, symbol) for _, row in frame.iterrows()]


def row_record(row: pd.Series, symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": stock_name(row, symbol),
        "market": "HK",
        "date": row["date"],
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "volume": row["volume"],
        "amount": row["amount"],
    }


def stock_name(row: pd.Series, symbol: str) -> str:
    value = row.get("name", "")
    if pd.isna(value):
        return symbol
    text = str(value).strip()
    return text or symbol


def symbol_metadata(symbol: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [str(row["date"]) for row in rows if str(row["date"])]
    return {
        "symbol": symbol,
        "provider": SOURCE,
        "rows": len(rows),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
    }


def build_metadata(
    args: argparse.Namespace,
    frame: pd.DataFrame,
    symbols_meta: list[dict[str, Any]],
    failed: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "source_scope": f"{SOURCE}_history_fetch",
        "source_type": "external_fetch",
        "source_claim_boundary": CLAIM_BOUNDARY,
        "data_source_note": (
            "akshare stock_hk_daily landed OHLCV; source stability, HKEX calendar, "
            "real-time coverage, and tradability are not proven"
        ),
        "real_market_data": "unknown",
        "requested_symbols": parse_symbols(args.symbols),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "market": "HK",
        "adjust": args.adjust,
        "rows": int(len(frame)),
        "raw_rows": int(len(frame)),
        "symbol_count": int(frame["symbol"].nunique()) if not frame.empty else 0,
        "symbols": symbols_meta,
        "failed_symbols": failed,
        "empty_symbols": empty_symbols(symbols_meta),
        "invalid_rows": 0,
        "invalid_symbols": [],
        "invalid_row_examples": [],
        "dropped_invalid_rows": 0,
    }


def output_status(
    metadata: dict[str, Any],
    *,
    output_written: bool,
    metadata_output_written: bool,
) -> dict[str, Any]:
    return {
        **metadata,
        "output_written": bool(output_written),
        "metadata_output_written": bool(metadata_output_written),
    }


def apply_quality_policy(
    frame: pd.DataFrame,
    metadata: dict[str, Any],
    drop_invalid_rows: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
    invalid = invalid_row_details(frame)
    metadata = dict(metadata)
    metadata["invalid_rows"] = len(invalid)
    metadata["invalid_symbols"] = sorted({item["symbol"] for item in invalid})
    metadata["invalid_row_examples"] = invalid[:10]
    metadata["dropped_invalid_rows"] = len(invalid) if drop_invalid_rows else 0
    result = (
        frame.drop(index=[item["index"] for item in invalid])
        if drop_invalid_rows
        else frame
    )
    result = result.reset_index(drop=True)
    metadata["rows"] = int(len(result))
    metadata["symbol_count"] = (
        int(result["symbol"].nunique()) if not result.empty else 0
    )
    metadata["symbols"] = [
        symbol_metadata_for_frame(symbol, result)
        for symbol in metadata["requested_symbols"]
    ]
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
    ensure_runtime_dependencies()
    invalid = []
    for column in NUMERIC_COLUMNS:
        value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
        if pd.isna(value):
            invalid.append(column)
    return invalid


def symbol_metadata_for_frame(symbol: str, frame: pd.DataFrame) -> dict[str, Any]:
    rows = (
        []
        if frame.empty
        else frame[frame["symbol"].astype(str) == symbol].to_dict("records")
    )
    return symbol_metadata(symbol, rows)


def empty_symbols(symbols_meta: list[dict[str, Any]]) -> list[str]:
    return [str(item["symbol"]) for item in symbols_meta if int(item["rows"]) == 0]


def strict_gate_errors(
    metadata: dict[str, Any],
    *,
    fail_on_fetch_error: bool,
) -> list[str]:
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
        errors.append(
            f"symbol_count={metadata['symbol_count']} "
            f"requested_symbols={len(metadata['requested_symbols'])}"
        )
    return errors


def summary_prefix(metadata: dict[str, Any]) -> str:
    if (
        metadata["failed_symbols"]
        or metadata["empty_symbols"]
        or metadata["symbol_count"] != len(metadata["requested_symbols"])
    ):
        return "PARTIAL"
    return "OK"


def write_outputs(
    frame: pd.DataFrame, metadata: dict[str, Any], output: Path, meta: Path
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    write_metadata(metadata, meta)


def write_metadata(metadata: dict[str, Any], meta: Path) -> None:
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def remove_output(output: Path) -> None:
    if not output.exists() and not output.is_symlink():
        return
    if output.is_dir() and not output.is_symlink():
        return
    output.unlink()


def print_summary(metadata: dict[str, Any], prefix: str = "OK") -> None:
    print(
        f"{prefix}: source={SOURCE} rows={metadata['rows']} "
        f"symbol_count={metadata['symbol_count']} "
        f"failed_symbols={len(metadata['failed_symbols'])} "
        f"empty_symbols={len(metadata['empty_symbols'])} "
        f"invalid_rows={metadata['invalid_rows']} "
        f"dropped_invalid_rows={metadata['dropped_invalid_rows']} "
        f"start_date={metadata['start_date']} end_date={metadata['end_date']} "
        f"adjust={metadata['adjust']} source_claim_boundary={CLAIM_BOUNDARY}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
