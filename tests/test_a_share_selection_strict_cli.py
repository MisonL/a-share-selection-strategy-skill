from __future__ import annotations

import json
import os
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
        self.assertNotIn("EMPTY_RESULT:", stdout)
        self.assertIn("effective_empty_result=true", stderr)
        self.assertIn("empty_result_reason=threshold_filtered_all", stderr)

    def test_cli_successful_empty_result_reports_artifact_paths(self) -> None:
        frame = build_frame(
            include_prediction=True,
            prediction_value=0.1,
            include_turn=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "prices.csv"
            output_path = root / "prediction_empty.csv"
            diagnostics_path = root / "diagnostics.csv"
            profile_path = root / "profile.json"
            frame.to_csv(input_path, index=False)
            code, stdout, stderr = run_score_cli(
                input_path,
                output_path,
                ["--profile-output", str(profile_path)],
                diagnostics_output=diagnostics_path,
            )
            output_exists = output_path.exists()
            diagnostics_exists = diagnostics_path.exists()
            profile_exists = profile_path.exists()

        self.assertEqual(0, code, stderr)
        self.assertTrue(output_exists)
        self.assertTrue(diagnostics_exists)
        self.assertTrue(profile_exists)
        empty_result_lines = [
            line for line in stdout.splitlines() if line.startswith("EMPTY_RESULT: ")
        ]
        self.assertEqual(1, len(empty_result_lines))
        empty_result = empty_result_lines[0]
        self.assertIn("candidates=0", empty_result)
        self.assertIn("effective_empty_result=true", empty_result)
        self.assertIn("empty_result_reason=threshold_filtered_all", empty_result)
        self.assertIn(f"candidates_output={output_path}", empty_result)
        self.assertIn(f"diagnostics_output={diagnostics_path}", empty_result)
        self.assertIn(f"profile_output={profile_path}", empty_result)

    def test_cli_empty_result_marks_unrequested_optional_outputs(self) -> None:
        frame = build_frame(
            include_prediction=True,
            prediction_value=0.1,
            include_turn=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "prices.csv"
            output_path = root / "prediction_empty.csv"
            frame.to_csv(input_path, index=False)
            code, stdout, stderr = run_score_cli(input_path, output_path, [])

        self.assertEqual(0, code, stderr)
        empty_result = next(
            line for line in stdout.splitlines() if line.startswith("EMPTY_RESULT: ")
        )
        self.assertIn("diagnostics_output=not_requested", empty_result)
        self.assertIn("profile_output=not_requested", empty_result)

    def test_cli_nonempty_success_does_not_report_empty_result(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "prices.csv"
            output_path = root / "prediction.csv"
            frame.to_csv(input_path, index=False)
            code, stdout, stderr = run_score_cli(input_path, output_path, [])
            output_exists = output_path.exists()

        self.assertEqual(0, code, stderr)
        self.assertTrue(output_exists)
        self.assertNotIn("EMPTY_RESULT:", stdout)

    def test_cli_bad_input_removes_stale_output_and_diagnostics(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        frame = frame.drop(columns=["market"])
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "prediction_bad.csv"
            diagnostics_path = Path(tmpdir) / "diagnostics.csv"
            frame.to_csv(input_path, index=False)
            input_contents = input_path.read_bytes()
            output_path.write_text("stale-candidates\n", encoding="utf-8")
            diagnostics_path.write_text("stale-diagnostics\n", encoding="utf-8")
            code, stdout, stderr = run_score_cli(
                input_path,
                output_path,
                [],
                diagnostics_output=diagnostics_path,
            )
            output_exists = output_path.exists()
            diagnostics_exists = diagnostics_path.exists()
            input_after = input_path.read_bytes()
        self.assertEqual(2, code)
        self.assertFalse(output_exists)
        self.assertFalse(diagnostics_exists)
        self.assertEqual(input_contents, input_after)
        self.assertNotIn("EMPTY_RESULT:", stdout)
        self.assertIn("output_not_written=true", stderr)

    def test_cli_rejects_output_collisions_before_loading_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_contents = b"prices input must remain intact\n"
            config_contents = b"{}\n"
            spot_contents = b"spot input must remain intact\n"
            output_contents = b"stale candidates\n"
            original_ensure = scorer.ensure_runtime_dependencies
            dependency_loads = 0

            def record_dependency_load() -> None:
                nonlocal dependency_loads
                dependency_loads += 1

            scorer.ensure_runtime_dependencies = record_dependency_load
            try:
                for name in [
                    "output_equals_input",
                    "diagnostics_equals_input",
                    "profile_equals_config",
                    "output_equals_spot_input",
                    "output_equals_diagnostics",
                    "relative_output_alias",
                    "symlink_output_alias",
                ]:
                    with self.subTest(name=name):
                        case_root = root / name
                        case_root.mkdir()
                        input_path = case_root / "prices.csv"
                        config_path = case_root / "config.json"
                        spot_path = case_root / "spot.csv"
                        output_path = case_root / "stale-candidates.csv"
                        input_path.write_bytes(input_contents)
                        config_path.write_bytes(config_contents)
                        spot_path.write_bytes(spot_contents)
                        output_path.write_bytes(output_contents)
                        symlink_output = case_root / "prices-link.csv"
                        symlink_output.symlink_to(input_path)
                        relative_input = os.path.relpath(input_path, start=Path.cwd())
                        output_value = str(output_path)
                        diagnostics_value = None
                        profile_value = None
                        spot_value = None
                        expected_error = "output path must differ from input paths"
                        if name == "output_equals_input":
                            output_value = str(input_path)
                        elif name == "diagnostics_equals_input":
                            diagnostics_value = str(input_path)
                        elif name == "profile_equals_config":
                            profile_value = str(config_path)
                        elif name == "output_equals_spot_input":
                            output_value = str(spot_path)
                            spot_value = str(spot_path)
                        elif name == "output_equals_diagnostics":
                            diagnostics_value = str(output_path)
                            expected_error = "output paths must be distinct"
                        elif name == "relative_output_alias":
                            output_value = relative_input
                        else:
                            output_value = str(symlink_output)
                        args = [
                            "--input",
                            str(input_path),
                            "--config",
                            str(config_path),
                            "--output",
                            output_value,
                        ]
                        if diagnostics_value is not None:
                            args.extend(["--diagnostics-output", diagnostics_value])
                        if profile_value is not None:
                            args.extend(["--profile-output", profile_value])
                        if spot_value is not None:
                            args.extend(["--spot-input", spot_value])
                        stdout = StringIO()
                        stderr = StringIO()
                        with redirect_stdout(stdout), redirect_stderr(stderr):
                            code = scorer.main(args)

                        self.assertEqual(2, code)
                        self.assertEqual("", stdout.getvalue())
                        self.assertIn(expected_error, stderr.getvalue())
                        self.assertIn("output_not_written=true", stderr.getvalue())
                        self.assertEqual(input_contents, input_path.read_bytes())
                        self.assertEqual(config_contents, config_path.read_bytes())
                        self.assertEqual(spot_contents, spot_path.read_bytes())
                        self.assertEqual(output_contents, output_path.read_bytes())
            finally:
                scorer.ensure_runtime_dependencies = original_ensure

            self.assertEqual(0, dependency_loads)

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
