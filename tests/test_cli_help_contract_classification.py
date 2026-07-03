from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import subprocess
import sys
import unittest
from pathlib import Path
from shutil import which


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from a_share_selection_cli_guard import fail_not_cli  # noqa: E402

CLI_HELP_ENTRIES = [
    "allocate_candidate_capital.py",
    "allocate_portfolio_candidate_capital.py",
    "backtest_buy_hold.py",
    "create_demo_data.py",
    "fetch_akshare_a_share.py",
    "fetch_akshare_hk_daily.py",
    "fetch_baostock_a_share.py",
    "fetch_eastmoney_a_share_spot.py",
    "fetch_yfinance_ohlcv.py",
    "fetch_zzshare_a_share.py",
    "generate_lightgbm_predictions.py",
    "portfolio_equity_curve.py",
    "portfolio_overlap_report.py",
    "probe_baostock_limit_fields.py",
    "probe_external_source_stability.py",
    "run_baostock_walk_forward.py",
    "run_today_a_share_selection.py",
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
    "run_today_a_share_selection_commands.py",
    "run_today_a_share_selection_helpers.py",
    "run_today_a_share_selection_history.py",
    "run_today_a_share_selection_input_metadata.py",
    "run_today_a_share_selection_modes.py",
    "run_today_a_share_selection_outputs.py",
    "run_today_a_share_selection_parser.py",
    "run_today_a_share_selection_provenance.py",
    "run_today_a_share_selection_summary.py",
    "run_today_a_share_selection_validation.py",
    "a_share_selection_backtest_rows.py",
    "a_share_selection_calendar_contract.py",
    "a_share_selection_candidate_fields.py",
    "a_share_selection_capital.py",
    "a_share_selection_cli_guard.py",
    "a_share_selection_config.py",
    "a_share_selection_disclosure.py",
    "a_share_selection_diagnostic_labels.py",
    "a_share_selection_data.py",
    "a_share_selection_diagnostics.py",
    "a_share_selection_html_assets.py",
    "a_share_selection_html_candidate_helpers.py",
    "a_share_selection_html_candidate_master.py",
    "a_share_selection_html_candidate_preview.py",
    "a_share_selection_html_data.py",
    "a_share_selection_html_format.py",
    "a_share_selection_html_history.py",
    "a_share_selection_html_report.py",
    "a_share_selection_html_i18n.py",
    "a_share_selection_html_modes.py",
    "a_share_selection_html_scripts.py",
    "a_share_selection_html_sections.py",
    "a_share_selection_html_spot.py",
    "a_share_selection_html_styles.py",
    "a_share_selection_metrics.py",
    "a_share_selection_model_contracts.py",
    "a_share_selection_output.py",
    "a_share_selection_paths.py",
    "a_share_selection_profile.py",
    "a_share_selection_prepare.py",
    "a_share_selection_provenance.py",
    "a_share_selection_score_summary.py",
    "a_share_selection_symbols.py",
    "a_share_selection_spot.py",
    "a_share_selection_tradability.py",
    "a_share_selection_universe.py",
    "walk_forward_allocation_checks.py",
    "walk_forward_artifact_checks.py",
    "walk_forward_metadata_checks.py",
    "walk_forward_date_checks.py",
    "walk_forward_portfolio_commands.py",
    "walk_forward_price_checks.py",
    "zzshare_a_share_data.py",
    "zzshare_a_share_quality.py",
]
HELPER_ARGPARSE_MODULES = {
    "run_today_a_share_selection_parser.py",
}


class CliHelpContractClassificationTests(unittest.TestCase):
    def test_all_scripts_are_classified_as_cli_or_helper(self) -> None:
        all_scripts = {path.name for path in (SKILL_ROOT / "scripts").glob("*.py")}
        classified = set(CLI_HELP_ENTRIES) | set(HELP_CONTRACT_EXCLUDED_HELPERS)

        self.assertEqual(all_scripts, classified)
        self.assertFalse(set(CLI_HELP_ENTRIES) & set(HELP_CONTRACT_EXCLUDED_HELPERS))

    def test_helper_modules_are_excluded_from_cli_help_contract(self) -> None:
        for script_name in HELP_CONTRACT_EXCLUDED_HELPERS:
            script = SCRIPTS / script_name
            with self.subTest(script=script.name):
                source = script.read_text(encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, "-S", str(script), "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if script_name not in HELPER_ARGPARSE_MODULES:
                    self.assertNotIn("argparse", source)
                self.assertNotIn("def main(", source)
                self.assertNotIn("usage:", result.stdout)
                if result.returncode != 0:
                    self.assertRegex(
                        result.stderr,
                        (
                            "ModuleNotFoundError|pandas|numpy|a_share_selection_data|"
                            "not a CLI entry"
                        ),
                    )

    def test_cli_guard_reports_standard_not_cli_error(self) -> None:
        stderr = StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            fail_not_cli("helper_module.py")

        self.assertEqual(2, raised.exception.code)
        self.assertIn("helper_module.py is not a CLI entry", stderr.getvalue())
        self.assertIn("use one of:", stderr.getvalue())

    def test_helper_modules_fail_fast_when_executed_with_dependencies(self) -> None:
        if which("uv") is None:
            self.skipTest("uv is required for dependency-isolated helper direct execution")
        for script_name in HELP_CONTRACT_EXCLUDED_HELPERS:
            script = SCRIPTS / script_name
            with self.subTest(script=script.name):
                result = subprocess.run(
                    helper_direct_exec_command(script),
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn("not a CLI entry", result.stderr)
                self.assertIn("use one of:", result.stderr)


def helper_direct_exec_command(script: Path) -> list[str]:
    uv = which("uv")
    if uv is None:
        raise RuntimeError("uv is required for dependency-isolated helper direct execution")
    return [
        str(uv),
        "run",
        "--with",
        "pandas",
        "--with",
        "numpy",
        "--with",
        "pyarrow",
        "python",
        str(script),
        "--help",
    ]
