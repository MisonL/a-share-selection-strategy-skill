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
    derive_short_history_data,
    read_frame,
    read_json,
    validate_paths,
)
from lib.gates.full_a_clean_pool_provenance import build_clean_pool_provenance
from lib.gates.incremental_history_artifacts import publish_output_pair
from lib.gates.incremental_history_merge import merge_incremental_history


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
    short_history_group = parser.add_mutually_exclusive_group()
    short_history_group.add_argument(
        "--short-history", help="Existing short_history_symbols.json."
    )
    short_history_group.add_argument(
        "--short-history-output",
        help=(
            "Persist a short-history audit derived from the effective prices frame; "
            "must be paired with --min-history-rows."
        ),
    )
    parser.add_argument(
        "--min-history-rows",
        type=int,
        help="Threshold for --short-history-output; must be a positive integer.",
    )
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
    parser.add_argument(
        "--universe-input",
        help="Explicit baostock_universe CSV or Parquet for clean-pool provenance.",
    )
    parser.add_argument(
        "--universe-metadata",
        help="Metadata paired with --universe-input for clean-pool provenance.",
    )
    parser.add_argument(
        "--provenance-output",
        help=(
            "Optional full-A clean-pool provenance JSON. Requires --universe-input "
            "and --universe-metadata; it does not prove final scoring or real-time data."
        ),
    )
    parser.add_argument("--ttl-days", type=int, default=7, help="Advisory skip TTL.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_short_history_options(args)
    paths = build_paths(args)
    validate_paths(inputs=input_paths(paths), outputs=output_paths(paths))
    metadata = read_json(paths["history_metadata"])
    short_data = (
        read_json(paths["short_history_input"])
        if paths["short_history_input"]
        else {}
    )
    frame = read_frame(paths["prices_input"])
    frame, metadata, merge_report = apply_optional_incremental_merge(
        frame, metadata, paths
    )
    if paths["short_history_output"]:
        short_data = derive_short_history_data(
            frame,
            int(args.min_history_rows),
            paths["prices_input"],
        )
    plan = build_clean_plan(metadata, short_data, int(args.ttl_days))
    clean = apply_clean_plan(frame, plan)
    clean_metadata = build_clean_metadata(
        metadata,
        plan,
        clean,
        paths["prices_input"],
    )
    write_outputs(
        paths,
        clean,
        clean_metadata,
        plan,
        frame,
        merge_report,
        short_data,
    )
    print_success(
        clean,
        plan,
        paths["output"],
        paths["metadata_output"],
        paths["provenance_output"],
        merge_report,
    )
    return 0


def build_paths(args: argparse.Namespace) -> dict[str, Path | None]:
    metadata_alias = (
        Path(args.metadata_alias_output) if args.metadata_alias_output else None
    )
    return {
        "prices_input": Path(args.prices_input),
        "history_metadata": Path(args.history_metadata),
        "short_history_input": Path(args.short_history) if args.short_history else None,
        "short_history_output": (
            Path(args.short_history_output) if args.short_history_output else None
        ),
        "short_history": (
            Path(args.short_history)
            if args.short_history
            else Path(args.short_history_output)
            if args.short_history_output
            else None
        ),
        "output": Path(args.output),
        "metadata_output": Path(args.metadata_output),
        "metadata_alias_output": metadata_alias,
        "report_output": Path(args.report_output),
        "incremental_plan": optional_incremental_path(args, "incremental_plan"),
        "incremental_prices": optional_incremental_path(args, "incremental_prices"),
        "incremental_metadata": optional_incremental_path(args, "incremental_metadata"),
        "universe_input": optional_provenance_path(args, "universe_input"),
        "universe_metadata": optional_provenance_path(args, "universe_metadata"),
        "provenance_output": optional_provenance_path(args, "provenance_output"),
    }


def validate_short_history_options(args: argparse.Namespace) -> None:
    if args.short_history_output and args.min_history_rows is None:
        raise ValueError("--short-history-output requires --min-history-rows")
    if args.short_history_output and any(
        (args.incremental_plan, args.incremental_prices, args.incremental_metadata)
    ):
        raise ValueError(
            "--short-history-output requires a persisted effective history artifact; "
            "publish the incremental merge first, then derive short history"
        )
    if args.min_history_rows is not None:
        if not args.short_history_output:
            raise ValueError("--min-history-rows requires --short-history-output")
        if args.min_history_rows < 1:
            raise ValueError("--min-history-rows must be positive")


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


def optional_provenance_path(args: argparse.Namespace, name: str) -> Path | None:
    values = [args.universe_input, args.universe_metadata, args.provenance_output]
    if any(values) and not all(values):
        raise ValueError(
            "--universe-input, --universe-metadata, and --provenance-output "
            "must be provided together"
        )
    if any(values) and args.incremental_plan:
        raise ValueError(
            "--provenance-output cannot be combined with incremental artifacts; "
            "persist a merged history artifact before creating full-A provenance"
        )
    value = getattr(args, name)
    return Path(value) if value else None


def input_paths(paths: dict[str, Path | None]) -> list[Path | None]:
    return [
        paths["prices_input"],
        paths["history_metadata"],
        paths["short_history_input"],
        paths["incremental_plan"],
        paths["incremental_prices"],
        paths["incremental_metadata"],
        paths["universe_input"],
        paths["universe_metadata"],
    ]


def output_paths(paths: dict[str, Path | None]) -> list[Path]:
    outputs = [
        paths["output"],
        paths["metadata_output"],
        paths["report_output"],
        paths["short_history_output"],
    ]
    if paths["metadata_alias_output"]:
        outputs.insert(2, paths["metadata_alias_output"])
    if paths["provenance_output"]:
        outputs.append(paths["provenance_output"])
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
    short_data: dict[str, Any] | None = None,
) -> None:
    if paths.get("short_history_output") is not None and short_data is None:
        raise ValueError("short-history output requires derived short-history data")
    short_data = short_data or {}
    report = build_report(
        plan,
        raw,
        clean,
        paths["history_metadata"],
        paths["short_history"],
        merge_report,
    )
    token = uuid.uuid4().hex
    stages, staged_outputs = build_staged_outputs(paths, token)
    try:
        write_frame(clean, required_output_path(stages, "output"))
        write_json(clean_metadata, required_output_path(stages, "metadata_output"))
        if stages["metadata_alias_output"] is not None:
            write_json(clean_metadata, stages["metadata_alias_output"])
        write_json(report, required_output_path(stages, "report_output"))
        if stages["short_history_output"] is not None:
            write_json(short_data, stages["short_history_output"])
        if stages["provenance_output"] is not None:
            provenance = build_staged_provenance(paths, stages, raw, clean)
            write_json(provenance, stages["provenance_output"])
        publish_output_pair(staged_outputs, token)
    except Exception:
        for staged, _target in staged_outputs:
            staged.unlink(missing_ok=True)
        raise


