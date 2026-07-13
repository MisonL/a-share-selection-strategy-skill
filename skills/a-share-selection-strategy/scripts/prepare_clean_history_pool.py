#!/usr/bin/env python3
"""Prepare an auditable clean history pool from fetched history artifacts."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from lib.gates.clean_history_pool import (
    CLAIM_BOUNDARY,
    apply_clean_plan,
    build_clean_metadata,
    build_clean_plan,
    build_report,
    read_frame,
    read_json,
    validate_paths,
)
from lib.gates.incremental_history_merge import merge_incremental_history
from lib.gates.incremental_history_execution import publish_output_pair


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Filter existing history prices by metadata artifacts; optionally merge "
            "a verified incremental fetch first; does not fetch data and does not "
            "prove full-market completion."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--prices-input", required=True)
    parser.add_argument("--history-metadata", required=True)
    parser.add_argument("--short-history", help="Optional short_history_symbols.json.")
    parser.add_argument("--output", required=True, help="Clean prices output.")
    parser.add_argument("--metadata-output", required=True, help="Clean metadata JSON.")
    parser.add_argument(
        "--metadata-alias-output",
        help="Optional explicit compatibility metadata JSON output; nothing is implicit.",
    )
    parser.add_argument(
        "--report-output",
        required=True,
        help="JSON report describing removed symbols, counts, and optional merge.",
    )
    parser.add_argument("--incremental-plan", help="Incremental plan JSON.")
    parser.add_argument("--incremental-prices", help="Fetched incremental prices.")
    parser.add_argument("--incremental-metadata", help="Incremental fetch metadata JSON.")
    parser.add_argument("--ttl-days", type=int, default=7, help="Advisory skip TTL.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = build_paths(args)
    validate_paths(inputs=input_paths(paths), outputs=output_paths(paths))
    metadata = read_json(paths["history_metadata"])
    short_data = read_json(paths["short_history"]) if paths["short_history"] else {}
    frame = read_frame(paths["prices_input"])
    frame, metadata, merge_report = apply_optional_incremental_merge(
        frame, metadata, paths
    )
    plan = build_clean_plan(metadata, short_data, int(args.ttl_days))
    clean = apply_clean_plan(frame, plan)
    clean_metadata = build_clean_metadata(
        metadata,
        plan,
        clean,
        paths["prices_input"],
    )
    write_outputs(paths, clean, clean_metadata, plan, frame, merge_report)
    print_success(clean, plan, paths["output"], paths["metadata_output"], merge_report)
    return 0


def build_paths(args: argparse.Namespace) -> dict[str, Path | None]:
    metadata_alias = (
        Path(args.metadata_alias_output) if args.metadata_alias_output else None
    )
    return {
        "prices_input": Path(args.prices_input),
        "history_metadata": Path(args.history_metadata),
        "short_history": Path(args.short_history) if args.short_history else None,
        "output": Path(args.output),
        "metadata_output": Path(args.metadata_output),
        "metadata_alias_output": metadata_alias,
        "report_output": Path(args.report_output),
        "incremental_plan": optional_incremental_path(args, "incremental_plan"),
        "incremental_prices": optional_incremental_path(args, "incremental_prices"),
        "incremental_metadata": optional_incremental_path(args, "incremental_metadata"),
    }


def optional_incremental_path(args: argparse.Namespace, name: str) -> Path | None:
    values = [
        args.incremental_plan,
        args.incremental_prices,
        args.incremental_metadata,
    ]
    if any(values) and not all(values):
        raise ValueError(
            "--incremental-plan, --incremental-prices, and --incremental-metadata "
            "must be provided together"
        )
    value = getattr(args, name)
    return Path(value) if value else None


def input_paths(paths: dict[str, Path | None]) -> list[Path | None]:
    return [
        paths["prices_input"],
        paths["history_metadata"],
        paths["short_history"],
        paths["incremental_plan"],
        paths["incremental_prices"],
        paths["incremental_metadata"],
    ]


def output_paths(paths: dict[str, Path | None]) -> list[Path]:
    outputs = [
        paths["output"],
        paths["metadata_output"],
        paths["report_output"],
    ]
    if paths["metadata_alias_output"]:
        outputs.insert(2, paths["metadata_alias_output"])
    return [path for path in outputs if path is not None]


def apply_optional_incremental_merge(
    frame: Any,
    metadata: dict[str, Any],
    paths: dict[str, Path | None],
) -> tuple[Any, dict[str, Any], dict[str, Any] | None]:
    if not paths["incremental_plan"]:
        return frame, metadata, None
    merged, merged_metadata, merge_report = merge_incremental_history(
        frame,
        metadata,
        read_json(paths["incremental_plan"]),
        read_frame(paths["incremental_prices"]),
        read_json(paths["incremental_metadata"]),
        compute_symbol_summaries=False,
    )
    return merged, merged_metadata, merge_report


def write_outputs(
    paths: dict[str, Path | None],
    clean: Any,
    clean_metadata: dict[str, Any],
    plan: dict[str, Any],
    raw: Any,
    merge_report: dict[str, Any] | None,
) -> None:
    report = build_report(
        plan,
        raw,
        clean,
        paths["history_metadata"],
        paths["short_history"],
        merge_report,
    )
    output = required_output_path(paths, "output")
    metadata_output = required_output_path(paths, "metadata_output")
    report_output = required_output_path(paths, "report_output")
    token = uuid.uuid4().hex
    staged_outputs = [
        (staged_output_path(output, token), output),
        (staged_output_path(metadata_output, token), metadata_output),
    ]
    metadata_alias = paths["metadata_alias_output"]
    if metadata_alias is not None:
        staged_outputs.append(
            (staged_output_path(metadata_alias, token), metadata_alias)
        )
    staged_outputs.append((staged_output_path(report_output, token), report_output))
    try:
        write_frame(clean, staged_outputs[0][0])
        write_json(clean_metadata, staged_outputs[1][0])
        next_index = 2
        if metadata_alias is not None:
            write_json(clean_metadata, staged_outputs[next_index][0])
            next_index += 1
        write_json(report, staged_outputs[next_index][0])
        publish_output_pair(staged_outputs, token)
    except Exception:
        for staged, _target in staged_outputs:
            staged.unlink(missing_ok=True)
        raise


def required_output_path(paths: dict[str, Path | None], name: str) -> Path:
    path = paths[name]
    if path is None:
        raise ValueError(f"missing required output path: {name}")
    return path


def staged_output_path(output: Path, token: str) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    return output.with_name(f".{output.stem}.{token}.stage{output.suffix}")


def print_success(
    clean: Any,
    plan: dict[str, Any],
    output: Path,
    metadata_output: Path,
    merge_report: dict[str, Any] | None,
) -> None:
    merge_count = 0 if merge_report is None else merge_report["planned_symbol_count"]
    print(
        "OK: clean_symbols="
        f"{clean['symbol'].nunique() if not clean.empty else 0} "
        f"removed_symbols={len(plan['remove_symbols'])} rows={len(clean)} "
        f"incremental_merged_symbols={merge_count} output={output} "
        f"metadata_output={metadata_output} claim_boundary={CLAIM_BOUNDARY}"
    )


def write_frame(frame: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame.to_csv(path, index=False)
        return
    if suffix in {".parquet", ".pq"}:
        frame.to_parquet(path, index=False)
        return
    raise ValueError("unsupported prices output format; use .csv, .parquet, or .pq")


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
