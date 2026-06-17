from __future__ import annotations

import sys
import tempfile
import unittest
import json
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import create_demo_data  # noqa: E402
import score_candidates as scorer  # noqa: E402


def run_score_cli(
    input_path: Path,
    output_path: Path,
    diagnostics_path: Path,
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = scorer.main(
            [
                "--input",
                str(input_path),
                "--config",
                str(SCRIPTS / "ultra_short_low_price_config.json"),
                "--output",
                str(output_path),
                "--diagnostics-output",
                str(diagnostics_path),
            ]
        )
    return code, stdout.getvalue(), stderr.getvalue()


class LowPriceDemoScenarioTests(unittest.TestCase):
    def test_low_price_demo_exercises_threshold_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            create_demo_data.main(
                [
                    "--output",
                    str(root),
                    "--days",
                    "160",
                    "--scenario",
                    "low-price-ultra-short",
                ]
            )
            output_path = root / "candidates.csv"
            diagnostics_path = root / "diagnostics.csv"
            code, stdout, stderr = run_score_cli(
                root / "prices.csv",
                output_path,
                diagnostics_path,
            )
            candidates = pd.read_csv(output_path, dtype={"symbol": str})
            diagnostics = pd.read_csv(diagnostics_path, dtype={"symbol": str})

        self.assertEqual(0, code, stderr)
        self.assertIn("threshold_failures=", stdout)
        self.assertEqual({"000002"}, set(candidates["symbol"]))
        failures = failure_map(diagnostics)
        expected_failures = {
            "000003": "max_close",
            "000004": "min_amount",
            "000005": "min_turn",
            "000006": "exclude_st",
            "000007": "require_tradestatus",
            "000008": "exclude_one_word_bar",
        }
        for symbol, threshold in expected_failures.items():
            self.assertIn(threshold, failures.get(symbol, set()))

    def test_low_price_demo_runs_today_runner_as_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            create_demo_data.main(
                [
                    "--output",
                    str(root),
                    "--days",
                    "160",
                    "--scenario",
                    "low-price-ultra-short",
                ]
            )
            output = root / "today"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_today_a_share_selection.py"),
                    "--prices-input",
                    str(root / "prices.csv"),
                    "--spot-input",
                    str(root / "spot.csv"),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "auto",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            candidates = pd.read_csv(output / "candidates.csv", dtype={"symbol": str})
            diagnostics = pd.read_csv(output / "diagnostics.csv", dtype={"symbol": str})

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("generic", summary["mode"])
        self.assertEqual("auto_generic", summary["mode_decision"])
        self.assertTrue(summary["lightgbm_not_used"])
        self.assertFalse(summary["lightgbm_executed_by_runner"])
        self.assertEqual(1120, summary["prices_rows"])
        self.assertEqual(1, summary["candidate_rows"])
        self.assertEqual(7, summary["diagnostic_rows"])
        self.assertEqual(7, summary["spot_rows"])
        self.assertEqual(7, summary["spot_matched_symbols"])
        self.assertTrue(summary["summary_output_written"])
        self.assertTrue(summary["manifest_output_written"])
        self.assertEqual("软件服务", candidates.iloc[0]["spot_industry"])
        self.assertEqual(7, len(diagnostics))
        self.assertEqual(
            "软件服务",
            diagnostics[diagnostics["symbol"].eq("000002")]["spot_industry"].iloc[0],
        )
        self.assertIn("threshold_failures", summary["score"])
        self.assertEqual(
            {
                "exclude_one_word_bar": 1,
                "exclude_st": 1,
                "max_close": 1,
                "min_amount": 1,
                "min_turn": 1,
                "require_tradestatus": 1,
            },
            summary["score"]["threshold_failures_by_rule"],
        )


def failure_map(diagnostics: pd.DataFrame) -> dict[str, set[str]]:
    failures = {}
    for _, row in diagnostics.iterrows():
        value = row["failed_thresholds"]
        if pd.isna(value):
            continue
        failures[row["symbol"]] = set(str(value).split(";"))
    return failures


if __name__ == "__main__":
    unittest.main()
