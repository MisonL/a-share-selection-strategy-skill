from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import probe_external_source_stability as probe  # noqa: E402


class ExternalSourceStabilityProbeTests(unittest.TestCase):
    def test_probe_accepts_all_sources_and_keeps_long_term_claim_unproven(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output)
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=output / "runs",
                manifest=manifest,
                executor=FakeExecutor(),
            )

        summary = manifest["summary"]
        self.assertEqual(4, summary["total_runs"])
        self.assertEqual(4, summary["passed_runs"])
        self.assertEqual(True, summary["all_sources_all_iterations_passed"])
        self.assertEqual("not_proven", summary["long_term_stability_claim"])
        self.assertEqual(
            "current_window_parameters_network_only",
            summary["short_window_claim_boundary"],
        )
        self.assertEqual({}, summary["sources"]["akshare"]["observation_failed_checks"])
        self.assertEqual([], probe.strict_errors(manifest))

    def test_print_summary_keeps_long_term_claim_unproven(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output)
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=output / "runs",
                manifest=manifest,
                executor=FakeExecutor(),
            )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            probe.print_summary(manifest)

        self.assertIn("all_sources_all_iterations_passed=True", stdout.getvalue())
        self.assertIn("long_term_stability_claim=not_proven", stdout.getvalue())
        self.assertIn(
            "short_window_claim_boundary=current_window_parameters_network_only",
            stdout.getvalue(),
        )

    def test_akshare_fallback_is_observation_not_hard_failure(self) -> None:
        metadata = akshare_metadata(fallback=True)
        checks = probe.source_checks("akshare", metadata)

        hist_provider = [item for item in checks if item["name"] == "hist_provider_clean"][0]
        self.assertEqual(False, hist_provider["passed"])
        self.assertEqual(False, hist_provider["required"])
        self.assertEqual([], [item for item in probe.required_checks(checks) if not item["passed"]])
        source_result = {"source": "akshare", "checks": checks, "passed": True}
        summary = probe.build_summary({"iterations": 1, "results": [source_result]})
        self.assertEqual({"hist_provider_clean": 1}, summary["sources"]["akshare"]["observation_failed_checks"])

    def test_baostock_adjustflag_must_match_requested_adjust(self) -> None:
        command = ["python", "fetch_baostock_a_share.py", "--adjust", "2"]
        metadata = valid_metadata("baostock")

        mismatch = probe.source_checks("baostock", metadata, command)
        adjust_check = [item for item in mismatch if item["name"] == "adjustflag_matches_request"][0]
        self.assertEqual(False, adjust_check["passed"])

        metadata["adjustflag"] = "2"
        matched = probe.source_checks("baostock", metadata, command)
        adjust_check = [item for item in matched if item["name"] == "adjustflag_matches_request"][0]
        self.assertEqual(True, adjust_check["passed"])

    def test_baostock_adjustflag_missing_value_does_not_raise(self) -> None:
        command = ["python", "fetch_baostock_a_share.py", "--adjust"]
        metadata = valid_metadata("baostock")

        checks = probe.source_checks("baostock", metadata, command)
        adjust_check = [item for item in checks if item["name"] == "adjustflag_matches_request"][0]

        self.assertEqual(False, adjust_check["passed"])

    def test_zzshare_limit_and_truncation_checks_are_required(self) -> None:
        command = [
            "python",
            "fetch_zzshare_a_share.py",
            "--limit",
            "500",
            "--max-pages",
            "3",
        ]
        metadata = valid_metadata("zzshare")
        metadata["limit"] = 500
        metadata["max_pages"] = 3

        checks = probe.source_checks("zzshare", metadata, command)
        by_name = {item["name"]: item for item in checks}

        self.assertEqual(True, by_name["limit_matches_request"]["passed"])
        self.assertEqual(True, by_name["max_pages_matches_request"]["passed"])
        self.assertEqual(True, by_name["possibly_truncated_symbols_empty"]["passed"])

        metadata["possibly_truncated_symbols"] = ["000001"]
        failed_checks = probe.source_checks("zzshare", metadata, command)
        by_name = {item["name"]: item for item in failed_checks}

        self.assertEqual(False, by_name["possibly_truncated_symbols_empty"]["passed"])
        self.assertIn(
            by_name["possibly_truncated_symbols_empty"],
            probe.required_checks(failed_checks),
        )

    def test_cli_returns_strict_error_when_required_source_fails(self) -> None:
        original_run = probe.run_command
        probe.run_command = FakeExecutor(fail_sources={"yfinance"})
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir)
                code = probe.main(
                    [
                        "--output-dir",
                        str(output / "runs"),
                        "--summary-output",
                        str(output / "summary.json"),
                        "--iterations",
                        "1",
                    ]
                )
                summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        finally:
            probe.run_command = original_run

        self.assertEqual(3, code)
        self.assertEqual(False, summary["summary"]["sources"]["yfinance"]["all_passed"])
        self.assertEqual("not_proven", summary["summary"]["long_term_stability_claim"])
        self.assertEqual(
            "current_window_parameters_network_only",
            summary["summary"]["short_window_claim_boundary"],
        )

    def test_probe_records_command_timeout_as_failed_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output)
            args.command_timeout_seconds = 1.0
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=output / "runs",
                manifest=manifest,
                executor=TimeoutExecutor("yfinance"),
            )

        yfinance = [item for item in manifest["results"] if item["source"] == "yfinance"][0]
        self.assertEqual(124, yfinance["returncode"])
        self.assertIn("timed out", yfinance["stderr"])
        self.assertEqual(False, yfinance["passed"])
        self.assertEqual(["yfinance_passed_runs=0 runs=1"], probe.strict_errors(manifest))


