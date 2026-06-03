from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "stock-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import score_candidates as scorer  # noqa: E402
import validate_ohlcv  # noqa: E402
from helpers import build_frame, load_config  # noqa: E402


class StockSelectionProfileGateTests(unittest.TestCase):
    def test_prediction_rejects_non_six_digit_ashare_symbol(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame = frame[frame["symbol"] == "600001"].copy()
        frame["symbol"] = "60001"
        with self.assertRaisesRegex(ValueError, "preserve leading zeros"):
            scorer.score_candidates(frame, config)

    def test_prediction_ignores_off_universe_short_history(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        off_universe = build_frame(
            days=10,
            include_prediction=True,
            include_turn=True,
        )
        off_universe = off_universe[off_universe["symbol"] == "000002"].copy()
        off_universe["symbol"] = "700000"
        frame = pd.concat([frame, off_universe], ignore_index=True)
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(3, summary["raw_symbols"])
        self.assertEqual(2, summary["input_symbols"])
        self.assertEqual(1, summary["universe_filtered_symbols"])
        self.assertEqual(0, summary["market_filtered_symbols"])
        self.assertEqual(0, summary["insufficient_history_symbols"])

    def test_prediction_reports_in_universe_short_history_in_summary(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        short = build_frame(days=10, include_prediction=True, include_turn=True)
        short = short[short["symbol"] == "000002"].copy()
        short["symbol"] = "300001"
        frame = pd.concat([frame, short], ignore_index=True)
        candidates, summary = scorer.score_candidates(frame, config)
        self.assertEqual(3, summary["input_symbols"])
        self.assertEqual(1, summary["insufficient_history_symbols"])
        self.assertEqual(["300001"], summary["insufficient_history_symbol_examples"])
        self.assertGreater(len(candidates), 0)

    def test_validate_cli_with_prediction_config_checks_profile_columns(self) -> None:
        frame = build_frame(include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            frame.to_csv(input_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = validate_ohlcv.main(
                    [
                        "--input",
                        str(input_path),
                        "--config",
                        str(SCRIPTS / "prediction_profile_config.json"),
                    ]
                )
        self.assertEqual(1, code)
        self.assertIn("prediction or prediction_score", stderr.getvalue())
        self.assertIn("instead of substituting technical indicators", stderr.getvalue())

    def test_validate_cli_rejects_yfinance_market_label_as_ashare_proof(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        frame["symbol"] = "AAPL"
        frame["market"] = "A-share"
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            frame.to_csv(input_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = validate_ohlcv.main(
                    [
                        "--input",
                        str(input_path),
                        "--config",
                        str(SCRIPTS / "prediction_profile_config.json"),
                    ]
                )
        self.assertEqual(1, code)
        self.assertIn("symbols must be six digits", stderr.getvalue())
        self.assertIn("market labels do not prove A-share source", stderr.getvalue())

    def test_validate_cli_with_prediction_config_rejects_market_alias(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        frame["market"] = "A股"
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            frame.to_csv(input_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = validate_ohlcv.main(
                    [
                        "--input",
                        str(input_path),
                        "--config",
                        str(SCRIPTS / "prediction_profile_config.json"),
                    ]
                )
        self.assertEqual(1, code)
        self.assertIn("requires at least one A-share row", stderr.getvalue())
        self.assertIn("invalid_market_values=A股", stderr.getvalue())

    def test_validate_cli_with_prediction_config_rejects_mixed_market_alias(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        frame.loc[frame["symbol"] == "000002", "market"] = "A股"
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            frame.to_csv(input_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = validate_ohlcv.main(
                    [
                        "--input",
                        str(input_path),
                        "--config",
                        str(SCRIPTS / "prediction_profile_config.json"),
                    ]
                )
        self.assertEqual(1, code)
        self.assertIn("A-share rows must use market=A-share", stderr.getvalue())
        self.assertIn("invalid_market_values=A股", stderr.getvalue())

    def test_validate_cli_with_prediction_config_rejects_suffixed_ashare_symbol(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        frame["symbol"] = frame["symbol"].map({"000002": "000002.SZ", "600001": "600001.SH"})
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            frame.to_csv(input_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = validate_ohlcv.main(
                    [
                        "--input",
                        str(input_path),
                        "--config",
                        str(SCRIPTS / "prediction_profile_config.json"),
                    ]
                )
        self.assertEqual(1, code)
        self.assertIn("six digits", stderr.getvalue())

    def test_low_price_profile_rejects_missing_tradability_columns(self) -> None:
        frame = build_frame(include_turn=True, include_tradability=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            frame.to_csv(input_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = validate_ohlcv.main(
                    [
                        "--input",
                        str(input_path),
                        "--config",
                        str(SCRIPTS / "ultra_short_low_price_config.json"),
                    ]
                )
        self.assertEqual(1, code)
        self.assertIn("requires isST column", stderr.getvalue())
        self.assertIn("requires tradestatus column", stderr.getvalue())

    def test_cli_reports_in_universe_short_history_examples(self) -> None:
        frame = build_frame(include_prediction=True, include_turn=True)
        short = build_frame(days=10, include_prediction=True, include_turn=True)
        short = short[short["symbol"] == "000002"].copy()
        short["symbol"] = "300001"
        frame = pd.concat([frame, short], ignore_index=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "prediction.csv"
            frame.to_csv(input_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = scorer.main(
                    [
                        "--input",
                        str(input_path),
                        "--config",
                        str(SCRIPTS / "prediction_profile_config.json"),
                        "--output",
                        str(output_path),
                    ]
                )
        self.assertEqual(0, code)
        self.assertIn("insufficient_history_symbols=1", stdout.getvalue())
        self.assertIn("insufficient_history_symbol_examples=300001", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
