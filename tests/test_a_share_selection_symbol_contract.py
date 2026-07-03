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
from a_share_selection_symbols import (  # noqa: E402
    A_SHARE_EXCHANGES,
    listing_board,
    normalize_symbol_values,
    parse_a_share_symbols,
    parse_six_digit_symbols,
    valid_hk_symbol_text,
)
from helpers import build_frame  # noqa: E402


class AShareSelectionSymbolContractTests(unittest.TestCase):
    def test_parse_six_digit_symbols_accepts_sh_sz_prefixes_and_suffixes(self) -> None:
        self.assertEqual(
            ["000001", "600000"],
            parse_six_digit_symbols("sz.000001,600000.SH"),
        )

    def test_parse_six_digit_symbols_rejects_bj_for_sh_sz_sources(self) -> None:
        with self.assertRaisesRegex(ValueError, "bj.430047"):
            parse_six_digit_symbols("bj.430047")

    def test_parse_a_share_symbols_accepts_bj_prefixes_and_suffixes(self) -> None:
        self.assertEqual(
            ["000001", "600000", "430047", "835185"],
            parse_a_share_symbols("sz.000001,600000.SH,bj.430047,835185.BJ"),
        )

    def test_normalize_symbol_values_only_strips_bj_when_explicitly_allowed(self) -> None:
        self.assertEqual(["bj.430047"], normalize_symbol_values(["bj.430047"]))
        self.assertEqual(
            ["430047"],
            normalize_symbol_values(["bj.430047"], allowed_exchanges=A_SHARE_EXCHANGES),
        )

    def test_listing_board_derives_a_share_board_from_symbol_prefix(self) -> None:
        cases = {
            "000001": "主板",
            "600000.SH": "主板",
            "sz.300001": "创业板",
            "688001": "科创板",
            "bj.430047": "北证",
            "835185.BJ": "北证",
            "920001": "北证",
            "00700.HK": "港股主板",
            "hk.09988": "港股主板",
            "08001.HK": "港股 GEM",
            "123456": "未知",
            "bad": "未知",
        }
        for symbol, expected in cases.items():
            with self.subTest(symbol=symbol):
                self.assertEqual(expected, listing_board(symbol))

    def test_listing_board_uses_hk_market_for_plain_five_digit_symbol(self) -> None:
        self.assertEqual("港股主板", listing_board("00700", "HK"))
        self.assertEqual("港股 GEM", listing_board("08001", "港股"))

    def test_hk_symbol_text_rejects_zero_code(self) -> None:
        for symbol in ["0", "00000", "HK.", ".HK"]:
            with self.subTest(symbol=symbol):
                self.assertFalse(valid_hk_symbol_text(symbol))

    def test_validate_rejects_float_numeric_damaged_symbol(self) -> None:
        frame = build_frame()
        frame["symbol"] = "1.0"
        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)
        joined = "; ".join(errors)

        self.assertIn("preserve leading zeros as text", joined)
        self.assertIn("examples=", joined)
        self.assertIn("symbol=1.0", joined)

    def test_validate_accepts_hk_five_digit_symbols_when_market_is_hk(self) -> None:
        frame = build_frame()
        frame["symbol"] = frame["symbol"].map({"000002": "00700", "600001": "08001"})
        frame["market"] = "HK"
        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)

        self.assertNotIn("preserve leading zeros", "; ".join(errors))

    def test_hk_parquet_numeric_symbols_are_not_silently_zero_padded(self) -> None:
        frame = build_frame()
        frame["symbol"] = 700
        frame["market"] = "HK"
        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)

        self.assertNotIn("preserve leading zeros", "; ".join(errors))
        self.assertNotEqual("港股主板", listing_board(700, "A-share"))

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
