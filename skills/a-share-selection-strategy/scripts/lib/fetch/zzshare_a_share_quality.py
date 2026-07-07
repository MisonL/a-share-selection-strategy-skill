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
) -> tuple[Any, dict[str, Any]]:
    data.ensure_runtime_dependencies()
    invalid = invalid_row_details(frame)
    metadata = quality_metadata(metadata, invalid, drop_invalid_rows)
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
    metadata.update(data.prefixed_tradability_stats(frame, "raw_"))
    metadata.update(data.tradability_stats(result))
    metadata["symbols"] = [
        symbol_metadata_for_frame(
            symbol, result, metadata_symbol_pages(metadata, symbol)
        )
        for symbol in metadata["requested_symbols"]
    ]
    metadata["empty_symbols"] = data.empty_symbols(metadata["symbols"])
    return result, metadata


def quality_metadata(
    metadata: dict[str, Any],
    invalid: list[dict[str, Any]],
    drop_invalid_rows: bool,
) -> dict[str, Any]:
    return {
        **metadata,
        "invalid_rows": len(invalid),
        "invalid_symbols": sorted({item["symbol"] for item in invalid}),
        "invalid_row_examples": invalid[:10],
        "dropped_invalid_rows": len(invalid) if drop_invalid_rows else 0,
    }


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
    details = []
    for index, row in frame.iterrows():
        invalid_columns = invalid_numeric_columns(row)
        if invalid_columns:
            details.append(
                {
                    "index": int(index),
                    "symbol": str(row.get("symbol", "")),
                    "date": str(row.get("date", "")),
                    "invalid_columns": invalid_columns,
                }
            )
    return details


def invalid_numeric_columns(row: Any) -> list[str]:
    pd = data.pd
    invalid = []
    for column in data.NUMERIC_COLUMNS:
        value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
        if pd.isna(value):
            invalid.append(column)
    return invalid


def symbol_metadata_for_frame(
    symbol: str, frame: Any, pages: tuple[int, bool]
) -> dict[str, Any]:
    rows = (
        []
        if frame.empty
        else frame[frame["symbol"].astype(str) == symbol].to_dict("records")
    )
    return data.symbol_metadata(symbol, rows, pages[0], pages[1])


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
    if metadata["invalid_rows"] != metadata["dropped_invalid_rows"]:
        errors.append(f"invalid_rows={metadata['invalid_rows']}")
    if metadata.get("tradestatus_missing_rows", 0):
        errors.append(
            f"tradestatus_missing_rows={metadata['tradestatus_missing_rows']}"
        )
    if metadata.get("non_trading_rows", 0):
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
