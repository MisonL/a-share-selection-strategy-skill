from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys_path = __import__("sys").path
sys_path.insert(0, str(SCRIPTS))

import portfolio_overlap_report as overlap_report  # noqa: E402


class PortfolioOverlapReportCliTests(unittest.TestCase):
    def test_build_overlap_report_counts_overlap_and_missing_capital_fields(self) -> None:
        frame = pd.DataFrame(
            [
                trade("000001", "2026-05-12", "2026-05-12", "2026-05-14"),
                trade("000001", "2026-05-13", "2026-05-13", "2026-05-15"),
                trade("000002", "2026-05-12", "2026-05-13", "2026-05-13"),
                incomplete_trade("000003", "2026-05-12"),
            ]
        )

        daily, overlaps, summary = overlap_report.build_overlap_report([frame])

        self.assertEqual(4, summary["trades"])
        self.assertEqual(3, summary["complete_trades"])
        self.assertEqual(1, summary["incomplete_trades"])
        self.assertEqual(overlap_report.CALENDAR_MODEL, summary["calendar_model"])
        self.assertEqual(3, summary["max_open_positions"])
        self.assertEqual(["2026-05-13"], summary["max_open_position_dates"])
        self.assertEqual(2, summary["same_symbol_overlap_rows"])
        self.assertEqual(["000001"], summary["same_symbol_overlap_symbols"])
        self.assertFalse(summary["cash_capacity_verifiable"])
        self.assertEqual(["weight", "notional", "quantity", "cash_reserved"], summary["capital_fields_missing"])
        self.assertEqual(["2026-05-12", "2026-05-13", "2026-05-14", "2026-05-15"], daily["date"].tolist())
        self.assertEqual(2, len(overlaps))
        self.assertEqual(["000001"], sorted(overlaps["symbol"].unique().tolist()))

    def test_numeric_missing_data_flag_excludes_trade(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    **trade("000001", "2026-05-12", "2026-05-12", "2026-05-14"),
                    "missing_data": 1.0,
                }
            ]
        )

        daily, overlaps, summary = overlap_report.build_overlap_report([frame])

        self.assertTrue(daily.empty)
        self.assertTrue(overlaps.empty)
        self.assertEqual(0, summary["complete_trades"])
        self.assertEqual(1, summary["incomplete_trades"])

    def test_calendar_model_is_pandas_business_day_not_exchange_calendar(self) -> None:
        frame = pd.DataFrame(
            [
                trade("000001", "2026-04-30", "2026-05-01", "2026-05-05"),
            ]
        )

        daily, _overlaps, summary = overlap_report.build_overlap_report([frame])

        self.assertEqual(overlap_report.CALENDAR_MODEL, summary["calendar_model"])
        self.assertEqual(["2026-05-01", "2026-05-04", "2026-05-05"], daily["date"].tolist())

    def test_cli_reports_real_overlap_and_writes_outputs(self) -> None:
        first = pd.DataFrame(
            [
                trade("000001", "2026-05-12", "2026-05-12", "2026-05-14"),
                trade("000002", "2026-05-12", "2026-05-12", "2026-05-13"),
            ]
        )
        second = pd.DataFrame(
            [
                trade("000001", "2026-05-13", "2026-05-13", "2026-05-15"),
                trade("000003", "2026-05-13", "2026-05-13", "2026-05-13"),
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            first_path = Path(tmpdir) / "first.csv"
            second_path = Path(tmpdir) / "second.csv"
            daily = Path(tmpdir) / "daily.csv"
            overlaps = Path(tmpdir) / "overlaps.csv"
            summary = Path(tmpdir) / "summary.json"
            first.to_csv(first_path, index=False)
            second.to_csv(second_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = overlap_report.main(
                    [
                        "--backtests",
                        str(first_path),
                        str(second_path),
                        "--daily-output",
                        str(daily),
                        "--overlap-output",
                        str(overlaps),
                        "--summary-output",
                        str(summary),
                        "--max-open-positions",
                        "3",
                        "--fail-on-symbol-overlap",
                    ]
                )

            data = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(3, code)
            self.assertTrue(daily.exists())
            self.assertTrue(overlaps.exists())
            self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
            self.assertIn("capital_fields_missing=weight,notional,quantity,cash_reserved", stdout.getvalue())
            self.assertIn("max_open_positions=4 limit=3", stderr.getvalue())
            self.assertIn("same_symbol_overlap_rows=", stderr.getvalue())
            self.assertEqual(4, data["max_open_positions"])
            self.assertEqual(2, data["same_symbol_overlap_rows"])

    def test_cli_accepts_capital_fields_and_gross_weight_under_limit(self) -> None:
        frame = pd.DataFrame(
            [
                capitalized_trade("000001", "2026-05-12", "2026-05-12", "2026-05-14", 0.4),
                capitalized_trade("000002", "2026-05-12", "2026-05-13", "2026-05-14", 0.5),
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            backtest = Path(tmpdir) / "backtest.csv"
            daily = Path(tmpdir) / "daily.csv"
            overlaps = Path(tmpdir) / "overlaps.csv"
            summary = Path(tmpdir) / "summary.json"
            frame.to_csv(backtest, index=False)
            code = overlap_report.main(
                [
                    "--backtests",
                    str(backtest),
                    "--daily-output",
                    str(daily),
                    "--overlap-output",
                    str(overlaps),
                    "--summary-output",
                    str(summary),
                    "--max-gross-weight",
                    "1.0",
                    "--require-capital-fields",
                ]
            )
            data = json.loads(summary.read_text(encoding="utf-8"))
            daily_frame = pd.read_csv(daily)

        self.assertEqual(0, code)
        self.assertTrue(data["weight_capacity_verifiable"])
        self.assertTrue(data["cash_capacity_verifiable"])
        self.assertEqual([], data["capital_fields_missing"])
        self.assertEqual(0.9, round(float(data["max_gross_weight"]), 6))
        self.assertEqual(["2026-05-13", "2026-05-14"], data["max_gross_weight_dates"])
        self.assertEqual([0.4, 0.9, 0.9], daily_frame["gross_weight"].round(6).tolist())

    def test_cli_fails_when_gross_weight_exceeds_limit(self) -> None:
        frame = pd.DataFrame(
            [
                capitalized_trade("000001", "2026-05-12", "2026-05-12", "2026-05-14", 0.7),
                capitalized_trade("000002", "2026-05-12", "2026-05-13", "2026-05-14", 0.45),
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            backtest = Path(tmpdir) / "backtest.csv"
            daily = Path(tmpdir) / "daily.csv"
            overlaps = Path(tmpdir) / "overlaps.csv"
            summary = Path(tmpdir) / "summary.json"
            frame.to_csv(backtest, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = overlap_report.main(
                    [
                        "--backtests",
                        str(backtest),
                        "--daily-output",
                        str(daily),
                        "--overlap-output",
                        str(overlaps),
                        "--summary-output",
                        str(summary),
                        "--max-gross-weight",
                        "1.0",
                    ]
                )
            output_exists = daily.exists()

        self.assertEqual(3, code)
        self.assertTrue(output_exists)
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("capital_fields_missing=none", stdout.getvalue())
        self.assertIn("weight_capacity_verifiable=True", stdout.getvalue())
        self.assertIn("max_gross_weight=1.15 limit=1.0", stderr.getvalue())

    def test_cli_max_gross_weight_requires_weight_column(self) -> None:
        frame = pd.DataFrame([trade("000001", "2026-05-12", "2026-05-12", "2026-05-14")])
        with tempfile.TemporaryDirectory() as tmpdir:
            backtest = Path(tmpdir) / "backtest.csv"
            daily = Path(tmpdir) / "daily.csv"
            overlaps = Path(tmpdir) / "overlaps.csv"
            summary = Path(tmpdir) / "summary.json"
            frame.to_csv(backtest, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = overlap_report.main(
                    [
                        "--backtests",
                        str(backtest),
                        "--daily-output",
                        str(daily),
                        "--overlap-output",
                        str(overlaps),
                        "--summary-output",
                        str(summary),
                        "--max-gross-weight",
                        "1.0",
                    ]
                )

        self.assertEqual(3, code)
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("weight_missing", stderr.getvalue())

    def test_non_numeric_or_negative_capital_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "weight must be numeric"):
            overlap_report.build_overlap_report([pd.DataFrame([bad_capital("weight", "bad")])])
        with self.assertRaisesRegex(ValueError, "weight must be >= 0"):
            overlap_report.build_overlap_report([pd.DataFrame([bad_capital("weight", -1)])])


def trade(
    symbol: str,
    signal_date: str,
    entry_date: str,
    exit_date: str,
    **capital_fields: object,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "missing_data": False,
        "status": "complete",
        "entry_date": entry_date,
        "exit_date": exit_date,
        **capital_fields,
    }


def capitalized_trade(
    symbol: str,
    signal_date: str,
    entry_date: str,
    exit_date: str,
    weight: object,
    notional: object = 10000.0,
) -> dict[str, object]:
    return {
        **trade(symbol, signal_date, entry_date, exit_date),
        "weight": weight,
        "notional": notional,
        "quantity": 100,
        "cash_reserved": notional,
    }


def bad_capital(field: str, value: object) -> dict[str, object]:
    row = capitalized_trade("000001", "2026-05-12", "2026-05-12", "2026-05-14", 0.1)
    row[field] = value
    return row


def incomplete_trade(symbol: str, signal_date: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "missing_data": True,
        "status": "incomplete",
        "entry_date": "",
        "exit_date": "",
    }


if __name__ == "__main__":
    unittest.main()
