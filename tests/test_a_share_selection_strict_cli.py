from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
