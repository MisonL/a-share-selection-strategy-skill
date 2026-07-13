"""Quality helpers for pytdx A-share fetches."""

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


from typing import Any

from lib.fetch.pytdx_a_share import (
    NUMERIC_COLUMNS,
    empty_symbols,
    symbol_metadata,
)


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
    invalid = invalid_row_details(frame)
    result = frame.drop(index=[item["index"] for item in invalid]) if drop_invalid_rows else frame
    result = result.reset_index(drop=True)
    metadata = {
        **metadata,
        "rows": int(len(result)),
        "symbol_count": int(result["symbol"].nunique()) if not result.empty else 0,
        "invalid_rows": len(invalid),
        "invalid_symbols": sorted({item["symbol"] for item in invalid}),
        "invalid_row_examples": invalid[:10],
        "dropped_invalid_rows": len(invalid) if drop_invalid_rows else 0,
    }
    metadata["symbols"] = [
        symbol_metadata_for_frame(str(item["symbol"]), result, item)
        for item in metadata["symbols"]
    ]
    metadata["empty_symbols"] = empty_symbols(metadata["symbols"])
    metadata["output_rows"] = int(len(result))
    metadata["overfetch_rows"] = int(metadata.get("raw_rows", 0)) - len(result)
    metadata["raw_to_output_ratio"] = (
        round(int(metadata.get("raw_rows", 0)) / len(result), 6)
        if len(result)
        else None
    )
    metadata["partial_result"] = bool(
        metadata["failed_symbols"]
        or metadata["empty_symbols"]
        or metadata.get("possibly_truncated_symbols")
    )
    return result, metadata


def invalid_row_details(frame: Any) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    import pandas as pd

    numeric = frame[NUMERIC_COLUMNS].apply(pd.to_numeric, errors="coerce")
    invalid_mask = numeric.isna()
    return [
        {
            "index": int(index),
            "symbol": str(frame.at[index, "symbol"]),
            "date": str(frame.at[index, "date"]),
            "invalid_columns": [
                column for column in NUMERIC_COLUMNS if bool(invalid_mask.at[index, column])
            ],
        }
        for index in frame.index
        if bool(invalid_mask.loc[index].any())
    ]


def symbol_metadata_for_frame(
    symbol: str,
    frame: Any,
    observation: dict[str, Any],
) -> dict[str, Any]:
    rows = [] if frame.empty else frame[frame["symbol"].astype(str) == symbol].to_dict("records")
    return symbol_metadata(symbol, rows, observation)


def strict_gate_errors(
    metadata: dict[str, Any],
    fail_on_fetch_error: bool,
) -> list[str]:
    errors = []
    if metadata["invalid_rows"] != metadata["dropped_invalid_rows"]:
        errors.append(f"invalid_rows={metadata['invalid_rows']}")
    if not fail_on_fetch_error:
        return errors
    if metadata["rows"] == 0:
        errors.append("rows=0")
    if metadata["failed_symbols"]:
        errors.append(f"failed_symbols={len(metadata['failed_symbols'])}")
    if metadata["empty_symbols"]:
        errors.append(f"empty_symbols={len(metadata['empty_symbols'])}")
    if metadata.get("possibly_truncated_symbols"):
        errors.append(
            "possibly_truncated_symbols="
            f"{len(metadata['possibly_truncated_symbols'])}"
        )
    requested = len(metadata["requested_symbols"])
    if metadata["symbol_count"] != requested:
        errors.append(f"symbol_count={metadata['symbol_count']} requested_symbols={requested}")
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


def print_summary(metadata: dict[str, Any], prefix: str = "OK") -> None:
    print(
        f"{prefix}: source=pytdx rows={metadata['rows']} "
        f"symbol_count={metadata['symbol_count']} "
        f"failed_symbols={len(metadata['failed_symbols'])} "
        f"empty_symbols={len(metadata['empty_symbols'])} "
        f"invalid_rows={metadata['invalid_rows']} "
        f"dropped_invalid_rows={metadata['dropped_invalid_rows']} "
        f"raw_rows={metadata.get('raw_rows', 0)} "
        f"requested_raw_rows={metadata.get('requested_raw_rows', 0)} "
        f"overfetch_rows={metadata.get('overfetch_rows', 0)} "
        f"possibly_truncated_symbols={len(metadata.get('possibly_truncated_symbols', []))} "
        f"source_claim_boundary={metadata['source_claim_boundary']}"
    )
