from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import fetch_zzshare_a_share as fetcher  # noqa: E402
import zzshare_a_share_data as zzshare_data  # noqa: E402
from zzshare_fetch_fakes import FakeDataApi, restore_module, valid_daily  # noqa: E402


class FetchZzshareAShareTests(unittest.TestCase):
    def test_fail_on_fetch_error_help_keeps_base_gates_explicit(self) -> None:
        help_text = fetcher.build_parser().format_help()

        self.assertIn("Also fail on failed_symbols, empty_symbols", help_text)
        self.assertIn("possibly_truncated_symbols", help_text)
        self.assertIn("Invalid, non-trading", help_text)
        self.assertIn("always strict gates", help_text)

    def test_zzshare_date_accepts_dash_or_compact(self) -> None:
        self.assertEqual("20260529", fetcher.zzshare_date("2026-05-29"))
        self.assertEqual("20260529", fetcher.zzshare_date("20260529"))
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            fetcher.zzshare_date("2026/05/29")

    def test_ts_code_maps_six_digit_symbols_to_exchange_suffix(self) -> None:
        self.assertEqual("000001.SZ", fetcher.ts_code("000001"))
        self.assertEqual("300750.SZ", fetcher.ts_code("300750"))
        self.assertEqual("600000.SH", fetcher.ts_code("600000"))
        self.assertEqual("688001.SH", fetcher.ts_code("688001"))
        self.assertEqual("900901.SH", fetcher.ts_code("900901"))
        self.assertEqual("430047.BJ", fetcher.ts_code("430047"))
        self.assertEqual("835185.BJ", fetcher.ts_code("835185"))
        self.assertEqual("920002.BJ", fetcher.ts_code("920002"))

    def test_parse_symbols_accepts_bj_prefixes_and_suffixes_for_zzshare(self) -> None:
        self.assertEqual(["430047", "835185"], fetcher.parse_symbols("bj.430047,835185.BJ"))

    def test_collect_rows_maps_zzshare_fields_and_preserves_amount(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260520",
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.9,
                    "close": 10.1,
                    "vol": 1000,
                    "amount": 10100,
                    "turnover_rate": 0.5,
                    "is_paused": 0,
                    "is_st": 0,
                    "name": "平安银行",
                }
            ]
        )

        rows = fetcher.collect_rows(raw, "000001")

        self.assertEqual("000001", rows[0]["symbol"])
        self.assertEqual("A-share", rows[0]["market"])
        self.assertEqual("2026-05-20", rows[0]["date"])
        self.assertEqual(1000, rows[0]["volume"])
        self.assertEqual(10100, rows[0]["amount"])
        self.assertEqual(0.5, rows[0]["turn"])
        self.assertEqual("zzshare", rows[0]["source"])

    def test_cli_writes_prices_and_metadata_with_fake_zzshare(self) -> None:
        fake_api = FakeDataApi({"000001.SZ": valid_daily()})
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with patch.dict("os.environ", {"ZZSHARE_TOKEN": "test-token"}):
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
                                "--http-url",
                                "https://example.test",
                                "--timeout-seconds",
                                "7",
                                "--request-interval-seconds",
                                "0",
                                "--fail-on-fetch-error",
                            ]
                        )
                    saved = json.loads(metadata.read_text(encoding="utf-8"))
                    frame = pd.read_csv(output, dtype={"symbol": str})
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertIn("OK: source=zzshare rows=1", stdout.getvalue())
        self.assertIn("source_scope=zzshare_history_fetch", stdout.getvalue())
        self.assertIn("limit=1000", stdout.getvalue())
        self.assertIn("max_pages=10", stdout.getvalue())
        self.assertIn("token_configured=true", stdout.getvalue())
        self.assertEqual(1, saved["rows"])
        self.assertEqual(1, saved["symbol_count"])
        self.assertEqual([], saved["failed_symbols"])
        self.assertEqual([], saved["empty_symbols"])
        self.assertTrue(saved["token_configured"])
        self.assertIn("quota and stability require external verification", saved["data_source_note"])
        self.assertNotIn("free SDK endpoint", saved["data_source_note"])
        self.assertEqual("https://example.test", saved["http_url"])
        self.assertEqual(7.0, saved["timeout_seconds"])
        self.assertEqual(0.0, saved["request_interval_seconds"])
        self.assertEqual("000001.SZ", saved["symbols"][0]["ts_code"])
        self.assertEqual("test-token", fake_api.instances[0].token)
        self.assertEqual(7.0, fake_api.instances[0].timeout)
        self.assertEqual("https://example.test", fake_api.instances[0].http_url)
        self.assertEqual("000001", frame["symbol"].iloc[0])

    def test_help_uses_environment_token_not_cli_token_argument(self) -> None:
        help_text = fetcher.build_parser().format_help()
        normalized = " ".join(help_text.split())

        self.assertNotIn("--token", help_text)
        self.assertIn("ZZSHARE_TOKEN environment variable", normalized)

    def test_collect_rows_leaves_missing_name_blank_for_symbol_fallback(self) -> None:
        rows = fetcher.collect_rows(valid_daily().drop(columns=["name"]), "000001")

        self.assertEqual("", rows[0]["name"])

    def test_cli_partial_default_discloses_empty_symbol(self) -> None:
        fake_api = FakeDataApi({"000001.SZ": valid_daily(), "600000.SH": pd.DataFrame()})
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stdout = StringIO()
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001,600000",
                            "--start-date",
                            "2026-05-01",
                            "--end-date",
                            "2026-05-29",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--request-interval-seconds",
                            "0",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                output_exists = output.exists()
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertTrue(output_exists)
        self.assertTrue(stdout.getvalue().startswith("PARTIAL:"))
        self.assertEqual(["600000"], saved["empty_symbols"])
        self.assertTrue(saved["output_written"])

    def test_cli_strict_error_removes_stale_output_and_keeps_metadata(self) -> None:
        fake_api = FakeDataApi({"000001.SZ": pd.DataFrame()})
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                output.write_text("symbol,date,close\n000001,2026-01-01,1\n", encoding="utf-8")
                metadata.write_text('{"stale": true}\n', encoding="utf-8")
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
                            "--request-interval-seconds",
                            "0",
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertEqual(["000001"], saved["empty_symbols"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("empty_symbols=1", stderr.getvalue())

    def test_cli_strict_invalid_rows_returns_error_with_metadata(self) -> None:
        fake_api = FakeDataApi(
            {
                "000001.SZ": pd.DataFrame(
                    [
                        {
                            **valid_daily().iloc[0].to_dict(),
                            "vol": "",
                            "amount": "",
                            "turnover_rate": "",
                            "is_paused": 0,
                            "is_st": 0,
                        }
                    ]
                )
            }
        )
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
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
                            "--request-interval-seconds",
                            "0",
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertEqual(1, saved["invalid_rows"])
        self.assertEqual(0, saved["dropped_invalid_rows"])
        self.assertIn("invalid_rows=1", stderr.getvalue())

    def test_fetch_prices_sleeps_between_symbol_requests(self) -> None:
        fake_api = FakeDataApi(
            {
                "000001.SZ": valid_daily(),
                "600000.SH": valid_daily(ts_code="600000.SH"),
            }
        )
        old_module = sys.modules.get("zzshare.client")
        old_sleep = zzshare_data.time.sleep
        sleep_calls: list[float] = []
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        zzshare_data.time.sleep = sleep_calls.append  # type: ignore[assignment]
        try:
            args = types.SimpleNamespace(
                symbols="000001,600000",
                start_date="2026-05-01",
                end_date="2026-05-29",
                output="",
                metadata_output="",
                token="",
                http_url="https://example.test",
                timeout_seconds=7,
                request_interval_seconds=1.25,
                fields="all",
                adjust="",
                limit=1000,
                max_pages=1,
            )

            frame, metadata = fetcher.fetch_prices(args)
        finally:
            restore_module("zzshare.client", old_module)
            zzshare_data.time.sleep = old_sleep  # type: ignore[assignment]

        self.assertEqual([1.25], sleep_calls)
        self.assertEqual(2, len(frame))
        self.assertEqual(2, metadata["symbol_count"])

if __name__ == "__main__":
    unittest.main()
