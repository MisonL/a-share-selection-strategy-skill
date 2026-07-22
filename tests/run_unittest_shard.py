#!/usr/bin/env python3
"""Run one deterministic unittest shard for CI."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = ROOT / "tests"
RUNNER_TEST_FILE = "test_today_a_share_selection_runner.py"
RUNNER_METHOD_SHARDS = (
    "runner-core",
    "runner-providers",
    "runner-artifacts",
    "runner-plan-resume",
    "runner-universe",
)
RUNNER_METHOD_SHARD_STARTS = {
    "runner-core": "test_removed_price_symbols_deduplicate_normalized_aliases",
    "runner-providers": "test_runner_redacts_sensitive_step_failure_stderr_in_cli_error",
    "runner-artifacts": "test_runner_reuses_verified_filtered_parquet_sidecar_metadata",
    "runner-plan-resume": "test_runner_rejects_symbols_file_that_collides_with_outputs",
    "runner-universe": "test_local_clean_pool_metadata_propagates_to_outputs",
}
SHARDS = (
    "core",
    "providers",
    "gates",
    "report",
    *RUNNER_METHOD_SHARDS,
)
RUNNER_AUXILIARY_FILES = {
    "test_baostock_walk_forward_runner.py",
    "test_today_a_share_runner_failure_evidence.py",
    "test_today_a_share_selection_runner_artifacts.py",
}
PROVIDER_PREFIXES = (
    "test_external_source_",
    "test_fetch_",
    "test_probe_",
    "test_zzshare_",
)
GATE_PREFIXES = (
    "test_allocate_",
    "test_buy_hold_",
    "test_full_a_",
    "test_incremental_",
    "test_portfolio_",
    "test_recovery_",
    "test_walk_forward_",
)


def shard_for(filename: str) -> str:
    if filename in RUNNER_AUXILIARY_FILES:
        return "runner-core"
    if filename.startswith("test_today_a_share_html_report"):
        return "report"
    if filename.startswith(PROVIDER_PREFIXES):
        return "providers"
    if filename.startswith(GATE_PREFIXES):
        return "gates"
    return "core"


def discover_test_files(tests_root: Path = TESTS_ROOT) -> list[Path]:
    return sorted(tests_root.glob("test_*.py"))


def files_for_shard(shard: str, tests_root: Path = TESTS_ROOT) -> list[Path]:
    if shard not in SHARDS:
        raise ValueError(f"unknown unittest shard: {shard}")
    if shard in RUNNER_METHOD_SHARDS:
        files = [tests_root / RUNNER_TEST_FILE]
        if shard == "runner-core":
            files.extend(tests_root / name for name in sorted(RUNNER_AUXILIARY_FILES))
        return files
    return [
        path
        for path in discover_test_files(tests_root)
        if path.name != RUNNER_TEST_FILE and shard_for(path.name) == shard
    ]


@lru_cache(maxsize=1)
def runner_method_names() -> tuple[str, ...]:
    path = TESTS_ROOT / RUNNER_TEST_FILE
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "TodayAShareSelectionRunnerTests"
    ]
    if len(classes) != 1:
        raise RuntimeError("runner test file must define one runner test class")
    names = tuple(
        node.name
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )
    if not names:
        raise RuntimeError("runner test file has no test methods")
    if len(names) != len(set(names)):
        raise RuntimeError("runner test methods must be unique")
    return names


@lru_cache(maxsize=1)
def runner_method_assignments() -> dict[str, str]:
    names = runner_method_names()
    starts = []
    for shard in RUNNER_METHOD_SHARDS:
        start = RUNNER_METHOD_SHARD_STARTS[shard]
        try:
            starts.append((names.index(start), shard))
        except ValueError as exc:
            raise RuntimeError(f"runner shard start method not found: {start}") from exc
    if [index for index, _shard in starts] != sorted(index for index, _shard in starts):
        raise RuntimeError("runner shard starts must follow test declaration order")
    assignments: dict[str, str] = {}
    for position, (start_index, shard) in enumerate(starts):
        end_index = starts[position + 1][0] if position + 1 < len(starts) else len(names)
        assignments.update({name: shard for name in names[start_index:end_index]})
    if set(assignments) != set(names):
        raise RuntimeError("runner shard assignments do not cover every test method")
    return assignments


def runner_method_shard(method_name: str) -> str:
    try:
        return runner_method_assignments()[method_name]
    except KeyError as exc:
        raise ValueError(f"unknown runner test method: {method_name}") from exc


def iter_test_cases(suite: unittest.TestSuite) -> Iterator[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_test_cases(item)
        else:
            yield item


def file_suite(path: Path) -> unittest.TestSuite:
    return unittest.TestLoader().discover(
        start_dir=str(TESTS_ROOT),
        pattern=path.name,
    )


def suite_for_shard(shard: str) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    for path in files_for_shard(shard):
        discovered = file_suite(path)
        if path.name != RUNNER_TEST_FILE:
            suite.addTests(discovered)
            continue
        suite.addTests(
            case
            for case in iter_test_cases(discovered)
            if runner_method_shard(case._testMethodName) == shard
        )
    return suite


def test_ids_for_shard(shard: str) -> list[str]:
    return [case.id() for case in iter_test_cases(suite_for_shard(shard))]


def all_test_ids() -> list[str]:
    suite = unittest.TestLoader().discover(
        start_dir=str(TESTS_ROOT),
        pattern="test_*.py",
    )
    return [case.id() for case in iter_test_cases(suite)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shard", choices=SHARDS)
    parser.add_argument("--list", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sys.path.insert(0, str(ROOT))
    suite = suite_for_shard(args.shard)
    test_ids = [case.id() for case in iter_test_cases(suite)]
    if not test_ids:
        raise RuntimeError(f"unittest shard is empty: {args.shard}")
    if args.list:
        print("\n".join(test_ids))
        return 0

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
