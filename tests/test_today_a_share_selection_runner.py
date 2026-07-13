from __future__ import annotations

import csv
import importlib.util
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import run_today_a_share_selection as runner  # noqa: E402
from lib.runner.run_today_a_share_selection_helpers import (  # noqa: E402
    summary_view,
    spot_rows,
    tabular_row_count,
)
from lib.runner.run_today_a_share_selection_history import (  # noqa: E402
    parse_history_symbols,
    read_symbols_file,
)
from lib.runner.run_today_a_share_selection_input_metadata import (  # noqa: E402
    history_metadata_for_output,
)
from lib.runner.run_today_a_share_selection_summary import (  # noqa: E402
    executed_step_duration,
    history_metadata_summary_fields,
)
from lib.runner.run_today_a_share_selection_outputs import clear_stale_run_outputs  # noqa: E402
from lib.runner.run_today_a_share_selection_prices_sidecar import (  # noqa: E402
    build_sidecar,
    write_sidecar,
)
from lib.runner.run_today_a_share_selection_prices_filter import (  # noqa: E402
    normalized_price_data,
    removed_price_symbols,
)
from helpers import build_frame, load_config  # noqa: E402

HAS_PARQUET_ENGINE = any(
    importlib.util.find_spec(name) for name in ("pyarrow", "fastparquet")
)


