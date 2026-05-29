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
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import backtest_buy_hold as backtest  # noqa: E402
from helpers import build_frame  # noqa: E402


class BuyHoldBacktestCliTests(unittest.TestCase):
    def test_buy_hold_returns_close_to_close_result(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][
            ["symbol", "date"]
        ]
        result, summary = backtest.run_backtest(prices, candidate, hold_days=5)
        history = prices[prices["symbol"] == "000002"].reset_index(drop=True)
        expected = history.loc[25, "close"] / history.loc[20, "close"] - 1

        self.assertEqual(1, summary["completed_trades"])
        self.assertEqual(0, summary["incomplete_trades"])
        self.assertAlmostEqual(expected, float(result["return"].iloc[0]))
        self.assertEqual("excluded", result["cost_model"].iloc[0])
        self.assertEqual("excluded", result["slippage_model"].iloc[0])
        self.assertEqual("not_modeled", result["tradability_model"].iloc[0])

    def test_missing_entry_date_is_not_rolled_forward(self) -> None:
        prices = build_frame(days=130)
        candidate = pd.DataFrame([{"symbol": "000002", "date": "2025-01-04"}])
        result, summary = backtest.run_backtest(prices, candidate, hold_days=5)
        self.assertEqual(1, summary["incomplete_trades"])
        self.assertTrue(bool(result["missing_data"].iloc[0]))
        self.assertEqual("missing_entry_price", result["missing_reason"].iloc[0])

    def test_cli_strict_incomplete_returns_error_without_output(self) -> None:
        prices = build_frame(days=130)
        candidate = pd.DataFrame([{"symbol": "000002", "date": "2025-12-31"}])
        with tempfile.TemporaryDirectory() as tmpdir:
            prices_path = Path(tmpdir) / "prices.csv"
            candidates_path = Path(tmpdir) / "candidates.csv"
            output_path = Path(tmpdir) / "backtest.csv"
            prices.to_csv(prices_path, index=False)
            candidate.to_csv(candidates_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = backtest.main(
                    [
                        "--prices",
                        str(prices_path),
                        "--candidates",
                        str(candidates_path),
                        "--output",
                        str(output_path),
                        "--fail-on-incomplete",
                    ]
                )
        self.assertEqual(3, code)
        self.assertFalse(output_path.exists())
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("incomplete_trades=1", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
