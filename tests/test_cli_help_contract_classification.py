from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CLI_HELP_ENTRIES = [
    "allocate_candidate_capital.py",
    "allocate_portfolio_candidate_capital.py",
    "backtest_buy_hold.py",
    "create_demo_data.py",
    "fetch_akshare_a_share.py",
    "fetch_baostock_a_share.py",
    "fetch_yfinance_ohlcv.py",
    "generate_lightgbm_predictions.py",
    "portfolio_equity_curve.py",
    "portfolio_overlap_report.py",
    "probe_baostock_limit_fields.py",
    "probe_external_source_stability.py",
    "run_baostock_walk_forward.py",
    "score_candidates.py",
    "slice_prices_as_of.py",
    "summarize_walk_forward_run.py",
    "validate_ohlcv.py",
    "validate_walk_forward_artifacts.py",
    "validate_walk_forward_manifest.py",
]
HELP_CONTRACT_EXCLUDED_HELPERS = [
    "lightgbm_prediction_summary.py",
    "portfolio_candidate_allocation.py",
    "stock_selection_backtest_rows.py",
    "stock_selection_calendar_contract.py",
    "stock_selection_capital.py",
    "stock_selection_config.py",
    "stock_selection_data.py",
    "stock_selection_diagnostics.py",
    "stock_selection_metrics.py",
    "stock_selection_model_contracts.py",
    "stock_selection_output.py",
    "stock_selection_profile.py",
    "stock_selection_symbols.py",
    "stock_selection_tradability.py",
    "stock_selection_universe.py",
    "walk_forward_allocation_checks.py",
    "walk_forward_artifact_checks.py",
    "walk_forward_metadata_checks.py",
    "walk_forward_portfolio_commands.py",
    "walk_forward_price_checks.py",
]


class CliHelpContractClassificationTests(unittest.TestCase):
    def test_all_scripts_are_classified_as_cli_or_helper(self) -> None:
        all_scripts = {path.name for path in (ROOT / "scripts").glob("*.py")}
        classified = set(CLI_HELP_ENTRIES) | set(HELP_CONTRACT_EXCLUDED_HELPERS)

        self.assertEqual(all_scripts, classified)
        self.assertFalse(set(CLI_HELP_ENTRIES) & set(HELP_CONTRACT_EXCLUDED_HELPERS))

    def test_helper_modules_are_excluded_from_cli_help_contract(self) -> None:
        for script_name in HELP_CONTRACT_EXCLUDED_HELPERS:
            script = ROOT / f"scripts/{script_name}"
            with self.subTest(script=script.name):
                source = script.read_text(encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, "-S", str(script), "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertNotIn("argparse", source)
                self.assertNotIn("def main(", source)
                self.assertNotIn('__name__ == "__main__"', source)
                self.assertNotIn("usage:", result.stdout)
                if result.returncode != 0:
                    self.assertRegex(
                        result.stderr,
                        "ModuleNotFoundError|pandas|numpy|stock_selection_data",
                    )
