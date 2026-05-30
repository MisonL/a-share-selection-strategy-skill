from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd


TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from test_walk_forward_artifact_cli import build_run, call_cli, drop_column  # noqa: E402
from test_walk_forward_artifact_cli import price_row  # noqa: E402
from walk_forward_artifact_checks import price_window_errors  # noqa: E402


class WalkForwardArtifactPriceCliTests(unittest.TestCase):
    def test_price_window_accepts_unsorted_expected_symbol_order(self) -> None:
        rows = [price_row("000001"), price_row("600000")]

        errors = price_window_errors(rows, "2026-05-12", ["600000", "000001"])

        self.assertEqual([], errors)

    def test_cli_rejects_candidate_close_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            update_first_value(root / "signals/2026-05-12/qsss_candidates.csv", "close", 9.0)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_candidates_close_raw_mismatch=000001", stderr)

    def test_cli_rejects_missing_candidate_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            drop_column(root / "signals/2026-05-12/qsss_candidates.csv", "close")

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_candidates_missing_close", stderr)

    def test_cli_rejects_sized_signal_close_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            update_first_value(root / "signals/2026-05-12/qsss_sized_candidates.csv", "signal_close", 9.0)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_sized_signal_close_raw_mismatch=000001", stderr)

    def test_cli_rejects_optional_sized_close_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            update_first_value(root / "signals/2026-05-12/qsss_sized_candidates.csv", "close", 9.0)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_sized_close_raw_mismatch=000001", stderr)


def update_first_value(path: Path, column: str, value: object) -> None:
    rows = pd.read_csv(path, dtype={"symbol": str})
    rows.loc[0, column] = value
    rows.to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
