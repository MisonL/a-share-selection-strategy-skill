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
SKILL_ROOT = ROOT / "skills" / "stock-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_akshare_a_share as fetcher  # noqa: E402


class FetchAkshareAShareTests(unittest.TestCase):
    def test_parse_symbols_requires_six_digits(self) -> None:
        self.assertEqual(["000001", "600000"], fetcher.parse_symbols("000001,600000"))
        with self.assertRaisesRegex(ValueError, "six digits"):
            fetcher.parse_symbols("1")

    def test_akshare_date_accepts_dash_or_compact(self) -> None:
        self.assertEqual("20260529", fetcher.akshare_date("2026-05-29"))
        self.assertEqual("20260529", fetcher.akshare_date("20260529"))
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            fetcher.akshare_date("2026/05/29")

    def test_collect_rows_maps_amount_separately_from_volume(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "日期": "2026-05-20",
                    "股票代码": "1",
                    "开盘": 10.0,
                    "最高": 10.2,
                    "最低": 9.9,
                    "收盘": 10.1,
                    "成交量": 1000,
                    "成交额": 10100,
                    "换手率": 0.5,
                }
            ]
        )
        rows = fetcher.collect_rows(raw, "000001")

        self.assertEqual("000001", rows[0]["symbol"])
        self.assertEqual("A-share", rows[0]["market"])
        self.assertEqual(1000, rows[0]["volume"])
        self.assertEqual(10100, rows[0]["amount"])
        self.assertEqual(0.5, rows[0]["turn"])

    def test_cli_writes_prices_and_metadata_with_fake_akshare(self) -> None:
        fake = fake_akshare(histories={"000001": valid_history()})
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
                            "000001",
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
        self.assertIn("OK: source=akshare rows=1", stdout.getvalue())
        self.assertEqual(1, saved["rows"])
        self.assertEqual(1, saved["symbol_count"])
        self.assertEqual([], saved["failed_symbols"])
        self.assertEqual([], saved["fallback_errors"])
        self.assertEqual("stock_zh_a_hist", saved["symbols"][0]["provider"])
        self.assertEqual("000001", frame["symbol"].iloc[0])

    def test_cli_falls_back_to_daily_when_hist_fails(self) -> None:
        fake = fake_akshare(hist_error=ConnectionError("hist unavailable"))
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
                            "000001",
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
        self.assertIn("fallback_errors=1", stdout.getvalue())
        self.assertEqual("stock_zh_a_daily", saved["symbols"][0]["provider"])
        self.assertEqual("000001", frame["symbol"].iloc[0])
        self.assertEqual(2000, frame["volume"].iloc[0])
        self.assertEqual(20400, frame["amount"].iloc[0])
        self.assertIn("hist unavailable", saved["fallback_errors"][0]["error"])

    def test_cli_strict_invalid_rows_returns_error_with_metadata(self) -> None:
        fake = fake_akshare(
            histories={
                "000001": pd.DataFrame(
                    [
                        {
                            **valid_history().iloc[0].to_dict(),
                            "成交量": "",
                            "成交额": "",
                            "换手率": "",
                        }
                    ]
                )
            }
        )
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
                            "000001",
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
        self.assertEqual(1, saved["invalid_rows"])
        self.assertEqual(0, saved["dropped_invalid_rows"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("invalid_rows=1", stderr.getvalue())


def valid_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "日期": "2026-05-20",
                "股票代码": "000001",
                "开盘": 10.0,
                "最高": 10.2,
                "最低": 9.9,
                "收盘": 10.1,
                "成交量": 1000,
                "成交额": 10100,
                "换手率": 0.5,
            }
        ]
    )


def valid_daily() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-05-20",
                "open": 10.0,
                "high": 10.3,
                "low": 9.8,
                "close": 10.2,
                "volume": 2000,
                "amount": 20400,
                "turnover": 0.8,
            }
        ]
    )


def fake_akshare(
    *,
    histories: dict[str, pd.DataFrame] | None = None,
    daily: dict[str, pd.DataFrame] | None = None,
    hist_error: Exception | None = None,
) -> types.SimpleNamespace:
    histories = histories or {"000001": valid_history()}
    daily = daily or {"sz000001": valid_daily()}

    def stock_zh_a_hist(**kwargs: object) -> pd.DataFrame:
        if hist_error:
            raise hist_error
        return histories[str(kwargs["symbol"])]

    def stock_zh_a_daily(**kwargs: object) -> pd.DataFrame:
        return daily[str(kwargs["symbol"])]

    return types.SimpleNamespace(
        stock_zh_a_hist=stock_zh_a_hist,
        stock_zh_a_daily=stock_zh_a_daily,
    )


def restore_module(name: str, module: object | None) -> None:
    if module is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = module


if __name__ == "__main__":
    unittest.main()
