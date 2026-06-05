from __future__ import annotations

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


def call_runner(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = runner.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