class TodayAShareSelectionRunnerTests(unittest.TestCase):
    def test_removed_price_symbols_deduplicate_normalized_aliases(self) -> None:
        price_keys, symbols_by_key = normalized_price_data(
            pd.Series(["000001", "sz.000001", "600000", "600000"])
        )

        removed = removed_price_symbols(symbols_by_key, set())

        self.assertEqual(
            ["000001", "000001", "600000", "600000"],
            price_keys,
        )
        self.assertEqual(["000001", "600000"], removed)

    def test_executed_step_duration_ignores_planned_steps(self) -> None:
        manifest = {
            "steps": [
                {
                    "step": "fetch_history",
                    "returncode": None,
                    "planned": True,
                    "duration_seconds": 99,
                },
                {
                    "step": "fetch_history",
                    "returncode": 0,
                    "duration_seconds": 2.5,
                },
            ]
        }

        self.assertEqual(2.5, executed_step_duration(manifest, "fetch_history"))

    def test_history_performance_metadata_reaches_summary_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            (output / "history_metadata.json").write_text(
                json.dumps(
                    {
                        "source": "pytdx",
                        "rows": 2,
                        "raw_rows": 16,
                        "output_rows": 2,
                        "requested_raw_rows": 16,
                        "api_request_count": 1,
                        "overfetch_rows": 14,
                        "raw_to_output_ratio": 8.0,
                        "duration_seconds": 7.5,
                        "rate_limit_429_events": 2,
                        "rate_limit_sleep_seconds": 4.5,
                        "network_retry_events": 1,
                        "network_retry_sleep_seconds": 2.0,
                    }
                ),
                encoding="utf-8",
            )
            metadata = history_metadata_for_output(output)

        projected = history_metadata_summary_fields(metadata)

        self.assertEqual(16, metadata["history_raw_rows"])
        self.assertEqual(14, projected["history_overfetch_rows"])
        self.assertEqual(8.0, projected["history_raw_to_output_ratio"])
        self.assertEqual(7.5, projected["history_duration_seconds"])
        self.assertEqual(2, projected["history_rate_limit_429_events"])
        self.assertEqual(2.0, projected["history_network_retry_sleep_seconds"])

    def test_unprocessed_history_metadata_reaches_runner_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "000001,600000",
                    "--start-date",
                    "2026-07-09",
                    "--end-date",
                    "2026-07-10",
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            manifest["run_outputs_initialized"] = True
            manifest["history_symbols"] = ["000001", "600000"]
            (output / "selected_symbols.json").write_text(
                json.dumps(
                    {
                        "source": "explicit_symbols",
                        "selected_symbols": ["000001", "600000"],
                        "selected_symbol_count": 2,
                    }
                ),
                encoding="utf-8",
            )
            (output / "history_metadata.json").write_text(
                json.dumps(
                    {
                        "source": "zzshare",
                        "requested_symbols": ["000001", "600000"],
                        "rows": 1,
                        "symbol_count": 1,
                        "failed_symbols": [],
                        "empty_symbols": [],
                        "possibly_truncated_symbols": [],
                        "unprocessed_symbols": ["600000"],
                        "partial_result": False,
                        "rate_limit_budget_exhausted": True,
                        "rate_limit_exhaustion_reason": "max_runtime_seconds_exceeded",
                        "output_written": False,
                        "metadata_output_written": True,
                    }
                ),
                encoding="utf-8",
            )
            manifest["input_metadata"] = history_metadata_for_output(output)

            summary = summary_view(manifest, "failed")
            stdout = StringIO()
            with redirect_stdout(stdout):
                runner.helpers.print_summary(manifest, output)

        history = summary["history_selection"]
        metadata = summary["input_metadata"]
        self.assertTrue(summary["history_partial_result"])
        self.assertEqual(1, summary["history_unprocessed_symbol_count"])
        self.assertTrue(summary["history_rate_limit_budget_exhausted"])
        self.assertEqual(
            "max_runtime_seconds_exceeded",
            summary["history_rate_limit_exhaustion_reason"],
        )
        self.assertEqual(["600000"], history["history_unprocessed_symbols"])
        self.assertEqual(1, metadata["history_unprocessed_symbol_count"])
        self.assertIn("history_unprocessed_symbol_count=1", stdout.getvalue())
        self.assertIn("history_unprocessed_symbols=600000", stdout.getvalue())
        self.assertIn(
            "history_rate_limit_exhaustion_reason=max_runtime_seconds_exceeded",
            stdout.getvalue(),
        )

    def test_baostock_history_command_reuses_fetched_universe_names(self) -> None:
        args = runner.build_parser().parse_args(
            [
                "--output-dir",
                "/tmp/baostock-run",
                "--history-source",
                "baostock",
                "--fetch-spot",
                "baostock_universe",
                "--symbols",
                "000001",
                "--start-date",
                "2026-07-10",
                "--end-date",
                "2026-07-10",
            ]
        )

        command = runner.fetch_history_command(
            args, Path(args.output_dir) / "prices.csv", ["000001"]
        )

        self.assertEqual(
            "/tmp/baostock-run/spot.csv",
            command[command.index("--names-input") + 1],
        )
        self.assertEqual(
            "query", command[command.index("--missing-name-policy") + 1]
        )
        self.assertEqual(
            "reject", command[command.index("--non-trading-policy") + 1]
        )

    def test_baostock_history_command_reuses_fallback_universe_names(self) -> None:
        args = runner.build_parser().parse_args(
            [
                "--output-dir",
                "/tmp/baostock-fallback-run",
                "--history-source",
                "baostock",
                "--fetch-spot",
                "eastmoney",
                "--fetch-spot-fallback",
                "baostock_universe",
                "--symbols",
                "000001",
                "--start-date",
                "2026-07-10",
                "--end-date",
                "2026-07-10",
            ]
        )

        command = runner.fetch_history_command(
            args, Path(args.output_dir) / "prices.csv", ["000001"]
        )

        self.assertEqual(
            "/tmp/baostock-fallback-run/spot.csv",
            command[command.index("--names-input") + 1],
        )

    def test_generic_runner_writes_manifest_summary_and_outputs(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertEqual(0, code, stderr)
        self.assertIn("runner=run_today_a_share_selection", stdout)
        self.assertIn("execution_path=local_prices_generic", stdout)
        self.assertIn("execution_path_reason=prices_input_provided", stdout)
        self.assertIn("coverage_class=local_input", stdout)
        self.assertIn("full_market_claim_allowed=false", stdout)
        self.assertIn(
            "full_market_claim_boundary=local_prices_input_not_full_market_scan",
            stdout,
        )
        self.assertIn("candidate_rows=2", stdout)
        self.assertIn("diagnostic_rows=2", stdout)
        self.assertIn("html_report=", stdout)
        self.assertGreaterEqual(summary["html_report_duration_seconds"], 0.0)
        self.assertGreaterEqual(summary["finalize_duration_seconds"], 0.0)
        self.assertGreater(summary["run_duration_seconds"], 0.0)
        self.assertEqual(summary["run_duration_seconds"], manifest["run_duration_seconds"])
        self.assertIn("external_prediction_consumed=false", stdout)
        self.assertIn("prediction_model_executed=false", stdout)
        self.assertIn("lightgbm_not_used=true", stdout)
        self.assertIn("lightgbm_output_source=not_used", stdout)
        self.assertIn("lightgbm_executed_by_runner=false", stdout)
        self.assertEqual(
            ["validate", "score"], [step["step"] for step in manifest["steps"]]
        )
        self.assertEqual("auto", manifest["requested_mode"])
        self.assertEqual("local_prices_generic", manifest["execution_path"])
        self.assertEqual("prices_input_provided", manifest["execution_path_reason"])
        self.assertEqual("local_input", manifest["coverage_class"])
        self.assertFalse(manifest["full_market_claim_allowed"])
        self.assertEqual(
            "local_prices_input_not_full_market_scan",
            manifest["full_market_claim_boundary"],
        )
        self.assertEqual("generic", manifest["mode"])
        self.assertEqual("auto_generic", manifest["mode_decision"])
        self.assertTrue(manifest["html_report_enabled"])
        self.assertEqual("auto", manifest["html_report_language"])
        self.assertIn(manifest["html_report_initial_language"], {"zh", "en"})
        self.assertTrue(manifest["summary_output_written"])
        self.assertTrue(manifest["manifest_output_written"])
        self.assertTrue(summary["summary_output_written"])
        self.assertTrue(summary["manifest_output_written"])
        self.assertIn(
            "missing_prediction_columns:prediction", manifest["mode_decision_reason"]
        )
        self.assertEqual(["prediction"], manifest["missing_prediction_column_groups"])
        self.assertEqual(
            "prediction_or_prediction_score",
            manifest["missing_prediction_requirement"],
        )
        self.assertTrue(manifest["lightgbm_not_used"])
        self.assertFalse(manifest["lightgbm_executed_by_runner"])
        self.assertFalse(manifest["consumes_prediction_columns"])
        self.assertEqual("not_used", manifest["prediction_input_source"])
        self.assertFalse(manifest["prediction_model_executed_by_runner"])
        self.assertEqual("not_used", manifest["lightgbm_output_source"])
        self.assertEqual("completed", summary["status"])
        self.assertEqual("local_prices_generic", summary["execution_path"])
        self.assertEqual("prices_input_provided", summary["execution_path_reason"])
        self.assertEqual("local_input", summary["coverage_class"])
        self.assertFalse(summary["full_market_claim_allowed"])
        self.assertEqual(
            "local_prices_input_not_full_market_scan",
            summary["full_market_claim_boundary"],
        )
        self.assertEqual("auto", summary["requested_mode"])
        self.assertEqual("generic", summary["mode"])
        self.assertEqual("auto_generic", summary["mode_decision"])
        self.assertIn(
            "missing_prediction_columns:prediction", summary["mode_decision_reason"]
        )
        self.assertEqual(["prediction"], summary["missing_prediction_column_groups"])
        self.assertEqual(
            "prediction_or_prediction_score",
            summary["missing_prediction_requirement"],
        )
        self.assertFalse(summary["lightgbm_executed_by_runner"])
        self.assertFalse(summary["consumes_prediction_columns"])
        self.assertEqual("not_used", summary["prediction_input_source"])
        self.assertFalse(summary["prediction_model_executed_by_runner"])
        self.assertEqual("not_used", summary["lightgbm_output_source"])
        self.assertIn("prediction_input_source=not_used", summary["boundary"])
        self.assertEqual([], summary["failed_steps"])
        self.assertEqual(0, summary["spot_rows"])
        self.assertEqual(2, summary["score"]["raw_symbols"])
        self.assertEqual(2, summary["score"]["candidates"])
        self.assertFalse(summary["score"]["effective_empty_result"])
        self.assertEqual(
            "not_investment_advice_not_trade_instruction_not_real_fill_not_return_proof",
            summary["advice_boundary"],
        )
        self.assertEqual(len(frame), summary["prices_rows"])
        self.assertEqual(2, summary["candidate_rows"])
        self.assertEqual(2, summary["diagnostic_rows"])
        self.assertTrue(summary["prices_output"].endswith("prices.csv"))
        self.assertTrue(summary["prices_output_written"])
        self.assertTrue(summary["candidates_output"].endswith("candidates.csv"))
        self.assertTrue(summary["candidates_output_written"])
        self.assertTrue(summary["diagnostics_output"].endswith("diagnostics.csv"))
        self.assertTrue(summary["diagnostics_output_written"])
        self.assertTrue(summary["html_report"].endswith("report.html"))
        self.assertTrue(summary["html_report_written"])
        self.assertEqual("auto", summary["html_report_language"])
        self.assertEqual(
            manifest["html_report_initial_language"],
            summary["html_report_initial_language"],
        )
        self.assertIn("A-share Strategy Selection Report", report)
        self.assertIn("Pipeline counts", report)
        self.assertIn("Watchlist Top 5 Preview", report)
        self.assertIn("Use boundary / risk reminder", report)
        self.assertIn("Complete Candidate Table", report)
        self.assertIn("Report Appendix", report)
        self.assertIn(
            "not_investment_advice_not_trade_instruction_not_real_fill_not_return_proof",
            report,
        )
        self.assertIn('data-lang-mode="auto"', report)
        self.assertTrue(
            all(
                row["advice_boundary"] == summary["advice_boundary"]
                for row in candidate_rows
            )
        )
        self.assertTrue(
            all(
                row["execution_path"] == "local_prices_generic"
                for row in candidate_rows
            )
        )
        self.assertTrue(
            all(row["coverage_class"] == "local_input" for row in candidate_rows)
        )
        self.assertTrue(
            all(row["full_market_claim_allowed"] == "False" for row in candidate_rows)
        )
        self.assertTrue(
            all(
                row["full_market_claim_boundary"]
                == "local_prices_input_not_full_market_scan"
                for row in candidate_rows
            )
        )
        self.assertTrue(
            all(
                row["advice_boundary"] == summary["advice_boundary"]
                for row in diagnostic_rows
            )
        )
        self.assertTrue(
            all(
                row["execution_path_reason"] == "prices_input_provided"
                for row in diagnostic_rows
            )
        )
        self.assertTrue(
            all(
                row["recommendation_boundary"]
                == "ranking_signal_not_buy_sell_instruction"
                for row in candidate_rows
            )
        )

    def test_prediction_runner_fails_without_prediction_and_keeps_manifest(
        self,
    ) -> None:
        frame = build_frame(
            include_turn=True,
            include_prediction=False,
            include_tradability=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "prediction",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")

        self.assertEqual(3, code)
        self.assertIn("step=validate", stderr)
        self.assertIn("prediction-derived profile requires prediction", stderr)
        self.assertEqual(["validate"], [step["step"] for step in manifest["steps"]])
        self.assertEqual(["validate"], summary["failed_steps"])
        self.assertEqual("validate", summary["failed_step_details"][0]["step"])
        self.assertEqual(1, summary["failed_step_details"][0]["returncode"])
        self.assertIn(
            "prediction-derived profile requires prediction",
            summary["failed_step_details"][0]["stderr_first_line"],
        )
        self.assertEqual("failed", summary["status"])
        self.assertTrue(manifest["prediction_mode"])
        self.assertFalse(manifest["consumes_prediction_columns"])
        self.assertEqual("not_used", manifest["prediction_input_source"])
        self.assertEqual(
            "external_input", manifest["requested_prediction_input_source"]
        )
        self.assertEqual("not_used", manifest["lightgbm_output_source"])
        self.assertEqual("external_input", manifest["requested_lightgbm_output_source"])
        self.assertFalse(summary["consumes_prediction_columns"])
        self.assertEqual("not_used", summary["prediction_input_source"])
        self.assertEqual("external_input", summary["requested_prediction_input_source"])
        self.assertEqual(["prediction"], manifest["missing_prediction_column_groups"])
        self.assertEqual(
            "prediction_or_prediction_score",
            manifest["missing_prediction_requirement"],
        )
        self.assertEqual(["prediction"], summary["missing_prediction_column_groups"])
        self.assertEqual(
            "prediction_or_prediction_score",
            summary["missing_prediction_requirement"],
        )
        self.assertEqual("missing_prediction_columns", summary["selection_failed_reason"])
        self.assertEqual(
            "provide_prediction_or_prediction_score_or_use_generic_mode",
            summary["selection_failed_next_action"],
        )
        self.assertEqual(
            summary["selection_failed_reason"],
            manifest["selection_failed_reason"],
        )
        self.assertEqual(
            summary["selection_failed_next_action"],
            manifest["selection_failed_next_action"],
        )
        self.assertFalse(summary["candidates_output_written"])
        self.assertFalse(summary["diagnostics_output_written"])
        self.assertFalse(manifest["candidates_output_written"])
        self.assertFalse(manifest["diagnostics_output_written"])
        self.assertTrue(summary["summary_output_written"])
        self.assertTrue(summary["manifest_output_written"])
        self.assertTrue(manifest["summary_output_written"])
        self.assertTrue(manifest["manifest_output_written"])
        self.assertEqual(str(output / "summary.json"), summary["summary_output"])
        self.assertEqual(str(output / "run_manifest.json"), summary["manifest_output"])
        self.assertEqual(str(output / "summary.json"), manifest["summary_output"])
        self.assertEqual(str(output / "run_manifest.json"), manifest["manifest_output"])
        self.assertTrue(summary["html_report_written"])
        self.assertIn("did not produce a usable watchlist", report)
        self.assertIn("This failed run has no usable watchlist", report)
        self.assertIn("prediction-derived profile requires prediction", report)
        self.assertIn("Missing required prediction columns", report)
        self.assertIn("validation failed before scoring", report)
        self.assertNotIn("Read from input columns", report)
        self.assertNotIn("ranked candidates from prediction columns", report)

    def test_generic_validate_failure_report_does_not_claim_completed_scoring(
        self,
    ) -> None:
        frame = build_frame(include_turn=False, include_tradability=True)
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
                    "--mode",
                    "generic",
                ]
            )

            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")

        self.assertEqual(3, code)
        self.assertIn("step=validate", stderr)
        self.assertEqual("failed", summary["status"])
        self.assertEqual(["validate"], summary["failed_steps"])
        self.assertEqual("validate", summary["failed_step_details"][0]["step"])
        self.assertEqual(1, summary["failed_step_details"][0]["returncode"])
        self.assertIn(
            "configured min_turn threshold requires turn or turnover column",
            summary["failed_step_details"][0]["stderr_first_line"],
        )
        self.assertTrue(summary["html_report_written"])
        self.assertIn("Generic scoring not completed", report)
        self.assertIn("validation or scoring did not complete", report)
        self.assertNotIn("Generic technical scoring", report)
        self.assertNotIn("filtered local A-share price data", report)
        self.assertNotIn("ranked the rows that passed", report)

    def test_history_validate_failure_writes_short_history_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"
            code, _stdout, stderr = call_runner_with_executor(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "000001,001220",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-request-interval-seconds",
                    "0",
                    "--no-html-report",
                ],
                short_history_validate_failure_executor,
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            short_txt = output / "short_history_symbols.txt"
            short_json = output / "short_history_symbols.json"
            short_text = short_txt.read_text(encoding="utf-8")
            short_data = json.loads(short_json.read_text(encoding="utf-8"))

        self.assertEqual(3, code)
        self.assertIn("step=validate", stderr)
        self.assertEqual("001220\n", short_text)
        self.assertEqual(1, short_data["short_history_symbol_count"])
        self.assertEqual("001220", short_data["symbols"][0]["symbol"])
        self.assertEqual(33, short_data["symbols"][0]["rows"])
        self.assertEqual(1, summary["short_history_symbol_count"])
        self.assertEqual(str(short_txt), summary["short_history_symbols_output"])
        self.assertEqual(1, manifest["short_history_symbol_count"])

    def test_local_prices_validate_failure_infers_short_history_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            prices.write_text(
                "symbol,date,open,high,low,close,volume\n"
                "000001,2026-01-01,1,1,1,1,1\n"
                "000001,2026-01-02,1,1,1,1,1\n"
                "600000,2026-01-01,1,1,1,1,1\n"
                "600000,2026-01-02,1,1,1,1,1\n"
                "600000,2026-01-03,1,1,1,1,1\n",
                encoding="utf-8",
            )
            output = root / "run"
            manifest = {"output_dir": str(output)}
            args = SimpleNamespace(
                min_history_rows=3,
                prices_input=str(prices),
            )

            runner.write_short_history_artifacts(manifest, args)

            short_data = json.loads(
                (output / "short_history_symbols.json").read_text(encoding="utf-8")
            )
            self.assertEqual(1, short_data["short_history_symbol_count"])
            self.assertEqual("000001", short_data["symbols"][0]["symbol"])
            self.assertEqual(2, short_data["symbols"][0]["rows"])

    def test_short_history_symbols_handles_empty_and_boundary_rows(self) -> None:
        metadata = {
            "symbols": [
                {"symbol": "000001", "rows": 120, "date_min": "2025-01-01"},
                {"symbol": "001220", "rows": 119, "date_max": "2026-01-01"},
                {"symbol": "600000", "rows": 0},
                {"symbol": "", "rows": 1},
                "ignored",
            ]
        }

        symbols = runner.short_history_symbols(metadata, 120)

        self.assertEqual(["001220", "600000"], [item["symbol"] for item in symbols])
        self.assertEqual(119, symbols[0]["rows"])
        self.assertEqual(120, symbols[0]["min_history_rows"])
        self.assertEqual("2026-01-01", symbols[0]["date_max"])

    def test_failed_reused_output_dir_does_not_show_stale_candidates(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, _stdout, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(output)]
            )
            self.assertEqual(0, code, stderr)
            old_candidates = output / "candidates.csv"
            old_diagnostics = output / "diagnostics.csv"
            self.assertTrue(old_candidates.exists())
            self.assertTrue(old_diagnostics.exists())
            self.assertIn("Zero Prefix", old_candidates.read_text(encoding="utf-8"))

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "prediction",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")
            candidates_exists = (output / "candidates.csv").exists()
            diagnostics_exists = (output / "diagnostics.csv").exists()

            self.assertEqual(3, code)
            self.assertIn("step=validate", stderr)
            self.assertFalse(candidates_exists)
            self.assertFalse(diagnostics_exists)
            self.assertFalse(summary["candidates_output_written"])
            self.assertFalse(summary["diagnostics_output_written"])
            self.assertEqual(0, summary["candidate_rows"])
            self.assertEqual(0, summary["diagnostic_rows"])
            self.assertIn("No rows written for this run.", report)
            self.assertNotIn("Zero Prefix", report)
            self.assertNotIn("Shanghai", report)

    def test_pre_mode_failure_clears_reused_output_files(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, _stdout, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(output)]
            )
            self.assertEqual(0, code, stderr)
            for name in ["prices.csv", "candidates.csv", "diagnostics.csv"]:
                self.assertTrue((output / name).exists())

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "prediction",
                    "--config",
                    str(SCRIPTS / "ultra_short_low_price_config.json"),
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

            self.assertEqual(2, code)
            self.assertIn("explicit mode conflicts with config score_mode", stderr)
            self.assertFalse((output / "prices.csv").exists())
            self.assertFalse((output / "candidates.csv").exists())
            self.assertFalse((output / "diagnostics.csv").exists())
            self.assertFalse(summary["prices_output_written"])
            self.assertFalse(summary["candidates_output_written"])
            self.assertFalse(summary["diagnostics_output_written"])

    def test_cleanup_failure_directory_is_not_reported_as_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"
            output.mkdir()
            (output / "selected_symbols.json").write_text(
                json.dumps(
                    {
                        "source": "stale_previous_run",
                        "selected_symbols": ["600000"],
                    }
                ),
                encoding="utf-8",
            )
            (output / "history_metadata.json").write_text(
                json.dumps(
                    {
                        "empty_symbols": ["600000"],
                        "output_written": True,
                        "metadata_output_written": True,
                    }
                ),
                encoding="utf-8",
            )
            (output / "candidates.csv").mkdir()

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-limit",
                    "0",
                    "--no-html-report",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(2, code)
        self.assertIn("stale run output path is a directory", stderr)
        self.assertEqual("IsADirectoryError", manifest["run_error_type"])
        self.assertEqual("IsADirectoryError", manifest["stale_cleanup_error_type"])
        self.assertFalse(manifest.get("run_outputs_initialized", False))
        self.assertFalse(summary["candidates_output_written"])
        self.assertEqual(0, summary["candidate_rows"])
        self.assertEqual({}, summary["history_selection"])
        self.assertEqual(0, summary["history_symbol_count"])
        self.assertNotIn("stale_previous_run", json.dumps(summary))
        self.assertNotIn("600000", json.dumps(summary["history_selection"]))
        self.assertTrue(summary["summary_output_written"])
        self.assertTrue(summary["manifest_output_written"])

    def test_auto_runner_uses_prediction_when_prediction_columns_exist(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")

        self.assertEqual(0, code, stderr)
        self.assertIn("prediction_input_source=external_input", stdout)
        self.assertIn(
            "prediction_claim_boundary="
            "external_input_columns_consumed_runner_does_not_execute_prediction_model",
            stdout,
        )
        self.assertIn("lightgbm_not_used=false", stdout)
        self.assertIn("external_prediction_consumed=true", stdout)
        self.assertIn("prediction_model_executed=false", stdout)
        self.assertIn("lightgbm_output_source=external_input", stdout)
        self.assertIn("lightgbm_executed_by_runner=false", stdout)
        self.assertEqual("prediction", manifest["mode"])
        self.assertEqual("auto_prediction", manifest["mode_decision"])
        self.assertFalse(manifest["lightgbm_not_used"])
        self.assertFalse(manifest["lightgbm_executed_by_runner"])
        self.assertTrue(manifest["consumes_prediction_columns"])
        self.assertEqual("external_input", manifest["prediction_input_source"])
        self.assertEqual(
            "external_input", manifest["requested_prediction_input_source"]
        )
        self.assertFalse(manifest["prediction_model_executed_by_runner"])
        self.assertEqual("external_input", manifest["lightgbm_output_source"])
        self.assertEqual("external_input", manifest["requested_lightgbm_output_source"])
        self.assertEqual(
            "external_input_columns_consumed_runner_does_not_execute_prediction_model",
            summary["prediction_claim_boundary"],
        )
        self.assertEqual(summary["source_provenance"], manifest["source_provenance"])
        self.assertIn("prediction_claim_boundary", report)
        self.assertIn(
            "external_input_columns_consumed_runner_does_not_execute_prediction_model",
            report,
        )

    def test_no_html_report_removes_stale_report_in_reused_output_dir(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, _stdout, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(output)]
            )
            self.assertEqual(0, code, stderr)
            self.assertTrue((output / "report.html").exists())

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--no-html-report",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

            self.assertEqual(0, code, stderr)
            self.assertIn("html_report=disabled", stdout)
            self.assertNotIn(f"html_report={output / 'report.html'}", stdout)
            self.assertFalse((output / "report.html").exists())
            self.assertFalse(summary["html_report_written"])

            stale_report = output / "report.html"
            stale_report.write_text("stale report", encoding="utf-8")
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
                    "--no-html-report",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

            self.assertEqual(2, code, stderr)
            self.assertIn("history fetch options would be ignored", stderr)
            self.assertFalse(stale_report.exists())
            self.assertFalse(summary["html_report_written"])

    def test_html_report_write_failure_does_not_block_success_summary(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            output.mkdir()
            (output / "report.html").mkdir()

            code, stdout, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(output)]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(0, code, stderr)
        self.assertIn("html_report=unavailable", stdout)
        self.assertIn("html_report_error_type=IsADirectoryError", stdout)
        self.assertEqual("completed", summary["status"])
        self.assertFalse(summary["html_report_written"])
        self.assertEqual("IsADirectoryError", summary["html_report_error_type"])
        self.assertIn("report.html", summary["html_report_error"])
        self.assertFalse(manifest["html_report_written"])
        self.assertEqual("IsADirectoryError", manifest["html_report_error_type"])

    def test_html_report_replaces_stale_symlink_without_corrupting_csv(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            report = output / "report.html"
            candidates = output / "candidates.csv"
            frame.to_csv(prices, index=False)

            code, _stdout, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(output)]
            )
            self.assertEqual(0, code, stderr)
            report.unlink()
            report.symlink_to(candidates)

            code, _stdout, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(output)]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            candidates_text = candidates.read_text(encoding="utf-8")
            report_text = report.read_text(encoding="utf-8")

        self.assertEqual(0, code, stderr)
        self.assertTrue(summary["html_report_written"])
        self.assertFalse(report.is_symlink())
        self.assertEqual(2, summary["candidate_rows"])
        self.assertIn("Zero Prefix", candidates_text)
        self.assertNotIn("<!doctype html>", candidates_text)
        self.assertIn("<!doctype html>", report_text)

    def test_html_report_write_failure_does_not_block_failed_summary(self) -> None:
        frame = build_frame(
            include_turn=True,
            include_prediction=False,
            include_tradability=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            output.mkdir()
            (output / "report.html").mkdir()

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "prediction",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(3, code)
        self.assertIn("step=validate", stderr)
        self.assertEqual("failed", summary["status"])
        self.assertEqual(["validate"], summary["failed_steps"])
        self.assertFalse(summary["html_report_written"])
        self.assertEqual("IsADirectoryError", summary["html_report_error_type"])
        self.assertFalse(manifest["html_report_written"])
        self.assertEqual("IsADirectoryError", manifest["html_report_error_type"])

    def test_explicit_mode_rejects_conflicting_config(self) -> None:
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
                    "--mode",
                    "prediction",
                    "--config",
                    str(SCRIPTS / "ultra_short_low_price_config.json"),
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("explicit mode conflicts with config score_mode", stderr)

    def test_prices_input_rejects_ignored_history_options(self) -> None:
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

    def test_prices_input_rejects_zero_valued_ignored_history_options(self) -> None:
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
                    "--history-request-interval-seconds",
                    "0",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("history fetch options would be ignored", stderr)
        self.assertIn("--history-request-interval-seconds", stderr)

    def test_prices_input_rejects_invalid_ignored_history_limit_by_scope(self) -> None:
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
                    "--history-limit",
                    "abc",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("history fetch options would be ignored", stderr)
        self.assertIn("--history-limit", stderr)
        self.assertNotIn("history-limit must be an integer", stderr)

    def test_runner_accepts_zzshare_history_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-http-url",
                    "https://example.test",
                    "--history-timeout-seconds",
                    "8",
                    "--history-request-interval-seconds",
                    "0",
                    "--history-max-concurrent-symbol-requests",
                    "7",
                    "--history-max-rate-limit-sleep-seconds",
                    "45",
                    "--history-max-429-events",
                    "6",
                    "--history-max-runtime-seconds",
                    "1800",
                    "--history-limit",
                    "321",
                    "--history-max-pages",
                    "4",
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                history_metadata_executor,
            )

            runner.run_pipeline(context)

        fetch_step = manifest["steps"][0]
        self.assertEqual("fetch_history", fetch_step["step"])
        self.assertIn("fetch_zzshare_a_share.py", fetch_step["command"][1])
        self.assertIn("--fields", fetch_step["command"])
        self.assertEqual("https://example.test", manifest["history_http_url"])
        self.assertEqual(8.0, manifest["history_timeout_seconds"])
        self.assertEqual(0.0, manifest["history_request_interval_seconds"])
        self.assertEqual(7, manifest["history_max_concurrent_symbol_requests"])
        self.assertEqual(45.0, manifest["history_max_rate_limit_sleep_seconds"])
        self.assertEqual(6, manifest["history_max_429_events"])
        self.assertEqual(1800.0, manifest["history_max_runtime_seconds"])
        self.assertEqual(321, manifest["history_limit"])
        self.assertEqual(4, manifest["history_max_pages"])
        self.assertIn("--http-url", fetch_step["command"])
        self.assertIn("https://example.test", fetch_step["command"])
        self.assertIn("--timeout-seconds", fetch_step["command"])
        self.assertIn("8.0", fetch_step["command"])
        self.assertIn("--request-interval-seconds", fetch_step["command"])
        self.assertIn("0.0", fetch_step["command"])
        self.assertIn("--max-concurrent-symbol-requests", fetch_step["command"])
        self.assertIn("7", fetch_step["command"])
        self.assertIn("--max-rate-limit-sleep-seconds", fetch_step["command"])
        self.assertIn("45.0", fetch_step["command"])
        self.assertIn("--max-429-events", fetch_step["command"])
        self.assertIn("6", fetch_step["command"])
        self.assertIn("--max-runtime-seconds", fetch_step["command"])
        self.assertIn("1800.0", fetch_step["command"])
        self.assertIn("--limit", fetch_step["command"])
        self.assertIn("321", fetch_step["command"])
        self.assertIn("--max-pages", fetch_step["command"])
        self.assertIn("4", fetch_step["command"])
        self.assertEqual("zzshare", manifest["history_source"])
        self.assertEqual("zzshare_history_fetch", manifest["source_scope"])

    def test_runner_redacts_sensitive_step_artifacts_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-http-url",
                    "https://example.test/api?token=placeholder-token-value",
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                sensitive_history_executor,
            )

            runner.run_pipeline(context)
            saved = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )

        text = json.dumps(saved)
        self.assertEqual(
            "https://example.test/api?token=%5BREDACTED%5D",
            saved["history_http_url"],
        )
        self.assertIn("[REDACTED]", text)
        self.assertNotIn("placeholder-token-value", text)
        self.assertNotIn("placeholder-secret-value", text)
        self.assertNotIn("placeholder-api-key-value", text)

    def test_runner_redacts_sensitive_generic_failure_message(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            original_apply_resume_from = runner.apply_resume_from
            runner.apply_resume_from = sensitive_preflight_failure
            try:
                code, _stdout, stderr = call_runner(
                    [
                        "--prices-input",
                        str(prices),
                        "--output-dir",
                        str(output),
                        "--no-html-report",
                    ]
                )
            finally:
                runner.apply_resume_from = original_apply_resume_from
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(2, code)
        self.assertIn("[REDACTED]", stderr)
        self.assertNotIn("placeholder-token-value", stderr)
        self.assertNotIn("placeholder-api-key-value", stderr)
        self.assertEqual(manifest["run_error"], summary["run_error"])
        self.assertIn("[REDACTED]", summary["run_error"])
        self.assertNotIn("placeholder-token-value", summary["run_error"])
        self.assertNotIn("placeholder-api-key-value", summary["run_error"])

    def test_runner_redacts_sensitive_step_failure_stderr_in_cli_error(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            original_run_command = runner.run_command
            runner.run_command = sensitive_failure_executor
            try:
                code, _stdout, stderr = call_runner(
                    [
                        "--prices-input",
                        str(prices),
                        "--output-dir",
                        str(output),
                        "--no-html-report",
                    ]
                )
            finally:
                runner.run_command = original_run_command
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(3, code)
        self.assertIn("step=validate", stderr)
        self.assertIn("[REDACTED]", stderr)
        self.assertNotIn("placeholder-token-value", stderr)
        self.assertNotIn("placeholder-api-key-value", stderr)
        failed = summary["failed_step_details"][0]["stderr_first_line"]
        self.assertIn("[REDACTED]", failed)
        self.assertNotIn("placeholder-token-value", failed)
        self.assertNotIn("placeholder-api-key-value", failed)

    def test_runner_accepts_yfinance_hk_history_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "yfinance",
                    "--symbols",
                    "00700,HK.09988,08001.HK",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-timeout-seconds",
                    "8",
                    "--mode",
                    "generic",
                    "--config",
                    str(SCRIPTS / "hong_kong_generic_config.json"),
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                yfinance_hk_executor,
            )

            runner.run_pipeline(context)
            summary = summary_view(manifest, "completed")

        fetch_step = manifest["steps"][0]
        self.assertEqual("fetch_history", fetch_step["step"])
        self.assertIn("fetch_yfinance_ohlcv.py", fetch_step["command"][1])
        self.assertIn("0700.HK,9988.HK,8001.HK", fetch_step["command"])
        self.assertIn("--market", fetch_step["command"])
        self.assertIn("HK", fetch_step["command"])
        self.assertIn("--timeout-seconds", fetch_step["command"])
        self.assertIn("8.0", fetch_step["command"])
        self.assertEqual(
            ["0700.HK", "9988.HK", "8001.HK"],
            manifest["history_symbols"],
        )
        self.assertEqual("yfinance", manifest["history_source"])
        self.assertEqual("yfinance_history_fetch", manifest["source_scope"])
        self.assertEqual("yfinance", summary["input_metadata"]["source"])
        self.assertEqual("HK", summary["input_metadata"]["market"])
        self.assertTrue(summary["input_metadata"]["market_label_only"])
        self.assertEqual("unknown", summary["input_metadata"]["real_market_data"])

    def test_runner_accepts_pytdx_history_source_as_explicit_supplement(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "pytdx",
                    "--symbols",
                    "000001,600000",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-timeout-seconds",
                    "8",
                    "--mode",
                    "generic",
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                pytdx_executor,
            )

            runner.run_pipeline(context)
            summary = summary_view(manifest, "completed")

        fetch_step = manifest["steps"][0]
        self.assertEqual("fetch_history", fetch_step["step"])
        self.assertIn("fetch_pytdx_a_share.py", fetch_step["command"][1])
        self.assertIn("000001,600000", fetch_step["command"])
        self.assertIn("--timeout-seconds", fetch_step["command"])
        self.assertIn("8.0", fetch_step["command"])
        self.assertNotIn("--adjust", fetch_step["command"])
        self.assertEqual(["000001", "600000"], manifest["history_symbols"])
        self.assertEqual("pytdx", manifest["history_source"])
        self.assertEqual("pytdx_history_fetch", manifest["source_scope"])
        self.assertEqual("pytdx", summary["input_metadata"]["source"])
        self.assertEqual(
            "pypi_license_unknown_readme_personal_research_boundary",
            summary["input_metadata"]["history_license_claim_boundary"],
        )
        self.assertEqual(
            ["turn", "tradestatus", "isST", "name"],
            summary["input_metadata"]["history_missing_provider_fields"],
        )

    def test_runner_accepts_akshare_hk_daily_history_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "akshare_hk_daily",
                    "--symbols",
                    "700,HK.09988,08001.HK",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-adjust",
                    "",
                    "--mode",
                    "generic",
                    "--config",
                    str(SCRIPTS / "hong_kong_generic_config.json"),
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                akshare_hk_daily_executor,
            )

            runner.run_pipeline(context)
            summary = summary_view(manifest, "completed")

        fetch_step = manifest["steps"][0]
        self.assertEqual("fetch_history", fetch_step["step"])
        self.assertIn("fetch_akshare_hk_daily.py", fetch_step["command"][1])
        self.assertIn("00700,09988,08001", fetch_step["command"])
        self.assertEqual(
            ["00700", "09988", "08001"],
            manifest["history_symbols"],
        )
        self.assertEqual("akshare_hk_daily", manifest["history_source"])
        self.assertEqual("akshare_hk_daily_history_fetch", manifest["source_scope"])
        self.assertEqual("akshare_stock_hk_daily", summary["input_metadata"]["source"])
        self.assertEqual("HK", summary["input_metadata"]["market"])
        self.assertEqual("unknown", summary["input_metadata"]["real_market_data"])

    def test_runner_rejects_pytdx_unsupported_adjust_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    tmpdir,
                    "--history-source",
                    "pytdx",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-adjust",
                    "qfq",
                    "--no-html-report",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("unsupported pytdx history options would be ignored", stderr)
        self.assertIn("--history-adjust", stderr)

    def test_history_metadata_output_written_respects_metadata_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
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
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            manifest["run_outputs_initialized"] = True
            selected = {
                "symbols": ["000001"],
                "selected_symbol_count": 1,
            }
            metadata = {
                "source": "baostock",
                "requested_symbols": ["000001"],
                "rows": 0,
                "symbol_count": 0,
                "output_written": False,
                "metadata_output_written": False,
            }
            output.mkdir(parents=True, exist_ok=True)
            (output / "selected_symbols.json").write_text(
                json.dumps(selected),
                encoding="utf-8",
            )
            (output / "history_metadata.json").write_text(
                json.dumps(metadata),
                encoding="utf-8",
            )

            summary = summary_view(manifest, "completed")

        history = summary["history_selection"]
        self.assertFalse(summary["history_metadata_output_written"])
        self.assertTrue(summary["history_metadata_file_exists"])
        self.assertFalse(history["history_metadata_output_written"])
        self.assertTrue(history["history_metadata_file_exists"])

    def test_legacy_history_metadata_without_output_flag_is_metadata_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
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
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            manifest["run_outputs_initialized"] = True
            output.mkdir(parents=True, exist_ok=True)
            (output / "selected_symbols.json").write_text(
                json.dumps(
                    {
                        "symbols": ["000001"],
                        "selected_symbol_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            (output / "history_metadata.json").write_text(
                json.dumps(
                    {
                        "source": "baostock",
                        "requested_symbols": ["000001"],
                        "rows": 0,
                        "symbol_count": 0,
                    }
                ),
                encoding="utf-8",
            )

            summary = summary_view(manifest, "completed")

        history = summary["history_selection"]
        self.assertFalse(summary["history_output_written"])
        self.assertTrue(summary["history_metadata_output_written"])
        self.assertEqual("metadata_only", summary["history_artifact_status"])
        self.assertFalse(history["history_output_written"])
        self.assertTrue(history["history_metadata_output_written"])
        self.assertEqual("metadata_only", history["history_artifact_status"])

    def test_history_metadata_inconsistent_output_flags_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
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
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            manifest["run_outputs_initialized"] = True
            output.mkdir(parents=True, exist_ok=True)
            (output / "selected_symbols.json").write_text(
                json.dumps(
                    {
                        "symbols": ["000001"],
                        "selected_symbol_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            (output / "history_metadata.json").write_text(
                json.dumps(
                    {
                        "requested_symbols": ["000001"],
                        "output_written": True,
                        "metadata_output_written": False,
                    }
                ),
                encoding="utf-8",
            )

            summary = summary_view(manifest, "completed")

        history = summary["history_selection"]
        self.assertTrue(summary["history_output_written"])
        self.assertFalse(summary["history_metadata_output_written"])
        self.assertEqual("inconsistent_metadata", summary["history_artifact_status"])
        self.assertTrue(history["history_output_written"])
        self.assertFalse(history["history_metadata_output_written"])
        self.assertEqual("inconsistent_metadata", history["history_artifact_status"])

    def test_history_metadata_written_flags_reject_string_booleans(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
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
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            manifest["run_outputs_initialized"] = True
            output.mkdir(parents=True, exist_ok=True)
            (output / "selected_symbols.json").write_text(
                json.dumps(
                    {
                        "symbols": ["000001"],
                        "selected_symbol_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            (output / "history_metadata.json").write_text(
                json.dumps(
                    {
                        "requested_symbols": ["000001"],
                        "output_written": "false",
                        "metadata_output_written": "false",
                    }
                ),
                encoding="utf-8",
            )

            summary = summary_view(manifest, "completed")

        history = summary["history_selection"]
        self.assertFalse(summary["history_output_written"])
        self.assertFalse(summary["history_metadata_output_written"])
        self.assertEqual("not_written", summary["history_artifact_status"])
        self.assertFalse(history["history_output_written"])
        self.assertFalse(history["history_metadata_output_written"])
        self.assertEqual("not_written", history["history_artifact_status"])

    def test_yfinance_hk_symbol_parser_maps_common_hk_forms(self) -> None:
        args = SimpleNamespace(
            history_source="yfinance",
            symbols="00700,HK.09988,08001.HK",
            history_market="HK",
        )

        self.assertEqual(
            ["0700.HK", "9988.HK", "8001.HK"],
            parse_history_symbols(args),
        )

    def test_yfinance_hk_symbol_parser_rejects_zero_code(self) -> None:
        args = SimpleNamespace(
            history_source="yfinance",
            symbols="0,00700",
            history_market="HK",
        )

        with self.assertRaisesRegex(ValueError, "HK yfinance symbols"):
            parse_history_symbols(args)

    def test_runner_rejects_yfinance_unsupported_adjust_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    tmpdir,
                    "--history-source",
                    "yfinance",
                    "--symbols",
                    "00700",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-adjust",
                    "qfq",
                    "--config",
                    str(SCRIPTS / "hong_kong_generic_config.json"),
                    "--no-html-report",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("unsupported yfinance history options would be ignored", stderr)
        self.assertIn("--history-adjust", stderr)

    def test_runner_rejects_yfinance_unsupported_drop_invalid_rows_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    tmpdir,
                    "--history-source",
                    "yfinance",
                    "--symbols",
                    "00700",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--drop-invalid-history-rows",
                    "--config",
                    str(SCRIPTS / "hong_kong_generic_config.json"),
                    "--no-html-report",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("unsupported yfinance history options would be ignored", stderr)
        self.assertIn("--drop-invalid-history-rows", stderr)

    def test_runner_rejects_zzshare_only_options_for_other_history_sources(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    tmpdir,
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-limit",
                    "10",
                    "--no-html-report",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn(
            "zzshare-specific history options require --history-source zzshare",
            stderr,
        )

    def test_runner_rejects_invalid_zzshare_only_option_for_other_source_by_scope(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    tmpdir,
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-limit",
                    "abc",
                    "--no-html-report",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn(
            "zzshare-specific history options require --history-source zzshare",
            stderr,
        )
        self.assertIn("--history-limit", stderr)
        self.assertNotIn("history-limit must be an integer", stderr)

    def test_preflight_error_clears_reused_output_files(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, _stdout, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(output)]
            )
            self.assertEqual(0, code, stderr)
            old_candidates = output / "candidates.csv"
            old_diagnostics = output / "diagnostics.csv"
            old_prices = output / "prices.csv"
            self.assertTrue(old_candidates.exists())
            self.assertTrue(old_diagnostics.exists())
            self.assertTrue(old_prices.exists())
            old_spot_metadata = output / "spot_metadata.json"
            old_spot_metadata.write_text(
                json.dumps(
                    {
                        "source": "eastmoney",
                        "source_scope": "a_share_spot_snapshot",
                        "requested_pages": 2,
                        "successful_pages": 1,
                        "failed_pages": [{"page": 2, "error": "disconnect"}],
                        "raw_items": 100,
                        "filtered_items": 100,
                        "partial_result": True,
                    }
                ),
                encoding="utf-8",
            )

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
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")

            self.assertEqual(2, code)
            self.assertIn("history fetch options would be ignored", stderr)
            self.assertFalse(old_candidates.exists())
            self.assertFalse(old_diagnostics.exists())
            self.assertFalse(old_prices.exists())
            self.assertFalse(old_spot_metadata.exists())
            self.assertEqual({}, summary["spot_metadata"])
            self.assertEqual(0, summary["spot_rows"])
            self.assertFalse(summary["candidates_output_written"])
            self.assertFalse(summary["diagnostics_output_written"])
            self.assertEqual(0, summary["candidate_rows"])
            self.assertEqual(0, summary["diagnostic_rows"])
            self.assertNotIn("Zero Prefix", report)
            self.assertNotIn("eastmoney", report)
            self.assertNotIn('"error": "disconnect"', report)

    def test_invalid_zzshare_history_limit_clears_reused_output_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"
            output.mkdir()
            old_candidates = output / "candidates.csv"
            old_diagnostics = output / "diagnostics.csv"
            old_prices = output / "prices.csv"
            old_metadata = output / "history_metadata.json"
            for path in [old_candidates, old_diagnostics, old_prices, old_metadata]:
                path.write_text("stale\n", encoding="utf-8")

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-limit",
                    "0",
                    "--no-html-report",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(2, code)
        self.assertIn("history-limit must be positive", stderr)
        self.assertFalse(old_candidates.exists())
        self.assertFalse(old_diagnostics.exists())
        self.assertFalse(old_prices.exists())
        self.assertFalse(old_metadata.exists())
        self.assertFalse(summary["candidates_output_written"])
        self.assertFalse(summary["diagnostics_output_written"])

    def test_invalid_zzshare_history_budgets_fail_before_fetch(self) -> None:
        cases = [
            (
                "--history-max-rate-limit-sleep-seconds",
                "-1",
                "history-max-rate-limit-sleep-seconds must be non-negative",
            ),
            (
                "--history-max-429-events",
                "0",
                "history-max-429-events must be positive",
            ),
            (
                "--history-max-runtime-seconds",
                "0",
                "history-max-runtime-seconds must be positive",
            ),
        ]
        for option, value, expected_error in cases:
            with self.subTest(option=option), tempfile.TemporaryDirectory() as tmpdir:
                code, _stdout, stderr = call_runner(
                    [
                        "--output-dir",
                        str(Path(tmpdir) / "run"),
                        "--history-source",
                        "zzshare",
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2025-01-01",
                        "--end-date",
                        "2026-01-01",
                        option,
                        value,
                        "--no-html-report",
                    ]
                )

            self.assertEqual(2, code)
            self.assertIn(expected_error, stderr)

    def test_invalid_zzshare_history_timeout_nan_clears_reused_output_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"
            output.mkdir()
            old_candidates = output / "candidates.csv"
            old_candidates.write_text("stale\n", encoding="utf-8")

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-timeout-seconds",
                    "nan",
                    "--no-html-report",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("history-timeout-seconds must be finite", stderr)
        self.assertFalse(old_candidates.exists())

    def test_runner_rejects_local_and_fetched_spot_inputs_together(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            spot = root / "spot.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            spot.write_text("symbol,price\n000002,8.88\n", encoding="utf-8")

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--fetch-spot",
                    "eastmoney",
                    "--output-dir",
                    str(output),
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("use either --spot-input or --fetch-spot", stderr)

    def test_runner_records_local_spot_input_in_score_command(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            spot = root / "spot.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            spot.write_text("symbol,price\n000002,8.88\n", encoding="utf-8")

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--output-dir",
                    str(output),
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        score_command = manifest["steps"][1]["command"]
        self.assertIn("--spot-input", score_command)
        self.assertEqual(
            "local_prices_input+local_spot_input", manifest["source_scope"]
        )
        self.assertEqual(1, summary["spot_rows"])

    def test_runner_does_not_write_score_profile_by_default(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--no-html-report",
                ]
            )
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertFalse((output / "score_profile.json").exists())
        self.assertFalse(manifest["score_profile_enabled"])
        self.assertEqual("", manifest["score_profile_output"])
        self.assertFalse(summary["score_profile_enabled"])
        self.assertEqual("", summary["score_profile_output"])
        self.assertFalse(summary["score_profile_output_written"])
        self.assertNotIn("--profile-output", manifest["steps"][1]["command"])
        self.assertIn("score_profile_enabled=false", stdout)

    def test_runner_writes_score_profile_when_explicitly_enabled(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            profile_path = output / "score_profile.json"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--score-profile",
                    "--no-html-report",
                ]
            )
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            profile_exists = profile_path.exists()
            profile = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertTrue(profile_exists)
        self.assertTrue(manifest["score_profile_enabled"])
        self.assertTrue(manifest["score_profile_output_written"])
        self.assertEqual(str(profile_path), manifest["score_profile_output"])
        self.assertEqual(profile["candidate_rows"], manifest["score_profile_rows"])
        self.assertEqual(
            profile["input_rows_per_second"],
            summary["score_profile_input_rows_per_second"],
        )
        self.assertEqual(
            profile["scored_symbols_per_second"],
            manifest["score_profile_scored_symbols_per_second"],
        )
        self.assertTrue(summary["score_profile_enabled"])
        self.assertTrue(summary["score_profile_output_written"])
        self.assertEqual(str(profile_path), summary["score_profile_output"])
        self.assertIn("--profile-output", manifest["steps"][1]["command"])
        self.assertIn("score_profile_enabled=true", stdout)
        self.assertIn("score_profile_output_written=true", stdout)
        self.assertEqual("score_candidates_profile_v1", profile["profile_schema"])
        self.assertGreater(profile["input_rows_per_second"], 0.0)
        self.assertGreater(profile["scored_symbols_per_second"], 0.0)
        self.assertEqual(profile["candidate_rows"], summary["candidate_rows"])

    def test_runner_can_filter_local_prices_to_spot_universe(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            spot = root / "spot.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            spot.write_text("symbol,price\n000002,8.88\n", encoding="utf-8")

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--filter-prices-to-spot-universe",
                    "--output-dir",
                    str(output),
                ]
            )

            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            filter_metadata = json.loads(
                (output / "prices_filter.json").read_text(
                    encoding="utf-8"
                )
            )
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")
            scored_symbols = {row["symbol"] for row in diagnostic_rows}

        self.assertEqual(0, code, stderr)
        self.assertIn("filter_prices_to_spot_universe=true", stdout)
        self.assertIn("prices_filter_spot_universe=true", stdout)
        self.assertIn("prices_filter_removed_symbol_count=1", stdout)
        self.assertEqual(130, summary["prices_rows"])
        self.assertEqual(1, summary["diagnostic_rows"])
        self.assertEqual(1, summary["candidate_rows"])
        self.assertTrue(summary["filter_prices_to_spot_universe"])
        self.assertTrue(summary["prices_filter_spot_universe"])
        self.assertEqual(1, summary["prices_filter_removed_symbol_count"])
        self.assertEqual(["600001"], summary["prices_filter_removed_symbols"])
        self.assertEqual(
            "local_prices_filtered_from_existing_artifacts_not_new_history_fetch",
            summary["prices_filter_claim_boundary"],
        )
        self.assertEqual(
            str(output / "prices_filter.json"),
            manifest["prices_filter_metadata_output"],
        )
        self.assertEqual(1, filter_metadata["prices_filter_removed_symbol_count"])
        self.assertGreaterEqual(filter_metadata["prices_filter_duration_seconds"], 0.0)
        self.assertEqual(
            filter_metadata["prices_filter_duration_seconds"],
            summary["prices_filter_duration_seconds"],
        )
        self.assertEqual({"000002"}, scored_symbols)
        self.assertEqual({"000002"}, {row["symbol"] for row in candidate_rows})
        self.assertEqual(
            "True",
            diagnostic_rows[0]["prices_filter_spot_universe"],
        )
        self.assertEqual(
            "1",
            diagnostic_rows[0]["prices_filter_removed_symbol_count"],
        )

    def test_runner_local_spot_input_does_not_filter_prices_by_default(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            spot = root / "spot.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            spot.write_text("symbol,price\n000002,8.88\n", encoding="utf-8")

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--output-dir",
                    str(output),
                ]
            )

            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertEqual(0, code, stderr)
        self.assertIn("filter_prices_to_spot_universe=false", stdout)
        self.assertEqual(260, summary["prices_rows"])
        self.assertEqual(2, summary["diagnostic_rows"])
        self.assertFalse(summary["prices_filter_spot_universe"])
        self.assertEqual(0, summary["prices_filter_removed_symbol_count"])
        self.assertEqual({"000002", "600001"}, {row["symbol"] for row in diagnostic_rows})

    def test_runner_can_filter_local_prices_by_latest_symbol_date(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame = frame.copy()
        frame.loc[frame["symbol"] == "600001", "date"] = "2025-01-31"
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--min-symbol-latest-date",
                    "2025-06-01",
                    "--output-dir",
                    str(output),
                ]
            )

            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            filter_metadata = json.loads(
                (output / "prices_filter.json").read_text(encoding="utf-8")
            )
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertEqual(0, code, stderr)
        self.assertIn("prices_filter_min_symbol_latest_date=2025-06-01", stdout)
        self.assertIn("prices_filter_removed_stale_symbol_count=1", stdout)
        self.assertEqual(130, summary["prices_rows"])
        self.assertEqual(1, summary["diagnostic_rows"])
        self.assertFalse(summary["prices_filter_spot_universe"])
        self.assertEqual("2025-06-01", summary["prices_filter_min_symbol_latest_date"])
        self.assertEqual(1, summary["prices_filter_removed_symbol_count"])
        self.assertEqual(1, summary["prices_filter_removed_stale_symbol_count"])
        self.assertEqual(["600001"], summary["prices_filter_removed_stale_symbols"])
        self.assertEqual(1, filter_metadata["prices_filter_removed_stale_symbol_count"])
        self.assertEqual({"000002"}, {row["symbol"] for row in diagnostic_rows})
        self.assertEqual(
            "2025-06-01",
            diagnostic_rows[0]["prices_filter_min_symbol_latest_date"],
        )
        self.assertEqual(
            "1",
            diagnostic_rows[0]["prices_filter_removed_stale_symbol_count"],
        )

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_can_write_filtered_local_prices_as_parquet(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            spot = root / "spot.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            spot.write_text("symbol,price\n000002,8.88\n", encoding="utf-8")

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--filter-prices-to-spot-universe",
                    "--prices-filter-output-format",
                    "parquet",
                    "--output-dir",
                    str(output),
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            filter_metadata = json.loads(
                (output / "prices_filter.json").read_text(encoding="utf-8")
            )
            diagnostic_rows = csv_rows(output / "diagnostics.csv")
            csv_exists = (output / "prices.csv").exists()
            parquet_exists = (output / "prices.parquet").exists()
            sidecar = json.loads(
                (output / "prices.parquet.metadata.json").read_text(encoding="utf-8")
            )

        self.assertEqual(0, code, stderr)
        self.assertIn("prices_filter_output_format=parquet", stdout)
        self.assertFalse(csv_exists)
        self.assertTrue(parquet_exists)
        self.assertEqual(1, sidecar["schema_version"])
        self.assertEqual(1, sidecar["symbol_count"])
        self.assertEqual(
            filter_metadata["prices_filter_output_prices"],
            sidecar["filter_contract"]["prices_filter_output_prices"],
        )
        self.assertEqual(
            filter_metadata["prices_filter_output_rows"],
            sidecar["filter_contract"]["prices_filter_output_rows"],
        )
        self.assertEqual(
            filter_metadata["prices_filter_sidecar_sha256"],
            sidecar["artifact"]["sha256"],
        )
        self.assertTrue(summary["prices_output"].endswith("prices.parquet"))
        self.assertEqual("parquet", summary["prices_filter_output_format"])
        self.assertEqual(
            str(output / "prices.parquet"), summary["prices_filter_output_prices"]
        )
        self.assertEqual(str(output / "prices.parquet"), manifest["prices_output_path"])
        self.assertEqual(str(output / "prices.parquet"), manifest["steps"][0]["command"][3])
        self.assertEqual(str(output / "prices.parquet"), manifest["steps"][1]["command"][3])
        self.assertEqual("parquet", filter_metadata["prices_filter_output_format"])
        self.assertEqual(
            str(output / "prices.parquet"),
            filter_metadata["prices_filter_output_prices"],
        )
        self.assertEqual("parquet", diagnostic_rows[0]["prices_filter_output_format"])

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_copies_same_format_prices_when_filter_removes_nothing(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.parquet"
            spot = root / "spot.csv"
            output = root / "run"
            frame.to_parquet(prices, index=False)
            spot.write_text("symbol,price\n000002,8.88\n600001,9.99\n", encoding="utf-8")

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--filter-prices-to-spot-universe",
                    "--prices-filter-output-format",
                    "parquet",
                    "--output-dir",
                    str(output),
                ]
            )
            filter_metadata = json.loads(
                (output / "prices_filter.json").read_text(encoding="utf-8")
            )
            copied = (output / "prices.parquet").read_bytes()
            source = prices.read_bytes()

        self.assertEqual(0, code, stderr)
        self.assertTrue(filter_metadata["prices_filter_passthrough_copy"])
        self.assertEqual(source, copied)

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_reuses_verified_filtered_parquet_sidecar_metadata(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source"
            source.mkdir()
            prices_csv = source / "input.csv"
            spot = source / "spot.csv"
            metadata = source / "metadata.json"
            first = root / "first"
            second = root / "second"
            frame.to_csv(prices_csv, index=False)
            spot.write_text("symbol,price\n000002,8.88\n", encoding="utf-8")
            metadata.write_text(
                json.dumps(
                    {
                        "source": "verified_source",
                        "source_type": "external_fetch",
                        "source_scope": "verified_history",
                        "real_market_data": True,
                    }
                ),
                encoding="utf-8",
            )
            first_code, _, first_stderr = call_runner(
                [
                    "--prices-input",
                    str(prices_csv),
                    "--spot-input",
                    str(spot),
                    "--filter-prices-to-spot-universe",
                    "--prices-filter-output-format",
                    "parquet",
                    "--output-dir",
                    str(first),
                ]
            )
            filtered_prices = first / "prices.parquet"
            stat = filtered_prices.stat()
            os.utime(
                filtered_prices,
                ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000),
            )
            second_code, _, second_stderr = call_runner(
                [
                    "--prices-input",
                    str(filtered_prices),
                    "--output-dir",
                    str(second),
                ]
            )
            summary = json.loads((second / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, first_code, first_stderr)
        self.assertEqual(0, second_code, second_stderr)
        self.assertEqual("verified_source", summary["source"])
        self.assertTrue(summary["input_metadata"]["input_metadata_sidecar_verified"])
        self.assertEqual(1, summary["input_metadata"]["input_metadata_sidecar_symbol_count"])
        self.assertEqual(
            130,
            summary["input_metadata"]["input_prices_filter_contract"][
                "prices_filter_output_rows"
            ],
        )

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_rejects_sidecar_table_statistic_drift(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.parquet"
            frame.to_parquet(prices, index=False)
            sidecar = build_sidecar(
                prices=prices,
                frame=frame,
                filter_metadata={
                    "prices_filter_output_prices": str(prices),
                    "prices_filter_output_rows": len(frame),
                    "prices_filter_kept_symbol_count": frame["symbol"].nunique(),
                },
                input_metadata={"source": "verified_source"},
            )
            sidecar["rows"] += 1
            write_sidecar(sidecar, prices)

            code, _, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(root / "run")]
            )

        self.assertNotEqual(0, code)
        self.assertIn("filtered prices sidecar table statistics mismatch", stderr)

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_rejects_tampered_filtered_parquet_sidecar(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.parquet"
            frame.to_parquet(prices, index=False)
            sidecar = root / "prices.parquet.metadata.json"
            sidecar.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "claim_boundary": (
                            "filtered_prices_sidecar_not_new_market_data_or_full_market_proof"
                        ),
                        "artifact": {
                            "path": str(prices.resolve()),
                            "size_bytes": 1,
                            "mtime_ns": 1,
                            "sha256": "invalid",
                        },
                        "input_metadata": {"source": "verified_source"},
                    }
                ),
                encoding="utf-8",
            )
            code, _, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(root / "run")]
            )

        self.assertNotEqual(0, code)
        self.assertIn("filtered prices sidecar fingerprint mismatch", stderr)

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_rejects_declared_filtered_parquet_without_sidecar(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.parquet"
            frame.to_parquet(prices, index=False)
            (root / "prices_filter.json").write_text(
                json.dumps({"prices_filter_output_prices": str(prices)}),
                encoding="utf-8",
            )
            code, _, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(root / "run")]
            )

        self.assertNotEqual(0, code)
        self.assertIn("filtered prices sidecar not found", stderr)

    def test_runner_writes_prices_filter_metadata_when_all_symbols_removed(
        self,
    ) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--min-symbol-latest-date",
                    "2026-01-01",
                    "--output-dir",
                    str(output),
                ]
            )

            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            filter_metadata = json.loads(
                (output / "prices_filter.json").read_text(encoding="utf-8")
            )

        self.assertEqual(2, code)
        self.assertIn("local prices filters removed all price symbols", stderr)
        self.assertEqual("failed", summary["status"])
        self.assertEqual("PricesFilterError", summary["run_error_type"])
        self.assertFalse(summary["prices_filter_output_written"])
        self.assertEqual(
            "all_price_symbols_removed",
            summary["prices_filter_failure_reason"],
        )
        self.assertEqual(2, summary["prices_filter_removed_symbol_count"])
        self.assertEqual(2, summary["prices_filter_removed_stale_symbol_count"])
        self.assertEqual(["000002", "600001"], summary["prices_filter_removed_symbols"])
        self.assertEqual([], summary["failed_steps"])
        self.assertFalse(manifest["prices_filter_output_written"])
        self.assertEqual(
            "all_price_symbols_removed",
            manifest["prices_filter_failure_reason"],
        )
        self.assertEqual(
            "local prices filters removed all price symbols",
            filter_metadata["prices_filter_error"],
        )
        self.assertEqual(260, filter_metadata["prices_filter_input_rows"])
        self.assertEqual(0, filter_metadata["prices_filter_output_rows"])
        self.assertEqual(2, filter_metadata["prices_filter_input_symbol_count"])
        self.assertEqual(0, filter_metadata["prices_filter_kept_symbol_count"])

    def test_runner_uses_spot_name_when_history_name_is_numeric(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame = frame[frame["symbol"] == "000002"].copy()
        frame["name"] = "2"
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            spot = root / "spot.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            spot.write_text(
                "symbol,name,price,amount\n000002,万科A,8.88,200000000\n",
                encoding="utf-8",
            )

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--output-dir",
                    str(output),
                ]
            )

            candidate_rows = csv_rows(output / "candidates.csv")
            report = (output / "report.html").read_text(encoding="utf-8")

        self.assertEqual(0, code, stderr)
        self.assertEqual("万科A", candidate_rows[0]["name"])
        self.assertIn("万科A", report)

    def test_runner_records_eastmoney_fetch_step_before_score(self) -> None:
        args = runner.build_parser().parse_args(
            [
                "--prices-input",
                "/tmp/prices.csv",
                "--output-dir",
                "/tmp/run",
                "--fetch-spot",
                "eastmoney",
                "--spot-pages",
                "2",
                "--fail-on-partial-spot",
            ]
        )

        command = runner.fetch_spot_command(args, Path("/tmp/run/spot.csv"))

        self.assertIn("fetch_eastmoney_a_share_spot.py", command[1])
        self.assertIn("--fail-on-partial", command)
        self.assertIn("2", command)

    def test_runner_explicit_spot_fallback_records_primary_failure(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame = frame[frame["symbol"] == "000001"].copy()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner_with_executor(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--fetch-spot",
                    "eastmoney",
                    "--fetch-spot-fallback",
                    "baostock_universe",
                    "--spot-fallback-lookback-days",
                    "7",
                    "--fail-on-partial-spot",
                    "--no-html-report",
                ],
                spot_fallback_executor,
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertIn("status=completed", stdout)
        self.assertIn("fetch_spot_fallback=baostock_universe", stdout)
        self.assertIn("fetch_spot_fallback_used=true", stdout)
        self.assertIn("fetch_spot_primary_failure_recorded=true", stdout)
        self.assertIn("fetch_spot_primary_failure_returncode=3", stdout)
        self.assertIn("spot_resolved_snapshot_date=2026-07-08", stdout)
        self.assertIn("spot_date_fallback_used=true", stdout)
        self.assertIn("spot_lookback_days=7", stdout)
        self.assertEqual(
            ["fetch_spot", "fetch_spot_fallback", "validate", "score"],
            [step["step"] for step in manifest["steps"]],
        )
        self.assertTrue(manifest["fetch_spot_fallback_used"])
        self.assertEqual(
            "baostock_universe",
            manifest["fetch_spot_fallback"],
        )
        self.assertEqual(7, manifest["spot_fallback_lookback_days"])
        self.assertEqual(1, manifest["spot_fallback_retries"])
        self.assertEqual(1.0, manifest["spot_fallback_retry_interval_seconds"])
        self.assertEqual(
            "local_prices_input+baostock_universe_snapshot",
            manifest["source_scope"],
        )
        self.assertEqual(
            "fetch_spot_fallback",
            manifest["steps"][0]["fallback_step"],
        )
        self.assertTrue(manifest["steps"][0]["handled_failure"])
        self.assertEqual(3, manifest["fetch_spot_primary_failure"]["returncode"])
        self.assertEqual([], summary["failed_steps"])
        self.assertTrue(summary["fetch_spot_fallback_used"])
        self.assertEqual("baostock_universe", summary["fetch_spot_fallback"])
        self.assertEqual(7, summary["spot_fallback_lookback_days"])
        self.assertEqual(1, summary["spot_fallback_retries"])
        self.assertEqual(1.0, summary["spot_fallback_retry_interval_seconds"])
        self.assertEqual(
            "baostock_universe_snapshot",
            summary["spot_metadata"]["source_scope"],
        )
        self.assertEqual(1, summary["spot_rows"])
        self.assertEqual(1, summary["spot_matched_symbols"])

    def test_runner_baostock_universe_default_has_no_date_lookback(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame = frame[frame["symbol"] == "000001"].copy()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner_with_executor(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--fetch-spot",
                    "baostock_universe",
                    "--no-html-report",
                ],
                baostock_universe_executor,
            )
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertEqual(0, manifest["spot_fallback_lookback_days"])
        self.assertEqual(0, summary["spot_fallback_lookback_days"])
        self.assertEqual(
            0,
            summary["planned_parameters"]["spot_fallback_lookback_days"],
        )
        self.assertEqual(
            1,
            summary["planned_parameters"]["spot_fallback_retries"],
        )
        self.assertFalse(summary["spot_metadata"]["date_fallback_used"])
        self.assertEqual("2026-07-09", summary["spot_metadata"]["resolved_snapshot_date"])
        self.assertIn("spot_resolved_snapshot_date=2026-07-09", stdout)
        self.assertIn("spot_date_fallback_used=false", stdout)
        self.assertIn("spot_lookback_days=0", stdout)

    def test_runner_plan_only_baostock_universe_stdout_uses_planned_lookback(
        self,
    ) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = Path(tmpdir) / "run"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--fetch-spot",
                    "baostock_universe",
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertTrue(stdout.startswith("PLAN_ONLY:"), stdout)
        self.assertIn("spot_lookback_days=0", stdout)
        self.assertEqual(
            0,
            summary["planned_parameters"]["spot_fallback_lookback_days"],
        )

    def test_summary_embeds_spot_metadata_failure_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            metadata = {
                "source": "eastmoney",
                "source_scope": "a_share_spot_snapshot",
                "snapshot_time": "2026-06-06T09:31:00Z",
                "requested_pages": 2,
                "retry_attempts_per_page": 1,
                "successful_pages": 1,
                "failed_pages": [{"page": 2, "error": "disconnect"}],
                "raw_items": 100,
                "filtered_items": 100,
                "partial_result": True,
                "coverage_claim": "partial_not_full_market",
                "allowed_failure_actions": ["rerun_with_fail_on_partial"],
                "output_written": False,
                "metadata_output_written": True,
            }
            (output / "spot_metadata.json").write_text(
                json.dumps(metadata),
                encoding="utf-8",
            )
            manifest = {
                "runner": "run_today_a_share_selection",
                "mode": "generic",
                "prediction_mode": False,
                "lightgbm_not_used": True,
                "source_scope": "local_prices_input",
                "output_dir": str(output),
                "run_outputs_initialized": True,
                "steps": [],
            }

            summary = summary_view(manifest, "completed")
            stdout = StringIO()
            with redirect_stdout(stdout):
                runner.helpers.print_summary(manifest, output)

        self.assertTrue(summary["spot_metadata"]["partial_result"])
        self.assertFalse(summary["spot_metadata"]["output_written"])
        self.assertTrue(summary["spot_metadata"]["metadata_output_written"])
        self.assertTrue(summary["spot_metadata_output"].endswith("spot_metadata.json"))
        self.assertTrue(summary["spot_metadata_output_written"])
        self.assertTrue(summary["spot_output"].endswith("spot.csv"))
        self.assertFalse(summary["spot_output_written"])
        self.assertEqual(
            "2026-06-06T09:31:00Z", summary["spot_metadata"]["snapshot_time"]
        )
        self.assertEqual(2, summary["spot_metadata"]["requested_pages"])
        self.assertEqual(1, summary["spot_metadata"]["successful_pages"])
        self.assertEqual(100, summary["spot_metadata"]["raw_items"])
        self.assertEqual(100, summary["spot_metadata"]["filtered_items"])
        self.assertEqual(
            "partial_not_full_market", summary["spot_metadata"]["coverage_claim"]
        )
        self.assertEqual(
            ["rerun_with_fail_on_partial"],
            summary["spot_metadata"]["allowed_failure_actions"],
        )
        self.assertIn("spot_partial_result=true", stdout.getvalue())
        self.assertIn("spot_failed_pages=1", stdout.getvalue())

    def test_summary_embeds_score_symbol_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            manifest = {
                "runner": "run_today_a_share_selection",
                "mode": "generic",
                "prediction_mode": False,
                "lightgbm_not_used": True,
                "source_scope": "local_prices_input",
                "output_dir": str(output),
                "run_outputs_initialized": True,
                "steps": [
                    {
                        "step": "score",
                        "returncode": 0,
                        "allowed_returncodes": [0],
                        "stdout": (
                            "OK: raw_symbols=3 input_symbols=3 candidates=1 "
                            "effective_empty_result=false\n"
                            "INFO: failed_symbol_examples=000003,000004\n"
                            "INFO: insufficient_history_symbol_examples=300001\n"
                        ),
                        "stderr": "",
                    }
                ],
            }

            summary = summary_view(manifest, "completed")

        self.assertEqual(
            ["000003", "000004"], summary["score"]["failed_symbol_examples"]
        )
        self.assertEqual(
            ["300001"],
            summary["score"]["insufficient_history_symbol_examples"],
        )

    def test_summary_preserves_zero_filtered_spot_metadata_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            (output / "spot_metadata.json").write_text(
                json.dumps({"raw_items": 100, "filtered_items": 0}),
                encoding="utf-8",
            )
            manifest = {"output_dir": str(output)}

            rows = spot_rows(manifest)

        self.assertEqual(0, rows)

    def test_tabular_row_count_counts_csv_records_with_embedded_newlines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rows.csv"
            path.write_text(
                'symbol,name\n000001,"Alpha\nName"\n000002,Beta\n', encoding="utf-8"
            )

            rows = tabular_row_count(path)

        self.assertEqual(2, rows)

    def test_tabular_row_count_ignores_csv_directory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rows.csv"
            path.mkdir()

            rows = tabular_row_count(path)

        self.assertEqual(0, rows)

    def test_stale_cleanup_preserves_samefile_prices_input_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            source = output / "prices.CSV"
            stale_alias = output / "prices.csv"
            source.write_text(
                "symbol,date,close\n000001,2026-01-01,8.0\n", encoding="utf-8"
            )
            if not stale_alias.exists():
                stale_alias.hardlink_to(source)
            args = SimpleNamespace(
                prices_input=str(source), spot_input=None, fetch_spot=None
            )

            clear_stale_run_outputs(args, output)

            self.assertTrue(source.exists())
            self.assertTrue(stale_alias.exists())

    def test_stale_cleanup_removes_alternate_prices_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            source = output / "source.csv"
            source.write_text("symbol,date,close\n", encoding="utf-8")
            for name in ["prices.csv", "prices.parquet", "prices.pq"]:
                (output / name).write_text("stale\n", encoding="utf-8")
            args = SimpleNamespace(
                prices_input=str(source), spot_input=None, fetch_spot=None
            )

            clear_stale_run_outputs(args, output)

            remaining = [
                name
                for name in ["prices.csv", "prices.parquet", "prices.pq"]
                if (output / name).exists()
            ]

        self.assertEqual([], remaining)

    def test_stale_cleanup_preserves_samefile_spot_input_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            source = output / "spot.PQ"
            stale_alias = output / "spot.pq"
            source.write_text("symbol,spot_price\n000001,8.0\n", encoding="utf-8")
            if not stale_alias.exists():
                stale_alias.hardlink_to(source)
            args = SimpleNamespace(
                prices_input=None, spot_input=str(source), fetch_spot=None
            )

            clear_stale_run_outputs(args, output)

            self.assertTrue(source.exists())
            self.assertTrue(stale_alias.exists())

    def test_stale_cleanup_preserves_symbols_file_inside_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            symbols_file = output / "retry_symbols.txt"
            symbols_file.write_text("000001\n600000\n", encoding="utf-8")
            args = SimpleNamespace(
                prices_input=None,
                spot_input=None,
                fetch_spot=None,
                symbols_file=str(symbols_file),
            )

            clear_stale_run_outputs(args, output)

            self.assertEqual(
                "000001\n600000\n", symbols_file.read_text(encoding="utf-8")
            )

    def test_runner_builds_history_fetch_before_validate_when_prices_are_omitted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "000001,600000",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)

        self.assertEqual(
            ["fetch_history", "validate", "score"],
            [step["step"] for step in manifest["steps"]],
        )
        self.assertEqual("generic", manifest["mode"])
        self.assertIn(
            "history_fetch_inputs_do_not_include_prediction",
            manifest["mode_decision_reason"],
        )
        self.assertIn("use_mode_prediction", manifest["mode_decision_reason"])
        self.assertEqual("baostock_history_fetch", manifest["source_scope"])
        self.assertEqual(["000001", "600000"], manifest["history_symbols"])
        self.assertIn("--fail-on-fetch-error", manifest["steps"][0]["command"])

    def test_runner_accepts_symbols_file_for_history_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "run"
            symbols_file = root / "symbols.txt"
            symbols_file.write_text("000001\n600000\n000001\n", encoding="utf-8")
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols-file",
                    str(symbols_file),
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                history_metadata_executor,
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        fetch_history = manifest["steps"][0]
        self.assertEqual(["000001", "600000"], manifest["history_symbols"])
        self.assertEqual("explicit_symbols_file", selected["source"])
        self.assertEqual(["000001", "600000"], selected["symbols"])
        self.assertEqual(str(symbols_file), selected["symbols_file"])
        self.assertEqual(str(symbols_file), manifest["symbols_file"])
        self.assertEqual(
            "history_fetch_explicit_symbols_file_generic",
            manifest["execution_path"],
        )
        self.assertEqual("explicit_symbols_file", manifest["execution_path_reason"])
        self.assertIn("000001,600000", fetch_history["command"])

    def test_runner_passes_symbols_file_to_zzshare_history_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "run"
            symbols_file = root / "symbols.txt"
            symbols_file.write_text("000001\n600000\n", encoding="utf-8")
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols-file",
                    str(symbols_file),
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-request-interval-seconds",
                    "0",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                history_metadata_executor,
            )

            runner.run_pipeline(context)

        fetch_history = next(
            step for step in manifest["steps"] if step["step"] == "fetch_history"
        )
        self.assertIn("--symbols-file", fetch_history["command"])
        self.assertIn(str(symbols_file), fetch_history["command"])
        self.assertNotIn("000001,600000", fetch_history["command"])

    def test_runner_writes_generated_zzshare_history_symbols_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "000001,600000",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-request-interval-seconds",
                    "0",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                history_metadata_executor,
            )

            runner.run_pipeline(context)
            generated = output / "history_symbols.txt"
            generated_text = generated.read_text(encoding="utf-8")

        fetch_history = next(
            step for step in manifest["steps"] if step["step"] == "fetch_history"
        )
        self.assertEqual("000001\n600000\n", generated_text)
        self.assertIn("--symbols-file", fetch_history["command"])
        self.assertIn(str(generated), fetch_history["command"])

    def test_read_symbols_file_rejects_empty_symbol_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            symbols_file = Path(tmpdir) / "symbols.txt"
            symbols_file.write_text(" \n,\n\t\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "symbols file is empty"):
                read_symbols_file(symbols_file)

    def test_read_symbols_file_normalizes_crlf_newlines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            symbols_file = Path(tmpdir) / "symbols.txt"
            symbols_file.write_text("000001\r\n600000\r300001\n", encoding="utf-8")

            text = read_symbols_file(symbols_file)

        self.assertEqual("000001,600000,300001", text)
        self.assertNotIn("\r", text)

    def test_read_symbols_file_strips_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            symbols_file = Path(tmpdir) / "symbols.txt"
            symbols_file.write_text("\ufeff000001\n600000\n", encoding="utf-8")

            text = read_symbols_file(symbols_file)

        self.assertEqual("000001,600000", text)
        self.assertNotIn("\ufeff", text)

    def test_read_symbols_file_reports_non_utf8_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            symbols_file = Path(tmpdir) / "symbols.txt"
            symbols_file.write_text("000001\n600000\n", encoding="utf-16")

            with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
                read_symbols_file(symbols_file)

    def test_runner_rejects_symbols_and_symbols_file_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            symbols_file = root / "symbols.txt"
            symbols_file.write_text("000001\n", encoding="utf-8")

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(root / "run"),
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "000001",
                    "--symbols-file",
                    str(symbols_file),
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--no-html-report",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("use either --symbols or --symbols-file", stderr)

    def test_runner_rejects_symbols_file_that_collides_with_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"
            output.mkdir()
            symbols_file = output / "selected_symbols.json"
            original = "000001\n600000\n"
            symbols_file.write_text(original, encoding="utf-8")

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols-file",
                    str(symbols_file),
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            self.assertEqual(2, code)
            self.assertIn("--symbols-file must not point to runner output path", stderr)
            self.assertEqual(original, symbols_file.read_text(encoding="utf-8"))

    def test_runner_plan_only_writes_steps_without_executing_commands(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertTrue(stdout.startswith("PLAN_ONLY:"), stdout)
        self.assertIn("status=planned", stdout)
        self.assertIn("commands_executed=false", stdout)
        self.assertIn("plan_only_reason=plan_only_no_commands_executed", stdout)
        self.assertIn("steps=2", stdout)
        self.assertEqual("planned", summary["status"])
        self.assertEqual("planned", manifest["status"])
        self.assertEqual("plan_only", manifest["execution_mode"])
        self.assertFalse(manifest["commands_executed"])
        self.assertTrue(manifest["plan_only"])
        self.assertEqual("plan_only_no_commands_executed", summary["plan_only_reason"])
        self.assertEqual(
            "execute_planned_workflow_to_collect_artifacts",
            summary["plan_only_next_action"],
        )
        self.assertEqual(summary["plan_only_reason"], manifest["plan_only_reason"])
        self.assertEqual(
            summary["plan_only_next_action"],
            manifest["plan_only_next_action"],
        )
        self.assertEqual({}, summary["planned_parameters"])
        self.assertEqual(summary["planned_parameters"], manifest["planned_parameters"])
        self.assertEqual(summary["source_provenance"], manifest["source_provenance"])
        self.assertEqual(
            ["validate", "score"], [step["step"] for step in manifest["steps"]]
        )
        self.assertTrue(all(step["planned"] for step in manifest["steps"]))
        self.assertTrue(all(not step["executed"] for step in manifest["steps"]))
        self.assertTrue(all(step["returncode"] is None for step in manifest["steps"]))
        self.assertEqual(
            [
                {
                    "step": "validate",
                    "planned": True,
                    "executed": False,
                    "returncode": None,
                },
                {
                    "step": "score",
                    "planned": True,
                    "executed": False,
                    "returncode": None,
                },
            ],
            summary["step_summary"],
        )
        self.assertEqual([], summary["failed_steps"])
        self.assertFalse((output / "candidates.csv").exists())
        self.assertFalse(summary["candidates_output_written"])
        self.assertFalse(manifest["candidates_output_written"])
        self.assertEqual(0, summary["candidate_rows"])
        self.assertEqual(len(frame), summary["prices_rows"])

    def test_runner_preflight_failure_does_not_mark_commands_executed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "000001",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(2, code)
        self.assertIn("missing required history options", stderr)
        self.assertFalse(manifest["commands_executed"])
        self.assertFalse(summary["commands_executed"])
        self.assertEqual([], manifest["steps"])

    def test_runner_plan_only_fetched_spot_derivation_uses_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"

            code, stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--fetch-spot",
                    "eastmoney",
                    "--fail-on-partial-spot",
                    "--derive-symbols-from-spot",
                    "--history-request-interval-seconds",
                    "0.5",
                    "--history-limit",
                    "1000",
                    "--history-max-pages",
                    "2",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertTrue(stdout.startswith("PLAN_ONLY:"), stdout)
        self.assertIn("status=planned", stdout)
        self.assertIn("commands_executed=false", stdout)
        self.assertIn("plan_only_reason=plan_only_no_commands_executed", stdout)
        self.assertIn("history_source=zzshare", stdout)
        self.assertFalse(manifest["commands_executed"])
        self.assertTrue(manifest["fail_on_partial_spot"])
        self.assertTrue(manifest["no_html_report"])
        self.assertEqual(["<derived_from_spot_snapshot>"], manifest["history_symbols"])
        self.assertEqual(0, summary["history_symbol_count"])
        self.assertEqual("planned_placeholder", summary["history_symbol_count_label"])
        self.assertEqual("zzshare", summary["history_source"])
        self.assertEqual(
            {
                "fetch_spot": "eastmoney",
                "spot_pages": 1,
                "history_source": "zzshare",
                "max_history_symbols": 50,
                "history_request_interval_seconds": 0.5,
                "history_max_concurrent_symbol_requests": 1,
                "history_limit": 1000,
                "history_max_pages": 2,
                "history_non_trading_policy": "drop",
                "history_checkpoint_batch_size": 100,
                "history_progress_interval": 100,
                "start_date": "2025-01-01",
                "end_date": "2026-01-01",
            },
            summary["planned_parameters"],
        )
        self.assertEqual(summary["planned_parameters"], manifest["planned_parameters"])
        self.assertEqual(summary["source_provenance"], manifest["source_provenance"])
        self.assertEqual(1000, summary["history_limit"])
        self.assertEqual(2, summary["history_max_pages"])
        self.assertEqual(1, summary["history_max_concurrent_symbol_requests"])
        self.assertIn("history_request_interval_seconds=0.5", stdout)
        self.assertIn("history_max_concurrent_symbol_requests=1", stdout)
        self.assertIn("history_limit=1000", stdout)
        self.assertIn("history_max_pages=2", stdout)
        self.assertEqual("plan_only_no_commands_executed", summary["plan_only_reason"])
        self.assertEqual(summary["plan_only_reason"], manifest["plan_only_reason"])
        self.assertEqual(0, summary["history_selection"]["selected_symbol_count"])
        self.assertFalse(summary["history_output_written"])
        self.assertFalse(summary["history_metadata_output_written"])
        self.assertEqual("not_written", summary["history_artifact_status"])
        self.assertFalse(manifest["history_output_written"])
        self.assertFalse(manifest["history_metadata_output_written"])
        self.assertEqual("not_written", manifest["history_artifact_status"])
        self.assertFalse(summary["history_selection"]["history_output_written"])
        self.assertFalse(
            summary["history_selection"]["history_metadata_output_written"]
        )
        self.assertEqual(
            "not_written",
            summary["history_selection"]["history_artifact_status"],
        )
        self.assertEqual(0, summary["history_failed_symbol_count"])
        self.assertEqual(0, summary["history_metadata_failed_symbol_count"])
        self.assertIn("history_symbols=planned_placeholder", stdout)
        self.assertIn("history_output_written=false", stdout)
        self.assertIn("history_artifact_status=not_written", stdout)
        self.assertNotIn("history_symbols=1", stdout)
        self.assertEqual(
            ["fetch_spot", "fetch_history", "validate", "score"],
            [step["step"] for step in manifest["steps"]],
        )
        self.assertIn("<derived_from_spot_snapshot>", manifest["steps"][1]["command"])
        self.assertFalse((output / "selected_symbols.json").exists())
        self.assertFalse((output / "history_metadata.json").exists())

    def test_runner_plan_only_fetched_spot_derivation_is_source_independent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"

            code, stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--fetch-spot",
                    "eastmoney",
                    "--fail-on-partial-spot",
                    "--derive-symbols-from-spot",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertTrue(stdout.startswith("PLAN_ONLY:"), stdout)
        self.assertEqual("baostock", manifest["history_source"])
        self.assertEqual("baostock", summary["history_source"])
        self.assertEqual(["<derived_from_spot_snapshot>"], manifest["history_symbols"])
        self.assertEqual(
            ["fetch_spot", "fetch_history", "validate", "score"],
            [step["step"] for step in manifest["steps"]],
        )
        self.assertIn("fetch_baostock_a_share.py", manifest["steps"][1]["command"][1])
        self.assertIn("<derived_from_spot_snapshot>", manifest["steps"][1]["command"])
        self.assertFalse(manifest["commands_executed"])
        self.assertFalse((output / "selected_symbols.json").exists())
        self.assertFalse((output / "history_metadata.json").exists())

    def test_runner_resume_from_uses_prior_retry_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            previous = root / "previous"
            output = root / "resume"
            previous.mkdir()
            (previous / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "output_dir": str(previous),
                        "history_source": "baostock",
                        "start_date": "2025-01-01",
                        "end_date": "2026-01-01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (previous / "selected_symbols.json").write_text(
                json.dumps(
                    {
                        "symbols": ["000001", "000002", "600000", "600001"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (previous / "history_metadata.json").write_text(
                json.dumps(
                    {
                        "failed_symbols": [{"symbol": "000002", "error": "timeout"}],
                        "empty_symbols": ["600000"],
                        "possibly_truncated_symbols": ["600001"],
                        "invalid_symbols": ["600001"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--resume-from",
                    str(previous / "run_manifest.json"),
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertEqual("planned", summary["status"])
        self.assertEqual("prior_history_retry_plan", manifest["resume_symbol_source"])
        self.assertEqual(2, manifest["resume_retry_symbol_count"])
        self.assertEqual(["000002", "600000"], manifest["history_symbols"])
        self.assertEqual("000002,600000", manifest["symbols"])
        self.assertEqual("baostock", manifest["history_source"])
        self.assertEqual("2025-01-01", manifest["start_date"])
        self.assertEqual("2026-01-01", manifest["end_date"])
        self.assertEqual("resume_retry_symbols", selected["source"])
        self.assertEqual(["000002", "600000"], selected["symbols"])
        self.assertEqual(
            "history_fetch_resume_retry_symbols_generic",
            manifest["execution_path"],
        )
        fetch_history = manifest["steps"][0]
        self.assertEqual("fetch_history", fetch_history["step"])
        self.assertIn("000002,600000", fetch_history["command"])

    def test_runner_resume_from_resolves_relative_output_dir_from_manifest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            previous = root / "previous"
            artifacts = previous / "artifacts"
            output = root / "resume"
            artifacts.mkdir(parents=True)
            (previous / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "output_dir": "artifacts",
                        "history_source": "baostock",
                        "start_date": "2025-01-01",
                        "end_date": "2026-01-01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (artifacts / "selected_symbols.json").write_text(
                json.dumps({"symbols": ["000001", "000002"]}) + "\n",
                encoding="utf-8",
            )
            (artifacts / "history_metadata.json").write_text(
                json.dumps({"failed_symbols": ["000002"]}) + "\n",
                encoding="utf-8",
            )

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--resume-from",
                    str(previous / "run_manifest.json"),
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(0, code, stderr)
        self.assertEqual(str(artifacts), manifest["resume_prior_output_dir"])
        self.assertEqual(["000002"], manifest["history_symbols"])

    def test_resume_output_dir_uses_manifest_parent_when_relative_path_matches(
        self,
    ) -> None:
        manifest_path = Path("/tmp/a-share-pass1/run_manifest.json")

        output = runner.resume_output_dir(
            {"output_dir": "a-share-pass1"},
            manifest_path,
        )

        self.assertEqual(Path("/tmp/a-share-pass1"), output)

    def test_resume_output_dir_uses_manifest_parent_for_nested_relative_suffix(
        self,
    ) -> None:
        manifest_path = Path("/tmp/runs/pass1/run_manifest.json")

        output = runner.resume_output_dir(
            {"output_dir": "runs/pass1"},
            manifest_path,
        )

        self.assertEqual(Path("/tmp/runs/pass1"), output)

    def test_runner_resume_from_inherits_zzshare_fetch_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            previous = root / "previous"
            output = root / "resume"
            previous.mkdir()
            (previous / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "output_dir": str(previous),
                        "history_source": "zzshare",
                        "history_adjust": "hfq",
                        "history_http_url": "https://example.test/api",
                        "history_timeout_seconds": "8",
                        "history_request_interval_seconds": "0.2",
                        "history_max_concurrent_symbol_requests": "5",
                        "history_max_rate_limit_sleep_seconds": "40",
                        "history_max_429_events": "4",
                        "history_max_runtime_seconds": "1200",
                        "history_limit": "500",
                        "history_max_pages": "3",
                        "history_non_trading_policy": "keep",
                        "start_date": "2025-01-01",
                        "end_date": "2026-01-01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (previous / "selected_symbols.json").write_text(
                json.dumps({"symbols": ["000001", "000002"]}) + "\n",
                encoding="utf-8",
            )
            (previous / "history_metadata.json").write_text(
                json.dumps({"failed_symbols": ["000002"]}) + "\n",
                encoding="utf-8",
            )

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--resume-from",
                    str(previous / "run_manifest.json"),
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(0, code, stderr)
        self.assertEqual(
            [
                "history_source",
                "start_date",
                "end_date",
                "history_adjust",
                "history_timeout_seconds",
                "history_request_interval_seconds",
                "history_max_concurrent_symbol_requests",
                "history_max_rate_limit_sleep_seconds",
                "history_max_429_events",
                "history_max_runtime_seconds",
                "history_limit",
                "history_max_pages",
                "history_non_trading_policy",
            ],
            manifest["resume_inherited_options"],
        )
        self.assertEqual("zzshare", manifest["history_source"])
        self.assertEqual("hfq", manifest["history_adjust"])
        self.assertEqual("", manifest["history_http_url"])
        self.assertEqual(
            ["history_http_url"],
            manifest["resume_sensitive_options_requiring_explicit_input"],
        )
        self.assertEqual(8.0, manifest["history_timeout_seconds"])
        self.assertEqual(0.2, manifest["history_request_interval_seconds"])
        self.assertEqual(5, manifest["history_max_concurrent_symbol_requests"])
        self.assertEqual(40.0, manifest["history_max_rate_limit_sleep_seconds"])
        self.assertEqual(4, manifest["history_max_429_events"])
        self.assertEqual(1200.0, manifest["history_max_runtime_seconds"])
        self.assertEqual(500, manifest["history_limit"])
        self.assertEqual(3, manifest["history_max_pages"])
        self.assertEqual("keep", manifest["history_non_trading_policy"])
        fetch_history = manifest["steps"][0]["command"]
        self.assertIn("--adjust", fetch_history)
        self.assertIn("hfq", fetch_history)
        self.assertIn("--max-concurrent-symbol-requests", fetch_history)
        self.assertIn("5", fetch_history)
        self.assertIn("--max-runtime-seconds", fetch_history)
        self.assertIn("1200.0", fetch_history)
        self.assertIn("--non-trading-policy", fetch_history)
        self.assertIn("keep", fetch_history)
        self.assertNotIn("--http-url", fetch_history)
        self.assertNotIn("https://example.test/api", fetch_history)

    def test_runner_resume_empty_retry_message_includes_unprocessed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            previous = root / "previous"
            output = root / "resume"
            previous.mkdir()
            (previous / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "output_dir": str(previous),
                        "history_source": "zzshare",
                        "start_date": "2025-01-01",
                        "end_date": "2026-01-01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (previous / "selected_symbols.json").write_text(
                json.dumps({"symbols": ["000001"]}) + "\n",
                encoding="utf-8",
            )
            (previous / "history_metadata.json").write_text(
                json.dumps(
                    {
                        "failed_symbols": [],
                        "empty_symbols": [],
                        "possibly_truncated_symbols": [],
                        "unprocessed_symbols": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--resume-from",
                    str(previous / "run_manifest.json"),
                    "--plan-only",
                    "--no-html-report",
                ]
            )

        self.assertEqual(2, code)
        self.assertIn("unprocessed", stderr)

    def test_runner_resume_from_inherits_yfinance_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            previous = root / "previous"
            output = root / "resume"
            previous.mkdir()
            (previous / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "output_dir": str(previous),
                        "history_source": "yfinance",
                        "history_timeout_seconds": "9.5",
                        "start_date": "2025-01-01",
                        "end_date": "2026-01-01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (previous / "selected_symbols.json").write_text(
                json.dumps({"symbols": ["MSFT", "AAPL"]}) + "\n",
                encoding="utf-8",
            )
            (previous / "history_metadata.json").write_text(
                json.dumps({"failed_symbols": ["MSFT"]}) + "\n",
                encoding="utf-8",
            )

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--resume-from",
                    str(previous / "run_manifest.json"),
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(0, code, stderr)
        self.assertEqual(
            ["history_source", "start_date", "end_date", "history_timeout_seconds"],
            manifest["resume_inherited_options"],
        )
        self.assertEqual("yfinance", manifest["history_source"])
        self.assertEqual(9.5, manifest["history_timeout_seconds"])
        fetch_history = manifest["steps"][0]["command"]
        self.assertIn("fetch_yfinance_ohlcv.py", fetch_history[1])
        self.assertIn("--timeout-seconds", fetch_history)
        self.assertIn("9.5", fetch_history)

    def test_runner_resume_from_does_not_inherit_source_specific_options_when_source_changes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            previous = root / "previous"
            output = root / "resume"
            previous.mkdir()
            (previous / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "output_dir": str(previous),
                        "history_source": "zzshare",
                        "history_adjust": "hfq",
                        "history_http_url": "https://example.test/api",
                        "history_timeout_seconds": "8",
                        "history_request_interval_seconds": "0.2",
                        "history_max_concurrent_symbol_requests": "5",
                        "history_limit": "500",
                        "history_max_pages": "3",
                        "start_date": "2025-01-01",
                        "end_date": "2026-01-01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (previous / "selected_symbols.json").write_text(
                json.dumps({"symbols": ["000001", "000002"]}) + "\n",
                encoding="utf-8",
            )
            (previous / "history_metadata.json").write_text(
                json.dumps({"failed_symbols": ["000002"]}) + "\n",
                encoding="utf-8",
            )

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--resume-from",
                    str(previous / "run_manifest.json"),
                    "--history-source",
                    "baostock",
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(0, code, stderr)
        self.assertEqual(
            ["start_date", "end_date"], manifest["resume_inherited_options"]
        )
        self.assertEqual("baostock", manifest["history_source"])
        self.assertEqual("", manifest["history_adjust"])
        self.assertEqual("", manifest["history_http_url"])
        fetch_history = manifest["steps"][0]["command"]
        self.assertNotIn("--http-url", fetch_history)
        self.assertNotIn("https://example.test/api", fetch_history)

    def test_runner_resume_from_same_output_dir_reads_artifacts_before_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"
            output.mkdir()
            manifest_path = output / "run_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "output_dir": str(output),
                        "history_source": "baostock",
                        "start_date": "2025-01-01",
                        "end_date": "2026-01-01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (output / "selected_symbols.json").write_text(
                json.dumps({"symbols": ["000001", "000002"]}) + "\n",
                encoding="utf-8",
            )
            (output / "history_metadata.json").write_text(
                json.dumps({"failed_symbols": ["000002"]}) + "\n",
                encoding="utf-8",
            )

            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--resume-from",
                    str(manifest_path),
                    "--plan-only",
                    "--no-html-report",
                ]
            )

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        self.assertEqual(0, code, stderr)
        self.assertEqual(["000002"], manifest["history_symbols"])
        self.assertEqual("000002", manifest["symbols"])
        self.assertEqual("resume_retry_symbols", selected["source"])
        self.assertEqual(["000002"], selected["symbols"])

    def test_runner_resume_failure_clears_reused_output_files(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            previous = root / "previous"
            frame.to_csv(prices, index=False)
            previous.mkdir()
            (previous / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "output_dir": str(previous),
                        "history_source": "baostock",
                        "start_date": "2025-01-01",
                        "end_date": "2026-01-01",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            code, _stdout, stderr = call_runner(
                ["--prices-input", str(prices), "--output-dir", str(output)]
            )
            self.assertEqual(0, code, stderr)
            self.assertTrue((output / "candidates.csv").exists())

            # Prior resume artifacts are intentionally incomplete; the failure
            # path must clear stale candidate outputs from the reused directory.
            code, _stdout, stderr = call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--resume-from",
                    str(previous / "run_manifest.json"),
                    "--no-html-report",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(2, code)
        self.assertIn("resume artifact not found", stderr)
        self.assertFalse((output / "candidates.csv").exists())
        self.assertFalse((output / "diagnostics.csv").exists())
        self.assertEqual("failed", summary["status"])
        self.assertEqual("FileNotFoundError", summary["run_error_type"])
        self.assertFalse(summary["candidates_output_written"])
        self.assertEqual(0, summary["candidate_rows"])

    def test_history_fetch_metadata_propagates_to_summary_stdout_and_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
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
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                history_metadata_executor,
            )

            runner.run_pipeline(context)
            summary = summary_view(manifest, "completed")
            stdout = StringIO()
            with redirect_stdout(stdout):
                runner.helpers.print_summary(manifest, output)
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertEqual("external_fetch", summary["source_type"])
        self.assertTrue(summary["real_market_data"])
        self.assertEqual("baostock", summary["input_metadata"]["source"])
        self.assertEqual(
            "baostock_history_fetch",
            summary["input_metadata"]["source_scope"],
        )
        self.assertEqual("baostock_history_fetch", summary["source_scope"])
        self.assertEqual("baostock_history_fetch", summary["runner_source_scope"])
        self.assertIn("source_scope=baostock_history_fetch", stdout.getvalue())
        self.assertIn("runner_source_scope=baostock_history_fetch", stdout.getvalue())
        self.assertIn("history_source=baostock", stdout.getvalue())
        self.assertEqual("baostock", summary["input_metadata"]["history_provider"])
        self.assertEqual(0, summary["history_rows"])
        self.assertEqual(0, summary["history_metadata_symbol_count"])
        self.assertEqual(1, summary["history_requested_symbol_count"])
        self.assertTrue(summary["history_partial_result"])
        self.assertFalse(summary["history_output_written"])
        self.assertEqual("metadata_only", summary["history_artifact_status"])
        self.assertEqual(1, summary["history_failed_symbol_count"])
        self.assertEqual(1, summary["history_metadata_failed_symbol_count"])
        self.assertEqual(1, summary["history_empty_symbol_count"])
        self.assertEqual(0, summary["history_possibly_truncated_symbol_count"])
        self.assertEqual(0, summary["history_metadata_fallback_error_count"])
        self.assertEqual("3", summary["input_metadata"]["history_adjustflag"])
        self.assertEqual(1, summary["input_metadata"]["history_failed_symbol_count"])
        self.assertEqual(0, summary["input_metadata"]["history_fallback_error_count"])
        self.assertFalse(summary["input_metadata"]["history_output_written"])
        self.assertTrue(summary["input_metadata"]["history_metadata_output_written"])
        self.assertEqual(1, summary["history_selection"]["history_empty_symbol_count"])
        self.assertEqual(
            ["000001"], summary["history_selection"]["history_empty_symbols"]
        )
        self.assertTrue(summary["history_selection"]["history_partial_result"])
        self.assertFalse(summary["history_selection"]["history_output_written"])
        self.assertEqual(
            "metadata_only",
            summary["history_selection"]["history_artifact_status"],
        )
        self.assertEqual("3", summary["history_selection"]["history_adjustflag"])
        self.assertIn("metadata_source=external_fetch", stdout.getvalue())
        self.assertIn("real_market_data=true", stdout.getvalue())
        self.assertIn("history_rows=0", stdout.getvalue())
        self.assertIn("history_metadata_symbol_count=0", stdout.getvalue())
        self.assertIn("history_requested_symbol_count=1", stdout.getvalue())
        self.assertIn("history_partial_result=true", stdout.getvalue())
        self.assertIn("history_output_written=false", stdout.getvalue())
        self.assertIn("history_artifact_status=metadata_only", stdout.getvalue())
        self.assertIn("history_empty_symbol_count=1", stdout.getvalue())
        self.assertIn("history_adjustflag=3", stdout.getvalue())
        for row in candidate_rows + diagnostic_rows:
            self.assertEqual("external_fetch", row["source_type"])
            self.assertEqual("True", row["real_market_data"])
            self.assertEqual("baostock", row["history_provider"])
            self.assertEqual("1", row["history_failed_symbol_count"])
            self.assertEqual("0", row["history_possibly_truncated_symbol_count"])
            self.assertEqual("0", row["history_invalid_rows"])
            self.assertEqual("0", row["history_fallback_error_count"])
            self.assertEqual("False", row["history_output_written"])
            self.assertEqual("True", row["history_metadata_output_written"])
            self.assertEqual("3", row["history_adjustflag"])

    def test_zzshare_history_quality_metadata_propagates_to_runner_surfaces(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                zzshare_quality_executor,
            )

            runner.run_pipeline(context)
            summary = summary_view(manifest, "completed")
            stdout = StringIO()
            with redirect_stdout(stdout):
                runner.helpers.print_summary(manifest, output)
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        metadata = summary["input_metadata"]
        history = summary["history_selection"]
        self.assertEqual("zzshare", summary["source"])
        self.assertEqual("zzshare", metadata["source"])
        self.assertFalse(metadata["history_token_configured"])
        self.assertEqual("all", metadata["history_fields"])
        self.assertEqual(0.0, metadata["history_request_interval_seconds"])
        self.assertEqual(6, metadata["history_max_concurrent_symbol_requests"])
        self.assertEqual(30.0, metadata["history_max_rate_limit_sleep_seconds"])
        self.assertEqual(2, metadata["history_max_429_events"])
        self.assertEqual(600.0, metadata["history_max_runtime_seconds"])
        self.assertEqual(1, metadata["history_limit"])
        self.assertEqual(2, metadata["history_max_pages"])
        self.assertEqual(2, metadata["history_invalid_rows"])
        self.assertEqual(1, metadata["history_dropped_invalid_rows"])
        self.assertEqual(3, metadata["history_non_trading_rows"])
        self.assertEqual(4, metadata["history_tradestatus_missing_rows"])
        self.assertEqual(1, metadata["history_possibly_truncated_symbol_count"])
        self.assertFalse(history["history_token_configured"])
        self.assertEqual("all", history["history_fields"])
        self.assertEqual(0.0, history["history_request_interval_seconds"])
        self.assertEqual(6, history["history_max_concurrent_symbol_requests"])
        self.assertEqual(30.0, history["history_max_rate_limit_sleep_seconds"])
        self.assertEqual(2, history["history_max_429_events"])
        self.assertEqual(600.0, history["history_max_runtime_seconds"])
        self.assertEqual(1, history["history_limit"])
        self.assertEqual(2, history["history_max_pages"])
        self.assertEqual(2, history["history_invalid_rows"])
        self.assertEqual(1, history["history_dropped_invalid_rows"])
        self.assertIn("history_token_configured=false", stdout.getvalue())
        self.assertIn("history_fields=all", stdout.getvalue())
        self.assertIn("history_request_interval_seconds=0.0", stdout.getvalue())
        self.assertIn("history_max_concurrent_symbol_requests=6", stdout.getvalue())
        self.assertIn("history_limit=1", stdout.getvalue())
        self.assertIn("history_max_pages=2", stdout.getvalue())
        self.assertIn("history_invalid_rows=2", stdout.getvalue())
        self.assertIn("history_dropped_invalid_rows=1", stdout.getvalue())
        self.assertNotIn("input_token_configured=unknown", stdout.getvalue())
        self.assertNotIn("input_partial_result=unknown", stdout.getvalue())
        for row in candidate_rows + diagnostic_rows:
            self.assertEqual("zzshare", row["history_provider"])
            self.assertEqual("False", row["history_token_configured"])
            self.assertEqual("all", row["history_fields"])
            self.assertEqual("0.0", row["history_request_interval_seconds"])
            self.assertEqual("6", row["history_max_concurrent_symbol_requests"])
            self.assertEqual("30.0", row["history_max_rate_limit_sleep_seconds"])
            self.assertEqual("2", row["history_max_429_events"])
            self.assertEqual("600.0", row["history_max_runtime_seconds"])
            self.assertEqual("1", row["history_limit"])
            self.assertEqual("2", row["history_max_pages"])
            self.assertEqual("1", row["history_possibly_truncated_symbol_count"])
            self.assertEqual("2", row["history_invalid_rows"])
            self.assertEqual("1", row["history_dropped_invalid_rows"])
            self.assertEqual("3", row["history_non_trading_rows"])
            self.assertEqual("4", row["history_tradestatus_missing_rows"])

    def test_embedded_csv_provenance_survives_runner_without_metadata_file(
        self,
    ) -> None:
        config = load_config("prediction_profile_config.json")
        config["thresholds"] = {
            "min_total_score": -10.0,
            "min_prediction_score": 0.0,
            "min_momentum_score": -10.0,
            "min_rsi": 0.0,
            "max_rsi": 100.0,
            "max_volatility": 10.0,
            "min_volume": 0.0,
            "min_close": 0.0,
            "min_history_rows": 120,
        }
        frame = build_frame(
            include_turn=True,
            include_prediction=True,
            include_tradability=True,
        )
        embedded_provenance = embedded_csv_provenance()
        for column, value in embedded_provenance.items():
            frame[column] = value
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            output = root / "run"
            config_path = root / "config.json"
            frame.to_csv(prices, index=False)
            config_path.write_text(json.dumps(config), encoding="utf-8")

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "prediction",
                    "--config",
                    str(config_path),
                    "--no-html-report",
                ]
            )

            self.assertEqual(0, code, stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertEqual("unknown", summary["source_type"])
        self.assertEqual("csv_embedded_probe", summary["score"]["source_type"])
        self.assertEqual(False, summary["score"]["real_market_data"])
        self.assertEqual(embedded_provenance, summary["input_csv_provenance"])
        self.assertIn("runner_metadata_source=unknown", stdout)
        self.assertIn("input_csv_source_type=csv_embedded_probe", stdout)
        self.assertIn("input_csv_real_market_data=false", stdout)
        assert_rows_keep_embedded_provenance(
            self,
            candidate_rows + diagnostic_rows,
            embedded_provenance,
        )

    def test_local_prices_metadata_preserves_partial_fetch_scope(self) -> None:
        frame = build_frame(days=130, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            (root / "metadata.json").write_text(
                json.dumps(
                    {
                        "source_type": "external_fetch",
                        "source": "yfinance",
                        "source_scope": "yfinance_history_fetch",
                        "market": "A-share",
                        "market_label_only": True,
                        "source_claim_boundary": (
                            "market_label_not_source_exchange_or_calendar_proof"
                        ),
                        "adjustment": "auto_adjust_false_close",
                        "requested_symbols": ["AAPL", "MSFT"],
                        "symbol_count": 1,
                        "rows": int(len(frame)),
                        "failed_symbols": [{"symbol": "MSFT", "error": "timeout"}],
                        "empty_symbols": [],
                        "possibly_truncated_symbols": ["AAPL"],
                        "token_configured": False,
                        "invalid_rows": 2,
                        "dropped_invalid_rows": 1,
                        "output_written": True,
                        "metadata_output_written": True,
                        "real_market_data": "unknown",
                    }
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "generic",
                    "--no-html-report",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertEqual(0, code, stderr)
        metadata = summary["input_metadata"]
        self.assertEqual("yfinance", metadata["source"])
        self.assertEqual("yfinance_history_fetch", metadata["source_scope"])
        self.assertFalse(metadata["token_configured"])
        self.assertTrue(metadata["input_partial_result"])
        self.assertEqual(["AAPL", "MSFT"], metadata["requested_symbols"])
        self.assertEqual(1, metadata["symbol_count"])
        self.assertEqual(1, metadata["input_failed_symbol_count"])
        self.assertEqual(0, metadata["input_empty_symbol_count"])
        self.assertEqual(1, metadata["input_possibly_truncated_symbol_count"])
        self.assertEqual(2, metadata["input_invalid_rows"])
        self.assertEqual(1, metadata["input_dropped_invalid_rows"])
        self.assertEqual("auto_adjust_false_close", metadata["adjustment"])
        self.assertEqual("yfinance_history_fetch", summary["source_scope"])
        self.assertEqual("local_prices_input", summary["runner_source_scope"])
        self.assertIn("input_partial_result=true", stdout)
        self.assertIn("input_metadata_file=metadata.json", stdout)
        self.assertIn("source_scope=yfinance_history_fetch", stdout)
        self.assertIn("runner_source_scope=local_prices_input", stdout)
        self.assertIn("input_token_configured=false", stdout)
        self.assertIn("input_failed_symbol_count=1", stdout)
        self.assertIn("input_possibly_truncated_symbol_count=1", stdout)
        self.assertIn("input_invalid_rows=2", stdout)
        self.assertIn("input_dropped_invalid_rows=1", stdout)
        self.assertIn("input_symbol_count=1/2", stdout)
        self.assertIn("input_requested_symbols=AAPL,MSFT", stdout)
        self.assertIn("input_failed_symbols=MSFT:timeout", stdout)
        self.assertIn("input_empty_symbols=none", stdout)
        self.assertIn("input_output_written=true", stdout)

    def test_metadata_list_stdout_truncates_large_symbol_lists(self) -> None:
        symbols = [f"{index:06d}" for index in range(25)]

        text = runner.helpers.metadata_list_stdout(symbols)

        self.assertTrue(text.startswith("000000,000001,000002"))
        self.assertIn("__truncated__=5", text)
        self.assertIn("__total__=25", text)
        self.assertNotIn("000020", text)

    def test_step_summary_includes_executed_duration_when_recorded(self) -> None:
        result = subprocess.CompletedProcess(["python"], 0, "OK\n", "")
        result.duration_seconds = 1.25
        record = runner.step_record(runner.Step("validate", ["python"]), result)
        manifest = {
            "runner": "run_today_a_share_selection",
            "mode": "generic",
            "prediction_mode": False,
            "lightgbm_not_used": True,
            "source_scope": "local_prices_input",
            "output_dir": "",
            "run_outputs_initialized": True,
            "steps": [record],
        }

        summary = summary_view(manifest, "completed")

        self.assertEqual(1.25, record["duration_seconds"])
        self.assertEqual(1.25, summary["step_summary"][0]["duration_seconds"])

    def test_local_prices_use_history_metadata_when_metadata_json_missing(self) -> None:
        frame = build_frame(days=130, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            (root / "history_metadata.json").write_text(
                json.dumps(
                    {
                        "source_type": "external_fetch",
                        "source": "zzshare",
                        "source_scope": "zzshare_history_fetch",
                        "source_claim_boundary": (
                            "zzshare_external_api_not_broker_order_or_long_term_stability_proof"
                        ),
                        "requested_symbols": ["000001", "600000"],
                        "symbol_count": 2,
                        "rows": int(len(frame)),
                        "failed_symbols": [],
                        "empty_symbols": [],
                        "possibly_truncated_symbols": [],
                        "token_configured": False,
                        "output_written": True,
                        "metadata_output_written": True,
                        "real_market_data": True,
                    }
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "generic",
                    "--no-html-report",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertEqual(0, code, stderr)
        self.assertEqual("zzshare", summary["input_metadata"]["source"])
        self.assertEqual(
            "zzshare_history_fetch",
            summary["input_metadata"]["source_scope"],
        )
        self.assertEqual(
            "history_metadata.json",
            summary["input_metadata"]["input_metadata_file"],
        )
        self.assertEqual("zzshare_history_fetch", summary["source_scope"])
        self.assertIn("source_scope=zzshare_history_fetch", stdout)
        self.assertIn("input_metadata_file=history_metadata.json", stdout)
        for row in candidate_rows + diagnostic_rows:
            self.assertEqual("zzshare_history_fetch", row["source_scope"])
            self.assertEqual("False", row["input_token_configured"])
            self.assertEqual("", row["input_partial_result"])
            self.assertEqual("0", row["input_possibly_truncated_symbol_count"])
        self.assertIn(
            "candidate_field_coverage=industry:0/0,one_year_pct_chg:0/0,market_cap:0/0,pe_ttm:0/0,pb_lf:0/0",
            stdout,
        )

    def test_local_clean_pool_metadata_propagates_to_outputs(self) -> None:
        frame = build_frame(days=130, include_tradability=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            output = root / "run"
            frame.to_csv(prices, index=False)
            (root / "metadata.json").write_text(
                json.dumps(
                    {
                        "source_type": "external_fetch",
                        "source": "zzshare",
                        "source_scope": "clean_history_pool",
                        "source_claim_boundary": (
                            "clean_history_pool_from_existing_artifacts_not_full_market_proof"
                        ),
                        "requested_symbols": ["000001", "600000"],
                        "symbol_count": 2,
                        "rows": int(len(frame)),
                        "failed_symbols": [],
                        "empty_symbols": [],
                        "possibly_truncated_symbols": [],
                        "clean_pool_generated_at": "2026-07-09T09:40:44+08:00",
                        "clean_pool_source_prices": str(root / "raw_prices.csv"),
                        "clean_pool_removed_symbol_count": 3,
                        "clean_pool_reason_counts": {
                            "empty_history": 1,
                            "short_history": 2,
                        },
                        "partial_result": True,
                        "output_written": True,
                        "metadata_output_written": True,
                        "real_market_data": True,
                    }
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                    "--mode",
                    "generic",
                ]
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertEqual(0, code, stderr)
        metadata = summary["input_metadata"]
        self.assertEqual(3, metadata["clean_pool_removed_symbol_count"])
        self.assertEqual(3, metadata["input_clean_pool_removed_symbol_count"])
        self.assertEqual(
            {"empty_history": 1, "short_history": 2},
            metadata["input_clean_pool_reason_counts"],
        )
        self.assertIn("input_clean_pool_removed_symbol_count=3", stdout)
        self.assertIn(
            'input_clean_pool_reason_counts={"empty_history":1,"short_history":2}',
            stdout,
        )
        self.assertIn("input_metadata.clean_pool_removed_symbol_count", report)
        self.assertIn("input_metadata.input_clean_pool_removed_symbol_count", report)
        for row in candidate_rows + diagnostic_rows:
            self.assertEqual("3", row["clean_pool_removed_symbol_count"])
            self.assertEqual("3", row["input_clean_pool_removed_symbol_count"])
            self.assertEqual(
                '{"empty_history":1,"short_history":2}',
                row["input_clean_pool_reason_counts"],
            )

    def test_history_fallback_marks_partial_in_summary_stdout_and_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "akshare",
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                history_fallback_executor,
            )

            runner.run_pipeline(context)
            summary = summary_view(manifest, "completed")
            stdout = StringIO()
            with redirect_stdout(stdout):
                runner.helpers.print_summary(manifest, output)
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertTrue(summary["input_metadata"]["history_partial_result"])
        self.assertEqual("hfq", summary["input_metadata"]["history_adjust"])
        self.assertEqual(1, summary["input_metadata"]["history_fallback_error_count"])
        self.assertTrue(summary["history_selection"]["history_partial_result"])
        self.assertEqual("hfq", summary["history_selection"]["history_adjust"])
        self.assertEqual(
            1,
            summary["history_selection"]["history_metadata_fallback_error_count"],
        )
        self.assertIn("history_partial_result=true", stdout.getvalue())
        self.assertIn("history_fallback_error_count=1", stdout.getvalue())
        self.assertIn("history_adjust=hfq", stdout.getvalue())
        for row in candidate_rows + diagnostic_rows:
            self.assertEqual("True", row["history_partial_result"])
            self.assertEqual("1", row["history_fallback_error_count"])
            self.assertEqual("hfq", row["history_adjust"])

    def test_runner_can_derive_history_symbols_from_spot_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text(
                "\n".join(
                    [
                        "symbol,name,spot_price,spot_amount,spot_pct_chg",
                        "000001,Alpha,8.2,200000000,1.2",
                        "600001,HighPrice,12.0,300000000,5.0",
                        "000002,LowAmount,8.0,1000,9.0",
                        "300001,ST Bad,8.0,300000000,9.0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--max-history-symbols",
                    "1",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )
            (output / "history_metadata.json").write_text(
                json.dumps(
                    {"failed_symbols": [{"symbol": "600001", "error": "offline"}]}
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                summary = summary_view(manifest, "completed")
                runner.helpers.print_summary(manifest, output)

        self.assertEqual(["000001"], manifest["history_symbols"])
        self.assertEqual(
            "history_fetch_spot_derived_explicit_limit_with_local_spot_generic",
            manifest["execution_path"],
        )
        self.assertEqual(
            "derive_symbols_from_spot+explicit_history_limit+spot_input",
            manifest["execution_path_reason"],
        )
        self.assertEqual("spot_derived_limited_pool", manifest["coverage_class"])
        self.assertFalse(manifest["full_market_claim_allowed"])
        self.assertEqual(
            "spot_derived_explicit_limit_requires_artifact_review",
            manifest["full_market_claim_boundary"],
        )
        self.assertEqual(["000001"], selected["selected_symbols"])
        self.assertEqual(1, selected["filtered_spot_rows"])
        self.assertEqual(1, selected["selected_symbol_count"])
        self.assertEqual(1, selected["max_history_symbols"])
        self.assertEqual("explicit_user_input", selected["history_symbol_limit_source"])
        self.assertEqual(4, summary["history_selection"]["raw_spot_rows"])
        self.assertEqual(
            "history_fetch_spot_derived_explicit_limit_with_local_spot_generic",
            summary["execution_path"],
        )
        self.assertEqual(
            "derive_symbols_from_spot+explicit_history_limit+spot_input",
            summary["execution_path_reason"],
        )
        self.assertEqual("spot_derived_limited_pool", summary["coverage_class"])
        self.assertFalse(summary["full_market_claim_allowed"])
        self.assertEqual(
            "spot_derived_explicit_limit_requires_artifact_review",
            summary["full_market_claim_boundary"],
        )
        self.assertEqual(1, summary["history_selection"]["filtered_spot_rows"])
        self.assertEqual(1, summary["history_selection"]["selected_symbol_count"])
        self.assertEqual(1, summary["history_selection"]["max_history_symbols"])
        self.assertEqual(
            "explicit_user_input",
            summary["history_selection"]["history_symbol_limit_source"],
        )
        self.assertFalse(summary["history_selection"]["allow_partial_history"])
        self.assertEqual(
            1,
            summary["history_selection"]["history_metadata_failed_symbol_count"],
        )
        self.assertTrue(summary["selected_symbols_output_written"])
        self.assertTrue(summary["history_metadata_output_written"])
        self.assertIn("history_symbols=1", stdout.getvalue())
        self.assertIn(
            "execution_path=history_fetch_spot_derived_explicit_limit_with_local_spot_generic",
            stdout.getvalue(),
        )
        self.assertIn("coverage_class=spot_derived_limited_pool", stdout.getvalue())
        self.assertIn("full_market_claim_allowed=false", stdout.getvalue())
        self.assertIn(
            "full_market_claim_boundary=spot_derived_explicit_limit_requires_artifact_review",
            stdout.getvalue(),
        )
        self.assertIn("raw_spot_rows=4", stdout.getvalue())
        self.assertIn("filtered_spot_rows=1", stdout.getvalue())
        self.assertIn("max_history_symbols=1", stdout.getvalue())
        self.assertIn(
            "history_symbol_limit_source=explicit_user_input",
            stdout.getvalue(),
        )
        self.assertIn("allow_partial_history=false", stdout.getvalue())
        self.assertIn("candidate_field_coverage=unknown", stdout.getvalue())

    def test_runner_can_derive_all_valid_spot_symbols_without_prefilters(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text(
                "\n".join(
                    [
                        "symbol,name,spot_price,spot_amount,spot_pct_chg",
                        "000001,Alpha,8.2,200000000,1.2",
                        "600001,HighPrice,12.0,300000000,5.0",
                        "000002,LowAmount,8.0,1000,9.0",
                        "300001,ST Bad,8.0,300000000,9.0",
                        "688825,MissingPrice,-,-,-",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--derive-all-spot-symbols",
                    "--max-history-symbols",
                    "10",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        self.assertTrue(manifest["derive_all_spot_symbols"])
        self.assertEqual(
            ["000001", "000002", "300001", "600001", "688825"],
            selected["selected_symbols"],
        )
        self.assertEqual(5, selected["filtered_spot_rows"])
        self.assertEqual(5, selected["selected_symbol_count"])
        self.assertEqual("all_valid_spot_symbols", selected["spot_symbol_filter_mode"])
        self.assertFalse(selected["spot_thresholds_applied"])
        self.assertFalse(selected["filters"]["thresholds_applied"])

    def test_explicit_history_symbols_do_not_report_spot_sample_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
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
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                summary = summary_view(manifest, "completed")
                runner.helpers.print_summary(manifest, output)

        self.assertEqual(
            "history_fetch_explicit_symbols_generic", manifest["execution_path"]
        )
        self.assertEqual("explicit_symbols", manifest["execution_path_reason"])
        self.assertEqual("explicit_symbol_pool", manifest["coverage_class"])
        self.assertEqual(
            "explicit_symbols_not_full_market_scan",
            manifest["full_market_claim_boundary"],
        )
        self.assertEqual(["000001"], selected["symbols"])
        self.assertEqual(1, selected["selected_symbol_count"])
        self.assertEqual(
            "explicit_symbols_no_spot_limit", selected["history_symbol_limit_source"]
        )
        self.assertEqual("explicit_symbols", summary["history_selection"]["source"])
        self.assertEqual(1, summary["history_selection"]["selected_symbol_count"])
        self.assertEqual("", summary["history_selection"]["max_history_symbols"])
        self.assertEqual(
            "explicit_symbols_no_spot_limit",
            summary["history_selection"]["history_symbol_limit_source"],
        )
        self.assertIn("max_history_symbols=unknown", stdout.getvalue())
        self.assertIn(
            "history_symbol_limit_source=explicit_symbols_no_spot_limit",
            stdout.getvalue(),
        )

    def test_yfinance_history_market_reads_source_config_not_output_dir_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            stale_config = output / "hong_kong_generic_config.json"
            stale_config.write_text(
                json.dumps({"universe": {"market": "US"}}),
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "yfinance",
                    "--symbols",
                    "00700,HK.09988,08001.HK",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--config",
                    str(SCRIPTS / "hong_kong_generic_config.json"),
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                yfinance_hk_executor,
            )

            runner.run_pipeline(context)

        fetch_step = manifest["steps"][0]
        market_index = fetch_step["command"].index("--market")
        self.assertEqual("HK", fetch_step["command"][market_index + 1])

    def test_explicit_history_symbols_with_limit_report_limited_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "000001,000002",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--max-history-symbols",
                    "50",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                summary = summary_view(manifest, "completed")
                runner.helpers.print_summary(manifest, output)

        self.assertEqual(
            "history_fetch_explicit_symbols_explicit_limit_generic",
            manifest["execution_path"],
        )
        self.assertEqual(
            "explicit_symbols+explicit_history_limit",
            manifest["execution_path_reason"],
        )
        self.assertEqual("explicit_symbol_limited_pool", manifest["coverage_class"])
        self.assertEqual(
            "explicit_symbols_explicit_limit_requires_artifact_review",
            manifest["full_market_claim_boundary"],
        )
        self.assertEqual(["000001", "000002"], selected["symbols"])
        self.assertEqual(2, summary["history_selection"]["selected_symbol_count"])
        self.assertEqual("", summary["history_selection"]["max_history_symbols"])
        self.assertEqual(
            "explicit_symbols_no_spot_limit",
            summary["history_selection"]["history_symbol_limit_source"],
        )
        self.assertIn(
            "execution_path=history_fetch_explicit_symbols_explicit_limit_generic",
            stdout.getvalue(),
        )
        self.assertIn("coverage_class=explicit_symbol_limited_pool", stdout.getvalue())

    def test_explicit_default_history_limit_is_not_misclassified_as_spot_sample_cap(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text(
                "\n".join(
                    [
                        "symbol,name,spot_price,spot_amount,spot_pct_chg",
                        "000001,Alpha,8.2,200000000,1.2",
                        "000002,Beta,8.0,300000000,9.0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--max-history-symbols",
                    "50",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                summary = summary_view(manifest, "completed")
                runner.helpers.print_summary(manifest, output)

        self.assertTrue(getattr(args, "max_history_symbols_supplied", False))
        self.assertEqual(
            "history_fetch_spot_derived_explicit_limit_with_local_spot_generic",
            manifest["execution_path"],
        )
        self.assertEqual(
            "derive_symbols_from_spot+explicit_history_limit+spot_input",
            manifest["execution_path_reason"],
        )
        self.assertEqual("spot_derived_limited_pool", manifest["coverage_class"])
        self.assertEqual(
            "spot_derived_explicit_limit_requires_artifact_review",
            manifest["full_market_claim_boundary"],
        )
        self.assertEqual("explicit_user_input", selected["history_symbol_limit_source"])
        self.assertEqual(
            "explicit_user_input",
            summary["history_selection"]["history_symbol_limit_source"],
        )
        self.assertEqual(50, summary["history_selection"]["max_history_symbols"])
        self.assertEqual(
            "history_fetch_spot_derived_explicit_limit_with_local_spot_generic",
            summary["execution_path"],
        )
        self.assertEqual("spot_derived_limited_pool", summary["coverage_class"])
        self.assertIn("max_history_symbols=50", stdout.getvalue())
        self.assertIn(
            "history_symbol_limit_source=explicit_user_input",
            stdout.getvalue(),
        )

    def test_runner_derives_akshare_hk_symbols_from_spot_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text(
                "\n".join(
                    [
                        "ticker,name,price,amount,pct_chg",
                        "HK.00700,Tencent,300,300000000,1.1",
                        "09988.HK,Alibaba,80,400000000,0.8",
                        "00000,InvalidZero,1,500000000,9.0",
                        "600001,Ashare,8,600000000,5.0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "akshare_hk_daily",
                    "--derive-symbols-from-spot",
                    "--max-history-symbols",
                    "2",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--mode",
                    "generic",
                    "--config",
                    str(SCRIPTS / "hong_kong_generic_config.json"),
                    "--no-html-report",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                akshare_hk_daily_executor,
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        self.assertEqual(["09988", "00700"], manifest["history_symbols"])
        self.assertEqual(["09988", "00700"], selected["selected_symbols"])
        self.assertEqual(4, selected["raw_spot_rows"])
        self.assertEqual(2, selected["filtered_spot_rows"])
        self.assertEqual(2, selected["selected_symbol_count"])

    def test_runner_derives_history_symbols_from_common_spot_code_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text(
                "\n".join(
                    [
                        "code,name,price,amount,pct_chg",
                        "sh.600001,Shanghai,8.2,200000000,1.2",
                        "000001,Alpha,7.8,300000000,0.8",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--max-history-symbols",
                    "2",
                    "--history-adjust",
                    "2",
                    "--drop-invalid-history-rows",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        self.assertEqual(["000001", "600001"], manifest["history_symbols"])
        self.assertEqual(["000001", "600001"], selected["selected_symbols"])
        self.assertEqual("2", manifest["history_adjust"])
        self.assertTrue(manifest["drop_invalid_history_rows"])
        self.assertIn("--adjust", manifest["steps"][0]["command"])
        self.assertIn("--drop-invalid-rows", manifest["steps"][0]["command"])

    def test_runner_derives_history_symbols_from_common_dot_suffix_aliases(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text(
                "\n".join(
                    [
                        "ticker,name,price,amount,pct_chg",
                        "600001.SH,Shanghai,8.2,200000000,1.2",
                        "000001.SZ,Alpha,7.8,300000000,0.8",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--max-history-symbols",
                    "2",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)

        self.assertEqual(["000001", "600001"], manifest["history_symbols"])

    def test_runner_accepts_prefixed_explicit_history_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "sz.000001,000001.SZ,sh.600000,600000.SH",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        self.assertEqual(["000001", "600000"], manifest["history_symbols"])
        self.assertEqual(["000001", "600000"], selected["symbols"])

    def test_runner_rejects_bj_explicit_history_symbols_for_baostock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "bj.430047",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            with self.assertRaisesRegex(ValueError, "bj.430047"):
                runner.run_pipeline(context)

    def test_runner_does_not_route_bj_spot_symbols_to_baostock_history(self) -> None:
        config = load_config("ultra_short_low_price_config.json")
        config["thresholds"]["min_amount"] = 0
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "run"
            output.mkdir()
            spot = root / "spot.csv"
            config_path = root / "config.json"
            with spot.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["code", "price", "amount"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"code": "bj.430047", "price": 7.7, "amount": 500000000},
                        {"code": "sz.000001", "price": 7.8, "amount": 400000000},
                    ]
                )
            config_path.write_text(json.dumps(config), encoding="utf-8")
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--spot-input",
                    str(spot),
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--no-html-report",
                ]
            )

            symbols = runner.history_symbols(args, spot, output, config_path)

        self.assertEqual(["000001"], symbols)

    def test_runner_accepts_bj_explicit_history_symbols_for_zzshare(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "zzshare",
                    "--symbols",
                    "bj.430047,835185.BJ",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                    "--history-request-interval-seconds",
                    "0",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )
            fetch_history = next(
                step for step in manifest["steps"] if step["step"] == "fetch_history"
            )
            symbols_file = Path(
                fetch_history["command"][
                    fetch_history["command"].index("--symbols-file") + 1
                ]
            )
            symbols_text = symbols_file.read_text(encoding="utf-8")

        self.assertEqual(["430047", "835185"], manifest["history_symbols"])
        self.assertEqual(["430047", "835185"], selected["symbols"])
        self.assertIn("--symbols-file", fetch_history["command"])
        self.assertEqual("430047\n835185\n", symbols_text)

    def test_runner_rejects_short_explicit_history_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols",
                    "1",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            with self.assertRaisesRegex(ValueError, "symbols must be six digits"):
                runner.run_pipeline(context)

    def test_runner_reports_missing_spot_price_alias_for_symbol_derivation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text("symbol,amount\n000001,200000000\n", encoding="utf-8")
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            with self.assertRaisesRegex(ValueError, "spot input requires price column"):
                runner.run_pipeline(context)

    def test_runner_filters_non_numeric_spot_rows_before_history_derivation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text(
                "\n".join(
                    [
                        "symbol,name,spot_price,spot_amount,spot_pct_chg",
                        "000001,Alpha,8.2,200000000,1.2",
                        "000002,BadPrice,--,300000000,2.0",
                        "000003,BadAmount,8.0,,3.0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--max-history-symbols",
                    "3",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        self.assertEqual(["000001"], manifest["history_symbols"])
        self.assertEqual(3, selected["raw_spot_rows"])
        self.assertEqual(1, selected["filtered_spot_rows"])

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_does_not_zero_pad_numeric_parquet_spot_symbols(self) -> None:
        pd = __import__("pandas")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.parquet"
            output = root / "run"
            pd.DataFrame(
                [{"symbol": 1, "spot_price": 8.2, "spot_amount": 200000000}]
            ).to_parquet(spot, index=False)
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            with self.assertRaisesRegex(
                ValueError,
                (
                    "zero history symbols.*preflight_stage=derive_symbols.*"
                    "filtered_spot_rows=0.*raw_spot_rows=1.*"
                    "selected_symbols_count=0.*max_history_symbols=50.*"
                    "next_action=expand_spot_universe_or_relax_filters"
                ),
            ):
                runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        self.assertTrue(selected["selection_failed"])
        self.assertEqual(
            "spot_snapshot_filtered_to_zero_history_symbols",
            selected["selection_failed_reason"],
        )
        self.assertEqual(
            "expand_spot_universe_or_relax_filters",
            selected["next_action"],
        )
        self.assertEqual(
            "expand_spot_universe_or_relax_filters",
            selected["selection_failed_next_action"],
        )

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_counts_parquet_spot_rows_in_summary(self) -> None:
        pd = __import__("pandas")
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            spot = root / "spot.parquet"
            output = root / "run"
            frame.to_csv(prices, index=False)
            pd.DataFrame(
                [
                    {"symbol": "000002", "spot_price": 8.8},
                    {"symbol": "600001", "spot_price": 9.2},
                ]
            ).to_parquet(spot, index=False)

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--output-dir",
                    str(output),
                ]
            )

            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertEqual(2, summary["spot_rows"])

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_counts_uppercase_parquet_spot_rows_in_summary(self) -> None:
        pd = __import__("pandas")
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            spot = root / "spot.PARQUET"
            output = root / "run"
            frame.to_csv(prices, index=False)
            pd.DataFrame(
                [
                    {"symbol": "000002", "spot_price": 8.8},
                    {"symbol": "600001", "spot_price": 9.2},
                ]
            ).to_parquet(spot, index=False)

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--output-dir",
                    str(output),
                ]
            )

            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            spot_copy_exists = (output / "spot.parquet").exists()

        self.assertEqual(0, code, stderr)
        self.assertTrue(spot_copy_exists)
        self.assertEqual(2, summary["spot_rows"])

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_preserves_pq_prices_input_extension(self) -> None:
        pd = __import__("pandas")
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.pq"
            output = root / "run"
            frame.to_parquet(prices, index=False)

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            prices_copy_exists = (output / "prices.pq").exists()

        self.assertEqual(0, code, stderr)
        self.assertTrue(prices_copy_exists)
        self.assertTrue(summary["prices_output"].endswith("prices.pq"))
        self.assertEqual(len(frame), summary["prices_rows"])
        self.assertIn(str(output / "prices.pq"), manifest["steps"][0]["command"])

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
    def test_runner_normalizes_uppercase_parquet_prices_input_extension(self) -> None:
        pd = __import__("pandas")
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.PQ"
            output = root / "run"
            frame.to_parquet(prices, index=False)

            code, _stdout, stderr = call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--output-dir",
                    str(output),
                ]
            )

            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            prices_copy_exists = (output / "prices.pq").exists()

        self.assertEqual(0, code, stderr)
        self.assertTrue(prices_copy_exists)
        self.assertTrue(summary["prices_output"].endswith("prices.pq"))
        self.assertEqual(len(frame), summary["prices_rows"])
        self.assertIn(str(output / "prices.pq"), manifest["steps"][0]["command"])

    def test_runner_does_not_filter_non_st_name_containing_st_letters(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text(
                "\n".join(
                    [
                        "symbol,name,spot_price,spot_amount,spot_pct_chg",
                        "000001,Best Tech,8.2,200000000,1.2",
                        "000002,*ST Bad,8.0,300000000,9.0",
                        "000003,SST Bad,8.0,400000000,9.0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--max-history-symbols",
                    "2",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        self.assertEqual(["000001"], manifest["history_symbols"])
        self.assertEqual(
            "history_fetch_spot_derived_explicit_limit_with_local_spot_generic",
            manifest["execution_path"],
        )
        self.assertEqual(
            "derive_symbols_from_spot+explicit_history_limit+spot_input",
            manifest["execution_path_reason"],
        )
        self.assertEqual(["000001"], selected["selected_symbols"])
        self.assertEqual("explicit_user_input", selected["history_symbol_limit_source"])

    def test_runner_marks_default_spot_derived_history_path_as_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            output = root / "run"
            spot.write_text(
                "\n".join(
                    [
                        "symbol,name,spot_price,spot_amount,spot_pct_chg",
                        "000001,Alpha,8.2,200000000,1.2",
                        "000002,Beta,8.0,300000000,9.0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            args = parsed_args(
                [
                    "--output-dir",
                    str(output),
                    "--spot-input",
                    str(spot),
                    "--history-source",
                    "baostock",
                    "--derive-symbols-from-spot",
                    "--start-date",
                    "2025-01-01",
                    "--end-date",
                    "2026-01-01",
                ]
            )
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args, manifest, output / "run_manifest.json", ok_executor
            )

            runner.run_pipeline(context)
            selected = json.loads(
                (output / "selected_symbols.json").read_text(encoding="utf-8")
            )

        self.assertEqual(
            "history_fetch_spot_derived_sample_with_local_spot_generic",
            manifest["execution_path"],
        )
        self.assertEqual(
            "derive_symbols_from_spot+default_small_sample_cap+spot_input",
            manifest["execution_path_reason"],
        )
        self.assertEqual("spot_derived_sample", manifest["coverage_class"])
        self.assertFalse(manifest["full_market_claim_allowed"])
        self.assertEqual(
            "default_small_sample_cap_not_full_market",
            manifest["full_market_claim_boundary"],
        )
        self.assertEqual(
            "small_sample_default_cap", selected["history_symbol_limit_source"]
        )


def call_runner(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = runner.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def call_runner_with_executor(
    args: list[str],
    executor,
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    old_run_command = runner.run_command
    runner.run_command = executor
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = runner.main(args)
    finally:
        runner.run_command = old_run_command
    return code, stdout.getvalue(), stderr.getvalue()


def parsed_args(args: list[str]) -> object:
    namespace = runner.build_parser().parse_args(args)
    namespace.default_generic_config = runner.DEFAULT_GENERIC_CONFIG
    namespace.default_prediction_config = runner.DEFAULT_PREDICTION_CONFIG
    return namespace


def embedded_csv_provenance() -> dict[str, object]:
    return {
        "source_type": "csv_embedded_probe",
        "source_scope": "csv_internal_prediction_rows",
        "real_market_data": False,
        "metadata_source": "csv_embedded_metadata_columns",
        "source_claim_boundary": "csv_internal_fields_not_real_market_gate",
        "data_source_note": "csv_provenance_should_survive_runner",
    }


def assert_rows_keep_embedded_provenance(
    test: unittest.TestCase,
    rows: list[dict[str, str]],
    expected: dict[str, object],
) -> None:
    for row in rows:
        test.assertEqual(expected["source_type"], row["source_type"])
        test.assertEqual(expected["source_scope"], row["source_scope"])
        test.assertEqual("False", row["real_market_data"])
        test.assertEqual(expected["metadata_source"], row["metadata_source"])
        test.assertEqual(
            expected["source_claim_boundary"], row["source_claim_boundary"]
        )
        test.assertEqual(expected["data_source_note"], row["data_source_note"])


def ok_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    stdout = ""
    if "score_candidates.py" in command[1]:
        stdout = "OK: raw_symbols=1 input_symbols=1 candidates=1 effective_empty_result=false\n"
    return subprocess.CompletedProcess(command, 0, stdout, "")


def baostock_universe_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script == "fetch_baostock_a_share_universe.py":
        assert "--lookback-days" in command
        assert command[command.index("--lookback-days") + 1] == "0"
        assert "--retries" in command
        assert command[command.index("--retries") + 1] == "1"
        assert "--retry-interval-seconds" in command
        assert command[command.index("--retry-interval-seconds") + 1] == "1.0"
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,name,spot_price,spot_pct_chg,spot_amount,spot_industry\n"
            "000001,平安银行,,,,\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "baostock",
                    "source_scope": "baostock_universe_snapshot",
                    "partial_result": False,
                    "raw_items": 1,
                    "filtered_items": 1,
                    "symbol_count": 1,
                    "requested_snapshot_date": "2026-07-09",
                    "resolved_snapshot_date": "2026-07-09",
                    "lookback_days": 0,
                    "date_fallback_used": False,
                    "coverage_claim": "symbol_universe_snapshot_not_realtime_spot_proof",
                    "source_claim_boundary": (
                        "baostock_universe_snapshot_not_realtime_spot_or_full_market_proof"
                    ),
                    "output_written": True,
                    "metadata_output_written": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: source=baostock source_scope=baostock_universe_snapshot raw_items=1\n",
            "",
        )
    if script == "score_candidates.py":
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,total_score\n000001,0.8\n",
            encoding="utf-8",
        )
        Path(command[command.index("--diagnostics-output") + 1]).write_text(
            "symbol,selection_status,spot_matched_symbols\n000001,selected,1\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            (
                "OK: raw_symbols=1 input_symbols=1 candidates=1 "
                "spot_matched_symbols=1 effective_empty_result=false\n"
            ),
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def spot_fallback_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script == "fetch_eastmoney_a_share_spot.py":
        metadata_path = Path(command[command.index("--metadata-output") + 1])
        metadata_path.write_text(
            json.dumps(
                {
                    "source": "eastmoney",
                    "source_scope": "a_share_spot_snapshot",
                    "partial_result": True,
                    "raw_items": 0,
                    "filtered_items": 0,
                    "failed_pages": [{"page": 1, "error": "disconnect"}],
                    "output_written": False,
                    "metadata_output_written": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            3,
            "ERROR_SUMMARY: source=eastmoney raw_items=0 partial_result=true\n",
            "ERROR: strict gate failed; raw_items=0\n",
        )
    if script == "fetch_baostock_a_share_universe.py":
        assert "--lookback-days" in command
        assert command[command.index("--lookback-days") + 1] == "7"
        assert "--retries" in command
        assert command[command.index("--retries") + 1] == "1"
        assert "--retry-interval-seconds" in command
        assert command[command.index("--retry-interval-seconds") + 1] == "1.0"
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,name,spot_price,spot_pct_chg,spot_amount,spot_industry\n"
            "000001,平安银行,,,,\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "baostock",
                    "source_scope": "baostock_universe_snapshot",
                    "partial_result": False,
                    "raw_items": 1,
                    "filtered_items": 1,
                    "symbol_count": 1,
                    "requested_snapshot_date": "2026-07-09",
                    "resolved_snapshot_date": "2026-07-08",
                    "lookback_days": 7,
                    "date_fallback_used": True,
                    "coverage_claim": "symbol_universe_snapshot_not_realtime_spot_proof",
                    "source_claim_boundary": (
                        "baostock_universe_snapshot_not_realtime_spot_or_full_market_proof"
                    ),
                    "output_written": True,
                    "metadata_output_written": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: source=baostock source_scope=baostock_universe_snapshot raw_items=1\n",
            "",
        )
    if script == "score_candidates.py":
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,total_score\n000001,0.8\n",
            encoding="utf-8",
        )
        Path(command[command.index("--diagnostics-output") + 1]).write_text(
            "symbol,selection_status,spot_matched_symbols\n000001,selected,1\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            (
                "OK: raw_symbols=1 input_symbols=1 candidates=1 "
                "spot_matched_symbols=1 effective_empty_result=false\n"
            ),
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def history_metadata_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script.startswith("fetch_") and "a_share" in script:
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,date,close\n000001,2026-01-01,8.0\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "baostock",
                    "adjustflag": "3",
                    "requested_symbols": ["000001"],
                    "rows": 0,
                    "symbol_count": 0,
                    "failed_symbols": [{"symbol": "000001", "error": "offline"}],
                    "empty_symbols": ["000001"],
                    "fallback_errors": [],
                    "partial_result": True,
                    "output_written": False,
                    "metadata_output_written": True,
                    "symbols": [
                        {
                            "symbol": "000001",
                            "rows": 0,
                            "date_min": "",
                            "date_max": "",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if script == "score_candidates.py":
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,total_score\n000001,0.8\n",
            encoding="utf-8",
        )
        Path(command[command.index("--diagnostics-output") + 1]).write_text(
            "symbol,selection_status\n000001,selected\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: raw_symbols=1 input_symbols=1 candidates=1 effective_empty_result=false\n",
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def short_history_validate_failure_executor(
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script.startswith("fetch_") and "a_share" in script:
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,date,close,open,high,low,volume,turn\n"
            "000001,2026-01-01,8.0,8.0,8.1,7.9,1000,1.0\n"
            "001220,2026-01-01,8.0,8.0,8.1,7.9,1000,1.0\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "zzshare",
                    "requested_symbols": ["000001", "001220"],
                    "rows": 153,
                    "symbol_count": 2,
                    "failed_symbols": [],
                    "empty_symbols": [],
                    "possibly_truncated_symbols": [],
                    "output_written": True,
                    "metadata_output_written": True,
                    "symbols": [
                        {
                            "symbol": "000001",
                            "rows": 120,
                            "date_min": "2025-01-01",
                            "date_max": "2026-01-01",
                        },
                        {
                            "symbol": "001220",
                            "rows": 33,
                            "date_min": "2025-11-01",
                            "date_max": "2026-01-01",
                        },
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "OK: source=zzshare\n", "")
    if script == "validate_ohlcv.py":
        return subprocess.CompletedProcess(
            command,
            1,
            "",
            "ERROR: insufficient_history_symbols=1 [input=prices.csv]\n",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def sensitive_history_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script.startswith("fetch_") and "a_share" in script:
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,date,close\n000001,2026-01-01,8.0\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "zzshare",
                    "failed_symbols": [],
                    "empty_symbols": [],
                    "possibly_truncated_symbols": [],
                    "output_written": True,
                    "metadata_output_written": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: ZZSHARE_TOKEN=placeholder-secret-value\n",
            "warning API_KEY=placeholder-api-key-value\n",
        )
    if script == "score_candidates.py":
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,total_score\n000001,0.8\n",
            encoding="utf-8",
        )
        Path(command[command.index("--diagnostics-output") + 1]).write_text(
            "symbol,selection_status\n000001,selected\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: raw_symbols=1 input_symbols=1 candidates=1 effective_empty_result=false\n",
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def sensitive_failure_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        command,
        1,
        "",
        (
            "ERROR API_KEY=placeholder-api-key-value "
            "url=https://example.test/path?token=placeholder-token-value\n"
        ),
    )


def sensitive_preflight_failure(_args: object) -> None:
    raise ValueError(
        "API_KEY=placeholder-api-key-value "
        "url=https://example.test/path?token=placeholder-token-value"
    )


def yfinance_hk_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script == "fetch_yfinance_ohlcv.py":
        symbols = command[command.index("--symbols") + 1].split(",")
        Path(command[command.index("--output") + 1]).write_text(
            "\n".join(
                [
                    "symbol,name,market,date,open,high,low,close,volume",
                    "0700.HK,0700.HK,HK,2026-01-01,300,310,295,305,100000",
                    "9988.HK,9988.HK,HK,2026-01-01,80,82,78,81,200000",
                    "8001.HK,8001.HK,HK,2026-01-01,1.2,1.3,1.1,1.25,300000",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "yfinance",
                    "source_scope": "yfinance_history_fetch",
                    "market": "HK",
                    "market_label_only": True,
                    "source_claim_boundary": (
                        "market_label_not_source_exchange_or_calendar_proof"
                    ),
                    "requested_symbols": symbols,
                    "rows": 3,
                    "symbol_count": 3,
                    "failed_symbols": [],
                    "empty_symbols": [],
                    "timeout_seconds": 8.0,
                    "adjustment": "auto_adjust_false_close",
                    "output_written": True,
                    "metadata_output_written": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if script == "score_candidates.py":
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,total_score\n0700.HK,0.8\n",
            encoding="utf-8",
        )
        Path(command[command.index("--diagnostics-output") + 1]).write_text(
            "symbol,market,listing_board,selection_status\n"
            "0700.HK,HK,港股主板,selected\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: raw_symbols=3 input_symbols=3 candidates=1 effective_empty_result=false\n",
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def pytdx_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script == "fetch_pytdx_a_share.py":
        symbols = command[command.index("--symbols") + 1].split(",")
        Path(command[command.index("--output") + 1]).write_text(
            "\n".join(
                [
                    "symbol,name,market,date,open,high,low,close,volume,amount",
                    "000001,000001,A-share,2026-01-01,10,11,9,10.5,100000,1050000",
                    "600000,600000,A-share,2026-01-01,20,21,19,20.5,200000,4100000",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "pytdx",
                    "source_scope": "pytdx_history_fetch",
                    "source_claim_boundary": (
                        "pytdx_external_fetch_not_turnover_tradability_or_stability_proof"
                    ),
                    "data_source_note": "pytdx fake metadata",
                    "license_claim_boundary": (
                        "pypi_license_unknown_readme_personal_research_boundary"
                    ),
                    "missing_provider_fields": ["turn", "tradestatus", "isST", "name"],
                    "requested_symbols": symbols,
                    "rows": 2,
                    "symbol_count": 2,
                    "failed_symbols": [],
                    "empty_symbols": [],
                    "invalid_rows": 0,
                    "dropped_invalid_rows": 0,
                    "timeout_seconds": 8.0,
                    "output_written": True,
                    "metadata_output_written": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if script == "score_candidates.py":
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,total_score\n000001,0.8\n600000,0.7\n",
            encoding="utf-8",
        )
        Path(command[command.index("--diagnostics-output") + 1]).write_text(
            "symbol,selection_status\n000001,selected\n600000,selected\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: raw_symbols=2 input_symbols=2 candidates=2 effective_empty_result=false\n",
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def akshare_hk_daily_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script == "fetch_akshare_hk_daily.py":
        symbols = command[command.index("--symbols") + 1].split(",")
        Path(command[command.index("--output") + 1]).write_text(
            "\n".join(
                [
                    "symbol,name,market,date,open,high,low,close,volume,amount",
                    "00700,00700,HK,2026-01-01,300,310,295,305,100000,30500000",
                    "09988,09988,HK,2026-01-01,80,82,78,81,200000,16200000",
                    "08001,08001,HK,2026-01-01,1.2,1.3,1.1,1.25,300000,375000",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "akshare_stock_hk_daily",
                    "source_scope": "akshare_hk_daily_history_fetch",
                    "source_type": "external_fetch",
                    "market": "HK",
                    "source_claim_boundary": (
                        "akshare_stock_hk_daily_not_exchange_calendar_or_tradability_proof"
                    ),
                    "requested_symbols": symbols,
                    "rows": 3,
                    "symbol_count": 3,
                    "failed_symbols": [],
                    "empty_symbols": [],
                    "adjust": "",
                    "output_written": True,
                    "metadata_output_written": True,
                    "real_market_data": "unknown",
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if script == "score_candidates.py":
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,total_score\n00700,0.8\n",
            encoding="utf-8",
        )
        Path(command[command.index("--diagnostics-output") + 1]).write_text(
            "symbol,market,listing_board,selection_status\n"
            "00700,HK,港股主板,selected\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: raw_symbols=3 input_symbols=3 candidates=1 effective_empty_result=false\n",
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def zzshare_quality_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script.startswith("fetch_") and "a_share" in script:
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,date,close\n000001,2026-01-01,8.0\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "zzshare",
                    "source_scope": "zzshare_history_fetch",
                    "source_claim_boundary": (
                        "zzshare_external_api_not_broker_order_or_long_term_stability_proof"
                    ),
                    "data_source_note": (
                        "zzshare SDK endpoint; quota and stability require external verification"
                    ),
                    "fields": "all",
                    "request_interval_seconds": 0.0,
                    "max_concurrent_symbol_requests": 6,
                    "max_rate_limit_sleep_seconds": 30.0,
                    "max_429_events": 2,
                    "max_runtime_seconds": 600.0,
                    "limit": 1,
                    "max_pages": 2,
                    "token_configured": False,
                    "requested_symbols": ["000001"],
                    "rows": 1,
                    "symbol_count": 1,
                    "failed_symbols": [],
                    "empty_symbols": [],
                    "possibly_truncated_symbols": ["000001"],
                    "invalid_rows": 2,
                    "invalid_symbols": ["000001"],
                    "invalid_row_examples": [],
                    "dropped_invalid_rows": 1,
                    "non_trading_rows": 3,
                    "non_trading_symbols": ["000001"],
                    "non_trading_row_examples": [],
                    "tradestatus_missing_rows": 4,
                    "output_written": True,
                    "metadata_output_written": True,
                    "symbols": [
                        {
                            "symbol": "000001",
                            "rows": 1,
                            "date_min": "2026-01-01",
                            "date_max": "2026-01-01",
                            "possibly_truncated": True,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if script == "score_candidates.py":
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,total_score\n000001,0.8\n",
            encoding="utf-8",
        )
        Path(command[command.index("--diagnostics-output") + 1]).write_text(
            "symbol,selection_status\n000001,selected\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: raw_symbols=1 input_symbols=1 candidates=1 effective_empty_result=false\n",
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def history_fallback_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(command[1]).name
    if script.startswith("fetch_") and "a_share" in script:
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,date,close\n000001,2026-01-01,8.0\n",
            encoding="utf-8",
        )
        Path(command[command.index("--metadata-output") + 1]).write_text(
            json.dumps(
                {
                    "source": "akshare",
                    "adjust": "hfq",
                    "requested_symbols": ["000001"],
                    "rows": 1,
                    "symbol_count": 1,
                    "failed_symbols": [],
                    "empty_symbols": [],
                    "fallback_errors": [
                        {"symbol": "000001", "error": "stock_zh_a_hist failed"}
                    ],
                    "output_written": True,
                    "metadata_output_written": True,
                    "symbols": [
                        {
                            "symbol": "000001",
                            "provider": "stock_zh_a_daily",
                            "rows": 1,
                            "date_min": "2026-01-01",
                            "date_max": "2026-01-01",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if script == "score_candidates.py":
        Path(command[command.index("--output") + 1]).write_text(
            "symbol,total_score\n000001,0.8\n",
            encoding="utf-8",
        )
        Path(command[command.index("--diagnostics-output") + 1]).write_text(
            "symbol,selection_status\n000001,selected\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            "OK: raw_symbols=1 input_symbols=1 candidates=1 effective_empty_result=false\n",
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
