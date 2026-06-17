from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_akshare_hk_daily as fetcher  # noqa: E402


class FetchAkshareHkDailyTests(unittest.TestCase):
    def test_parse_symbols_accepts_common_hk_forms(self) -> None:
        self.assertEqual(
            ["00700", "09988", "08001"],
            fetcher.parse_symbols("700,HK.09988,08001.HK"),
        )
        with self.assertRaisesRegex(ValueError, "HK symbols"):
            fetcher.parse_symbols("0700.HK.US")

    def test_parse_symbols_rejects_empty_and_zero_codes_before_padding(self) -> None:
        for symbols in ["0", "00000", "HK.", ".HK"]:
            with self.subTest(symbols=symbols):
                with self.assertRaisesRegex(ValueError, "HK symbols"):
                    fetcher.parse_symbols(symbols)

    def test_collect_rows_maps_hk_ohlcv_and_amount(self) -> None:
        rows = fetcher.collect_rows(valid_history(), "00700")

        self.assertEqual("00700", rows[0]["symbol"])
        self.assertEqual("HK", rows[0]["market"])
        self.assertEqual(1000, rows[0]["volume"])
        self.assertEqual(10100, rows[0]["amount"])

    def test_cli_writes_prices_and_metadata_with_fake_akshare(self) -> None:
        fake = fake_akshare(histories={"00700": valid_history()})
        old_module = sys.modules.get("akshare")
        sys.modules["akshare"] = fake
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stdout = StringIO()
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "700",
                            "--start-date",
                            "2026-05-01",
                            "--end-date",
                            "2026-05-29",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                frame = pd.read_csv(output, dtype={"symbol": str})
        finally:
            restore_module("akshare", old_module)

        self.assertEqual(0, code)
        self.assertIn("OK: source=akshare_stock_hk_daily rows=1", stdout.getvalue())
        self.assertEqual("unknown", saved["real_market_data"])
        self.assertEqual(
            "akshare_stock_hk_daily_not_exchange_calendar_or_tradability_proof",
            saved["source_claim_boundary"],
        )
        self.assertEqual("00700", frame["symbol"].iloc[0])
        self.assertEqual("HK", frame["market"].iloc[0])

    def test_cli_strict_empty_symbol_returns_metadata_without_prices(self) -> None:
        fake = fake_akshare(histories={"00700": pd.DataFrame(columns=valid_history().columns)})
        old_module = sys.modules.get("akshare")
        sys.modules["akshare"] = fake
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "00700",
                            "--start-date",
                            "2026-05-01",
                            "--end-date",
                            "2026-05-29",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
        finally:
            restore_module("akshare", old_module)

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertEqual(["00700"], saved["empty_symbols"])
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("empty_symbols=1", stderr.getvalue())


def valid_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-05-20",
                "open": 10.0,
                "high": 10.2,
                "low": 9.9,
                "close": 10.1,
                "volume": 1000,
                "amount": 10100,
            }
        ]
    )


def fake_akshare(
    *,
    histories: dict[str, pd.DataFrame] | None = None,
) -> types.SimpleNamespace:
    histories = histories or {"00700": valid_history()}

    def stock_hk_daily(**kwargs: object) -> pd.DataFrame:
        return histories[str(kwargs["symbol"])]

    return types.SimpleNamespace(stock_hk_daily=stock_hk_daily)


def restore_module(name: str, module: object | None) -> None:
    if module is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = module


if __name__ == "__main__":
    unittest.main()
