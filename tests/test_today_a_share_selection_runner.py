from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
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
        self.assertEqual("generic", manifest["mode"])
        self.assertTrue(manifest["lightgbm_not_used"])
        self.assertEqual("completed", summary["status"])
        self.assertEqual([], summary["failed_steps"])
        self.assertEqual(2, summary["score"]["raw_symbols"])
        self.assertEqual(2, summary["score"]["candidates"])
        self.assertFalse(summary["score"]["effective_empty_result"])

    def test_qsss_runner_fails_without_prediction_and_keeps_manifest(self) -> None:
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
                    "qsss",
                ]
            )

            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(3, code)
        self.assertIn("step=validate", stderr)
        self.assertEqual(["validate"], [step["step"] for step in manifest["steps"]])
        self.assertEqual(["validate"], summary["failed_steps"])
        self.assertEqual("failed", summary["status"])
        self.assertTrue(manifest["qsss_mode"])

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

        self.assertEqual(0, code, stderr)
        score_command = manifest["steps"][1]["command"]
        self.assertIn("--spot-input", score_command)
        self.assertEqual("local_prices_input", manifest["source_scope"])

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
                "qsss_mode": False,
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


def call_runner(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = runner.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
