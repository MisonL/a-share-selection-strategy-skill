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
sys.path.insert(0, str(SCRIPTS))

import portfolio_equity_curve as equity_curve  # noqa: E402


class PortfolioEquityCurveCliTests(unittest.TestCase):
    def test_builds_equal_weight_compounded_curve(self) -> None:
        first = backtest_frame("2026-05-12", [-0.02, -0.04])
        second = backtest_frame("2026-05-15", [0.10, 0.00])

        curve, summary = equity_curve.build_equity_curve(
            [second, first],
            initial_equity=100.0,
        )

        self.assertEqual(["2026-05-12", "2026-05-15"], curve["signal_date"].tolist())
        self.assertEqual(2, int(curve["positions"].iloc[0]))
        self.assertAlmostEqual(-0.03, float(curve["mean_return"].iloc[0]))
        self.assertAlmostEqual(97.0, float(curve["equity"].iloc[0]))
        self.assertAlmostEqual(101.85, float(curve["equity"].iloc[1]))
        self.assertAlmostEqual(100.0, float(curve["running_peak"].iloc[0]))
        self.assertEqual(4, summary["positions"])
        self.assertEqual(0, summary["incomplete_trades"])
        self.assertAlmostEqual(0.0185, summary["total_return"])
        self.assertAlmostEqual(-0.03, summary["max_drawdown"])
        self.assertEqual("START", summary["max_drawdown_peak_date"])
        self.assertEqual("2026-05-12", summary["max_drawdown_trough_date"])

    def test_cli_strict_incomplete_returns_error_without_output(self) -> None:
        frame = backtest_frame("2026-05-12", [0.05], incomplete_rows=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            backtest = Path(tmpdir) / "backtest.csv"
            output = Path(tmpdir) / "equity.csv"
            frame.to_csv(backtest, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = equity_curve.main(
                    [
                        "--backtests",
                        str(backtest),
                        "--output",
                        str(output),
                        "--fail-on-incomplete",
                    ]
                )

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("incomplete_trades=1", stderr.getvalue())

    def test_cli_threshold_failure_returns_error_without_output(self) -> None:
        frame = backtest_frame("2026-05-12", [-0.05, -0.07])
        with tempfile.TemporaryDirectory() as tmpdir:
            backtest = Path(tmpdir) / "backtest.csv"
            output = Path(tmpdir) / "equity.csv"
            frame.to_csv(backtest, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = equity_curve.main(
                    [
                        "--backtests",
                        str(backtest),
                        "--output",
                        str(output),
                        "--min-final-equity",
                        "0.98",
                        "--max-drawdown-floor",
                        "-0.03",
                    ]
                )

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("final_equity=0.94 min_final_equity=0.98", stderr.getvalue())
        self.assertIn("max_drawdown=-0.06000000000000005", stderr.getvalue())

    def test_cli_success_discloses_local_baseline_boundary(self) -> None:
        frame = backtest_frame("2026-05-12", [0.05])
        with tempfile.TemporaryDirectory() as tmpdir:
            backtest = Path(tmpdir) / "backtest.csv"
            output = Path(tmpdir) / "equity.csv"
            frame.to_csv(backtest, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = equity_curve.main(
                    [
                        "--backtests",
                        str(backtest),
                        "--output",
                        str(output),
                    ]
                )
            output_exists = output.exists()
            curve = pd.read_csv(output)

        self.assertEqual(0, code, stderr.getvalue())
        self.assertTrue(output_exists)
        self.assertEqual(
            ["local_complete_trades_baseline_not_return_promise"],
            curve["claim_boundary"].tolist(),
        )
        self.assertIn(
            "claim_boundary=local_complete_trades_baseline_not_return_promise",
            stdout.getvalue(),
        )

    def test_cli_non_strict_incomplete_warns_about_excluded_trades(self) -> None:
        frame = backtest_frame("2026-05-12", [0.05], incomplete_rows=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            backtest = Path(tmpdir) / "backtest.csv"
            output = Path(tmpdir) / "equity.csv"
            frame.to_csv(backtest, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = equity_curve.main(
                    [
                        "--backtests",
                        str(backtest),
                        "--output",
                        str(output),
                    ]
                )

        self.assertEqual(0, code, stderr.getvalue())
        self.assertIn("incomplete_trades=1", stdout.getvalue())
        self.assertIn("complete_trades_only=true", stdout.getvalue())
        self.assertIn("final_equity_excludes_incomplete=true", stdout.getvalue())
        self.assertIn("WARNING: incomplete_trades_excluded=1", stderr.getvalue())
        self.assertIn("--fail-on-incomplete", stderr.getvalue())

    def test_rejects_missing_required_columns(self) -> None:
        frame = pd.DataFrame([{"signal_date": "2026-05-12", "return": 0.01}])

        with self.assertRaisesRegex(ValueError, "missing_data"):
            equity_curve.build_equity_curve([frame], initial_equity=1.0)

    def test_numeric_missing_data_flag_excludes_trade(self) -> None:
        frame = backtest_frame("2026-05-12", [0.01])
        frame["missing_data"] = 1.0

        with self.assertRaisesRegex(ValueError, "no complete trades"):
            equity_curve.build_equity_curve([frame], initial_equity=1.0)


def backtest_frame(
    signal_date: str,
    returns: list[float],
    *,
    incomplete_rows: int = 0,
) -> pd.DataFrame:
    rows = [
        {
            "symbol": f"00000{index}",
            "signal_date": signal_date,
            "return": value,
            "missing_data": False,
            "status": "complete",
        }
        for index, value in enumerate(returns, start=1)
    ]
    rows.extend(
        {
            "symbol": f"99999{index}",
            "signal_date": signal_date,
            "return": pd.NA,
            "missing_data": True,
            "status": "incomplete",
        }
        for index in range(incomplete_rows)
    )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
