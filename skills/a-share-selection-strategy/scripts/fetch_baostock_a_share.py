#!/usr/bin/env python3
"""Fetch A-share OHLCV data through baostock and save local gate files."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from lib.fetch.baostock_a_share_universe import (
    baostock_a_share_stock_symbol,
    collect_a_share_stock_symbols,
    is_baostock_a_share_stock_code,
)
from lib.fetch.baostock_a_share_names import (
    collect_stock_basic_name,
    fetch_symbol_names,
    resolve_symbol_names,
)
from lib.selection_core.a_share_selection_symbols import (
    baostock_code,
    parse_six_digit_symbols,
    read_symbols_file,
)


FIELDS = (
    "date,code,open,high,low,close,preclose,pctChg,volume,amount,turn,tradestatus,isST"
)
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount", "turn"]
CLAIM_BOUNDARY = "baostock_external_api_not_broker_order_or_full_market_proof"
DATA_SOURCE_NOTE = "baostock public API; scope is requested symbols and date range only"
OUTPUT_FORMATS = {".csv": "csv", ".parquet": "parquet", ".pq": "parquet"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch baostock A-share daily data into local CSV or Parquet and metadata. "
            "Exit 0 plus written files still require metadata and gate review."
        )
    )
    parser.add_argument("--symbols", help="Comma-separated six-digit symbols.")
    parser.add_argument(
        "--symbols-file",
        help="Text file containing comma-separated or newline-separated symbols.",
    )
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument(
        "--output",
        required=True,
        help=(
            "Output CSV or Parquet path. Parquet requires pyarrow or fastparquet."
        ),
    )
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
    parser.add_argument(
        "--names-input",
        default="",
        help="Optional CSV or Parquet with symbol/name columns.",
    )
    parser.add_argument(
        "--missing-name-policy",
        choices=("query", "fail", "blank"),
        default="query",
        help="How to handle names absent from --names-input. Default: query.",
    )
    parser.add_argument(
        "--non-trading-policy",
        choices=("reject", "drop", "keep"),
        default="reject",
        help="How to handle tradestatus values other than 1. Default: reject.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output)
    metadata_output = Path(args.metadata_output)
    try:
        normalize_symbol_arguments(args)
    except ValueError as exc:
        return fail_before_fetch(
            output,
            metadata_output,
            code="invalid_argument",
            message=str(exc),
        )
    try:
        output_format = prices_output_format(output)
    except ValueError as exc:
        return fail_before_fetch(
            output,
            metadata_output,
            code="invalid_output_format",
            message=str(exc),
        )
    if output.resolve() == metadata_output.resolve():
        return fail_before_fetch(
            output,
            metadata_output,
            code="invalid_output_path",
            message="prices output and metadata output must differ",
        )
    if output_format == "parquet" and not parquet_engine_available():
        return fail_before_fetch(
            output,
            metadata_output,
            code="missing_dependency",
            message="Parquet output requires pyarrow or fastparquet",
        )
    try:
        metadata = fetch_and_write(
            args,
            output,
            metadata_output,
            output_format=output_format,
        )
    except Exception as exc:  # noqa: BLE001
        return fail_before_fetch(
            output,
            metadata_output,
            code="fetch_failed",
            message=str(exc),
        )
    strict_errors = strict_gate_errors(metadata, fail_on_fetch_error=args.fail_on_fetch_error)
    if strict_errors:
        metadata = output_status(
            metadata, output_written=False, metadata_output_written=True
        )
        remove_output(output)
        write_metadata(metadata, metadata_output)
        print_summary(metadata, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; "
            f"{'; '.join(strict_errors)} output_written=false "
            "metadata_output_written=true "
            f"source_claim_boundary={CLAIM_BOUNDARY}",
            file=sys.stderr,
        )
        return 3
    print_summary(metadata, prefix=summary_prefix(metadata))
    return 0


def fail_before_fetch(
    output: Path,
    metadata_output: Path,
    *,
    code: str,
    message: str,
) -> int:
    remove_output(output)
    remove_output(metadata_output)
    print(
        f"ERROR: code={code} output_written=false metadata_output_written=false "
        f"source_claim_boundary={CLAIM_BOUNDARY} message={message}",
        file=sys.stderr,
    )
    return 2


def fetch_and_write(
    args: argparse.Namespace,
    output: Path,
    metadata_output: Path,
    *,
    output_format: str,
) -> dict[str, Any]:
    frame, metadata = fetch_prices(args)
    frame, metadata = apply_quality_policy(
        frame,
        metadata,
        drop_invalid_rows=args.drop_invalid_rows,
        non_trading_policy=args.non_trading_policy,
    )
    metadata = output_status(
        metadata, output_written=True, metadata_output_written=True
    )
    metadata.update(
        {
            "output_format": output_format,
            "output_path": str(output),
        }
    )
    write_outputs(
        frame,
        metadata,
        output,
        metadata_output,
        output_format=output_format,
    )
    return metadata


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import lib.selection_core.a_share_selection_tradability as tradability_module

    globals().update(
        {
            "pd": pandas_module,
            "prefixed_tradability_stats": tradability_module.prefixed_tradability_stats,
            "raw_quality_counter_metadata": tradability_module.raw_quality_counter_metadata,
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
        name_lookup = resolve_symbol_names(
            bs,
            symbols,
            getattr(args, "names_input", ""),
            getattr(args, "missing_name_policy", "query"),
        )
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


def normalize_symbol_arguments(args: argparse.Namespace) -> None:
    if args.symbols and args.symbols_file:
        raise ValueError("use either --symbols or --symbols-file, not both")
    if args.symbols_file:
        try:
            args.symbols = read_symbols_file(Path(args.symbols_file))
        except OSError as exc:
            raise ValueError(str(exc)) from exc
    if not str(args.symbols or "").strip():
        raise ValueError("provide --symbols or --symbols-file")
    args.symbols = ",".join(dict.fromkeys(parse_symbols(args.symbols)))


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
        "source_type": "external_fetch",
        "source_scope": "baostock_history_fetch",
        "real_market_data": True,
        "partial_result": partial_result(failed, symbols_meta),
        "source_claim_boundary": CLAIM_BOUNDARY,
        "data_source_note": DATA_SOURCE_NOTE,
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
        "names_input": name_lookup.get("input_path", ""),
        "names_input_count": int(name_lookup.get("input_name_count", 0)),
        "name_query_count": int(name_lookup.get("query_count", 0)),
        "missing_name_policy": name_lookup.get(
            "policy", getattr(args, "missing_name_policy", "query")
        ),
        "non_trading_policy": getattr(args, "non_trading_policy", "reject"),
        "dropped_non_trading_rows": 0,
        **prefixed_tradability_stats(frame, "raw_"),
        **tradability_stats(frame),
    }


def partial_result(
    failed: list[dict[str, Any]],
    symbols_meta: list[dict[str, Any]],
) -> bool:
    return bool(failed or empty_symbols(symbols_meta))


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
    non_trading_policy: str = "reject",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
    invalid = invalid_row_details(frame)
    metadata = dict(metadata)
    metadata["raw_symbols"] = list(metadata.get("symbols", []))
    metadata["invalid_rows"] = len(invalid)
    metadata["invalid_symbols"] = sorted({item["symbol"] for item in invalid})
    metadata["invalid_row_examples"] = invalid[:10]
    metadata["dropped_invalid_rows"] = len(invalid) if drop_invalid_rows else 0
    metadata.update(
        raw_quality_counter_metadata(frame, (item["index"] for item in invalid))
    )
    result = (
        frame.drop(index=[item["index"] for item in invalid])
        if drop_invalid_rows
        else frame
    )
    if non_trading_policy not in {"reject", "drop", "keep"}:
        raise ValueError(f"unsupported non-trading-policy: {non_trading_policy}")
    raw_non_trading_mask = non_trading_row_mask(frame)
    non_trading_mask = non_trading_row_mask(result)
    dropped_non_trading = int(non_trading_mask.sum()) if non_trading_policy == "drop" else 0
    if dropped_non_trading:
        result = result.loc[~non_trading_mask]
    result = result.reset_index(drop=True)
    empty_after_quality = set(
        empty_symbols(
            [
                symbol_metadata_for_frame(symbol, result)
                for symbol in metadata["requested_symbols"]
            ]
        )
    )
    metadata["non_trading_only_empty_symbols"] = sorted(
        symbol
        for symbol in empty_after_quality
        if not frame.loc[frame["symbol"].eq(symbol)].empty
        and bool(raw_non_trading_mask.loc[frame["symbol"].eq(symbol)].all())
    )
    metadata["non_trading_policy"] = non_trading_policy
    metadata["dropped_non_trading_rows"] = dropped_non_trading
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
    metadata["partial_result"] = partial_result(
        metadata.get("failed_symbols", []),
        metadata["symbols"],
    )
    return result, metadata


def non_trading_row_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty or "tradestatus" not in frame:
        return pd.Series([False] * len(frame), index=frame.index)
    status = frame["tradestatus"].astype(str).str.strip()
    return status.ne("") & status.ne("1")


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
    if (
        metadata.get("non_trading_policy", "reject") == "reject"
        and metadata.get("non_trading_rows", 0)
    ):
        errors.append(f"non_trading_rows={metadata['non_trading_rows']}")
    if fail_on_fetch_error and metadata["failed_symbols"]:
        errors.append(f"failed_symbols={len(metadata['failed_symbols'])}")
    if fail_on_fetch_error and metadata["empty_symbols"]:
        errors.append(f"empty_symbols={len(metadata['empty_symbols'])}")
    missing_name_policy = metadata.get("missing_name_policy", "query")
    name_failure_is_strict = missing_name_policy != "blank" and (
        fail_on_fetch_error or missing_name_policy == "fail"
    )
    if name_failure_is_strict and metadata.get("name_lookup_failed_symbols"):
        errors.append(
            f"name_lookup_failed_symbols={len(metadata['name_lookup_failed_symbols'])}"
        )
    if name_failure_is_strict and metadata.get("name_lookup_missing_symbols"):
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
    *,
    output_format: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "csv":
        frame.to_csv(output, index=False)
    else:
        frame.to_parquet(output, index=False)
    write_metadata(metadata, metadata_output)


def prices_output_format(output: Path) -> str:
    output_format = OUTPUT_FORMATS.get(output.suffix.lower())
    if output_format is None:
        raise ValueError(
            "unsupported prices output format; use .csv, .parquet, or .pq"
        )
    return output_format


def parquet_engine_available() -> bool:
    return any(
        importlib.util.find_spec(module) is not None
        for module in ("pyarrow", "fastparquet")
    )


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
        f"names_input_count={metadata.get('names_input_count', 0)} "
        f"name_query_count={metadata.get('name_query_count', 0)} "
        f"missing_name_policy={metadata.get('missing_name_policy', 'query')} "
        f"non_trading_policy={metadata.get('non_trading_policy', 'reject')} "
        f"dropped_non_trading_rows={metadata.get('dropped_non_trading_rows', 0)} "
        f"non_trading_rows={metadata.get('non_trading_rows', 0)} "
        f"tradestatus_missing_rows={metadata.get('tradestatus_missing_rows', 0)} "
        f"start_date={metadata['start_date']} end_date={metadata['end_date']} "
        f"adjustflag={metadata['adjustflag']} "
        f"output_format={metadata.get('output_format', 'csv')} "
        f"output_path={metadata.get('output_path', '')}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
