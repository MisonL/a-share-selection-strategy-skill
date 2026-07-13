#!/usr/bin/env python3
"""Prepare an auditable retry symbol list from history fetch artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


RETRY_METADATA_KEYS = [
    "failed_symbols",
    "empty_symbols",
    "possibly_truncated_symbols",
    "unprocessed_symbols",
]
DEFAULT_EXCLUDE_KEYS = [
    "invalid_symbols",
    "non_trading_symbols",
    "st_symbols",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a comma-separated retry symbol list from selected_symbols.json "
            "and history_metadata.json. This is a recovery helper only; it does "
            "not fetch data and does not prove full-market completion."
        )
    )
    parser.add_argument("--selected-symbols", required=True)
    parser.add_argument("--history-metadata", required=True)
    parser.add_argument("--output", required=True, help="JSON retry plan output path.")
    parser.add_argument(
        "--symbols-output",
        help="Optional text file containing the comma-separated retry symbols.",
    )
    parser.add_argument(
        "--include-clean-selected",
        action="store_true",
        help=(
            "Include selected symbols that are not listed as failed, empty, "
            "truncated, unprocessed, invalid, non-trading, or ST."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected_path = Path(args.selected_symbols)
    metadata_path = Path(args.history_metadata)
    output = Path(args.output)
    symbols_output = Path(args.symbols_output) if args.symbols_output else None
    validate_output_paths(
        inputs=[selected_path, metadata_path],
        outputs=[path for path in [output, symbols_output] if path is not None],
    )
    selected_data = read_json(selected_path)
    metadata = read_json(metadata_path)
    plan = build_retry_plan(
        selected_data=selected_data,
        metadata=metadata,
        include_clean_selected=bool(args.include_clean_selected),
    )
    write_json(plan, output)
    if symbols_output:
        symbols_output.parent.mkdir(parents=True, exist_ok=True)
        symbols_output.write_text(
            ",".join(plan["retry_symbols"]) + "\n",
            encoding="utf-8",
        )
    print(
        "OK: retry_symbols="
        f"{len(plan['retry_symbols'])} clean_selected_symbols={len(plan['clean_selected_symbols'])} "
        f"retry_reason_counts={plan['retry_reason_counts']} output={output}"
    )
    return 0


def build_retry_plan(
    *,
    selected_data: dict[str, Any],
    metadata: dict[str, Any],
    include_clean_selected: bool,
) -> dict[str, Any]:
    selected = unique_symbols(selected_symbols(selected_data))
    selected_set = set(selected)
    retry_by_reason = retry_symbols_by_reason(metadata)
    blocked = symbols_for_keys(metadata, DEFAULT_EXCLUDE_KEYS)
    retry_candidates = unique_symbols(
        symbol
        for symbols in retry_by_reason.values()
        for symbol in symbols
    )
    unexpected = sorted(symbol for symbol in retry_candidates if symbol not in selected_set)
    retry = unique_symbols(
        symbol for symbol in retry_candidates if symbol in selected_set and symbol not in blocked
    )
    clean = [
        symbol
        for symbol in selected
        if symbol not in set(retry)
        and symbol not in blocked
        and not symbol_in_any_reason(symbol, retry_by_reason)
    ]
    if include_clean_selected:
        retry = unique_symbols([*retry, *clean])
    return {
        "source": "history_retry_plan",
        "selected_symbol_count": len(selected),
        "retry_symbols": retry,
        "retry_symbol_count": len(retry),
        "retry_symbols_csv": ",".join(retry),
        "retry_reasons": retry_by_reason,
        "retry_reason_counts": {
            key: len(value) for key, value in retry_by_reason.items()
        },
        "excluded_symbols": sorted(blocked),
        "excluded_symbol_count": len(blocked),
        "unexpected_metadata_symbols": unexpected,
        "unexpected_metadata_symbol_count": len(unexpected),
        "clean_selected_symbols": clean,
        "clean_selected_symbol_count": len(clean),
        "include_clean_selected": include_clean_selected,
        "claim_boundary": (
            "retry_plan_only_not_full_market_completion_or_history_fetch_success"
        ),
        "next_action": (
            "rerun_history_fetch_with_retry_symbols_then_revalidate_metadata"
        ),
    }


def selected_symbols(data: dict[str, Any]) -> list[str]:
    for key in ("selected_symbols", "symbols"):
        value = data.get(key)
        if isinstance(value, list):
            return normalize_symbol_items(value)
    return []


def normalize_symbol_items(items: list[Any]) -> list[str]:
    result = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("symbol", "")
        else:
            value = item
        text = str(value).strip()
        if text:
            result.append(text)
    return result


def retry_symbols_by_reason(metadata: dict[str, Any]) -> dict[str, list[str]]:
    return {
        key: sorted(symbols_for_keys(metadata, [key]))
        for key in RETRY_METADATA_KEYS
    }


def symbols_for_keys(metadata: dict[str, Any], keys: list[str]) -> set[str]:
    symbols: set[str] = set()
    for key in keys:
        symbols.update(metadata_symbols(metadata.get(key, [])))
    return symbols


def metadata_symbols(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    result = set()
    for item in value:
        if isinstance(item, dict):
            item = item.get("symbol", "")
        text = str(item).strip()
        if text:
            result.add(text)
    return result


def symbol_in_any_reason(symbol: str, retry_by_reason: dict[str, list[str]]) -> bool:
    return any(symbol in symbols for symbols in retry_by_reason.values())


def unique_symbols(symbols: Any) -> list[str]:
    seen = set()
    result = []
    for value in symbols:
        symbol = str(value).strip()
        if not symbol or symbol in seen:
            continue
        result.append(symbol)
        seen.add(symbol)
    return result


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def validate_output_paths(*, inputs: list[Path], outputs: list[Path]) -> None:
    input_paths = {resolved_path(path) for path in inputs}
    seen_outputs = set()
    for output in outputs:
        output_path = resolved_path(output)
        if output_path in input_paths:
            raise ValueError(f"output path must not overwrite input: {output}")
        if output_path in seen_outputs:
            raise ValueError(f"duplicate output path: {output}")
        seen_outputs.add(output_path)


def resolved_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def write_json(data: dict[str, Any], path: Path) -> None:
    # Keep this CLI self-contained; this intentionally mirrors the runner helper.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
