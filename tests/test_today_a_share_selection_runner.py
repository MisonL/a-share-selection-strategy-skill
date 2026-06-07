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
from run_today_a_share_selection_outputs import clear_stale_run_outputs  # noqa: E402
from helpers import build_frame  # noqa: E402


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
        self.assertIn("A-Share Selection Strategy", report)
        self.assertIn("Scoring Notes", report)
        self.assertIn("Candidates", report)
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
        self.assertIn("Failed report", report)
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

        self.assertEqual(0, code, stderr)
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
        self.assertEqual("baostock", summary["input_metadata"]["history_provider"])
        self.assertEqual(1, summary["input_metadata"]["history_failed_symbol_count"])
        self.assertEqual(0, summary["input_metadata"]["history_fallback_error_count"])
        self.assertFalse(summary["input_metadata"]["history_output_written"])
        self.assertTrue(summary["input_metadata"]["history_metadata_output_written"])
        self.assertEqual(1, summary["history_selection"]["history_empty_symbol_count"])
        self.assertEqual(["000001"], summary["history_selection"]["history_empty_symbols"])
        self.assertTrue(summary["history_selection"]["history_partial_result"])
        self.assertFalse(summary["history_selection"]["history_output_written"])
        self.assertIn("metadata_source=external_fetch", stdout.getvalue())
        self.assertIn("real_market_data=true", stdout.getvalue())
        self.assertIn("history_partial_result=true", stdout.getvalue())
        self.assertIn("history_output_written=false", stdout.getvalue())
        self.assertIn("history_empty_symbol_count=1", stdout.getvalue())
        for row in candidate_rows + diagnostic_rows:
            self.assertEqual("external_fetch", row["source_type"])
            self.assertEqual("True", row["real_market_data"])
            self.assertEqual("baostock", row["history_provider"])
            self.assertEqual("1", row["history_failed_symbol_count"])
            self.assertEqual("0", row["history_fallback_error_count"])
            self.assertEqual("False", row["history_output_written"])
            self.assertEqual("True", row["history_metadata_output_written"])

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
        self.assertEqual(1, summary["input_metadata"]["history_fallback_error_count"])
        self.assertTrue(summary["history_selection"]["history_partial_result"])
        self.assertEqual(
            1,
            summary["history_selection"]["history_metadata_fallback_error_count"],
        )
        self.assertIn("history_partial_result=true", stdout.getvalue())
        self.assertIn("history_fallback_error_count=1", stdout.getvalue())
        for row in candidate_rows + diagnostic_rows:
            self.assertEqual("True", row["history_partial_result"])
            self.assertEqual("1", row["history_fallback_error_count"])

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
                    "sz.000001,sh.600000",
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
