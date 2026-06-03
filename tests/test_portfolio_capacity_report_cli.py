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
TESTS = ROOT / "tests"
sys_path = __import__("sys").path
sys_path.insert(0, str(SCRIPTS))
sys_path.insert(0, str(TESTS))

import portfolio_overlap_report as overlap_report  # noqa: E402
from test_portfolio_overlap_report_cli import capitalized_trade, trade  # noqa: E402


class PortfolioCapacityReportCliTests(unittest.TestCase):
    def test_cli_accepts_notional_and_cash_reserved_under_limits(self) -> None:
        frame = pd.DataFrame(
            [
                capitalized_trade(
                    "000001", "2026-05-12", "2026-05-12", "2026-05-14", 0.4, 40000.0
                ),
                capitalized_trade(
                    "000002", "2026-05-12", "2026-05-13", "2026-05-14", 0.5, 50000.0
                ),
            ]
        )
        code, _, _, summary, daily = run_overlap_cli(
            frame, ["--max-gross-notional", "100000", "--max-cash-reserved", "100000"]
        )

        self.assertEqual(0, code)
        self.assertEqual(90000.0, summary["max_gross_notional"])
        self.assertEqual(90000.0, summary["max_cash_reserved"])
        self.assertEqual(["2026-05-13", "2026-05-14"], summary["max_gross_notional_dates"])
        self.assertEqual([40000.0, 90000.0, 90000.0], daily["gross_notional"].tolist())
        self.assertEqual([40000.0, 90000.0, 90000.0], daily["cash_reserved"].tolist())

    def test_cli_fails_when_notional_or_cash_reserved_exceeds_limit(self) -> None:
        frame = pd.DataFrame(
            [
                capitalized_trade(
                    "000001", "2026-05-12", "2026-05-12", "2026-05-14", 0.5, 70000.0
                ),
                capitalized_trade(
                    "000002", "2026-05-12", "2026-05-13", "2026-05-14", 0.5, 45000.0
                ),
            ]
        )
        code, stdout, stderr, _, _ = run_overlap_cli(
            frame, ["--max-gross-notional", "100000", "--max-cash-reserved", "100000"]
        )

        self.assertEqual(3, code)
        self.assertIn("ERROR_SUMMARY:", stdout)
        self.assertIn("max_gross_notional=115000.0 limit=100000.0", stderr)
        self.assertIn("max_cash_reserved=115000.0 limit=100000.0", stderr)

    def test_amount_gates_only_require_their_own_columns(self) -> None:
        notional_only = pd.DataFrame(
            [trade("000001", "2026-05-12", "2026-05-12", "2026-05-14", notional=1000.0)]
        )
        no_amounts = pd.DataFrame([trade("000001", "2026-05-12", "2026-05-12", "2026-05-14")])

        self.assertEqual(0, run_overlap_cli(notional_only, ["--max-gross-notional", "1000"])[0])
        self.assertIn(
            "cash_reserved_missing",
            run_overlap_cli(no_amounts, ["--max-cash-reserved", "1000"])[2],
        )
        self.assertIn(
            "notional_missing",
            run_overlap_cli(no_amounts, ["--max-gross-notional", "1000"])[2],
        )

    def test_non_numeric_or_negative_amount_fields_are_rejected(self) -> None:
        for field in ["notional", "cash_reserved"]:
            with self.assertRaisesRegex(ValueError, f"{field} must be numeric"):
                overlap_report.build_overlap_report([pd.DataFrame([bad_capital(field, "bad")])])
            with self.assertRaisesRegex(ValueError, f"{field} must be >= 0"):
                overlap_report.build_overlap_report([pd.DataFrame([bad_capital(field, -1)])])


def run_overlap_cli(
    frame: pd.DataFrame,
    gate_args: list[str],
) -> tuple[int, str, str, dict[str, object], pd.DataFrame]:
    with tempfile.TemporaryDirectory() as tmpdir:
        backtest = Path(tmpdir) / "backtest.csv"
        daily = Path(tmpdir) / "daily.csv"
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
                    str(Path(tmpdir) / "overlaps.csv"),
                    "--summary-output",
                    str(summary),
                    *gate_args,
                ]
            )
        data = json.loads(summary.read_text(encoding="utf-8"))
        daily_frame = pd.read_csv(daily)
    return code, stdout.getvalue(), stderr.getvalue(), data, daily_frame


def bad_capital(field: str, value: object) -> dict[str, object]:
    row = capitalized_trade("000001", "2026-05-12", "2026-05-12", "2026-05-14", 0.1)
    row[field] = value
    return row


if __name__ == "__main__":
    unittest.main()
