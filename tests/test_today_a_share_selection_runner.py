from __future__ import annotations

import csv
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import run_today_a_share_selection as runner  # noqa: E402
from run_today_a_share_selection_helpers import (  # noqa: E402
    summary_view,
    spot_rows,
    tabular_row_count,
)
from run_today_a_share_selection_history import parse_history_symbols  # noqa: E402
from run_today_a_share_selection_outputs import clear_stale_run_outputs  # noqa: E402
from helpers import build_frame, load_config  # noqa: E402


class TodayAShareSelectionRunnerTests(unittest.TestCase):
    def test_generic_runner_writes_manifest_summary_and_outputs(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            report = (output / "report.html").read_text(encoding="utf-8")
            candidate_rows = csv_rows(output / "candidates.csv")
            diagnostic_rows = csv_rows(output / "diagnostics.csv")

        self.assertEqual(0, code, stderr)
        self.assertIn("runner=run_today_a_share_selection", stdout)
        self.assertIn("candidate_rows=2", stdout)
        self.assertIn("diagnostic_rows=2", stdout)
        self.assertIn("html_report=", stdout)
        self.assertIn("lightgbm_not_used=true", stdout)
        self.assertIn("lightgbm_output_source=not_used", stdout)
        self.assertIn("lightgbm_executed_by_runner=false", stdout)
        self.assertEqual(["validate", "score"], [step["step"] for step in manifest["steps"]])
        self.assertEqual("auto", manifest["requested_mode"])
        self.assertEqual("generic", manifest["mode"])
        self.assertEqual("auto_generic", manifest["mode_decision"])
        self.assertTrue(manifest["html_report_enabled"])
        self.assertEqual("auto", manifest["html_report_language"])
        self.assertIn(manifest["html_report_initial_language"], {"zh", "en"})
        self.assertTrue(manifest["summary_output_written"])
        self.assertTrue(manifest["manifest_output_written"])
        self.assertIn("missing_prediction_columns:prediction", manifest["mode_decision_reason"])
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
        self.assertEqual("auto", summary["requested_mode"])
        self.assertEqual("generic", summary["mode"])
        self.assertEqual("auto_generic", summary["mode_decision"])
        self.assertIn("missing_prediction_columns:prediction", summary["mode_decision_reason"])
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
        self.assertIn("Pre-use checklist", report)
        self.assertIn("Complete Candidate Table", report)
        self.assertIn("Audit Appendix", report)
        self.assertIn("not_investment_advice_not_trade_instruction_not_real_fill_not_return_proof", report)
        self.assertIn('data-lang-mode="auto"', report)
        self.assertTrue(
            all(row["advice_boundary"] == summary["advice_boundary"] for row in candidate_rows)
        )
        self.assertTrue(
            all(row["advice_boundary"] == summary["advice_boundary"] for row in diagnostic_rows)
        )
        self.assertTrue(
            all(
                row["recommendation_boundary"] == "ranking_signal_not_buy_sell_instruction"
                for row in candidate_rows
            )
        )

    def test_prediction_runner_fails_without_prediction_and_keeps_manifest(self) -> None:
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

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
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
        self.assertEqual("external_input", manifest["requested_prediction_input_source"])
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
        self.assertFalse(summary["candidates_output_written"])
        self.assertFalse(summary["diagnostics_output_written"])
        self.assertTrue(summary["html_report_written"])
        self.assertIn("did not produce a usable watchlist", report)
        self.assertIn("This failed run has no usable watchlist", report)
        self.assertIn("prediction-derived profile requires prediction", report)
        self.assertIn("Missing required prediction columns", report)
        self.assertIn("validation failed before scoring", report)
        self.assertNotIn("Read from input columns", report)
        self.assertNotIn("ranked candidates from prediction columns", report)

    def test_generic_validate_failure_report_does_not_claim_completed_scoring(self) -> None:
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

    def test_failed_reused_output_dir_does_not_show_stale_candidates(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
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
        self.assertIn("lightgbm_output_source=external_input", stdout)
        self.assertIn("lightgbm_executed_by_runner=false", stdout)
        self.assertEqual("prediction", manifest["mode"])
        self.assertEqual("auto_prediction", manifest["mode_decision"])
        self.assertFalse(manifest["lightgbm_not_used"])
        self.assertFalse(manifest["lightgbm_executed_by_runner"])
        self.assertTrue(manifest["consumes_prediction_columns"])
        self.assertEqual("external_input", manifest["prediction_input_source"])
        self.assertEqual("external_input", manifest["requested_prediction_input_source"])
        self.assertFalse(manifest["prediction_model_executed_by_runner"])
        self.assertEqual("external_input", manifest["lightgbm_output_source"])
        self.assertEqual("external_input", manifest["requested_lightgbm_output_source"])
        self.assertEqual(
            "external_input_columns_consumed_runner_does_not_execute_prediction_model",
            summary["prediction_claim_boundary"],
        )
        self.assertIn("prediction_claim_boundary", report)
        self.assertIn(
            "external_input_columns_consumed_runner_does_not_execute_prediction_model",
            report,
        )

    def test_no_html_report_removes_stale_report_in_reused_output_dir(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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

    def test_html_report_write_failure_does_not_block_success_summary(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))

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
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))

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
        self.assertEqual(321, manifest["history_limit"])
        self.assertEqual(4, manifest["history_max_pages"])
        self.assertIn("--http-url", fetch_step["command"])
        self.assertIn("https://example.test", fetch_step["command"])
        self.assertIn("--timeout-seconds", fetch_step["command"])
        self.assertIn("8.0", fetch_step["command"])
        self.assertIn("--request-interval-seconds", fetch_step["command"])
        self.assertIn("0.0", fetch_step["command"])
        self.assertIn("--limit", fetch_step["command"])
        self.assertIn("321", fetch_step["command"])
        self.assertIn("--max-pages", fetch_step["command"])
        self.assertIn("4", fetch_step["command"])
        self.assertEqual("zzshare", manifest["history_source"])
        self.assertEqual("zzshare_history_fetch", manifest["source_scope"])

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

    def test_runner_rejects_zzshare_only_options_for_other_history_sources(self) -> None:
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
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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
            self.assertNotIn("disconnect", report)

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

    def test_invalid_zzshare_history_timeout_nan_clears_reused_output_files(self) -> None:
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
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        score_command = manifest["steps"][1]["command"]
        self.assertIn("--spot-input", score_command)
        self.assertEqual("local_prices_input+local_spot_input", manifest["source_scope"])
        self.assertEqual(1, summary["spot_rows"])
        self.assertEqual(1, summary["spot_matched_symbols"])

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
        self.assertEqual("2026-06-06T09:31:00Z", summary["spot_metadata"]["snapshot_time"])
        self.assertEqual(2, summary["spot_metadata"]["requested_pages"])
        self.assertEqual(1, summary["spot_metadata"]["successful_pages"])
        self.assertEqual(100, summary["spot_metadata"]["raw_items"])
        self.assertEqual(100, summary["spot_metadata"]["filtered_items"])
        self.assertEqual("partial_not_full_market", summary["spot_metadata"]["coverage_claim"])
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

        self.assertEqual(["000003", "000004"], summary["score"]["failed_symbol_examples"])
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
            path.write_text('symbol,name\n000001,"Alpha\nName"\n000002,Beta\n', encoding="utf-8")

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
            source.write_text("symbol,date,close\n000001,2026-01-01,8.0\n", encoding="utf-8")
            if not stale_alias.exists():
                stale_alias.hardlink_to(source)
            args = SimpleNamespace(prices_input=str(source), spot_input=None, fetch_spot=None)

            clear_stale_run_outputs(args, output)

            self.assertTrue(source.exists())
            self.assertTrue(stale_alias.exists())

    def test_stale_cleanup_preserves_samefile_spot_input_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            source = output / "spot.PQ"
            stale_alias = output / "spot.pq"
            source.write_text("symbol,spot_price\n000001,8.0\n", encoding="utf-8")
            if not stale_alias.exists():
                stale_alias.hardlink_to(source)
            args = SimpleNamespace(prices_input=None, spot_input=str(source), fetch_spot=None)

            clear_stale_run_outputs(args, output)

            self.assertTrue(source.exists())
            self.assertTrue(stale_alias.exists())

    def test_runner_builds_history_fetch_before_validate_when_prices_are_omitted(self) -> None:
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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            runner.run_pipeline(context)

        self.assertEqual(["fetch_history", "validate", "score"], [step["step"] for step in manifest["steps"]])
        self.assertEqual("generic", manifest["mode"])
        self.assertIn("history_fetch_inputs_do_not_include_prediction", manifest["mode_decision_reason"])
        self.assertIn("use_mode_prediction", manifest["mode_decision_reason"])
        self.assertEqual("baostock_history_fetch", manifest["source_scope"])
        self.assertEqual(["000001", "600000"], manifest["history_symbols"])
        self.assertIn("--fail-on-fetch-error", manifest["steps"][0]["command"])

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
        self.assertEqual("baostock", summary["input_metadata"]["history_provider"])
        self.assertEqual("3", summary["input_metadata"]["history_adjustflag"])
        self.assertEqual(1, summary["input_metadata"]["history_failed_symbol_count"])
        self.assertEqual(0, summary["input_metadata"]["history_fallback_error_count"])
        self.assertFalse(summary["input_metadata"]["history_output_written"])
        self.assertTrue(summary["input_metadata"]["history_metadata_output_written"])
        self.assertEqual(1, summary["history_selection"]["history_empty_symbol_count"])
        self.assertEqual(["000001"], summary["history_selection"]["history_empty_symbols"])
        self.assertTrue(summary["history_selection"]["history_partial_result"])
        self.assertFalse(summary["history_selection"]["history_output_written"])
        self.assertEqual("3", summary["history_selection"]["history_adjustflag"])
        self.assertIn("metadata_source=external_fetch", stdout.getvalue())
        self.assertIn("real_market_data=true", stdout.getvalue())
        self.assertIn("history_partial_result=true", stdout.getvalue())
        self.assertIn("history_output_written=false", stdout.getvalue())
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

    def test_zzshare_history_quality_metadata_propagates_to_runner_surfaces(self) -> None:
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
        self.assertEqual(1, history["history_limit"])
        self.assertEqual(2, history["history_max_pages"])
        self.assertEqual(2, history["history_invalid_rows"])
        self.assertEqual(1, history["history_dropped_invalid_rows"])
        self.assertIn("history_token_configured=false", stdout.getvalue())
        self.assertIn("history_fields=all", stdout.getvalue())
        self.assertIn("history_request_interval_seconds=0.0", stdout.getvalue())
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
            self.assertEqual("1", row["history_limit"])
            self.assertEqual("2", row["history_max_pages"])
            self.assertEqual("1", row["history_possibly_truncated_symbol_count"])
            self.assertEqual("2", row["history_invalid_rows"])
            self.assertEqual("1", row["history_dropped_invalid_rows"])
            self.assertEqual("3", row["history_non_trading_rows"])
            self.assertEqual("4", row["history_tradestatus_missing_rows"])

    def test_embedded_csv_provenance_survives_runner_without_metadata_file(self) -> None:
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
        self.assertIn("input_metadata_output_written=true", stdout)
        for row in candidate_rows + diagnostic_rows:
            self.assertEqual("yfinance_history_fetch", row["source_scope"])
            self.assertEqual("False", row["input_token_configured"])
            self.assertEqual("True", row["input_partial_result"])
            self.assertEqual("1", row["input_possibly_truncated_symbol_count"])
            self.assertEqual("2", row["input_invalid_rows"])
            self.assertEqual("1", row["input_dropped_invalid_rows"])

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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            runner.run_pipeline(context)
            selected = json.loads((output / "selected_symbols.json").read_text(encoding="utf-8"))
            (output / "history_metadata.json").write_text(
                json.dumps({"failed_symbols": [{"symbol": "600001", "error": "offline"}]}),
                encoding="utf-8",
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                summary = summary_view(manifest, "completed")
                runner.helpers.print_summary(manifest, output)

        self.assertEqual(["000001"], manifest["history_symbols"])
        self.assertEqual(["000001"], selected["selected_symbols"])
        self.assertEqual(1, selected["filtered_spot_rows"])
        self.assertEqual(1, selected["selected_symbol_count"])
        self.assertEqual(1, selected["max_history_symbols"])
        self.assertEqual(4, summary["history_selection"]["raw_spot_rows"])
        self.assertEqual(1, summary["history_selection"]["filtered_spot_rows"])
        self.assertEqual(1, summary["history_selection"]["selected_symbol_count"])
        self.assertEqual(1, summary["history_selection"]["max_history_symbols"])
        self.assertFalse(summary["history_selection"]["allow_partial_history"])
        self.assertEqual(
            1,
            summary["history_selection"]["history_metadata_failed_symbol_count"],
        )
        self.assertTrue(summary["selected_symbols_output_written"])
        self.assertTrue(summary["history_metadata_output_written"])
        self.assertIn("history_symbols=1", stdout.getvalue())
        self.assertIn("raw_spot_rows=4", stdout.getvalue())
        self.assertIn("filtered_spot_rows=1", stdout.getvalue())
        self.assertIn("max_history_symbols=1", stdout.getvalue())
        self.assertIn("allow_partial_history=false", stdout.getvalue())

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
            selected = json.loads((output / "selected_symbols.json").read_text(encoding="utf-8"))

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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            runner.run_pipeline(context)
            selected = json.loads((output / "selected_symbols.json").read_text(encoding="utf-8"))

        self.assertEqual(["000001", "600001"], manifest["history_symbols"])
        self.assertEqual(["000001", "600001"], selected["selected_symbols"])
        self.assertEqual("2", manifest["history_adjust"])
        self.assertTrue(manifest["drop_invalid_history_rows"])
        self.assertIn("--adjust", manifest["steps"][0]["command"])
        self.assertIn("--drop-invalid-rows", manifest["steps"][0]["command"])

    def test_runner_derives_history_symbols_from_common_dot_suffix_aliases(self) -> None:
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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            runner.run_pipeline(context)
            selected = json.loads((output / "selected_symbols.json").read_text(encoding="utf-8"))

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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            runner.run_pipeline(context)
            selected = json.loads((output / "selected_symbols.json").read_text(encoding="utf-8"))
            fetch_history = next(step for step in manifest["steps"] if step["step"] == "fetch_history")

        self.assertEqual(["430047", "835185"], manifest["history_symbols"])
        self.assertEqual(["430047", "835185"], selected["symbols"])
        self.assertIn("--symbols", fetch_history["command"])
        self.assertIn("430047,835185", fetch_history["command"])

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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            with self.assertRaisesRegex(ValueError, "symbols must be six digits"):
                runner.run_pipeline(context)

    def test_runner_reports_missing_spot_price_alias_for_symbol_derivation(self) -> None:
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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            with self.assertRaisesRegex(ValueError, "spot input requires price column"):
                runner.run_pipeline(context)

    def test_runner_filters_non_numeric_spot_rows_before_history_derivation(self) -> None:
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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            runner.run_pipeline(context)
            selected = json.loads((output / "selected_symbols.json").read_text(encoding="utf-8"))

        self.assertEqual(["000001"], manifest["history_symbols"])
        self.assertEqual(3, selected["raw_spot_rows"])
        self.assertEqual(1, selected["filtered_spot_rows"])

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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            with self.assertRaisesRegex(ValueError, "zero history symbols"):
                runner.run_pipeline(context)

    def test_runner_counts_parquet_spot_rows_in_summary(self) -> None:
        pd = __import__("pandas")
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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

    def test_runner_counts_uppercase_parquet_spot_rows_in_summary(self) -> None:
        pd = __import__("pandas")
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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

    def test_runner_preserves_pq_prices_input_extension(self) -> None:
        pd = __import__("pandas")
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            prices_copy_exists = (output / "prices.pq").exists()

        self.assertEqual(0, code, stderr)
        self.assertTrue(prices_copy_exists)
        self.assertTrue(summary["prices_output"].endswith("prices.pq"))
        self.assertEqual(len(frame), summary["prices_rows"])
        self.assertIn(str(output / "prices.pq"), manifest["steps"][0]["command"])

    def test_runner_normalizes_uppercase_parquet_prices_input_extension(self) -> None:
        pd = __import__("pandas")
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
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

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
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
            context = runner.RunContext(args, manifest, output / "run_manifest.json", ok_executor)

            runner.run_pipeline(context)
            selected = json.loads((output / "selected_symbols.json").read_text(encoding="utf-8"))

        self.assertEqual(["000001"], manifest["history_symbols"])
        self.assertEqual(["000001"], selected["selected_symbols"])



def call_runner(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = runner.main(args)
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
        test.assertEqual(expected["source_claim_boundary"], row["source_claim_boundary"])
        test.assertEqual(expected["data_source_note"], row["data_source_note"])


def ok_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    stdout = ""
    if "score_candidates.py" in command[1]:
        stdout = "OK: raw_symbols=1 input_symbols=1 candidates=1 effective_empty_result=false\n"
    return subprocess.CompletedProcess(command, 0, stdout, "")


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