class FakeExecutor:
    def __init__(self, fail_sources: set[str] | None = None) -> None:
        self.fail_sources = fail_sources or set()

    def __call__(
        self,
        command: list[str],
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        source = source_from_command(command)
        metadata_path = metadata_path_from_command(command)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if source in self.fail_sources:
            metadata_path.write_text(json.dumps(failed_metadata(source), ensure_ascii=False), encoding="utf-8")
            return subprocess.CompletedProcess(command, 3, stdout="", stderr=f"{source} failed")
        metadata_path.write_text(json.dumps(valid_metadata(source), ensure_ascii=False), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=f"{source} ok", stderr="")


class TimeoutExecutor:
    def __init__(self, source: str) -> None:
        self.source = source

    def __call__(
        self,
        command: list[str],
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        source = source_from_command(command)
        if source == self.source:
            raise subprocess.TimeoutExpired(command, timeout or 0)
        metadata_path = metadata_path_from_command(command)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(valid_metadata(source), ensure_ascii=False), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=f"{source} ok", stderr="")


def source_from_command(command: list[str]) -> str:
    script = Path(command[1]).name
    if script == "fetch_akshare_a_share.py":
        return "akshare"
    if script == "fetch_yfinance_ohlcv.py":
        return "yfinance"
    if script == "fetch_baostock_a_share.py":
        return "baostock"
    if script == "fetch_zzshare_a_share.py":
        return "zzshare"
    raise AssertionError(f"unknown command: {command}")


def metadata_path_from_command(command: list[str]) -> Path:
    index = command.index("--metadata-output")
    return Path(command[index + 1])


def valid_metadata(source: str) -> dict[str, object]:
    if source == "akshare":
        return akshare_metadata(fallback=False)
    if source == "yfinance":
        return {
            "source": "yfinance",
            "requested_symbols": ["AAPL", "MSFT"],
            "rows": 4,
            "symbol_count": 2,
            "failed_symbols": [],
            "empty_symbols": [],
            "timeout_seconds": 10.0,
            "adjustment": "auto_adjust_false_close",
            "symbols": [
                {"symbol": "AAPL", "rows": 2, "date_max": "2026-05-29"},
                {"symbol": "MSFT", "rows": 2, "date_max": "2026-05-29"},
            ],
        }
    if source == "baostock":
        return {
            "source": "baostock",
            "requested_symbols": ["000001", "600000"],
            "rows": 4,
            "symbol_count": 2,
            "failed_symbols": [],
            "empty_symbols": [],
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "non_trading_rows": 0,
            "tradestatus_missing_rows": 0,
            "adjustflag": "3",
        }
    if source == "zzshare":
        return {
            "source": "zzshare",
            "requested_symbols": ["000001", "600000"],
            "rows": 4,
            "symbol_count": 2,
            "failed_symbols": [],
            "empty_symbols": [],
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "non_trading_rows": 0,
            "tradestatus_missing_rows": 0,
            "possibly_truncated_symbols": [],
            "fields": "all",
            "limit": 1000,
            "max_pages": 10,
            "token_configured": False,
            "symbols": [
                {"symbol": "000001", "rows": 2, "date_max": "2026-05-29"},
                {"symbol": "600000", "rows": 2, "date_max": "2026-05-29"},
            ],
        }
    raise AssertionError(source)


def akshare_metadata(*, fallback: bool) -> dict[str, object]:
    return {
        "source": "akshare",
        "requested_symbols": ["000001"],
        "rows": 2,
        "symbol_count": 1,
        "failed_symbols": [],
        "empty_symbols": [],
        "invalid_rows": 0,
        "dropped_invalid_rows": 0,
        "fallback_errors": [{"symbol": "000001", "error": "hist failed"}] if fallback else [],
        "symbols": [{"symbol": "000001", "rows": 2, "provider": "stock_zh_a_daily"}],
    }


def failed_metadata(source: str) -> dict[str, object]:
    return {
        "source": source,
        "requested_symbols": ["BAD"],
        "rows": 0,
        "symbol_count": 0,
        "failed_symbols": [{"symbol": "BAD", "error": "failed"}],
        "empty_symbols": ["BAD"],
    }


def args_for(output: Path) -> object:
    return probe.build_parser().parse_args(
        [
            "--output-dir",
            str(output / "runs"),
            "--summary-output",
            str(output / "summary.json"),
            "--iterations",
            "1",
        ]
    )


if __name__ == "__main__":
    unittest.main()
