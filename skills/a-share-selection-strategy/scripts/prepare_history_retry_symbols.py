#!/usr/bin/env python3
"""Prepare an auditable retry symbol list from history fetch artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lib.gates.a_share_selection_output_safety import validate_output_paths
from lib.runner.run_today_a_share_selection_retry_plan import build_retry_plan


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
        outputs=[path for path in [output, symbols_output] if path is not None],
        inputs=[selected_path, metadata_path],
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


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
