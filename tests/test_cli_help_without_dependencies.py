from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"


def load_cli_help_entries() -> list[str]:
    module_path = TESTS / "test_cli_help_contract_classification.py"
    spec = importlib.util.spec_from_file_location("cli_help_contract_classification", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CLI_HELP_ENTRIES


def read_constant(module_path: Path, name: str) -> str:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise AssertionError(f"{name} string constant not found in {module_path}")


CALENDAR_MODEL = read_constant(
    SKILL_ROOT / "scripts/lib/a_share_selection_calendar_contract.py",
    "CALENDAR_MODEL",
)
CLI_HELP_ENTRIES = load_cli_help_entries()
FETCH_CORE_OPTIONS = frozenset(
    {
        "--symbols",
        "--start-date",
        "--end-date",
        "--output",
        "--metadata-output",
        "--fail-on-fetch-error",
    }
)
WALK_FORWARD_MODEL_OPTIONS = frozenset(
    {
        "--required-tradability-model",
        "--required-limit-rules-model",
    }
)
WALK_FORWARD_CAPACITY_OPTIONS = frozenset(
    {
        "--max-open-positions",
        "--max-gross-weight",
        "--max-gross-notional",
        "--max-cash-reserved",
    }
)


class CliHelpWithoutDependenciesTests(unittest.TestCase):
    def test_core_navigation_help_does_not_import_pandas(self) -> None:
        cases = {
            "create_demo_data.py": {"--output", "--days"},
            "run_baostock_walk_forward.py": {"--offline-plan"},
            "probe_baostock_limit_fields.py": set(),
            "validate_ohlcv.py": {"--input", "--config", "--min-history-rows"},
            "fetch_baostock_a_share.py": FETCH_CORE_OPTIONS | {"--drop-invalid-rows"},
            "fetch_akshare_a_share.py": FETCH_CORE_OPTIONS | {"--drop-invalid-rows"},
            "fetch_akshare_hk_daily.py": FETCH_CORE_OPTIONS
            | {
                "--adjust",
                "--drop-invalid-rows",
                "HKEX calendar",
                "tradability",
            },
            "fetch_zzshare_a_share.py": FETCH_CORE_OPTIONS
            | {
                "--http-url",
                "--timeout-seconds",
                "--request-interval-seconds",
                "--fields",
                "--adjust",
                "--limit",
                "--max-pages",
                "--drop-invalid-rows",
            },
            "fetch_eastmoney_a_share_spot.py": {
                "--output",
                "--metadata-output",
                "--pages",
                "--page-size",
                "--retries",
                "--fail-on-partial",
            },
            "fetch_yfinance_ohlcv.py": FETCH_CORE_OPTIONS | {"--market", "--timeout-seconds"},
            "probe_external_source_stability.py": {
                "--output-dir",
                "--summary-output",
                "--iterations",
                "--akshare-symbols",
                "--yfinance-symbols",
                "--baostock-symbols",
                "--zzshare-symbols",
                "long_term_stability_claim=not_proven",
            },
            "run_today_a_share_selection.py": {
                "--prices-input",
                "--output-dir",
                "--mode",
                "--config",
                "--plan-only",
                "--resume-from",
                "--history-source",
                "--symbols",
                "--symbols-file",
                "--start-date",
                "--end-date",
                "--derive-symbols-from-spot",
                "--max-history-symbols",
                "--history-http-url",
                "--history-timeout-seconds",
                "--history-request-interval-seconds",
                "--history-limit",
                "--history-max-pages",
                "--allow-partial-history",
                "--fail-on-empty-result",
                "--fail-on-skipped",
                "--no-html-report",
                "--html-report-language",
            },
            "generate_lightgbm_predictions.py": {
                "--input",
                "--output",
                "--horizon",
                "--train-ratio",
                "--min-history-rows",
                "--summary-output",
                "--fail-on-skipped",
                "--as-of-date",
                "generation_audit_only",
                "skipped_symbols",
            },
            "slice_prices_as_of.py": {"--input", "--output", "--as-of-date"},
            "allocate_candidate_capital.py": {
                "--prices",
                "--candidates",
                "--output",
                "--cash-budget",
                "--lot-size",
                "--fail-on-unallocated",
                "claim_boundary=local_sizing_not_broker_order",
                "sizing_claim_boundary=local_sizing_not_broker_order",
            },
            "allocate_portfolio_candidate_capital.py": {
                "--prices",
                "--raw-candidates",
                "--candidate-outputs",
                "--sized-outputs",
                "--skipped-output",
                "--summary-output",
                "--cash-budget",
                "--hold-days",
                "--max-open-positions",
            },
            "backtest_buy_hold.py": {
                "--prices",
                "--candidates",
                "--output",
                "--hold-days",
                "--cost-bps",
                "--slippage-bps",
                "--require-tradable-bars",
                "--require-tradable-holding-period",
                "--fail-on-incomplete",
                "incomplete output is not a successful backtest",
            },
            "portfolio_equity_curve.py": {
                "--backtests",
                "--output",
                "--initial-equity",
                "--fail-on-incomplete",
                "--min-final-equity",
                "--max-drawdown-floor",
                "final_equity_excludes_incomplete=true",
            },
            "portfolio_overlap_report.py": WALK_FORWARD_CAPACITY_OPTIONS
            | {
                "--backtests",
                "--daily-output",
                "--overlap-output",
                "--summary-output",
                "--fail-on-symbol-overlap",
                "--require-capital-fields",
                CALENDAR_MODEL,
                "pandas.bdate_range",
                "not an exchange trading calendar",
            },
            "prepare_history_retry_symbols.py": {
                "--selected-symbols",
                "--history-metadata",
                "--output",
                "--symbols-output",
                "--include-clean-selected",
                "does not prove full-market completion",
            },
            "summarize_walk_forward_run.py": WALK_FORWARD_MODEL_OPTIONS
            | WALK_FORWARD_CAPACITY_OPTIONS
            | {
                "--run-dir",
                "--output",
                "--signal-dates",
                "--expected-symbol-count",
                "--fail-on-symbol-overlap",
                "--expect-portfolio-violations",
                "--allow-dropped-invalid-rows",
                "known violations only, not a capacity pass",
            },
            "validate_walk_forward_manifest.py": WALK_FORWARD_MODEL_OPTIONS
            | {
                "--manifest",
                "--output",
                "--signal-dates",
                "--expected-symbol-count",
                "--expected-max-candidates",
                "--expect-portfolio-violations",
                "does not validate artifacts",
                "known violations only, not a capacity pass",
            },
            "validate_walk_forward_artifacts.py": WALK_FORWARD_MODEL_OPTIONS
            | {
                "--run-dir",
                "--output",
                "--signal-dates",
                "--expected-symbols",
                "--expected-candidates",
                "--expected-final-equity",
                "--expected-portfolio-violations",
                "--required-allocation-model",
                "--manifest-validation",
                "--allow-dropped-invalid-rows",
                "checked automatically",
                "capacity pass",
                "known violations only, not a capacity pass",
            },
            "score_candidates.py": {
                "--input",
                "--config",
                "--output",
                "--spot-input",
                "--fail-on-skipped",
                "--fail-on-empty-result",
                "external_unverified",
                "does not train or execute LightGBM",
                "CSV only",
                ".parquet/.pq output paths fail",
            },
        }
        self.assertEqual(set(CLI_HELP_ENTRIES), set(cases))
        for script_name, expected_options in cases.items():
            script = SCRIPTS / script_name
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

    def test_external_source_help_discloses_metadata_boundaries(self) -> None:
        cases = {
            "run_today_a_share_selection.py": [
                "metadata still require validation",
                "--fail-on-partial-spot",
                "partial_result=true",
                "--allow-partial-history",
                "metadata must be checked",
                "only used with --history-source zzshare",
                "ZZSHARE_TOKEN",
                "does not prove unlimited free quota",
            ],
            "fetch_eastmoney_a_share_spot.py": [
                "local CSV and metadata",
                "do not prove full-market coverage",
                "partial_result=true",
            ],
            "fetch_baostock_a_share.py": [
                "local CSV and metadata",
                "metadata and gate review",
                "failed, empty, invalid, or non-trading rows",
            ],
            "fetch_akshare_a_share.py": [
                "local CSV and metadata",
                "Fallback providers and partial symbols",
                "failed, empty, invalid, or fallback-affected rows",
            ],
            "fetch_akshare_hk_daily.py": [
                "local CSV and metadata",
                "HKEX calendar",
                "tradability",
                "long-term source stability",
            ],
            "fetch_zzshare_a_share.py": [
                "local CSV and metadata",
                "ZZSHARE_TOKEN environment variable",
                "possibly_truncated_symbols",
                "do not prove unlimited free quota or long-term stability",
            ],
            "fetch_yfinance_ohlcv.py": [
                "local CSV and metadata JSON",
                "output label only",
                "calendar proof",
            ],
            "probe_external_source_stability.py": [
                "akshare, yfinance, baostock, and zzshare",
                "long_term_stability_claim=not_proven",
                "--zzshare-symbols",
            ],
        }
        for script_name, expected_texts in cases.items():
            script = SCRIPTS / script_name
            with self.subTest(script=script.name):
                result = subprocess.run(
                    [sys.executable, "-S", str(script), "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                normalized_stdout = " ".join(result.stdout.split())
                for expected in expected_texts:
                    self.assertIn(expected, normalized_stdout)

    def test_cli_help_discloses_runner_and_sizing_boundaries(self) -> None:
        cases = {
            "run_today_a_share_selection.py": [
                "Standard outputs are run_manifest.json, summary.json, report.html, candidates.csv, diagnostics.csv",
                "strict all-Parquet output is not supported by this CLI",
                "runner outputs still include CSV artifacts",
            ],
            "allocate_candidate_capital.py": [
                "not broker orders or real fills",
                "--lot-size",
            ],
            "backtest_buy_hold.py": [
                "close-to-close buy-hold backtest",
                "local baseline",
                "not a promise of future returns or real tradability",
            ],
            "portfolio_equity_curve.py": [
                "Defaults to complete trades only",
                "--fail-on-incomplete",
            ],
            "run_baostock_walk_forward.py": [
                "--offline-plan",
                "without executing fetch, prediction",
                "backtest, equity, or summary commands",
                "planned manifests cannot validate as executed runs",
            ],
            "score_candidates.py": [
                "prediction-derived config consumes existing prediction",
                "external_unverified",
                "does not train or execute LightGBM",
                "strict empty results return non-zero",
                "--output and --diagnostics-output accept CSV output paths only",
            ],
            "generate_lightgbm_predictions.py": [
                "generation_audit_only",
                "skipped_symbols",
                "scoring success does not prove skipped symbols or model quality",
            ],
        }
        for script_name, expected_texts in cases.items():
            script = SCRIPTS / script_name
            with self.subTest(script=script.name):
                result = subprocess.run(
                    [sys.executable, "-S", str(script), "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                normalized_stdout = " ".join(result.stdout.split())
                for expected in expected_texts:
                    self.assertIn(expected, normalized_stdout)

    def test_runtime_paths_still_fail_without_dataframe_dependencies(self) -> None:
        validate_script = SKILL_ROOT / "scripts/validate_ohlcv.py"
        score_script = SKILL_ROOT / "scripts/score_candidates.py"
        fetch_baostock_script = SKILL_ROOT / "scripts/fetch_baostock_a_share.py"
        fetch_akshare_script = SKILL_ROOT / "scripts/fetch_akshare_a_share.py"
        fetch_zzshare_script = SKILL_ROOT / "scripts/fetch_zzshare_a_share.py"
        fetch_yfinance_script = SKILL_ROOT / "scripts/fetch_yfinance_ohlcv.py"
        lightgbm_script = SKILL_ROOT / "scripts/generate_lightgbm_predictions.py"
        slice_script = SKILL_ROOT / "scripts/slice_prices_as_of.py"
        allocate_script = SKILL_ROOT / "scripts/allocate_candidate_capital.py"
        portfolio_allocate_script = SKILL_ROOT / "scripts/allocate_portfolio_candidate_capital.py"
        backtest_script = SKILL_ROOT / "scripts/backtest_buy_hold.py"
        equity_curve_script = SKILL_ROOT / "scripts/portfolio_equity_curve.py"
        overlap_report_script = SKILL_ROOT / "scripts/portfolio_overlap_report.py"
        run_summary_script = SKILL_ROOT / "scripts/summarize_walk_forward_run.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "candidates.csv"
            baostock_output = Path(tmpdir) / "baostock.csv"
            baostock_metadata = Path(tmpdir) / "baostock-metadata.json"
            akshare_output = Path(tmpdir) / "akshare.csv"
            akshare_metadata = Path(tmpdir) / "akshare-metadata.json"
            zzshare_output = Path(tmpdir) / "zzshare.csv"
            zzshare_metadata = Path(tmpdir) / "zzshare-metadata.json"
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
                    str(SKILL_ROOT / "scripts/example_config.json"),
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
                    str(fetch_zzshare_script),
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2026-05-20",
                    "--end-date",
                    "2026-05-20",
                    "--output",
                    str(zzshare_output),
                    "--metadata-output",
                    str(zzshare_metadata),
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
            self.assertFalse(zzshare_output.exists())
            self.assertFalse(zzshare_metadata.exists())
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
