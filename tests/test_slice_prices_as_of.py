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

import slice_prices_as_of as slicer  # noqa: E402
from helpers import build_frame  # noqa: E402


class SlicePricesAsOfTests(unittest.TestCase):
    def test_slice_keeps_only_rows_on_or_before_cutoff(self) -> None:
        frame = build_frame(days=20)
        cutoff = sorted(frame["date"].unique())[9]
        sliced = slicer.slice_prices(frame, as_of_date=cutoff)
        dates = pd.to_datetime(sliced["date"])
        self.assertLessEqual(dates.max(), pd.Timestamp(cutoff))
        self.assertEqual(20, len(sliced))
        self.assertEqual({"000002", "600001"}, set(sliced["symbol"]))

    def test_cli_writes_output_and_reports_summary(self) -> None:
        frame = build_frame(days=20)
        cutoff = sorted(frame["date"].unique())[9]
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "slice.csv"
            frame.to_csv(input_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = slicer.main(
                    [
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_path),
                        "--as-of-date",
                        cutoff,
                    ]
                )
            self.assertEqual(0, code, stderr.getvalue())
            self.assertTrue(output_path.exists())
            self.assertIn("rows=20", stdout.getvalue())
            self.assertIn("as_of_date_observed=true", stdout.getvalue())
            self.assertIn("claim_boundary=as_of_cutoff_not_signal_day", stdout.getvalue())

    def test_cli_discloses_when_as_of_date_is_not_observed(self) -> None:
        frame = build_frame(days=3)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "slice.csv"
            frame.to_csv(input_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = slicer.main(
                    [
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_path),
                        "--as-of-date",
                        "2026-06-06",
                    ]
                )

            self.assertEqual(0, code, stderr.getvalue())
            self.assertIn("as_of_date=2026-06-06", stdout.getvalue())
            self.assertIn("as_of_date_observed=false", stdout.getvalue())
            self.assertIn("claim_boundary=as_of_cutoff_not_signal_day", stdout.getvalue())
            actual_date = pd.to_datetime(frame["date"]).max().date().isoformat()
            sliced = pd.read_csv(output_path, dtype={"symbol": str})
            self.assertEqual({"2026-06-06"}, set(sliced["requested_as_of_date"]))
            self.assertEqual({actual_date}, set(sliced["actual_data_date"]))
            self.assertEqual({False}, set(sliced["as_of_date_observed"]))

    def test_empty_slice_is_error_without_output(self) -> None:
        frame = build_frame(days=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "slice.csv"
            frame.to_csv(input_path, index=False)
            stderr = StringIO()
            with redirect_stderr(stderr):
                code = slicer.main(
                    [
                        "--input",
                        str(input_path),
                        "--output",
                        str(output_path),
                        "--as-of-date",
                        "2020-01-01",
                    ]
                )
        self.assertEqual(2, code)
        self.assertFalse(output_path.exists())
        self.assertIn("no rows on or before", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
