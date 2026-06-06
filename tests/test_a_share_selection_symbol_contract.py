from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import score_candidates as scorer  # noqa: E402
import validate_ohlcv  # noqa: E402
from helpers import build_frame  # noqa: E402


class AShareSelectionSymbolContractTests(unittest.TestCase):
    def test_validate_rejects_float_numeric_damaged_symbol(self) -> None:
        frame = build_frame()
        frame["symbol"] = "1.0"
        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)
        joined = "; ".join(errors)

        self.assertIn("preserve leading zeros as text", joined)
        self.assertIn("examples=", joined)
        self.assertIn("symbol=1.0", joined)

    def test_score_rejects_float_numeric_damaged_symbol_without_output(self) -> None:
        frame = build_frame()
        frame.loc[frame["symbol"] == "000002", "symbol"] = "1.0"
        frame.loc[frame["symbol"] == "600001", "symbol"] = "600001.0"
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            input_path = base / "prices.csv"
            output_path = base / "candidates.csv"
            frame.to_csv(input_path, index=False)

            code, _, stderr = run_score_cli(input_path, output_path)

        self.assertEqual(2, code)
        self.assertFalse(output_path.exists())
        self.assertIn("preserve leading zeros as text", stderr)
        self.assertIn("symbol=1.0", stderr)


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


if __name__ == "__main__":
    unittest.main()
