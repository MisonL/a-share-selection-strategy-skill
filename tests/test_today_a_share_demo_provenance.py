from __future__ import annotations

import csv
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import create_demo_data  # noqa: E402
import run_today_a_share_selection as runner  # noqa: E402


class TodayAShareDemoProvenanceTests(unittest.TestCase):
    def test_create_demo_data_writes_demo_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            code = create_demo_data.main(
                [
                    "--output",
                    tmpdir,
                    "--days",
                    "160",
                    "--scenario",
                    "low-price-ultra-short",
                ]
            )
            metadata = json.loads((Path(tmpdir) / "metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertEqual("synthetic_demo", metadata["source_type"])
        self.assertEqual("low-price-ultra-short", metadata["scenario"])
        self.assertFalse(metadata["synthetic_prediction_proves_real_model"])

    def test_today_runner_reports_synthetic_demo_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            demo = root / "demo"
            output = root / "run"
            create_demo_data.main(
                [
                    "--output",
                    str(demo),
                    "--days",
                    "160",
                    "--scenario",
                    "low-price-ultra-short",
                ]
            )
            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(demo / "prices.csv"),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "auto",
                    "--html-report-language",
                    "en",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")

        self.assertEqual(0, code, stderr)
        self.assertEqual("synthetic_demo", summary["input_metadata"]["source_type"])
        self.assertEqual("low-price-ultra-short", summary["input_metadata"]["scenario"])
        self.assertIn("Synthetic demo data", report)
        self.assertIn("not real market data", report)

    def test_runner_artifacts_carry_synthetic_demo_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            demo = root / "demo"
            output = root / "run"
            create_demo_data.main(
                [
                    "--output",
                    str(demo),
                    "--days",
                    "160",
                    "--scenario",
                    "low-price-ultra-short",
                ]
            )
            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(demo / "prices.csv"),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "auto",
                ]
            )
            candidates = csv_rows(output / "candidates.csv")
            diagnostics = csv_rows(output / "diagnostics.csv")

        self.assertEqual(0, code, stderr)
        self.assertIn("metadata_source=synthetic_demo", stdout)
        self.assertIn("real_market_data=false", stdout)
        self.assertEqual("synthetic_demo", candidates[0]["source_type"])
        self.assertEqual("False", candidates[0]["real_market_data"])
        self.assertEqual("auto_generic", candidates[0]["mode_decision"])
        self.assertEqual("False", candidates[0]["consumes_prediction_columns"])
        self.assertEqual("False", candidates[0]["prediction_model_executed_by_runner"])
        self.assertEqual("False", candidates[0]["lightgbm_executed_by_runner"])
        self.assertTrue(diagnostics)
        self.assertEqual("synthetic_demo", diagnostics[0]["source_type"])
        self.assertEqual("False", diagnostics[0]["real_market_data"])

    def test_preflight_failure_keeps_synthetic_demo_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            demo = root / "demo"
            output = root / "run"
            create_demo_data.main(
                [
                    "--output",
                    str(demo),
                    "--days",
                    "160",
                    "--scenario",
                    "low-price-ultra-short",
                ]
            )
            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(demo / "prices.csv"),
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--html-report-language",
                    "en",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")

        self.assertEqual(2, code)
        self.assertIn("history fetch options would be ignored", stderr)
        self.assertEqual("synthetic_demo", summary["input_metadata"]["source_type"])
        self.assertFalse(summary["input_metadata"]["real_market_data"])
        self.assertIn("Synthetic demo data", report)
        self.assertIn("not real market data", report)


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def call_runner(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = runner.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
