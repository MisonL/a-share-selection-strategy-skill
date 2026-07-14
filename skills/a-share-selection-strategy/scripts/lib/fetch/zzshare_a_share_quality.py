"""Quality gates and output helpers for zzshare A-share fetches."""

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


import json
from pathlib import Path
from typing import Any

import lib.fetch.zzshare_a_share_data as data


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
    frame: Any,
    metadata: dict[str, Any],
    *,
    drop_invalid_rows: bool,
    non_trading_policy: str,
) -> tuple[Any, dict[str, Any]]:
    data.ensure_runtime_dependencies()
    invalid = invalid_row_details(frame)
    raw_tradability = data.prefixed_tradability_stats(frame, "raw_")
    metadata = quality_metadata(
        metadata,
        invalid,
        drop_invalid_rows,
        non_trading_policy,
    )
    metadata.update(
        data.raw_quality_counter_metadata(frame, (item["index"] for item in invalid))
    )
    result = (
        frame.drop(index=[item["index"] for item in invalid])
        if drop_invalid_rows
        else frame
    )
    result, dropped_non_trading = apply_non_trading_policy(
        result,
        non_trading_policy,
    )
    result = result.reset_index(drop=True)
    metadata["rows"] = int(len(result))
    metadata["symbol_count"] = (
        int(result["symbol"].nunique()) if not result.empty else 0
    )
    metadata.update(raw_tradability)
    metadata.update(data.tradability_stats(result))
    metadata["dropped_non_trading_rows"] = int(dropped_non_trading)
    metadata["retained_non_trading_rows"] = int(metadata.get("non_trading_rows", 0))
    pages_map = metadata_symbol_pages_map(metadata)
    symbol_summary = symbol_metadata_summary(result)
    metadata["symbols"] = [
        symbol_metadata_for_frame(symbol, symbol_summary.get(symbol), pages_map.get(symbol))
        for symbol in metadata["requested_symbols"]
    ]
    excluded_empty = {
        str(item.get("symbol", "") if isinstance(item, dict) else item).strip()
        for key in ("failed_symbols", "unprocessed_symbols")
        for item in metadata.get(key, [])
        if str(item.get("symbol", "") if isinstance(item, dict) else item).strip()
    }
    metadata["empty_symbols"] = [
        symbol
        for symbol in data.empty_symbols(metadata["symbols"])
        if symbol not in excluded_empty
    ]
    metadata["partial_result"] = bool(
        metadata.get("failed_symbols")
        or metadata["empty_symbols"]
        or metadata.get("possibly_truncated_symbols")
        or metadata.get("unprocessed_symbols")
        or metadata.get("rate_limit_budget_exhausted") is True
    )
    return result, metadata


def quality_metadata(
    metadata: dict[str, Any],
    invalid: list[dict[str, Any]],
    drop_invalid_rows: bool,
    non_trading_policy: str,
) -> dict[str, Any]:
    return {
        **metadata,
        "non_trading_policy": non_trading_policy,
        "invalid_rows": len(invalid),
        "invalid_symbols": sorted({item["symbol"] for item in invalid}),
        "invalid_row_examples": invalid[:10],
        "dropped_invalid_rows": len(invalid) if drop_invalid_rows else 0,
    }


def apply_non_trading_policy(frame: Any, policy: str) -> tuple[Any, int]:
    if policy != "drop" or frame.empty or "tradestatus" not in frame:
        return frame, 0
    status = frame["tradestatus"].astype(str).str.strip()
    non_trading = status.ne("1") & status.ne("")
    if not non_trading.any():
        return frame, 0
    return frame.loc[~non_trading], int(non_trading.sum())


def metadata_symbol_pages_map(metadata: dict[str, Any]) -> dict[str, tuple[int, bool]]:
    pages_map = {}
    for item in metadata.get("symbols", []):
        symbol = str(item.get("symbol", ""))
        if not symbol:
            continue
        pages_map[symbol] = (
            int(item.get("pages_used", 0)),
            bool(item.get("possibly_truncated", False)),
        )
    return pages_map


def metadata_symbol_pages(metadata: dict[str, Any], symbol: str) -> tuple[int, bool]:
    for item in metadata.get("symbols", []):
        if str(item.get("symbol", "")) == symbol:
            return int(item.get("pages_used", 0)), bool(
                item.get("possibly_truncated", False)
            )
    return 0, False


