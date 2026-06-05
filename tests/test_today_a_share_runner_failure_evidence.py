from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import run_today_a_share_selection as runner  # noqa: E402
from helpers import build_frame  # noqa: E402


class TodayAShareRunnerFailureEvidenceTests(unittest.TestCase):
    def test_preflight_error_reports_summary_and_manifest_only(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
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
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("history fetch options would be ignored", stderr)
        self.assertIn("summary_written=true", stderr)
        self.assertIn("manifest_written=true", stderr)
        self.assertNotIn("output_written=true", stderr)


def call_runner(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = runner.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
