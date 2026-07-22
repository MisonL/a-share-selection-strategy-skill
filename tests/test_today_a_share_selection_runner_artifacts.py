from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
sys.path.insert(0, str(TESTS))

import test_today_a_share_selection_runner as runner_suite  # noqa: E402


class TodayAShareSelectionRunnerArtifactTests(unittest.TestCase):
    def test_runner_copies_local_spot_companion_metadata_for_execution(self) -> None:
        frame = runner_suite.build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = (
            frame[["open", "high", "low", "close"]] * 0.75
        )
        metadata = {
            "source": "baostock",
            "source_scope": "baostock_universe_snapshot",
            "real_market_data": True,
            "resolved_snapshot_date": "2026-07-21",
            "date_fallback_used": True,
            "partial_result": False,
            "source_claim_boundary": (
                "baostock_universe_snapshot_not_realtime_spot_or_full_market_proof"
            ),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "input.csv"
            spot = root / "spot.csv"
            source_metadata = root / "spot_metadata.json"
            output = root / "run"
            frame.to_csv(prices, index=False)
            spot.write_text("symbol,price\n000002,8.88\n", encoding="utf-8")
            source_metadata.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            source_metadata_text = source_metadata.read_text(encoding="utf-8")

            code, _stdout, stderr = runner_suite.call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--output-dir",
                    str(output),
                    "--no-html-report",
                ]
            )
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            copied_metadata = output / "spot_metadata.json"
            copied_metadata_text = copied_metadata.read_text(encoding="utf-8")

        expected_sha256 = hashlib.sha256(source_metadata_text.encode("utf-8")).hexdigest()
        self.assertEqual(0, code, stderr)
        self.assertEqual(source_metadata_text, copied_metadata_text)
        self.assertEqual("local_spot_input_companion", manifest["spot_metadata_origin"])
        self.assertEqual(str(source_metadata), manifest["spot_input_metadata_source"])
        self.assertEqual(str(copied_metadata), manifest["spot_input_metadata_output"])
        self.assertTrue(manifest["spot_input_metadata_output_exists"])
        self.assertTrue(manifest["spot_input_metadata_output_written"])
        self.assertEqual(expected_sha256, manifest["spot_input_metadata_sha256"])
        self.assertEqual(
            "local_spot_input_companion_metadata_not_runner_fetch_output_or_full_market_proof",
            manifest["spot_input_metadata_claim_boundary"],
        )
        self.assertEqual("local_spot_input_companion", summary["spot_metadata_origin"])
        self.assertTrue(summary["spot_input_metadata_output_exists"])
        self.assertTrue(summary["spot_input_metadata_output_written"])
        self.assertEqual(expected_sha256, summary["spot_input_metadata_sha256"])
        self.assertTrue(summary["spot_metadata"]["date_fallback_used"])
        self.assertEqual("2026-07-21", summary["spot_metadata"]["resolved_snapshot_date"])
        self.assertEqual(1, summary["spot_rows"])
        self.assertFalse(summary["full_market_claim_allowed"])

    def test_runner_plan_only_copies_local_spot_companion_metadata(self) -> None:
        metadata = {
            "source": "baostock",
            "source_scope": "baostock_universe_snapshot",
            "real_market_data": True,
            "symbol_count": 2,
            "resolved_snapshot_date": "2026-07-21",
            "date_fallback_used": True,
            "partial_result": False,
            "source_claim_boundary": (
                "baostock_universe_snapshot_not_realtime_spot_or_full_market_proof"
            ),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            source_metadata = root / "spot_metadata.json"
            output = root / "run"
            spot.write_text(
                "symbol,name\n000001,Alpha\n600000,Beta\n", encoding="utf-8"
            )
            source_metadata.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            source_metadata_text = source_metadata.read_text(encoding="utf-8")

            code, _stdout, stderr = runner_suite.call_runner(
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
            copied_metadata = output / "spot_metadata.json"
            copied_metadata_text = copied_metadata.read_text(encoding="utf-8")

        expected_sha256 = hashlib.sha256(source_metadata_text.encode("utf-8")).hexdigest()
        self.assertEqual(0, code, stderr)
        self.assertFalse(manifest["commands_executed"])
        self.assertEqual("planned", summary["status"])
        self.assertEqual("local_spot_input_companion", summary["spot_metadata_origin"])
        self.assertEqual(str(source_metadata), summary["spot_input_metadata_source"])
        self.assertEqual(str(copied_metadata), summary["spot_input_metadata_output"])
        self.assertTrue(summary["spot_input_metadata_output_exists"])
        self.assertTrue(summary["spot_input_metadata_output_written"])
        self.assertEqual(expected_sha256, summary["spot_input_metadata_sha256"])
        self.assertEqual(source_metadata_text, copied_metadata_text)
        self.assertEqual(2, summary["spot_rows"])
        self.assertTrue(summary["spot_metadata"]["date_fallback_used"])
        self.assertEqual("2026-07-21", summary["spot_metadata"]["resolved_snapshot_date"])
        self.assertFalse(summary["full_market_claim_allowed"])

    def test_runner_reuses_samefile_spot_companion_without_claiming_copy(self) -> None:
        frame = runner_suite.build_frame(include_turn=True, include_tradability=True)
        metadata = {
            "source": "baostock",
            "source_scope": "baostock_universe_snapshot",
            "real_market_data": True,
            "symbol_count": 1,
            "partial_result": False,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            inputs = root / "inputs"
            output = root / "run"
            inputs.mkdir()
            output.mkdir()
            prices = inputs / "prices.csv"
            spot = inputs / "spot.csv"
            source_metadata = inputs / "spot_metadata.json"
            target_metadata = output / "spot_metadata.json"
            frame.to_csv(prices, index=False)
            spot.write_text("symbol,price\n000002,8.88\n", encoding="utf-8")
            source_metadata.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            target_metadata.hardlink_to(source_metadata)
            source_metadata_text = source_metadata.read_text(encoding="utf-8")

            code, _stdout, stderr = runner_suite.call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--output-dir",
                    str(output),
                    "--no-html-report",
                ]
            )
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            target_metadata_text = target_metadata.read_text(encoding="utf-8")

        expected_sha256 = hashlib.sha256(source_metadata_text.encode("utf-8")).hexdigest()
        self.assertEqual(0, code, stderr)
        self.assertEqual(source_metadata_text, target_metadata_text)
        self.assertEqual("local_spot_input_companion", manifest["spot_metadata_origin"])
        self.assertEqual(str(source_metadata), manifest["spot_input_metadata_source"])
        self.assertEqual(str(target_metadata), manifest["spot_input_metadata_output"])
        self.assertTrue(manifest["spot_input_metadata_output_exists"])
        self.assertFalse(manifest["spot_input_metadata_output_written"])
        self.assertEqual(expected_sha256, manifest["spot_input_metadata_sha256"])
        self.assertTrue(summary["spot_input_metadata_output_exists"])
        self.assertFalse(summary["spot_input_metadata_output_written"])
        self.assertEqual(expected_sha256, summary["spot_input_metadata_sha256"])

    def test_runner_reuses_samepath_spot_companion_without_claiming_copy(self) -> None:
        frame = runner_suite.build_frame(include_turn=True, include_tradability=True)
        metadata = {
            "source": "baostock",
            "source_scope": "baostock_universe_snapshot",
            "real_market_data": True,
            "symbol_count": 1,
            "partial_result": False,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            inputs = root / "inputs"
            output = root / "run"
            inputs.mkdir()
            output.mkdir()
            prices = inputs / "prices.csv"
            spot = output / "spot.csv"
            metadata_path = output / "spot_metadata.json"
            frame.to_csv(prices, index=False)
            spot.write_text("symbol,price\n000002,8.88\n", encoding="utf-8")
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            metadata_text = metadata_path.read_text(encoding="utf-8")

            code, _stdout, stderr = runner_suite.call_runner(
                [
                    "--prices-input",
                    str(prices),
                    "--spot-input",
                    str(spot),
                    "--output-dir",
                    str(output),
                    "--no-html-report",
                ]
            )
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            output_metadata_text = metadata_path.read_text(encoding="utf-8")

        expected_sha256 = hashlib.sha256(metadata_text.encode("utf-8")).hexdigest()
        self.assertEqual(0, code, stderr)
        self.assertEqual(metadata_text, output_metadata_text)
        self.assertEqual("local_spot_input_companion", manifest["spot_metadata_origin"])
        self.assertEqual(str(metadata_path), manifest["spot_input_metadata_source"])
        self.assertEqual(str(metadata_path), manifest["spot_input_metadata_output"])
        self.assertTrue(manifest["spot_input_metadata_output_exists"])
        self.assertFalse(manifest["spot_input_metadata_output_written"])
        self.assertEqual(expected_sha256, manifest["spot_input_metadata_sha256"])
        self.assertTrue(summary["spot_input_metadata_output_exists"])
        self.assertFalse(summary["spot_input_metadata_output_written"])
        self.assertEqual(expected_sha256, summary["spot_input_metadata_sha256"])

    def test_runner_writes_generated_baostock_history_symbols_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"
            args = runner_suite.parsed_args(
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
            manifest = runner_suite.runner.initial_manifest(args)
            context = runner_suite.runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                runner_suite.history_metadata_executor,
            )

            runner_suite.runner.run_pipeline(context)
            generated = output / "history_symbols.txt"
            generated_text = generated.read_text(encoding="utf-8")

        fetch_history = next(
            step for step in manifest["steps"] if step["step"] == "fetch_history"
        )
        self.assertEqual("000001\n600000\n", generated_text)
        self.assertIn("--symbols-file", fetch_history["command"])
        self.assertIn(str(generated), fetch_history["command"])
        self.assertNotIn("000001,600000", fetch_history["command"])
        self.assertEqual(str(generated), manifest["history_symbols_file"])
        self.assertEqual(
            "runner_generated_history_symbols",
            manifest["history_symbols_file_origin"],
        )
        self.assertTrue(manifest["history_symbols_file_output_written"])
        self.assertEqual(2, manifest["history_symbols_file_symbol_count"])
        self.assertEqual(
            hashlib.sha256(generated_text.encode("utf-8")).hexdigest(),
            manifest["history_symbols_file_sha256"],
        )

    def test_runner_preserves_explicit_baostock_symbols_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "run"
            symbols_file = root / "symbols.txt"
            symbols_file.write_text("000001\n600000\n000001\n", encoding="utf-8")
            expected_sha256 = hashlib.sha256(symbols_file.read_bytes()).hexdigest()
            args = runner_suite.parsed_args(
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
            manifest = runner_suite.runner.initial_manifest(args)
            context = runner_suite.runner.RunContext(
                args,
                manifest,
                output / "run_manifest.json",
                runner_suite.history_metadata_executor,
            )

            runner_suite.runner.run_pipeline(context)

        fetch_history = next(
            step for step in manifest["steps"] if step["step"] == "fetch_history"
        )
        self.assertIn("--symbols-file", fetch_history["command"])
        self.assertIn(str(symbols_file), fetch_history["command"])
        self.assertNotIn("000001,600000", fetch_history["command"])
        self.assertEqual(str(symbols_file), manifest["history_symbols_file"])
        self.assertEqual("explicit_symbols_file", manifest["history_symbols_file_origin"])
        self.assertTrue(manifest["history_symbols_file_exists"])
        self.assertFalse(manifest["history_symbols_file_output_written"])
        self.assertEqual(2, manifest["history_symbols_file_symbol_count"])
        self.assertEqual(expected_sha256, manifest["history_symbols_file_sha256"])

    def test_runner_baostock_plan_only_writes_large_symbols_file(self) -> None:
        symbols = [f"{600000 + index:06d}" for index in range(5200)]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"

            code, _stdout, stderr = runner_suite.call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--symbols",
                    ",".join(symbols),
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
            symbols_path = output / "history_symbols.txt"
            symbols_text = symbols_path.read_text(encoding="utf-8")
            fetch_history = next(
                step for step in manifest["steps"] if step["step"] == "fetch_history"
            )

        self.assertEqual(0, code, stderr)
        self.assertFalse(manifest["commands_executed"])
        self.assertTrue(manifest["plan_only"])
        self.assertIn("--symbols-file", fetch_history["command"])
        self.assertIn(str(symbols_path), fetch_history["command"])
        self.assertNotIn(",".join(symbols), fetch_history["command"])
        self.assertEqual("\n".join(symbols) + "\n", symbols_text)
        self.assertEqual(str(symbols_path), manifest["history_symbols_file"])
        self.assertTrue(manifest["history_symbols_file_output_written"])
        self.assertEqual(5200, manifest["history_symbols_file_symbol_count"])
        self.assertEqual(
            hashlib.sha256(symbols_text.encode("utf-8")).hexdigest(),
            manifest["history_symbols_file_sha256"],
        )
        self.assertEqual(str(symbols_path), summary["history_symbols_file"])
        self.assertTrue(summary["history_symbols_file_output_written"])
        self.assertEqual(5200, summary["history_symbols_file_symbol_count"])
        self.assertEqual(
            manifest["history_symbols_file_sha256"],
            summary["history_symbols_file_sha256"],
        )

    def test_runner_placeholder_does_not_write_history_symbols_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "run"

            code, _stdout, stderr = runner_suite.call_runner(
                [
                    "--output-dir",
                    str(output),
                    "--history-source",
                    "baostock",
                    "--fetch-spot",
                    "baostock_universe",
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
            fetch_history = next(
                step for step in manifest["steps"] if step["step"] == "fetch_history"
            )

        self.assertEqual(0, code, stderr)
        self.assertFalse(manifest["commands_executed"])
        self.assertEqual(["<derived_from_spot_snapshot>"], manifest["history_symbols"])
        self.assertEqual("", manifest["history_symbols_file"])
        self.assertEqual("not_applicable", manifest["history_symbols_file_origin"])
        self.assertFalse((output / "history_symbols.txt").exists())
        self.assertIn("<derived_from_spot_snapshot>", fetch_history["command"])
        self.assertNotIn("--symbols-file", fetch_history["command"])
