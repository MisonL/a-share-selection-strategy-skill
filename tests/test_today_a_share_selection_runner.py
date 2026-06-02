from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_today_a_share_selection as runner  # noqa: E402
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

        self.assertEqual(0, code, stderr)
        self.assertIn("runner=run_today_a_share_selection", stdout)
        self.assertEqual(["validate", "score"], [step["step"] for step in manifest["steps"]])
        self.assertEqual("auto", manifest["requested_mode"])
        self.assertEqual("generic", manifest["mode"])
        self.assertEqual("auto_generic", manifest["mode_decision"])
        self.assertIn("missing_prediction_columns:prediction", manifest["mode_decision_reason"])
        self.assertTrue(manifest["lightgbm_not_used"])
        self.assertFalse(manifest["lightgbm_executed_by_runner"])
        self.assertEqual("completed", summary["status"])
        self.assertEqual("auto", summary["requested_mode"])
        self.assertEqual("generic", summary["mode"])
        self.assertEqual("auto_generic", summary["mode_decision"])
        self.assertIn("missing_prediction_columns:prediction", summary["mode_decision_reason"])
        self.assertFalse(summary["lightgbm_executed_by_runner"])
        self.assertEqual([], summary["failed_steps"])
        self.assertEqual(0, summary["spot_rows"])
        self.assertEqual(2, summary["score"]["raw_symbols"])
        self.assertEqual(2, summary["score"]["candidates"])
        self.assertFalse(summary["score"]["effective_empty_result"])
        self.assertEqual(len(frame), summary["prices_rows"])
        self.assertEqual(2, summary["candidate_rows"])
        self.assertEqual(2, summary["diagnostic_rows"])
        self.assertTrue(summary["prices_output"].endswith("prices.csv"))
        self.assertTrue(summary["candidates_output"].endswith("candidates.csv"))
        self.assertTrue(summary["diagnostics_output"].endswith("diagnostics.csv"))

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

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(3, code)
        self.assertIn("step=validate", stderr)
        self.assertEqual(["validate"], [step["step"] for step in manifest["steps"]])
        self.assertEqual(["validate"], summary["failed_steps"])
        self.assertEqual("failed", summary["status"])
        self.assertTrue(manifest["prediction_mode"])

    def test_auto_runner_uses_prediction_when_prediction_columns_exist(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
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
                ]
            )

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertEqual("prediction", manifest["mode"])
        self.assertEqual("auto_prediction", manifest["mode_decision"])
        self.assertFalse(manifest["lightgbm_not_used"])
        self.assertFalse(manifest["lightgbm_executed_by_runner"])

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
                "requested_pages": 2,
                "retry_attempts_per_page": 1,
                "successful_pages": 1,
                "failed_pages": [{"page": 2, "error": "disconnect"}],
                "raw_items": 100,
                "filtered_items": 100,
                "partial_result": True,
                "allowed_failure_actions": ["rerun_with_fail_on_partial"],
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
                "steps": [],
            }

            summary = runner.summary_view(manifest, "completed")

        self.assertTrue(summary["spot_metadata"]["partial_result"])
        self.assertEqual(
            ["rerun_with_fail_on_partial"],
            summary["spot_metadata"]["allowed_failure_actions"],
        )

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
        self.assertEqual("baostock_history_fetch", manifest["source_scope"])
        self.assertEqual(["000001", "600000"], manifest["history_symbols"])
        self.assertIn("--fail-on-fetch-error", manifest["steps"][0]["command"])

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

        self.assertEqual(["000001"], manifest["history_symbols"])
        self.assertEqual(["000001"], selected["selected_symbols"])
        self.assertEqual(1, selected["filtered_spot_rows"])
        self.assertEqual(1, selected["selected_symbol_count"])
        self.assertEqual(1, selected["max_history_symbols"])

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


if __name__ == "__main__":
    unittest.main()
