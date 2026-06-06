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

import fetch_yfinance_ohlcv as fetcher  # noqa: E402


class FetchYfinanceOhlcvTests(unittest.TestCase):
    def test_parse_symbols_uppercases_and_rejects_empty(self) -> None:
        self.assertEqual(["AAPL", "MSFT"], fetcher.parse_symbols("aapl, MSFT"))
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            fetcher.parse_symbols(" , ")

    def test_history_rows_maps_close_not_adj_close(self) -> None:
        history = pd.DataFrame(
            [
                {
                    "Open": 10.0,
                    "High": 11.0,
                    "Low": 9.5,
                    "Close": 10.5,
                    "Adj Close": 99.0,
                    "Volume": 1200,
                }
            ],
            index=pd.to_datetime(["2026-05-20"]),
        )
        rows = fetcher.history_rows(history, "AAPL", market="US")

        self.assertEqual("AAPL", rows[0]["symbol"])
        self.assertEqual("US", rows[0]["market"])
        self.assertEqual("2026-05-20", rows[0]["date"])
        self.assertEqual(10.5, rows[0]["close"])
        self.assertEqual(1200, rows[0]["volume"])

    def test_cli_writes_prices_and_metadata_with_fake_yfinance(self) -> None:
        calls = []
        fake = fake_yfinance(
            {
                "AAPL": pd.DataFrame(
                    [
                        {
                            "Open": 10.0,
                            "High": 11.0,
                            "Low": 9.5,
                            "Close": 10.5,
                            "Volume": 1200,
                        }
                    ],
                    index=pd.to_datetime(["2026-05-20"]),
                )
            },
            calls=calls,
        )
        old_module = sys.modules.get("yfinance")
        sys.modules["yfinance"] = fake
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stdout = StringIO()
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "AAPL",
                            "--start-date",
                            "2026-05-01",
                            "--end-date",
                            "2026-05-29",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--timeout-seconds",
                            "7",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                frame = pd.read_csv(output)
        finally:
            restore_module("yfinance", old_module)

        self.assertEqual(0, code)
        self.assertIn("OK: source=yfinance rows=1", stdout.getvalue())
        self.assertIn("market_label_only=true", stdout.getvalue())
        self.assertEqual(1, saved["rows"])
        self.assertTrue(saved["market_label_only"])
        self.assertEqual(
            "market_label_not_source_exchange_or_calendar_proof",
            saved["source_claim_boundary"],
        )
        self.assertEqual(7.0, saved["timeout_seconds"])
        self.assertEqual(7.0, calls[0]["timeout"])
        self.assertEqual([], saved["failed_symbols"])
        self.assertEqual([], saved["empty_symbols"])
        self.assertEqual("AAPL", frame["symbol"].iloc[0])

    def test_cli_empty_fetch_returns_strict_error_with_metadata(self) -> None:
        fake = fake_yfinance({"AAPL": pd.DataFrame()})
        old_module = sys.modules.get("yfinance")
        sys.modules["yfinance"] = fake
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
                            "AAPL",
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
            restore_module("yfinance", old_module)

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertEqual(0, saved["rows"])
        self.assertEqual(["AAPL"], saved["empty_symbols"])
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("rows=0", stderr.getvalue())
        self.assertIn("empty_symbols=1", stderr.getvalue())

    def test_cli_partial_default_stdout_discloses_partial_result(self) -> None:
        fake = fake_yfinance(
            {
                "AAPL": pd.DataFrame(
                    [
                        {
                            "Open": 10.0,
                            "High": 11.0,
                            "Low": 9.5,
                            "Close": 10.5,
                            "Volume": 1200,
                        }
                    ],
                    index=pd.to_datetime(["2026-05-20"]),
                ),
                "MSFT": pd.DataFrame(),
            }
        )
        old_module = sys.modules.get("yfinance")
        sys.modules["yfinance"] = fake
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stdout = StringIO()
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "AAPL,MSFT",
                            "--start-date",
                            "2026-05-01",
                            "--end-date",
                            "2026-05-29",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                output_exists = output.exists()
        finally:
            restore_module("yfinance", old_module)

        self.assertEqual(0, code)
        self.assertTrue(output_exists)
        self.assertTrue(saved["output_written"])
        self.assertEqual(["MSFT"], saved["empty_symbols"])
        self.assertTrue(stdout.getvalue().startswith("PARTIAL:"))
        self.assertIn("empty_symbols=1", stdout.getvalue())

    def test_cli_strict_error_removes_stale_outputs(self) -> None:
        fake = fake_yfinance({"AAPL": pd.DataFrame()})
        old_module = sys.modules.get("yfinance")
        sys.modules["yfinance"] = fake
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                output.write_text("symbol,date,close\nSTALE,2026-01-01,1\n", encoding="utf-8")
                metadata.write_text('{"stale": true}\n', encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "AAPL",
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
                output_exists = output.exists()
                metadata_exists = metadata.exists()
                saved = json.loads(metadata.read_text(encoding="utf-8"))
        finally:
            restore_module("yfinance", old_module)

        self.assertEqual(3, code)
        self.assertFalse(output_exists)
        self.assertTrue(metadata_exists)
        self.assertEqual(["AAPL"], saved["empty_symbols"])
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("empty_symbols=1", stderr.getvalue())


def fake_yfinance(
    histories: dict[str, pd.DataFrame],
    calls: list[dict[str, object]] | None = None,
) -> types.SimpleNamespace:
    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kwargs: object) -> pd.DataFrame:
            if calls is not None:
                calls.append({"symbol": self.symbol, **kwargs})
            return histories[self.symbol]

    return types.SimpleNamespace(Ticker=FakeTicker)


def restore_module(name: str, module: object | None) -> None:
    if module is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = module


if __name__ == "__main__":
    unittest.main()
