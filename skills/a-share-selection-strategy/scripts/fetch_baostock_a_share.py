#!/usr/bin/env python3
"""Fetch A-share OHLCV data through baostock and save local gate files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lib.selection_core.a_share_selection_symbols import (
    baostock_code,
    parse_six_digit_symbols,
)


FIELDS = (
    "date,code,open,high,low,close,preclose,pctChg,volume,amount,turn,tradestatus,isST"
)
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount", "turn"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch baostock A-share daily data into local CSV and metadata. "
            "Exit 0 plus written files still require metadata and gate review."
        )
    )
    parser.add_argument(
        "--symbols", required=True, help="Comma-separated six-digit symbols."
    )
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--output", required=True, help="Output CSV path.")
    parser.add_argument(
        "--metadata-output", required=True, help="Output metadata JSON path."
    )
    parser.add_argument(
        "--adjust", default="3", help="baostock adjustflag. Default: 3."
    )
    parser.add_argument(
        "--fail-on-fetch-error",
        action="store_true",
        help="Fail if metadata contains failed, empty, invalid, or non-trading rows.",
    )
    parser.add_argument(
        "--drop-invalid-rows",
        action="store_true",
        help="Explicitly drop rows with invalid baostock OHLCV, amount, or turn values.",
    )
    args = parser.parse_args(argv)
    output = Path(args.output)
    metadata_output = Path(args.metadata_output)
    try:
        frame, metadata = fetch_prices(args)
        frame, metadata = apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=args.drop_invalid_rows,
        )
        metadata = output_status(
            metadata, output_written=True, metadata_output_written=True
        )
        write_outputs(frame, metadata, output, metadata_output)
    except Exception as exc:  # noqa: BLE001
        remove_output(output)
        print(
            f"ERROR: code=fetch_failed output_written=false message={exc}",
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


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import lib.selection_core.a_share_selection_tradability as tradability_module

    globals().update(
        {
            "pd": pandas_module,
            "prefixed_tradability_stats": tradability_module.prefixed_tradability_stats,
            "tradability_stats": tradability_module.tradability_stats,
        }
    )


def fetch_prices(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
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
            raise RuntimeError(
                f"baostock login failed: {login.error_code} {login.error_msg}"
            )
        symbols = parse_symbols(args.symbols)
        name_lookup = fetch_symbol_names(bs, symbols)
        for symbol in symbols:
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
            symbol_rows = collect_rows(
                result, symbol, name_lookup["names"].get(symbol, "")
            )
            rows.extend(symbol_rows)
            symbols_meta.append(symbol_metadata(symbol, code, symbol_rows))
    finally:
        bs.logout()
    frame = pd.DataFrame(rows)
    metadata = build_metadata(args, frame, symbols_meta, failed, name_lookup)
    return frame, metadata


def parse_symbols(text: str) -> list[str]:
    return parse_six_digit_symbols(text)


def fetch_symbol_names(bs: Any, symbols: list[str]) -> dict[str, Any]:
    names = {}
    failed = []
    missing = []
    for symbol in symbols:
        code = baostock_code(symbol)
        result = bs.query_stock_basic(code=code)
        if result.error_code != "0":
            failed.append({"symbol": symbol, "error": result.error_msg})
            continue
        name = collect_stock_basic_name(result)
        if name:
            names[symbol] = name
        else:
            missing.append(symbol)
    return {
        "source": "baostock_query_stock_basic",
        "names": names,
        "failed_symbols": failed,
        "missing_symbols": missing,
    }


def collect_stock_basic_name(result: Any) -> str:
    while result.next():
        raw = dict(zip(result.fields, result.get_row_data()))
        return str(raw.get("code_name", "")).strip()
    return ""


def collect_rows(result: Any, symbol: str, name: str = "") -> list[dict[str, Any]]:
    rows = []
    clean_name = str(name).strip()
    while result.next():
        raw = dict(zip(result.fields, result.get_row_data()))
        rows.append(
            {
                "symbol": symbol,
                "name": clean_name,
                "market": "A-share",
                "date": raw["date"],
                "open": raw["open"],
                "high": raw["high"],
                "low": raw["low"],
                "close": raw["close"],
                "preclose": raw.get("preclose", ""),
                "pctChg": raw.get("pctChg", ""),
                "volume": raw["volume"],
                "amount": raw["amount"],
                "turn": raw["turn"],
                "tradestatus": raw.get("tradestatus", ""),
                "isST": raw.get("isST", ""),
            }
        )
    return rows


def symbol_metadata(
    symbol: str, code: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
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
    name_lookup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name_lookup = name_lookup or {
        "source": "",
        "names": {},
        "failed_symbols": [],
        "missing_symbols": [],
    }
    return {
        "source": "baostock",
        "requested_symbols": parse_symbols(args.symbols),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "adjustflag": str(args.adjust),
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
        "name_source": name_lookup["source"],
        "name_lookup_count": len(name_lookup["names"]),
        "name_lookup_failed_symbols": name_lookup["failed_symbols"],
        "name_lookup_missing_symbols": name_lookup["missing_symbols"],
        **prefixed_tradability_stats(frame, "raw_"),
        **tradability_stats(frame),
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
    *,
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
    metadata.update(prefixed_tradability_stats(frame, "raw_"))
    metadata.update(tradability_stats(result))
    metadata["symbols"] = [
        symbol_metadata_for_frame(symbol, result)
        for symbol in metadata["requested_symbols"]
    ]
    metadata["empty_symbols"] = empty_symbols(metadata["symbols"])
    return result, metadata


def invalid_row_details(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    numeric = frame[NUMERIC_COLUMNS].apply(pd.to_numeric, errors="coerce")
    invalid_mask = numeric.isna()
    row_mask = invalid_mask.any(axis=1)
    details = []
    for index in frame.index[row_mask]:
        invalid_columns = [
            column for column in NUMERIC_COLUMNS if bool(invalid_mask.at[index, column])
        ]
        row = frame.loc[index]
        details.append(
            {
                "index": int(index),
                "symbol": str(row.get("symbol", "")),
                "date": str(row.get("date", "")),
                "invalid_columns": invalid_columns,
            }
        )
    return details


def invalid_numeric_columns(row: pd.Series) -> list[str]:
    invalid = []
    for column in NUMERIC_COLUMNS:
        value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
        if pd.isna(value):
            invalid.append(column)
    return invalid


def symbol_metadata_for_frame(symbol: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        rows = []
    else:
        rows = frame[frame["symbol"].astype(str) == symbol].to_dict("records")
    return symbol_metadata(symbol, baostock_code(symbol), rows)


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
    if metadata.get("tradestatus_missing_rows", 0):
        errors.append(
            f"tradestatus_missing_rows={metadata['tradestatus_missing_rows']}"
        )
    if metadata.get("non_trading_rows", 0):
        errors.append(f"non_trading_rows={metadata['non_trading_rows']}")
    if fail_on_fetch_error and metadata["failed_symbols"]:
        errors.append(f"failed_symbols={len(metadata['failed_symbols'])}")
    if fail_on_fetch_error and metadata["empty_symbols"]:
        errors.append(f"empty_symbols={len(metadata['empty_symbols'])}")
    if fail_on_fetch_error and metadata.get("name_lookup_failed_symbols"):
        errors.append(
            f"name_lookup_failed_symbols={len(metadata['name_lookup_failed_symbols'])}"
        )
    if fail_on_fetch_error and metadata.get("name_lookup_missing_symbols"):
        errors.append(
            f"name_lookup_missing_symbols={len(metadata['name_lookup_missing_symbols'])}"
        )
    if fail_on_fetch_error:
        requested = len(metadata["requested_symbols"])
        if metadata["symbol_count"] != requested:
            errors.append(
                f"symbol_count={metadata['symbol_count']} requested_symbols={requested}"
            )
    return errors


def summary_prefix(metadata: dict[str, Any]) -> str:
    requested = len(metadata["requested_symbols"])
    if (
        metadata["failed_symbols"]
        or metadata["empty_symbols"]
        or metadata["symbol_count"] != requested
    ):
        return "PARTIAL"
    return "OK"


def write_outputs(
    frame: pd.DataFrame,
    metadata: dict[str, Any],
    output: Path,
    metadata_output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    write_metadata(metadata, metadata_output)


def write_metadata(metadata: dict[str, Any], metadata_output: Path) -> None:
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.write_text(
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
        f"{prefix}: source=baostock rows={metadata['rows']} "
        f"symbol_count={metadata['symbol_count']} "
        f"failed_symbols={len(metadata['failed_symbols'])} "
        f"empty_symbols={len(metadata['empty_symbols'])} "
        f"invalid_rows={metadata['invalid_rows']} "
        f"dropped_invalid_rows={metadata['dropped_invalid_rows']} "
        f"name_lookup_count={metadata.get('name_lookup_count', 0)} "
        f"name_lookup_failed_symbols={len(metadata.get('name_lookup_failed_symbols', []))} "
        f"name_lookup_missing_symbols={len(metadata.get('name_lookup_missing_symbols', []))} "
        f"non_trading_rows={metadata.get('non_trading_rows', 0)} "
        f"tradestatus_missing_rows={metadata.get('tradestatus_missing_rows', 0)} "
        f"start_date={metadata['start_date']} end_date={metadata['end_date']} "
        f"adjustflag={metadata['adjustflag']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
