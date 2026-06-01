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
            "create_demo_data.py": ["--output", "--days"],
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
            "probe_external_source_stability.py": [
                "--output-dir",
                "--summary-output",
                "--iterations",
                "--akshare-symbols",
                "--yfinance-symbols",
                "--baostock-symbols",
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
            "slice_prices_as_of.py": ["--input", "--output", "--as-of-date"],
            "allocate_candidate_capital.py": [
                "--prices",
                "--candidates",
                "--output",
                "--cash-budget",
                "--lot-size",
                "--fail-on-unallocated",
            ],
            "allocate_portfolio_candidate_capital.py": [
                "--prices",
                "--raw-candidates",
                "--candidate-outputs",
                "--sized-outputs",
                "--skipped-output",
                "--summary-output",
                "--cash-budget",
                "--hold-days",
                "--max-open-positions",
            ],
            "backtest_buy_hold.py": [
                "--prices",
                "--candidates",
                "--output",
                "--hold-days",
                "--cost-bps",
                "--slippage-bps",
                "--require-tradable-bars",
                "--require-tradable-holding-period",
                "--fail-on-incomplete",
            ],
            "portfolio_equity_curve.py": [
                "--backtests",
                "--output",
                "--initial-equity",
                "--fail-on-incomplete",
                "--min-final-equity",
                "--max-drawdown-floor",
            ],
            "portfolio_overlap_report.py": [
                "--backtests",
                "--daily-output",
                "--overlap-output",
                "--summary-output",
                "--max-open-positions",
                "--max-gross-weight",
                "--max-gross-notional",
                "--max-cash-reserved",
                "--fail-on-symbol-overlap",
                "--require-capital-fields",
                "business_day_closed_interval",
                "pandas.bdate_range",
                "not an exchange trading calendar",
            ],
            "summarize_walk_forward_run.py": [
                "--run-dir",
                "--output",
                "--signal-dates",
                "--expected-symbol-count",
                "--required-tradability-model",
                "--required-limit-rules-model",
                "--max-open-positions",
                "--max-gross-weight",
                "--max-gross-notional",
                "--max-cash-reserved",
                "--fail-on-symbol-overlap",
                "--expect-portfolio-violations",
                "--allow-dropped-invalid-rows",
            ],
            "validate_walk_forward_manifest.py": [
                "--manifest",
                "--output",
                "--signal-dates",
                "--expected-symbol-count",
                "--required-tradability-model",
                "--required-limit-rules-model",
                "--expected-max-candidates",
                "--expect-portfolio-violations",
            ],
            "validate_walk_forward_artifacts.py": [
                "--run-dir",
                "--output",
                "--signal-dates",
                "--expected-symbols",
                "--expected-candidates",
                "--expected-final-equity",
                "--expected-portfolio-violations",
                "--required-allocation-model",
                "--required-tradability-model",
                "--required-limit-rules-model",
                "--manifest-validation",
                "--allow-dropped-invalid-rows",
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
        slice_script = ROOT / "scripts/slice_prices_as_of.py"
        allocate_script = ROOT / "scripts/allocate_candidate_capital.py"
        portfolio_allocate_script = ROOT / "scripts/allocate_portfolio_candidate_capital.py"
        backtest_script = ROOT / "scripts/backtest_buy_hold.py"
        equity_curve_script = ROOT / "scripts/portfolio_equity_curve.py"
        overlap_report_script = ROOT / "scripts/portfolio_overlap_report.py"
        run_summary_script = ROOT / "scripts/summarize_walk_forward_run.py"

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
            slice_output = Path(tmpdir) / "slice.csv"
            allocation_output = Path(tmpdir) / "allocated.csv"
            portfolio_selected = Path(tmpdir) / "portfolio-selected.csv"
            portfolio_sized = Path(tmpdir) / "portfolio-sized.csv"
            portfolio_skipped = Path(tmpdir) / "portfolio-skipped.csv"
            portfolio_summary = Path(tmpdir) / "portfolio-summary.json"
            backtest_output = Path(tmpdir) / "backtest.csv"
            equity_output = Path(tmpdir) / "equity.csv"
            overlap_daily = Path(tmpdir) / "overlap-daily.csv"
            overlap_rows = Path(tmpdir) / "overlap-rows.csv"
            overlap_summary = Path(tmpdir) / "overlap-summary.json"
            run_summary = Path(tmpdir) / "run-summary.json"
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
                [
                    str(slice_script),
                    "--input",
                    str(Path(tmpdir) / "missing-prices.csv"),
                    "--output",
                    str(slice_output),
                    "--as-of-date",
                    "2026-05-20",
                ],
                [
                    str(allocate_script),
                    "--prices",
                    str(Path(tmpdir) / "missing-prices.csv"),
                    "--candidates",
                    str(Path(tmpdir) / "missing-candidates.csv"),
                    "--output",
                    str(allocation_output),
                    "--cash-budget",
                    "10000",
                ],
                [
                    str(portfolio_allocate_script),
                    "--prices",
                    str(Path(tmpdir) / "missing-prices.csv"),
                    "--raw-candidates",
                    str(Path(tmpdir) / "missing-candidates.csv"),
                    "--candidate-outputs",
                    str(portfolio_selected),
                    "--sized-outputs",
                    str(portfolio_sized),
                    "--skipped-output",
                    str(portfolio_skipped),
                    "--summary-output",
                    str(portfolio_summary),
                    "--cash-budget",
                    "10000",
                    "--hold-days",
                    "5",
                    "--max-open-positions",
                    "10",
                    "--max-gross-weight",
                    "1.0",
                    "--max-gross-notional",
                    "10000",
                    "--max-cash-reserved",
                    "10000",
                ],
                [
                    str(backtest_script),
                    "--prices",
                    str(Path(tmpdir) / "missing-prices.csv"),
                    "--candidates",
                    str(Path(tmpdir) / "missing-candidates.csv"),
                    "--output",
                    str(backtest_output),
                ],
                [
                    str(equity_curve_script),
                    "--backtests",
                    str(Path(tmpdir) / "missing-backtest.csv"),
                    "--output",
                    str(equity_output),
                ],
                [
                    str(overlap_report_script),
                    "--backtests",
                    str(Path(tmpdir) / "missing-backtest.csv"),
                    "--daily-output",
                    str(overlap_daily),
                    "--overlap-output",
                    str(overlap_rows),
                    "--summary-output",
                    str(overlap_summary),
                ],
                [
                    str(run_summary_script),
                    "--run-dir",
                    str(Path(tmpdir) / "missing-run"),
                    "--output",
                    str(run_summary),
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
            self.assertFalse(slice_output.exists())
            self.assertFalse(allocation_output.exists())
            self.assertFalse(portfolio_selected.exists())
            self.assertFalse(portfolio_sized.exists())
            self.assertFalse(portfolio_skipped.exists())
            self.assertFalse(portfolio_summary.exists())
            self.assertFalse(backtest_output.exists())
            self.assertFalse(equity_output.exists())
            self.assertFalse(overlap_daily.exists())
            self.assertFalse(overlap_rows.exists())
            self.assertFalse(overlap_summary.exists())
            self.assertFalse(run_summary.exists())
