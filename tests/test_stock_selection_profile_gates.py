from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import score_candidates as scorer  # noqa: E402
import validate_ohlcv  # noqa: E402
from helpers import build_frame, load_config  # noqa: E402


class StockSelectionProfileGateTests(unittest.TestCase):
    def test_qsss_rejects_non_six_digit_ashare_symbol(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame = frame[frame["symbol"] == "600001"].copy()
        frame["symbol"] = "60001"
        with self.assertRaisesRegex(ValueError, "six digits"):
            scorer.score_candidates(frame, config)

    def test_qsss_ignores_off_universe_short_history(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        off_universe = build_frame(
            days=10,
            include_prediction=True,
            include_turn=True,
        )
        off_universe = off_universe[off_universe["symbol"] == "000002"].copy()
        off_universe["symbol"] = "00700"
        off_universe["market"] = "HK"
        frame = pd.concat([frame, off_universe], ignore_index=True)
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(3, summary["raw_symbols"])
        self.assertEqual(2, summary["input_symbols"])
        self.assertEqual(1, summary["universe_filtered_symbols"])
        self.assertEqual(0, summary["insufficient_history_symbols"])

    def test_validate_cli_with_qsss_config_checks_profile_columns(self) -> None:
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
                        str(SCRIPTS / "qsss_profile_config.json"),
                    ]
                )
        self.assertEqual(1, code)
        self.assertIn("prediction or prediction_score", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
