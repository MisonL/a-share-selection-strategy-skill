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
            "fetch_baostock_a_share.py": [
                "--symbols",
                "--start-date",
                "--end-date",
                "--output",
                "--metadata-output",
                "--fail-on-fetch-error",
                "--drop-invalid-rows",
            ],
            "fetch_akshare_a_share.py": [
                "--symbols",
                "--start-date",
                "--end-date",
                "--output",
                "--metadata-output",
                "--fail-on-fetch-error",
                "--drop-invalid-rows",
            ],
            "fetch_yfinance_ohlcv.py": [
                "--symbols",
                "--start-date",
                "--end-date",
                "--output",
                "--metadata-output",
                "--market",
                "--timeout-seconds",
                "--fail-on-fetch-error",
            ],
            "generate_lightgbm_predictions.py": [
                "--input",
                "--output",
                "--horizon",
                "--train-ratio",
                "--min-history-rows",
                "--summary-output",
                "--fail-on-skipped",
            ],
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

    def test_runtime_paths_still_fail_without_dataframe_dependencies(self) -> None:
        validate_script = ROOT / "scripts/validate_ohlcv.py"
        score_script = ROOT / "scripts/score_candidates.py"
        fetch_baostock_script = ROOT / "scripts/fetch_baostock_a_share.py"
        fetch_akshare_script = ROOT / "scripts/fetch_akshare_a_share.py"
        fetch_yfinance_script = ROOT / "scripts/fetch_yfinance_ohlcv.py"
        lightgbm_script = ROOT / "scripts/generate_lightgbm_predictions.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "candidates.csv"
            baostock_output = Path(tmpdir) / "baostock.csv"
            baostock_metadata = Path(tmpdir) / "baostock-metadata.json"
            akshare_output = Path(tmpdir) / "akshare.csv"
            akshare_metadata = Path(tmpdir) / "akshare-metadata.json"
            yfinance_output = Path(tmpdir) / "yfinance.csv"
            yfinance_metadata = Path(tmpdir) / "yfinance-metadata.json"
            lightgbm_output = Path(tmpdir) / "predictions.csv"
            lightgbm_summary = Path(tmpdir) / "prediction-summary.json"
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
                [
                    str(fetch_baostock_script),
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2026-05-20",
                    "--end-date",
                    "2026-05-20",
                    "--output",
                    str(baostock_output),
                    "--metadata-output",
                    str(baostock_metadata),
                ],
                [
                    str(fetch_akshare_script),
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2026-05-20",
                    "--end-date",
                    "2026-05-20",
                    "--output",
                    str(akshare_output),
                    "--metadata-output",
                    str(akshare_metadata),
                ],
                [
                    str(fetch_yfinance_script),
                    "--symbols",
                    "AAPL",
                    "--start-date",
                    "2026-05-20",
                    "--end-date",
                    "2026-05-20",
                    "--output",
                    str(yfinance_output),
                    "--metadata-output",
                    str(yfinance_metadata),
                ],
                [
                    str(lightgbm_script),
                    "--input",
                    str(Path(tmpdir) / "missing-prices.csv"),
                    "--output",
                    str(lightgbm_output),
                    "--summary-output",
                    str(lightgbm_summary),
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
                    self.assertRegex(result.stderr, "pandas|numpy")
            self.assertFalse(output.exists())
            self.assertFalse(baostock_output.exists())
            self.assertFalse(baostock_metadata.exists())
            self.assertFalse(akshare_output.exists())
            self.assertFalse(akshare_metadata.exists())
            self.assertFalse(yfinance_output.exists())
            self.assertFalse(yfinance_metadata.exists())
            self.assertFalse(lightgbm_output.exists())
            self.assertFalse(lightgbm_summary.exists())
