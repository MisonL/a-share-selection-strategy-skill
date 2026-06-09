"""Metadata gate checks for walk-forward artifacts."""

from __future__ import annotations

from typing import Any


def metadata_gate_errors(
    metadata: dict[str, Any],
    expected_symbol_count: int | None,
    *,
    allow_dropped_invalid_rows: bool = False,
) -> list[str]:
    errors = missing_metadata_errors(metadata)
    if int(metadata.get("rows", 0)) <= 0:
        errors.append(f"metadata_rows={metadata.get('rows')}")
    if int(metadata.get("raw_rows", 0)) <= 0:
        errors.append(f"metadata_raw_rows={metadata.get('raw_rows')}")
    actual_count = int(metadata.get("symbol_count", 0))
    if expected_symbol_count is not None and actual_count != expected_symbol_count:
        errors.append(f"metadata_symbol_count={actual_count} expected={expected_symbol_count}")
    for key in ["failed_symbols", "empty_symbols"]:
        if metadata.get(key):
            errors.append(f"metadata_{key}={len(metadata[key])}")
    errors.extend(invalid_row_errors(metadata, allow_dropped_invalid_rows))
    return errors


def missing_metadata_errors(metadata: dict[str, Any]) -> list[str]:
    errors = []
    for key in metadata_gate_keys():
        if key not in metadata:
            errors.append(f"metadata_missing_{key}")
    return errors


def invalid_row_errors(
    metadata: dict[str, Any],
    allow_dropped_invalid_rows: bool,
) -> list[str]:
    if allow_dropped_invalid_rows:
        return dropped_invalid_row_errors(metadata)
    errors = []
    for key in strict_invalid_metadata_keys():
        if int(metadata.get(key, 0)) != 0:
            errors.append(f"metadata_{key}={metadata.get(key)}")
    return errors


def dropped_invalid_row_errors(metadata: dict[str, Any]) -> list[str]:
    errors = []
    invalid_rows = int(metadata.get("invalid_rows", 0))
    dropped_rows = int(metadata.get("dropped_invalid_rows", 0))
    raw_rows = raw_invalid_rows(metadata)
    if dropped_rows != invalid_rows:
        errors.append(f"metadata_invalid_rows={invalid_rows} dropped_invalid_rows={dropped_rows}")
    if raw_rows and invalid_rows == 0:
        errors.append(f"metadata_raw_invalid_rows={raw_rows} invalid_rows={invalid_rows}")
    for key in ["non_trading_rows", "tradestatus_missing_rows"]:
        if int(metadata.get(key, 0)) != 0:
            errors.append(f"metadata_{key}={metadata.get(key)}")
    return errors


def metadata_gate_keys() -> tuple[str, ...]:
    return (
        "rows", "raw_rows", "symbol_count", "failed_symbols", "empty_symbols",
        "invalid_rows", "dropped_invalid_rows", "raw_non_trading_rows",
        "non_trading_rows", "raw_tradestatus_missing_rows", "tradestatus_missing_rows",
    )


def strict_invalid_metadata_keys() -> tuple[str, ...]:
    return (
        "invalid_rows", "dropped_invalid_rows", "raw_non_trading_rows",
        "non_trading_rows", "raw_tradestatus_missing_rows", "tradestatus_missing_rows",
    )


def raw_invalid_rows(metadata: dict[str, Any]) -> int:
    return sum(
        int(metadata.get(key, 0))
        for key in ["raw_non_trading_rows", "raw_tradestatus_missing_rows"]
    )

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
