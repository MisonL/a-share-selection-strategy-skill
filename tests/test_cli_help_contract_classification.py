from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import json
import subprocess
import sys
import unittest
from pathlib import Path
from shutil import which


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import a_share_selection_cli_guard as cli_guard  # noqa: E402

CLI_HELP_ENTRIES = [
    "allocate_candidate_capital.py",
    "allocate_portfolio_candidate_capital.py",
    "backtest_buy_hold.py",
    "create_demo_data.py",
    "execute_incremental_history_plan.py",
    "fetch_akshare_a_share.py",
    "fetch_akshare_hk_daily.py",
    "fetch_baostock_a_share.py",
    "fetch_baostock_a_share_universe.py",
    "fetch_eastmoney_a_share_spot.py",
    "fetch_pytdx_a_share.py",
    "fetch_yfinance_ohlcv.py",
    "fetch_zzshare_a_share.py",
    "generate_lightgbm_predictions.py",
    "portfolio_equity_curve.py",
    "portfolio_overlap_report.py",
    "prepare_clean_history_pool.py",
    "prepare_history_retry_symbols.py",
    "prepare_incremental_history_plan.py",
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
    "a_share_selection_calendar_contract.py",
    "a_share_selection_cli_guard.py",
    "a_share_selection_config.py",
    "a_share_selection_paths.py",
]
HELPER_ARGPARSE_MODULES: set[str] = set()


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
            cli_guard.fail_not_cli("helper_module.py")

        self.assertEqual(2, raised.exception.code)
        self.assertIn("helper_module.py is not a CLI entry", stderr.getvalue())
        self.assertIn("use one of:", stderr.getvalue())

    def test_cli_guard_lists_registered_public_entries(self) -> None:
        registry = json.loads(
            (SKILL_ROOT / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )
        expected = tuple(
            sorted(
                script
                for script, metadata in registry["entries"].items()
                if metadata["public_entry"]
            )
        )

        self.assertEqual(expected, cli_guard.cli_entries())

    def test_helper_modules_fail_fast_when_executed_with_dependencies(self) -> None:
        if which("uv") is None:
            self.skipTest(
                "uv is required for dependency-isolated helper direct execution"
            )
        helper_scripts = [SCRIPTS / name for name in HELP_CONTRACT_EXCLUDED_HELPERS]
        helper_scripts.extend(lib_helper_scripts_with_main_guard())
        for script in helper_scripts:
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

    def test_lib_helper_modules_fail_fast_before_runtime_imports(self) -> None:
        for script in lib_helper_scripts_with_main_guard():
            with self.subTest(script=script.relative_to(SCRIPTS).as_posix()):
                result = subprocess.run(
                    [sys.executable, "-S", str(script), "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn("not a CLI entry", result.stderr)
                self.assertIn("use one of:", result.stderr)


def lib_helper_scripts_with_main_guard() -> list[Path]:
    lib_dir = SCRIPTS / "lib"
    scripts = []
    for path in sorted(lib_dir.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        if 'if __name__ == "__main__":' in source:
            scripts.append(path)
    return scripts


def helper_direct_exec_command(script: Path) -> list[str]:
    uv = which("uv")
    if uv is None:
        raise RuntimeError(
            "uv is required for dependency-isolated helper direct execution"
        )
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