def invalid_row_details(frame: Any) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    pd = data.pd
    numeric = frame[data.NUMERIC_COLUMNS].apply(pd.to_numeric, errors="coerce")
    invalid_matrix = numeric.isna()
    invalid_rows = invalid_matrix.any(axis=1)
    if not bool(invalid_rows.any()):
        return []
    details = []
    invalid_frame = frame.loc[invalid_rows, ["symbol", "date"]]
    invalid_columns_frame = invalid_matrix.loc[invalid_rows]
    for index in invalid_frame.index:
        invalid_columns = [
            column
            for column, is_invalid in invalid_columns_frame.loc[index].items()
            if bool(is_invalid)
        ]
        if not invalid_columns:
            continue
        row = invalid_frame.loc[index]
        details.append(
            {
                "index": int(index),
                "symbol": str(row.get("symbol", "")),
                "date": str(row.get("date", "")),
                "invalid_columns": invalid_columns,
            }
        )
    return details


def symbol_metadata_for_frame(
    symbol: str,
    summary: dict[str, Any] | None,
    pages: tuple[int, bool] | None,
) -> dict[str, Any]:
    pages = pages or (0, False)
    summary = summary or {}
    return {
        "symbol": symbol,
        "ts_code": data.ts_code(symbol),
        "rows": int(summary.get("rows", 0)),
        "date_min": str(summary.get("date_min", "")),
        "date_max": str(summary.get("date_max", "")),
        "pages_used": int(pages[0]),
        "possibly_truncated": bool(pages[1]),
    }


def symbol_metadata_summary(frame: Any) -> dict[str, dict[str, Any]]:
    if frame.empty:
        return {}
    grouped = (
        frame.assign(_symbol_key=frame["symbol"].astype(str))
        .groupby("_symbol_key", sort=False)["date"]
        .agg(["size", "min", "max"])
    )
    summary = {}
    for symbol, row in grouped.iterrows():
        summary[str(symbol)] = {
            "rows": int(row["size"]),
            "date_min": str(row["min"]),
            "date_max": str(row["max"]),
        }
    return summary


def strict_gate_errors(
    metadata: dict[str, Any],
    *,
    fail_on_fetch_error: bool,
) -> list[str]:
    errors = base_gate_errors(metadata)
    if fail_on_fetch_error and metadata["failed_symbols"]:
        errors.append(f"failed_symbols={len(metadata['failed_symbols'])}")
    if fail_on_fetch_error and metadata["empty_symbols"]:
        errors.append(f"empty_symbols={len(metadata['empty_symbols'])}")
    if fail_on_fetch_error and metadata.get("possibly_truncated_symbols"):
        errors.append(
            f"possibly_truncated_symbols={len(metadata['possibly_truncated_symbols'])}"
        )
    if fail_on_fetch_error:
        requested = len(metadata["requested_symbols"])
        if metadata["symbol_count"] != requested:
            errors.append(
                f"symbol_count={metadata['symbol_count']} requested_symbols={requested}"
            )
    return errors


def base_gate_errors(metadata: dict[str, Any]) -> list[str]:
    errors = []
    if metadata.get("rate_limit_budget_exhausted"):
        errors.append(
            "rate_limit_budget_exhausted="
            f"{metadata.get('rate_limit_exhaustion_reason', 'unknown')}"
        )
    if metadata["invalid_rows"] != metadata["dropped_invalid_rows"]:
        errors.append(f"invalid_rows={metadata['invalid_rows']}")
    if metadata.get("tradestatus_missing_rows", 0):
        errors.append(
            f"tradestatus_missing_rows={metadata['tradestatus_missing_rows']}"
        )
    if metadata.get("non_trading_rows", 0) and metadata.get(
        "non_trading_policy",
        "fail",
    ) == "fail":
        errors.append(f"non_trading_rows={metadata['non_trading_rows']}")
    return errors


def summary_prefix(metadata: dict[str, Any]) -> str:
    requested = len(metadata["requested_symbols"])
    if (
        metadata["failed_symbols"]
        or metadata["empty_symbols"]
        or metadata.get("possibly_truncated_symbols")
        or metadata["symbol_count"] != requested
    ):
        return "PARTIAL"
    return "OK"


def write_outputs(
    frame: Any,
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
