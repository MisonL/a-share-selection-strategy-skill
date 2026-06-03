from __future__ import annotations

import importlib.util
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
from stock_selection_data import read_table  # noqa: E402
from helpers import build_frame  # noqa: E402


HAS_PARQUET_ENGINE = any(
    importlib.util.find_spec(name) for name in ("pyarrow", "fastparquet")
)


def run_validate_cli(input_path: Path) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = validate_ohlcv.main(["--input", str(input_path)])
    return code, stdout.getvalue(), stderr.getvalue()


def run_score_cli(input_path: Path, output_path: Path) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = scorer.main(
            [
                "--input",
                str(input_path),
                "--config",
                str(SCRIPTS / "example_config.json"),
                "--output",
                str(output_path),
            ]
        )
    return code, stdout.getvalue(), stderr.getvalue()


@unittest.skipUnless(HAS_PARQUET_ENGINE, "pyarrow or fastparquet is required")
class StockSelectionParquetCliTests(unittest.TestCase):
    def test_validate_and_score_parquet_matches_csv_output(self) -> None:
        frame = build_frame(include_turn=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            csv_input = base / "prices.csv"
            parquet_input = base / "prices.parquet"
            csv_output = base / "candidates_csv.csv"
            parquet_output = base / "candidates_parquet.csv"
            frame.to_csv(csv_input, index=False)
            frame.to_parquet(parquet_input, index=False)

            validate_code, validate_stdout, validate_stderr = run_validate_cli(
                parquet_input
            )
            csv_code, _, csv_stderr = run_score_cli(csv_input, csv_output)
            parquet_code, parquet_stdout, parquet_stderr = run_score_cli(
                parquet_input,
                parquet_output,
            )

            self.assertEqual(0, validate_code, validate_stderr)
            self.assertIn("OK: validated", validate_stdout)
            self.assertEqual(0, csv_code, csv_stderr)
            self.assertEqual(0, parquet_code, parquet_stderr)
            csv_result = pd.read_csv(csv_output, dtype={"symbol": str})
            parquet_result = pd.read_csv(parquet_output, dtype={"symbol": str})
            exact_columns = ["symbol", "signal_tier", "recommendation"]
            self.assertEqual(
                csv_result[exact_columns].to_dict("records"),
                parquet_result[exact_columns].to_dict("records"),
            )
            for csv_score, parquet_score in zip(
                csv_result["total_score"],
                parquet_result["total_score"],
            ):
                self.assertAlmostEqual(csv_score, parquet_score, places=12)
            self.assertIn("input=prices.parquet", parquet_stdout)

    def test_read_table_keeps_parquet_symbol_column_as_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "numeric-symbol.parquet"
            pd.DataFrame([{"symbol": 12345, "date": "2026-05-30"}]).to_parquet(
                path,
                index=False,
            )

            loaded = read_table(path)

        self.assertEqual("12345", loaded["symbol"].iloc[0])


if __name__ == "__main__":
    unittest.main()
