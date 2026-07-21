from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import probe_external_source_stability as probe  # noqa: E402
from lib.gates import external_source_evidence_archive as archive  # noqa: E402


class ExternalSourceStabilitySummaryTests(unittest.TestCase):
    def test_success_summary_projects_latest_command_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            args = args_for(root)
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=root / "runs",
                manifest=manifest,
                executor=ProbeExecutor(stderr_by_source={"yfinance": "provider notice"}),
                monotonic=IncrementingClock(),
            )

        yfinance_result = result_for(manifest, "yfinance")
        yfinance = manifest["summary"]["sources"]["yfinance"]

        self.assertTrue(manifest["summary"]["all_sources_all_iterations_passed"])
        self.assertEqual([], probe.strict_errors(manifest))
        self.assertEqual(
            {
                "latest_source_returncode": 0,
                "latest_command_elapsed_seconds": 0.25,
                "latest_command_timeout_seconds": 120.0,
                "latest_command_timed_out": False,
                "latest_first_required_failure": None,
                "latest_metadata_output": yfinance_result["metadata_output"],
                "latest_stderr_nonempty": True,
            },
            latest_projection(yfinance),
        )
        self.assertTrue(
            {
                "command",
                "stdout",
                "stderr",
                "metadata",
            }.isdisjoint(yfinance)
        )

    def test_strict_failure_stderr_is_compact_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "api_key=probe-secret-path"
            executor = ProbeExecutor(
                metadata_by_source={"yfinance": {}},
                stderr_by_source={
                    "yfinance": "api_key=probe-secret-stderr strict-source-detail"
                },
            )
            stderr = io.StringIO()
            stdout = io.StringIO()
            with (
                patch.object(probe, "run_command", executor),
                redirect_stderr(stderr),
                redirect_stdout(stdout),
            ):
                code = probe.main(
                    [
                        "--output-dir",
                        str(root / "runs"),
                        "--summary-output",
                        str(root / "summary.json"),
                        "--iterations",
                        "1",
                    ]
                )
            saved = json.loads((root / "summary.json").read_text(encoding="utf-8"))

        yfinance = saved["summary"]["sources"]["yfinance"]
        error_output = stderr.getvalue()
        self.assertEqual(3, code)
        self.assertFalse(yfinance["all_passed"])
        self.assertEqual(0, yfinance["latest_source_returncode"])
        self.assertEqual("metadata_written", yfinance["latest_first_required_failure"])
        self.assertTrue(yfinance["latest_stderr_nonempty"])
        self.assertNotIn("probe-secret-path", yfinance["latest_metadata_output"])
        self.assertIn("ERROR: strict gate failed;", error_output)
        self.assertIn("source=yfinance", error_output)
        self.assertIn("failed_source_returncode=0", error_output)
        self.assertIn("failed_first_required_failure=metadata_written", error_output)
        self.assertIn("failed_metadata_output=", error_output)
        self.assertIn("failed_command_timed_out=false", error_output)
        self.assertIn("failed_command_timeout_seconds=120.0", error_output)
        self.assertNotIn("probe-secret-stderr", error_output)
        self.assertNotIn("strict-source-detail", error_output)
        self.assertNotIn("probe-secret-path", error_output)
        self.assertNotIn("probe-secret-stderr", json.dumps(saved))
        self.assertNotIn("probe-secret-path", json.dumps(saved))

    def test_timeout_projection_marks_only_timeout_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            args = args_for(root)
            args.command_timeout_seconds = 7.5
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=root / "runs",
                manifest=manifest,
                executor=TimeoutProbeExecutor("yfinance"),
                monotonic=IncrementingClock(),
            )

        yfinance = manifest["summary"]["sources"]["yfinance"]
        self.assertFalse(yfinance["all_passed"])
        self.assertEqual(124, yfinance["latest_source_returncode"])
        self.assertEqual(0.25, yfinance["latest_command_elapsed_seconds"])
        self.assertEqual(7.5, yfinance["latest_command_timeout_seconds"])
        self.assertTrue(yfinance["latest_command_timed_out"])
        self.assertEqual("metadata_written", yfinance["latest_first_required_failure"])

    def test_disabled_command_timeout_projects_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            args = args_for(root)
            args.command_timeout_seconds = 0.0
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=root / "runs",
                manifest=manifest,
                executor=ProbeExecutor(),
                monotonic=IncrementingClock(),
            )

        yfinance = manifest["summary"]["sources"]["yfinance"]
        self.assertIsNone(yfinance["latest_command_timeout_seconds"])
        self.assertFalse(yfinance["latest_command_timed_out"])

    def test_latest_projection_stays_on_the_last_iteration(self) -> None:
        first = summary_result(
            source="yfinance",
            returncode=3,
            elapsed=0.5,
            timeout=10.0,
            timed_out=False,
            metadata_output="/tmp/first-metadata.json",
            checks=[
                {"name": "metadata_written", "passed": False, "required": True}
            ],
            passed=False,
        )
        latest = summary_result(
            source="yfinance",
            returncode=0,
            elapsed=0.75,
            timeout=10.0,
            timed_out=False,
            metadata_output="/tmp/latest-metadata.json",
            checks=[
                {"name": "metadata_written", "passed": True, "required": True}
            ],
            passed=True,
        )

        summary = probe.build_summary({"iterations": 2, "results": [first, latest]})
        yfinance = summary["sources"]["yfinance"]

        self.assertFalse(yfinance["all_passed"])
        self.assertEqual(1, yfinance["passed_runs"])
        self.assertEqual(0, yfinance["latest_source_returncode"])
        self.assertEqual(0.75, yfinance["latest_command_elapsed_seconds"])
        self.assertEqual("/tmp/latest-metadata.json", yfinance["latest_metadata_output"])
        self.assertIsNone(yfinance["latest_first_required_failure"])
        diagnostics = probe.strict_failure_diagnostics(
            {"results": [first, latest], "summary": summary}
        )
        self.assertEqual(1, len(diagnostics))
        self.assertIn("failed_source_returncode=3", diagnostics[0])
        self.assertIn("failed_first_required_failure=metadata_written", diagnostics[0])
        self.assertIn("first-metadata.json", diagnostics[0])
        self.assertNotIn("latest-metadata.json", diagnostics[0])

    def test_latest_first_required_failure_uses_check_order(self) -> None:
        result = summary_result(
            source="yfinance",
            returncode=0,
            elapsed=0.5,
            timeout=10.0,
            timed_out=False,
            metadata_output="/tmp/metadata.json",
            checks=[
                {"name": "optional_notice", "passed": False, "required": False},
                {"name": "metadata_written", "passed": False, "required": True},
                {"name": "rows_positive", "passed": False, "required": True},
            ],
            passed=False,
        )

        summary = probe.build_summary({"iterations": 1, "results": [result]})
        yfinance = summary["sources"]["yfinance"]

        self.assertEqual("metadata_written", yfinance["latest_first_required_failure"])
        self.assertEqual({"optional_notice": 1}, yfinance["observation_failed_checks"])

    def test_returncode_124_without_timeout_exception_is_not_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            args = args_for(root)
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=root / "runs",
                manifest=manifest,
                executor=ProbeExecutor(returncodes={"yfinance": 124}),
                monotonic=IncrementingClock(),
            )

        yfinance = manifest["summary"]["sources"]["yfinance"]
        self.assertFalse(yfinance["all_passed"])
        self.assertEqual(124, yfinance["latest_source_returncode"])
        self.assertFalse(yfinance["latest_command_timed_out"])
        self.assertIsNone(yfinance["latest_first_required_failure"])
        diagnostics = probe.strict_failure_diagnostics(manifest)
        self.assertEqual(1, len(diagnostics))
        self.assertIn("failed_source_returncode=124", diagnostics[0])
        self.assertIn("failed_first_required_failure=null", diagnostics[0])
        self.assertIn("failed_command_timed_out=false", diagnostics[0])

    def test_optional_observation_failure_does_not_become_required_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            args = args_for(root)
            manifest = probe.initial_manifest(args)
            metadata = valid_metadata("akshare")
            metadata["fallback_errors"] = [{"symbol": "000001", "error": "hist failed"}]
            probe.run_probe(
                args,
                output_dir=root / "runs",
                manifest=manifest,
                executor=ProbeExecutor(metadata_by_source={"akshare": metadata}),
                monotonic=IncrementingClock(),
            )

        akshare = manifest["summary"]["sources"]["akshare"]
        self.assertTrue(akshare["all_passed"])
        self.assertEqual(
            {"hist_provider_clean": 1},
            akshare["observation_failed_checks"],
        )
        self.assertIsNone(akshare["latest_first_required_failure"])

    def test_observation_failures_accumulate_across_iterations(self) -> None:
        first = summary_result(
            source="akshare",
            returncode=0,
            elapsed=0.5,
            timeout=10.0,
            timed_out=False,
            metadata_output="/tmp/first-metadata.json",
            checks=[
                {"name": "hist_provider_clean", "passed": False, "required": False},
                {"name": "rows_positive", "passed": True, "required": True},
            ],
            passed=True,
        )
        second = summary_result(
            source="akshare",
            returncode=0,
            elapsed=0.75,
            timeout=10.0,
            timed_out=False,
            metadata_output="/tmp/second-metadata.json",
            checks=[
                {"name": "hist_provider_clean", "passed": False, "required": False},
                {"name": "rows_positive", "passed": True, "required": True},
            ],
            passed=True,
        )

        summary = probe.build_summary({"iterations": 2, "results": [first, second]})
        akshare = summary["sources"]["akshare"]

        self.assertTrue(akshare["all_passed"])
        self.assertEqual(
            {"hist_provider_clean": 2},
            akshare["observation_failed_checks"],
        )

    def test_strict_failure_diagnostics_include_each_source_in_summary_order(self) -> None:
        yfinance = summary_result(
            source="yfinance",
            returncode=7,
            elapsed=0.5,
            timeout=10.0,
            timed_out=False,
            metadata_output="/tmp/yfinance-metadata.json",
            checks=[{"name": "rows_positive", "passed": True, "required": True}],
            passed=False,
        )
        pytdx = summary_result(
            source="pytdx",
            returncode=8,
            elapsed=0.75,
            timeout=10.0,
            timed_out=False,
            metadata_output="/tmp/pytdx-metadata.json",
            checks=[{"name": "rows_positive", "passed": True, "required": True}],
            passed=False,
        )

        summary = probe.build_summary({"iterations": 1, "results": [yfinance, pytdx]})
        diagnostics = probe.strict_failure_diagnostics(
            {"results": [yfinance, pytdx], "summary": summary}
        )

        self.assertEqual(2, len(diagnostics))
        self.assertTrue(diagnostics[0].startswith("source=pytdx "))
        self.assertTrue(diagnostics[1].startswith("source=yfinance "))

    def test_runbook_documents_summary_first_diagnostic_path(self) -> None:
        runbook = (
            ROOT
            / "skills"
            / "a-share-selection-strategy"
            / "instructions"
            / "runbook.md"
        ).read_text(encoding="utf-8")

        for field in [
            "latest_source_returncode",
            "latest_command_elapsed_seconds",
            "latest_command_timeout_seconds",
            "latest_command_timed_out",
            "latest_first_required_failure",
            "latest_metadata_output",
            "latest_stderr_nonempty",
        ]:
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", runbook)
        self.assertIn("source 子命令", runbook)
        self.assertIn("完整审计", runbook)
        self.assertIn("`results[]`", runbook)
        self.assertIn("不复制原始 stderr", runbook)

    def test_archive_rejects_recorded_metadata_symlink(self) -> None:
        if os.name != "posix":
            self.skipTest("metadata symlink contract is POSIX-specific")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "metadata-target.json"
            target.write_text("{}", encoding="utf-8")
            metadata_path = root / "metadata.json"
            metadata_path.symlink_to(target)
            spec = probe.SourceSpec(
                name="yfinance",
                command=["python", "fetch_yfinance_ohlcv.py"],
                metadata_path=metadata_path,
                output_path=root / "prices.csv",
            )
            record = probe.source_record(
                spec,
                subprocess.CompletedProcess(spec.command, 0, stdout="", stderr=""),
                valid_metadata("yfinance"),
            )

            self.assertTrue(record["metadata_output_is_symlink"])
            self.assertFalse(record["metadata_output_is_file"])
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                archive.archive_evidence({"results": [record]}, root / "evidence")


class IncrementingClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        current = self.value
        self.value += 0.25
        return current


class ProbeExecutor:
    def __init__(
        self,
        *,
        returncodes: dict[str, int] | None = None,
        stderr_by_source: dict[str, str] | None = None,
        metadata_by_source: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.returncodes = returncodes or {}
        self.stderr_by_source = stderr_by_source or {}
        self.metadata_by_source = metadata_by_source or {}

    def __call__(
        self,
        command: list[str],
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        source = source_from_command(command)
        metadata_path = metadata_path_from_command(command)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = self.metadata_by_source.get(source, valid_metadata(source))
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            self.returncodes.get(source, 0),
            stdout=f"{source} stdout",
            stderr=self.stderr_by_source.get(source, ""),
        )


class TimeoutProbeExecutor(ProbeExecutor):
    def __init__(self, timeout_source: str) -> None:
        super().__init__()
        self.timeout_source = timeout_source

    def __call__(
        self,
        command: list[str],
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if source_from_command(command) == self.timeout_source:
            raise subprocess.TimeoutExpired(command, timeout or 0.0)
        return super().__call__(command, timeout)


def latest_projection(source_summary: dict[str, object]) -> dict[str, object]:
    fields = [
        "latest_source_returncode",
        "latest_command_elapsed_seconds",
        "latest_command_timeout_seconds",
        "latest_command_timed_out",
        "latest_first_required_failure",
        "latest_metadata_output",
        "latest_stderr_nonempty",
    ]
    return {field: source_summary[field] for field in fields}


def result_for(manifest: dict[str, object], source: str) -> dict[str, object]:
    results = manifest["results"]
    assert isinstance(results, list)
    for result in results:
        assert isinstance(result, dict)
        if result["source"] == source:
            return result
    raise AssertionError(f"missing result for {source}")


def source_from_command(command: list[str]) -> str:
    scripts = {
        "fetch_eastmoney_a_share_spot.py": "eastmoney_spot",
        "fetch_baostock_a_share_universe.py": "baostock_universe",
        "fetch_akshare_a_share.py": "akshare",
        "fetch_pytdx_a_share.py": "pytdx",
        "fetch_yfinance_ohlcv.py": "yfinance",
        "fetch_baostock_a_share.py": "baostock",
        "fetch_zzshare_a_share.py": "zzshare",
    }
    return scripts[Path(command[1]).name]


def metadata_path_from_command(command: list[str]) -> Path:
    return Path(command[command.index("--metadata-output") + 1])


def valid_metadata(source: str) -> dict[str, object]:
    if source == "eastmoney_spot":
        return {
            "source": "eastmoney",
            "raw_items": 10,
            "filtered_items": 10,
            "partial_result": False,
            "output_written": True,
            "metadata_output_written": True,
        }
    if source == "baostock_universe":
        return {
            "source": "baostock",
            "raw_items": 2,
            "filtered_items": 2,
            "partial_result": False,
            "output_written": True,
            "metadata_output_written": True,
            "resolved_snapshot_date": "2026-07-09",
            "lookback_days": 7,
        }

    metadata: dict[str, object] = {
        "requested_symbols": ["000001"],
        "rows": 2,
        "symbol_count": 1,
        "failed_symbols": [],
        "empty_symbols": [],
    }
    if source == "akshare":
        return {
            **metadata,
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "fallback_errors": [],
        }
    if source == "pytdx":
        return {
            **metadata,
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "timeout_seconds": 10.0,
            "max_pages": 1,
            "token_configured": False,
            "license_claim_boundary": "personal_research_boundary",
            "missing_provider_fields": ["turn", "tradestatus", "isST", "name"],
        }
    if source == "yfinance":
        return {
            **metadata,
            "timeout_seconds": 10.0,
            "adjustment": "auto_adjust_false_close",
        }
    if source == "baostock":
        return {
            **metadata,
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "non_trading_rows": 0,
            "tradestatus_missing_rows": 0,
            "adjustflag": "3",
        }
    if source == "zzshare":
        return {
            **metadata,
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "non_trading_rows": 0,
            "tradestatus_missing_rows": 0,
            "possibly_truncated_symbols": [],
            "fields": "all",
            "limit": 1000,
            "max_pages": 10,
        }
    raise AssertionError(source)


def summary_result(
    *,
    source: str,
    returncode: int,
    elapsed: float,
    timeout: float | None,
    timed_out: bool,
    metadata_output: str,
    checks: list[dict[str, object]],
    passed: bool,
) -> dict[str, object]:
    return {
        "source": source,
        "returncode": returncode,
        "command_elapsed_seconds": elapsed,
        "command_timeout_seconds": timeout,
        "command_timed_out": timed_out,
        "metadata_output": metadata_output,
        "stderr": "",
        "checks": checks,
        "passed": passed,
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
