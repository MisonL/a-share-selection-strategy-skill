from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliHelpWithoutDependenciesTests(unittest.TestCase):
    def test_core_navigation_help_does_not_import_pandas(self) -> None:
        cases = {
            "run_baostock_walk_forward.py": [],
            "probe_baostock_limit_fields.py": [],
            "validate_ohlcv.py": ["--input", "--config", "--min-history-rows"],
            "score_candidates.py": [
                "--input",
                "--config",
                "--output",
                "--fail-on-skipped",
                "--fail-on-empty-result",
            ],
        }
        for script_name, expected_options in cases.items():
            script = ROOT / f"scripts/{script_name}"
            with self.subTest(script=script.name):
                result = subprocess.run(
                    [sys.executable, "-S", str(script), "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("usage:", result.stdout)
                for option in expected_options:
                    self.assertIn(option, result.stdout)

    def test_runtime_paths_still_fail_without_pandas(self) -> None:
        validate_script = ROOT / "scripts/validate_ohlcv.py"
        score_script = ROOT / "scripts/score_candidates.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "candidates.csv"
            cases = [
                [
                    str(validate_script),
                    "--input",
                    str(Path(tmpdir) / "missing-prices.csv"),
                ],
                [
                    str(score_script),
                    "--input",
                    str(Path(tmpdir) / "missing-prices.csv"),
                    "--config",
                    str(ROOT / "scripts/example_config.json"),
                    "--output",
                    str(output),
                ],
            ]
            for command in cases:
                with self.subTest(script=Path(command[0]).name):
                    result = subprocess.run(
                        [sys.executable, "-S", *command],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("pandas", result.stderr)
            self.assertFalse(output.exists())