def build_staged_outputs(
    paths: dict[str, Path | None], token: str
) -> tuple[dict[str, Path | None], list[tuple[Path, Path]]]:
    names = (
        "output",
        "metadata_output",
        "metadata_alias_output",
        "report_output",
        "short_history_output",
        "provenance_output",
    )
    stages: dict[str, Path | None] = {}
    for name in names:
        target = paths.get(name)
        stages[name] = staged_output_path(target, token) if target is not None else None
    staged_outputs = [
        (stages[name], paths[name])
        for name in names
        if stages[name] is not None and paths.get(name) is not None
    ]
    return stages, staged_outputs


def build_staged_provenance(
    paths: dict[str, Path | None],
    stages: dict[str, Path | None],
    raw: Any,
    clean: Any,
) -> dict[str, Any]:
    metadata_alias = paths.get("metadata_alias_output")
    short_history_output = paths.get("short_history_output")
    short_history_input = paths.get("short_history_input") or paths.get("short_history")
    return build_clean_pool_provenance(
        universe_input=required_output_path(paths, "universe_input"),
        universe_metadata=required_output_path(paths, "universe_metadata"),
        history_prices=required_output_path(paths, "prices_input"),
        history_metadata=required_output_path(paths, "history_metadata"),
        short_history=stages["short_history_output"] or short_history_input,
        short_history_display_path=paths.get("short_history"),
        clean_prices=required_output_path(stages, "output"),
        clean_metadata=required_output_path(stages, "metadata_output"),
        clean_metadata_alias=stages["metadata_alias_output"],
        clean_report=required_output_path(stages, "report_output"),
        display_paths={
            "clean_prices": required_output_path(paths, "output"),
            "clean_metadata": required_output_path(paths, "metadata_output"),
            **(
                {"clean_metadata_alias": metadata_alias} if metadata_alias else {}
            ),
            "clean_report": required_output_path(paths, "report_output"),
            **(
                {"short_history": short_history_output}
                if short_history_output is not None
                else {}
            ),
        },
        history_frame=raw,
        clean_frame=clean,
    )


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
    provenance_output: Path | None,
    merge_report: dict[str, Any] | None,
) -> None:
    merge_count = 0 if merge_report is None else merge_report["planned_symbol_count"]
    provenance_text = (
        f"provenance_output={provenance_output} " if provenance_output is not None else ""
    )
    print(
        "OK: clean_symbols="
        f"{clean['symbol'].nunique() if not clean.empty else 0} "
        f"removed_symbols={len(plan['remove_symbols'])} rows={len(clean)} "
        f"incremental_merged_symbols={merge_count} output={output} "
        f"metadata_output={metadata_output} {provenance_text}"
        f"claim_boundary={CLAIM_BOUNDARY}"
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
