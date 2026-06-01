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
        result, summary = backtest.run_backtest(
            prices,
            candidate,
            hold_days=5,
            cost_bps=12.5,
            slippage_bps=7.5,
        )
        history = prices[prices["symbol"] == "000002"].reset_index(drop=True)
        gross = history.loc[25, "close"] / history.loc[20, "close"] - 1
        expected = gross - 0.002

        self.assertEqual(1, summary["completed_trades"])
        self.assertEqual(0, summary["incomplete_trades"])
        self.assertEqual(12.5, summary["cost_bps"])
        self.assertEqual(7.5, summary["slippage_bps"])
        self.assertAlmostEqual(gross, float(result["gross_return"].iloc[0]))
        self.assertAlmostEqual(expected, float(result["return"].iloc[0]))
        self.assertEqual(12.5, float(result["cost_bps"].iloc[0]))
        self.assertEqual(7.5, float(result["slippage_bps"].iloc[0]))
        self.assertEqual("round_trip_bps", result["cost_model"].iloc[0])
        self.assertEqual("round_trip_bps", result["slippage_model"].iloc[0])
        self.assertEqual("not_modeled", result["tradability_model"].iloc[0])
        self.assertEqual("not_modeled", result["limit_rules_model"].iloc[0])

    def test_cli_preserves_candidate_capital_fields_for_all_rows(self) -> None:
        prices = build_frame(days=130)
        candidate = pd.DataFrame(
            [
                {
                    "symbol": "000002",
                    "date": prices[prices["symbol"] == "000002"].iloc[20]["date"],
                    "weight": 0.25,
                    "notional": 25000.0,
                    "quantity": 1000,
                    "cash_reserved": 25000.0,
                },
                {
                    "symbol": "000002",
                    "date": "2025-12-31",
                    "weight": 0.4,
                    "notional": 40000.0,
                    "quantity": 1500,
                    "cash_reserved": 40000.0,
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            prices_path = Path(tmpdir) / "prices.csv"
            candidates_path = Path(tmpdir) / "candidates.csv"
            output_path = Path(tmpdir) / "backtest.csv"
            prices.to_csv(prices_path, index=False)
            candidate.to_csv(candidates_path, index=False)
            code = backtest.main(
                [
                    "--prices",
                    str(prices_path),
                    "--candidates",
                    str(candidates_path),
                    "--output",
                    str(output_path),
                    "--hold-days",
                    "5",
                ]
            )
            result = pd.read_csv(output_path)

        self.assertEqual(0, code)
        self.assertEqual(["complete", "incomplete"], result["status"].tolist())
        self.assertEqual(["none", "missing_entry_price"], result["missing_reason"].tolist())
        self.assertEqual([0.25, 0.4], result["weight"].tolist())
        self.assertEqual([25000.0, 40000.0], result["notional"].tolist())
        self.assertEqual([1000, 1500], result["quantity"].tolist())
        self.assertEqual([25000.0, 40000.0], result["cash_reserved"].tolist())

    def test_result_does_not_invent_missing_capital_fields(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]
        result, _ = backtest.run_backtest(prices, candidate, hold_days=5)

        self.assertNotIn("weight", result)
        self.assertNotIn("notional", result)
        self.assertNotIn("quantity", result)
        self.assertNotIn("cash_reserved", result)

    def test_missing_entry_date_is_not_rolled_forward(self) -> None:
        prices = build_frame(days=130)
        candidate = pd.DataFrame([{"symbol": "000002", "date": "2025-01-04"}])
        result, summary = backtest.run_backtest(prices, candidate, hold_days=5)
        self.assertEqual(1, summary["incomplete_trades"])
        self.assertTrue(bool(result["missing_data"].iloc[0]))
        self.assertEqual("missing_entry_price", result["missing_reason"].iloc[0])

    def test_negative_cost_or_slippage_is_rejected(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][
            ["symbol", "date"]
        ]
        with self.assertRaisesRegex(ValueError, "cost-bps"):
            backtest.run_backtest(prices, candidate, hold_days=5, cost_bps=-1)
        with self.assertRaisesRegex(ValueError, "slippage-bps"):
            backtest.run_backtest(prices, candidate, hold_days=5, slippage_bps=-1)

    def test_require_tradable_bars_marks_non_tradable_entry(self) -> None:
        prices = build_frame(days=130)
        prices["tradestatus"] = "1"
        mask = (prices["symbol"] == "000002") & (prices["date"] == prices.iloc[20]["date"])
        prices.loc[mask, "tradestatus"] = "0"
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]

        result, summary = backtest.run_backtest(
            prices,
            candidate,
            hold_days=5,
            require_tradable_bars=True,
        )

        self.assertEqual(0, summary["completed_trades"])
        self.assertEqual(1, summary["incomplete_trades"])
        self.assertTrue(summary["tradability_required"])
        self.assertEqual("tradestatus_entry_exit_only", summary["tradability_model"])
        self.assertEqual("non_tradable_entry", result["missing_reason"].iloc[0])
        self.assertEqual("tradestatus_entry_exit_only", result["tradability_model"].iloc[0])
        self.assertEqual("not_modeled", result["limit_rules_model"].iloc[0])
        self.assertEqual("non_tradable_entry:1", summary["missing_reason_counts"])

    def test_require_tradable_bars_keeps_middle_non_trading_complete(self) -> None:
        prices = build_frame(days=130)
        prices["tradestatus"] = "1"
        history = prices[prices["symbol"] == "000002"].reset_index(drop=True)
        middle_date = history.loc[23, "date"]
        mask = (prices["symbol"] == "000002") & (prices["date"] == middle_date)
        prices.loc[mask, "tradestatus"] = "0"
        candidate = history.iloc[[20]][["symbol", "date"]]

        result, summary = backtest.run_backtest(
            prices,
            candidate,
            hold_days=5,
            require_tradable_bars=True,
        )

        self.assertEqual(1, summary["completed_trades"])
        self.assertEqual(0, summary["incomplete_trades"])
        self.assertEqual("tradestatus_entry_exit_only", summary["tradability_model"])
        self.assertEqual("complete", result["status"].iloc[0])

    def test_require_tradable_holding_period_marks_middle_non_trading(self) -> None:
        prices = build_frame(days=130)
        prices["tradestatus"] = "1"
        history = prices[prices["symbol"] == "000002"].reset_index(drop=True)
        middle_date = history.loc[23, "date"]
        mask = (prices["symbol"] == "000002") & (prices["date"] == middle_date)
        prices.loc[mask, "tradestatus"] = "0"
        candidate = history.iloc[[20]][["symbol", "date"]]

        result, summary = backtest.run_backtest(
            prices,
            candidate,
            hold_days=5,
            require_holding_period_tradable=True,
        )

        self.assertEqual(0, summary["completed_trades"])
        self.assertEqual(1, summary["incomplete_trades"])
        self.assertTrue(summary["tradability_required"])
        self.assertEqual("tradestatus_holding_period_bars", summary["tradability_model"])
        self.assertEqual("non_tradable_holding_period", result["missing_reason"].iloc[0])
        self.assertEqual("tradestatus_holding_period_bars", result["tradability_model"].iloc[0])
        self.assertEqual("non_tradable_holding_period:1", summary["missing_reason_counts"])

    def test_require_tradable_holding_period_requires_status_column(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]

        result, summary = backtest.run_backtest(
            prices,
            candidate,
            hold_days=5,
            require_holding_period_tradable=True,
        )

        self.assertEqual(1, summary["incomplete_trades"])
        self.assertEqual("tradestatus_holding_period_bars", summary["tradability_model"])
        self.assertEqual("missing_tradestatus", result["missing_reason"].iloc[0])

    def test_require_tradable_bars_requires_status_column(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]

        result, summary = backtest.run_backtest(
            prices,
            candidate,
            hold_days=5,
            require_tradable_bars=True,
        )

        self.assertEqual(1, summary["incomplete_trades"])
        self.assertEqual("tradestatus_entry_exit_only", summary["tradability_model"])
        self.assertEqual("missing_tradestatus", result["missing_reason"].iloc[0])
        self.assertEqual("tradestatus_entry_exit_only", result["tradability_model"].iloc[0])

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
        self.assertIn("missing_reason_counts=missing_entry_price:1", stdout.getvalue())
        self.assertIn("tradability_model=not_modeled", stdout.getvalue())
        self.assertIn("incomplete_trades=1", stderr.getvalue())

    def test_cli_strict_missing_future_price_returns_error_without_output(self) -> None:
        prices = build_frame(days=130)
        history = prices[prices["symbol"] == "000002"].reset_index(drop=True)
        candidate = history.iloc[[-2]][["symbol", "date"]]
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
                        "--hold-days",
                        "5",
                        "--cost-bps",
                        "10",
                        "--slippage-bps",
                        "5",
                        "--fail-on-incomplete",
                    ]
                )
        self.assertEqual(3, code)
        self.assertFalse(output_path.exists())
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("missing_reason_counts=missing_future_price:1", stdout.getvalue())
        self.assertIn("cost_bps=10.0", stdout.getvalue())
        self.assertIn("slippage_bps=5.0", stdout.getvalue())
        self.assertIn("incomplete_trades=1", stderr.getvalue())

    def test_cli_require_tradable_bars_returns_error_without_output(self) -> None:
        prices = build_frame(days=130)
        prices["tradestatus"] = "1"
        history = prices[prices["symbol"] == "000002"].reset_index(drop=True)
        mask = (prices["symbol"] == "000002") & (prices["date"] == history.loc[20, "date"])
        prices.loc[mask, "tradestatus"] = "0"
        candidate = history.iloc[[20]][["symbol", "date"]]
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
                        "--require-tradable-bars",
                        "--fail-on-incomplete",
                    ]
                )

        self.assertEqual(3, code)
        self.assertFalse(output_path.exists())
        self.assertIn("tradability_required=True", stdout.getvalue())
        self.assertIn("tradability_model=tradestatus_entry_exit_only", stdout.getvalue())
        self.assertIn("limit_rules_model=not_modeled", stdout.getvalue())
        self.assertIn("missing_reason_counts=non_tradable_entry:1", stdout.getvalue())

    def test_cli_require_tradable_holding_period_returns_error_without_output(self) -> None:
        prices = build_frame(days=130)
        prices["tradestatus"] = "1"
        history = prices[prices["symbol"] == "000002"].reset_index(drop=True)
        middle_date = history.loc[23, "date"]
        mask = (prices["symbol"] == "000002") & (prices["date"] == middle_date)
        prices.loc[mask, "tradestatus"] = "0"
        candidate = history.iloc[[20]][["symbol", "date"]]
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
                        "--require-tradable-holding-period",
                        "--fail-on-incomplete",
                    ]
                )

        self.assertEqual(3, code)
        self.assertFalse(output_path.exists())
        self.assertIn("tradability_required=True", stdout.getvalue())
        self.assertIn("tradability_model=tradestatus_holding_period_bars", stdout.getvalue())
        self.assertIn("missing_reason_counts=non_tradable_holding_period:1", stdout.getvalue())
        self.assertIn("incomplete_trades=1", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
