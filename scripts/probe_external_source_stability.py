#!/usr/bin/env python3
"""Run repeated external source probes through the stable fetch CLIs."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPTS = Path(__file__).resolve().parent
Executor = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class SourceSpec:
    name: str
    command: list[str]
    metadata_path: Path
    output_path: Path


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = initial_manifest(args)
    try:
        run_probe(args, output_dir=Path(args.output_dir), manifest=manifest, executor=run_command)
        write_json(manifest, Path(args.summary_output))
    except Exception as exc:  # noqa: BLE001
        write_json(manifest, Path(args.summary_output))
        print(f"ERROR: code=probe_failed output_written=true message={exc}", file=sys.stderr)
        return 2
    errors = strict_errors(manifest)
    if errors:
        print_summary(manifest, prefix="ERROR_SUMMARY")
        print(f"ERROR: strict gate failed; {'; '.join(errors)} output_written=true", file=sys.stderr)
        return 3
    print_summary(manifest)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe external source stability through fetch CLIs.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--iterations", type=positive_int, default=3)
    parser.add_argument("--akshare-symbols", default="000001")
    parser.add_argument("--akshare-start-date", default="2025-09-01")
    parser.add_argument("--akshare-end-date", default="2026-05-29")
    parser.add_argument("--yfinance-symbols", default="AAPL,MSFT")
    parser.add_argument("--yfinance-start-date", default="2024-01-01")
    parser.add_argument("--yfinance-end-date", default="2026-05-29")
    parser.add_argument("--yfinance-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--baostock-symbols", default="000001,600000")
    parser.add_argument("--baostock-start-date", default="2024-01-01")
    parser.add_argument("--baostock-end-date", default="2026-05-29")
    parser.add_argument("--baostock-adjust", default="3")
    return parser


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(Path.cwd()), capture_output=True, text=True)


def run_probe(args: argparse.Namespace, *, output_dir: Path, manifest: dict[str, Any], executor: Executor) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for iteration in range(1, int(args.iterations) + 1):
        iteration_dir = output_dir / f"iteration-{iteration}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        for spec in source_specs(args, iteration_dir):
            result = executor(spec.command)
            metadata = read_metadata(spec.metadata_path)
            source_result = source_record(spec, result, metadata)
            manifest["results"].append(source_result)
    manifest["summary"] = build_summary(manifest)


def source_specs(args: argparse.Namespace, iteration_dir: Path) -> list[SourceSpec]:
    return [akshare_spec(args, iteration_dir), yfinance_spec(args, iteration_dir), baostock_spec(args, iteration_dir)]


def akshare_spec(args: argparse.Namespace, iteration_dir: Path) -> SourceSpec:
    output = iteration_dir / "akshare" / "prices.csv"
    metadata = iteration_dir / "akshare" / "metadata.json"
    return SourceSpec(
        name="akshare",
        output_path=output,
        metadata_path=metadata,
        command=script_command(
            "fetch_akshare_a_share.py",
            "--symbols", args.akshare_symbols,
            "--start-date", args.akshare_start_date,
            "--end-date", args.akshare_end_date,
            "--output", output,
            "--metadata-output", metadata,
            "--fail-on-fetch-error",
        ),
    )


def yfinance_spec(args: argparse.Namespace, iteration_dir: Path) -> SourceSpec:
    output = iteration_dir / "yfinance" / "prices.csv"
    metadata = iteration_dir / "yfinance" / "metadata.json"
    return SourceSpec(
        name="yfinance",
        output_path=output,
        metadata_path=metadata,
        command=script_command(
            "fetch_yfinance_ohlcv.py",
            "--symbols", args.yfinance_symbols,
            "--start-date", args.yfinance_start_date,
            "--end-date", args.yfinance_end_date,
            "--output", output,
            "--metadata-output", metadata,
            "--timeout-seconds", args.yfinance_timeout_seconds,
            "--fail-on-fetch-error",
        ),
    )


def baostock_spec(args: argparse.Namespace, iteration_dir: Path) -> SourceSpec:
    output = iteration_dir / "baostock" / "prices.csv"
    metadata = iteration_dir / "baostock" / "metadata.json"
    return SourceSpec(
        name="baostock",
        output_path=output,
        metadata_path=metadata,
        command=script_command(
            "fetch_baostock_a_share.py",
            "--symbols", args.baostock_symbols,
            "--start-date", args.baostock_start_date,
            "--end-date", args.baostock_end_date,
            "--output", output,
            "--metadata-output", metadata,
            "--adjust", args.baostock_adjust,
            "--fail-on-fetch-error",
        ),
    )


def script_command(script: str, *parts: object) -> list[str]:
    return [sys.executable, str(SCRIPTS / script), *[str(part) for part in parts]]


def read_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def source_record(
    spec: SourceSpec,
    result: subprocess.CompletedProcess[str],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    checks = source_checks(spec.name, metadata, spec.command)
    passed = result.returncode == 0 and all(item["passed"] for item in required_checks(checks))
    return {
        "source": spec.name,
        "command": spec.command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output": str(spec.output_path),
        "metadata_output": str(spec.metadata_path),
        "metadata": metadata,
        "checks": checks,
        "passed": passed,
    }


def source_checks(source: str, metadata: dict[str, Any], command: list[str] | None = None) -> list[dict[str, Any]]:
    common = [
        check("metadata_written", bool(metadata)),
        check("rows_positive", int(metadata.get("rows", 0)) > 0),
        check("symbol_count_matches_requested", int(metadata.get("symbol_count", -1)) == len(metadata.get("requested_symbols", []))),
        check("failed_symbols_empty", not metadata.get("failed_symbols")),
        check("empty_symbols_empty", not metadata.get("empty_symbols")),
    ]
    if source == "akshare":
        return common + [
            check(
                "invalid_rows_accounted",
                int(metadata.get("invalid_rows", 0)) == int(metadata.get("dropped_invalid_rows", 0)),
            ),
            check("hist_provider_clean", not metadata.get("fallback_errors"), required=False),
        ]
    if source == "yfinance":
        return common + [
            check("timeout_seconds_recorded", float(metadata.get("timeout_seconds", 0.0)) > 0),
            check("close_adjustment_recorded", metadata.get("adjustment") == "auto_adjust_false_close"),
        ]
    if source == "baostock":
        return common + [
            check("invalid_rows_accounted", int(metadata.get("invalid_rows", 0)) == int(metadata.get("dropped_invalid_rows", 0))),
            check("non_trading_rows_zero", int(metadata.get("non_trading_rows", 0)) == 0),
            check("tradestatus_missing_rows_zero", int(metadata.get("tradestatus_missing_rows", 0)) == 0),
            check("adjustflag_matches_request", str(metadata.get("adjustflag", "")) == requested_value(command, "--adjust")),
        ]
    return common


def requested_value(command: list[str] | None, option: str) -> str:
    if not command or option not in command:
        return ""
    return str(command[command.index(option) + 1])


def required_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in checks if item.get("required", True)]


def check(name: str, passed: bool, *, required: bool = True) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "required": bool(required)}


def build_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    results = manifest["results"]
    by_source = {source: [item for item in results if item["source"] == source] for source in sorted({item["source"] for item in results})}
    return {
        "iterations": manifest["iterations"],
        "total_runs": len(results),
        "passed_runs": sum(1 for item in results if item["passed"]),
        "sources": {
            source: {
                "runs": len(items),
                "passed_runs": sum(1 for item in items if item["passed"]),
                "all_passed": all(item["passed"] for item in items),
                "observation_failed_checks": observation_failures(items),
            }
            for source, items in by_source.items()
        },
        "all_sources_all_iterations_passed": bool(results) and all(item["passed"] for item in results),
        "long_term_stability_claim": "not_proven",
        "interpretation": "Repeated success only describes this run window, parameters, and network environment.",
    }


def strict_errors(manifest: dict[str, Any]) -> list[str]:
    summary = manifest.get("summary", {})
    errors = []
    for source, data in summary.get("sources", {}).items():
        if not data.get("all_passed"):
            errors.append(f"{source}_passed_runs={data.get('passed_runs')} runs={data.get('runs')}")
    return errors


def observation_failures(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for check_item in item["checks"]:
            if check_item.get("required", True) or check_item["passed"]:
                continue
            name = str(check_item["name"])
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def initial_manifest(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "probe_type": "external_source_stability",
        "iterations": int(args.iterations),
        "long_term_stability_claim": "not_proven",
        "results": [],
        "summary": {},
    }


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def print_summary(manifest: dict[str, Any], prefix: str = "OK") -> None:
    summary = manifest.get("summary", {})
    print(
        f"{prefix}: probe_type=external_source_stability iterations={summary.get('iterations', 0)} "
        f"total_runs={summary.get('total_runs', 0)} passed_runs={summary.get('passed_runs', 0)} "
        f"all_sources_all_iterations_passed={summary.get('all_sources_all_iterations_passed', False)} "
        "long_term_stability_claim=not_proven"
    )


if __name__ == "__main__":
    raise SystemExit(main())
