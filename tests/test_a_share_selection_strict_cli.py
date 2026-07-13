from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import score_candidates as scorer  # noqa: E402
import validate_ohlcv  # noqa: E402
from helpers import build_frame  # noqa: E402


def run_score_cli(
    input_path: Path,
    output_path: Path,
    extra_args: list[str],
    diagnostics_output: Path | None = None,
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    args = [
        "--input",
        str(input_path),
        "--config",
        str(SCRIPTS / "prediction_profile_config.json"),
        "--output",
        str(output_path),
        *extra_args,
    ]
    if diagnostics_output is not None:
        args.extend(["--diagnostics-output", str(diagnostics_output)])
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = scorer.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class AShareSelectionStrictCliTests(unittest.TestCase):
    def test_cli_help_lists_strict_gate_arguments(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as caught:
            scorer.main(["--help"])
        self.assertEqual(0, caught.exception.code)
        self.assertIn("--fail-on-skipped", stdout.getvalue())
        self.assertIn("--fail-on-empty-result", stdout.getvalue())

    def test_validate_help_lists_profile_config_argument(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as caught:
            validate_ohlcv.main(["--help"])
        self.assertEqual(0, caught.exception.code)
        self.assertIn("--config", stdout.getvalue())

    def test_cli_strict_skipped_symbols_returns_error_without_output(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        short = build_frame(days=10, include_prediction=True, include_turn=True)
        short = short[short["symbol"] == "000002"].copy()
        short["symbol"] = "300001"
        frame = pd.concat([frame, short], ignore_index=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "prediction_strict.csv"
            frame.to_csv(input_path, index=False)
            code, stdout, stderr = run_score_cli(
                input_path,
                output_path,
                ["--fail-on-skipped"],
            )
        self.assertEqual(3, code)
        self.assertFalse(output_path.exists())
        self.assertIn("ERROR_SUMMARY:", stdout)
        self.assertIn("insufficient_history_symbols=1", stderr)

    def test_cli_strict_empty_result_returns_error_without_output(self) -> None:
        frame = build_frame(
            include_prediction=True,
            prediction_value=0.1,
            include_turn=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "prediction_empty_strict.csv"
            frame.to_csv(input_path, index=False)
            code, stdout, stderr = run_score_cli(
                input_path,
                output_path,
                ["--fail-on-empty-result"],
            )
        self.assertEqual(3, code)
        self.assertFalse(output_path.exists())
        self.assertIn("ERROR_SUMMARY:", stdout)
        self.assertIn("effective_empty_result=true", stderr)
        self.assertIn("empty_result_reason=threshold_filtered_all", stderr)

    def test_cli_bad_input_removes_stale_output_and_diagnostics(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        frame = frame.drop(columns=["market"])
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "prediction_bad.csv"
            diagnostics_path = Path(tmpdir) / "diagnostics.csv"
            frame.to_csv(input_path, index=False)
            output_path.write_text("stale-candidates\n", encoding="utf-8")
            diagnostics_path.write_text("stale-diagnostics\n", encoding="utf-8")
            code, _stdout, stderr = run_score_cli(
                input_path,
                output_path,
                [],
                diagnostics_output=diagnostics_path,
            )
            output_exists = output_path.exists()
            diagnostics_exists = diagnostics_path.exists()
        self.assertEqual(2, code)
        self.assertFalse(output_exists)
        self.assertFalse(diagnostics_exists)
        self.assertIn("output_not_written=true", stderr)

    def test_cli_strict_empty_removes_stale_output_and_diagnostics(self) -> None:
        frame = build_frame(
            include_prediction=True,
            prediction_value=0.1,
            include_turn=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "prediction_empty_strict.csv"
            diagnostics_path = Path(tmpdir) / "diagnostics.csv"
            frame.to_csv(input_path, index=False)
            output_path.write_text("stale-candidates\n", encoding="utf-8")
            diagnostics_path.write_text("stale-diagnostics\n", encoding="utf-8")
            code, _stdout, stderr = run_score_cli(
                input_path,
                output_path,
                ["--fail-on-empty-result"],
                diagnostics_output=diagnostics_path,
            )
            output_exists = output_path.exists()
            diagnostics_exists = diagnostics_path.exists()
        self.assertEqual(3, code)
        self.assertFalse(output_exists)
        self.assertFalse(diagnostics_exists)
        self.assertIn("output_not_written=true", stderr)

    def test_cli_profile_output_is_explicit_observability_only(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "prices.csv"
            output_path = root / "candidates.csv"
            diagnostics_path = root / "diagnostics.csv"
            profile_path = root / "score_profile.json"
            frame.to_csv(input_path, index=False)

            code, _stdout, stderr = run_score_cli(
                input_path,
                output_path,
                ["--profile-output", str(profile_path)],
                diagnostics_output=diagnostics_path,
            )
            output_exists = output_path.exists()
            diagnostics_exists = diagnostics_path.exists()
            profile = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertEqual(0, code, stderr)
        self.assertTrue(output_exists)
        self.assertTrue(diagnostics_exists)
        self.assertEqual("score_candidates_profile_v1", profile["profile_schema"])
        self.assertEqual(len(frame), profile["input_rows"])
        self.assertGreaterEqual(profile["candidate_rows"], 0)
        self.assertGreater(profile["duration_seconds"], 0)
        self.assertNotIn("started_monotonic", profile)
        self.assertNotIn("last_monotonic", profile)
        stages = [item["stage"] for item in profile["stages"]]
        self.assertIn("input_loaded", stages)
        self.assertIn("scored", stages)
        self.assertIn("profile_write_started", stages)

    def test_cli_default_does_not_write_profile_output(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "prices.csv"
            output_path = root / "candidates.csv"
            profile_path = root / "score_profile.json"
            frame.to_csv(input_path, index=False)

            code, _stdout, stderr = run_score_cli(input_path, output_path, [])
            output_exists = output_path.exists()
            profile_exists = profile_path.exists()

        self.assertEqual(0, code, stderr)
        self.assertTrue(output_exists)
        self.assertFalse(profile_exists)

    def test_cli_strict_failure_removes_stale_profile_output(self) -> None:
        frame = build_frame(
            include_prediction=True,
            prediction_value=0.1,
            include_turn=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "prices.csv"
            output_path = root / "prediction_empty_strict.csv"
            profile_path = root / "score_profile.json"
            frame.to_csv(input_path, index=False)
            output_path.write_text("stale-candidates\n", encoding="utf-8")
            profile_path.write_text("{}\n", encoding="utf-8")

            code, _stdout, stderr = run_score_cli(
                input_path,
                output_path,
                ["--fail-on-empty-result", "--profile-output", str(profile_path)],
            )

        self.assertEqual(3, code)
        self.assertFalse(output_path.exists())
        self.assertFalse(profile_path.exists())
        self.assertIn("output_not_written=true", stderr)


if __name__ == "__main__":
    unittest.main()
