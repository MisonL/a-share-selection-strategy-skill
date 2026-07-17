from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from datetime import date
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_pytdx_a_share as fetcher  # noqa: E402
import lib.fetch.pytdx_a_share as pytdx_helpers  # noqa: E402


class FetchPytdxAShareTests(unittest.TestCase):
    def test_fetch_cli_defaults_to_current_verified_endpoint(self) -> None:
        args = fetcher.build_parser().parse_args(
            [
                "--symbols",
                "000001",
                "--start-date",
                "2026-01-01",
                "--end-date",
                "2026-01-02",
                "--output",
                "/tmp/prices.csv",
                "--metadata-output",
                "/tmp/metadata.json",
            ]
        )

        self.assertEqual("180.153.18.170", args.host)
        self.assertEqual(7709, args.port)
        self.assertEqual(args.host, pytdx_helpers.DEFAULT_HOST)
        self.assertEqual(args.port, pytdx_helpers.DEFAULT_PORT)

    def test_recent_window_uses_bounded_first_request(self) -> None:
        count = pytdx_helpers.initial_request_count(
            "2026-07-10", 800, today=date(2026, 7, 12)
        )

        self.assertEqual(16, count)

    def test_pagination_uses_actual_returned_rows_as_next_offset(self) -> None:
        api = PagedTdxApi(
            [bar("000001", f"2026-07-{day:02d}", 10.0) for day in range(12, 0, -1)]
        )
        args = types.SimpleNamespace(
            start_date="2026-07-05",
            end_date="2026-07-12",
            page_size=5,
            max_pages=3,
        )

        rows, observation = pytdx_helpers.fetch_symbol_rows(api, args, "000001")

        self.assertEqual([0, 5], observation["request_offsets"])
        self.assertEqual([5, 5], observation["request_counts"])
        self.assertEqual(10, observation["raw_rows"])
        self.assertEqual(8, observation["output_rows"])
        self.assertTrue(observation["reached_start_boundary"])
        self.assertTrue(observation["window_complete"])
        self.assertEqual("2026-07-05", min(row["date"] for row in rows))

    def test_parse_symbols_accepts_six_digit_a_share_symbols(self) -> None:
        self.assertEqual(["000001", "600000"], pytdx_helpers.parse_symbols("000001,600000"))
        with self.assertRaisesRegex(ValueError, "six digits"):
            pytdx_helpers.parse_symbols("AAPL")

    def test_pytdx_date_accepts_dash_or_compact(self) -> None:
        self.assertEqual("2026-01-02", pytdx_helpers.pytdx_date("2026-01-02"))
        self.assertEqual("2026-01-02", pytdx_helpers.pytdx_date("20260102"))
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            pytdx_helpers.pytdx_date("2026/01/02")

    def test_normalize_bar_maps_vol_to_volume_and_keeps_amount(self) -> None:
        row = pytdx_helpers.normalize_bar(
            "000001",
            {
                "datetime": "2026-01-02 00:00",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "vol": 100000,
                "amount": 1050000,
            },
        )

        self.assertEqual("000001", row["symbol"])
        self.assertEqual("", row["name"])
        self.assertEqual("2026-01-02", row["date"])
        self.assertEqual(100000, row["volume"])
        self.assertEqual(1050000, row["amount"])
        self.assertEqual("A-share", row["market"])

    def test_cli_writes_prices_and_metadata_with_fake_pytdx(self) -> None:
        with fake_pytdx_module(FakeTdxApi):
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
                            "2026-01-01",
                            "--end-date",
                            "2026-01-02",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                frame = pd.read_csv(output, dtype={"symbol": str})

        self.assertEqual(0, code)
        self.assertIn("OK: source=pytdx rows=4", stdout.getvalue())
        self.assertEqual(4, saved["rows"])
        self.assertEqual(2, saved["symbol_count"])
        self.assertEqual([], saved["failed_symbols"])
        self.assertEqual([], saved["empty_symbols"])
        self.assertFalse(saved["token_configured"])
        self.assertEqual(
            "pypi_license_unknown_readme_personal_research_boundary",
            saved["license_claim_boundary"],
        )
        self.assertEqual(["turn", "tradestatus", "isST", "name"], saved["missing_provider_fields"])
        self.assertEqual("blank_missing_provider_name", saved["name_value_policy"])
        self.assertEqual(["symbol", "date"], saved["merge_join_keys"])
        self.assertTrue(saved["strict_fields_same_date_required"])
        self.assertFalse(saved["selection_ready"])
        self.assertLess(saved["requested_raw_rows"], 800 * 2)
        self.assertEqual(["000001", "600000"], saved["requested_symbols"])
        self.assertEqual(["000001", "600000"], sorted(frame["symbol"].unique()))

    def test_cli_strict_fails_when_symbol_is_empty(self) -> None:
        with fake_pytdx_module(FakeEmptyTdxApi):
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
                            "2026-01-01",
                            "--end-date",
                            "2026-01-02",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertEqual(["000001"], saved["empty_symbols"])
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("empty_symbols=1", stderr.getvalue())

    def test_cli_strict_fails_when_max_pages_truncates_window(self) -> None:
        with fake_pytdx_module(FakeTruncatedTdxApi):
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stderr = StringIO()
                with redirect_stderr(stderr):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001",
                            "--start-date",
                            "2026-01-01",
                            "--end-date",
                            "2026-01-10",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--page-size",
                            "2",
                            "--max-pages",
                            "1",
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertEqual(["000001"], saved["possibly_truncated_symbols"])
        self.assertFalse(saved["symbols"][0]["window_complete"])
        self.assertIn("possibly_truncated_symbols=1", stderr.getvalue())

    def test_cli_removes_stale_metadata_when_strict_metadata_write_fails(self) -> None:
        with fake_pytdx_module(FakeEmptyTdxApi):
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                output.write_text("symbol,date\nSTALE,2026-01-01\n", encoding="utf-8")
                metadata.write_text('{"stale": true}\n', encoding="utf-8")
                original_write_metadata = fetcher.write_metadata
                writes = 0

                def fail_strict_metadata_write(
                    data: dict[str, object], path: Path
                ) -> None:
                    nonlocal writes
                    writes += 1
                    if writes == 2:
                        raise OSError("strict metadata write failed")
                    original_write_metadata(data, path)

                stderr = StringIO()
                with (
                    patch.object(
                        fetcher,
                        "write_metadata",
                        side_effect=fail_strict_metadata_write,
                    ),
                    redirect_stderr(stderr),
                ):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001",
                            "--start-date",
                            "2026-01-01",
                            "--end-date",
                            "2026-01-02",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--fail-on-fetch-error",
                        ]
                    )

        self.assertEqual(2, code)
        self.assertFalse(output.exists())
        self.assertFalse(metadata.exists())
        self.assertIn("metadata_output_written=false", stderr.getvalue())


class FakeTdxApi:
    def __init__(self, **_kwargs: object) -> None:
        self.connected = False

    def connect(self, *_args: object, **_kwargs: object) -> object:
        self.connected = True
        return self

    def disconnect(self) -> None:
        self.connected = False

    def get_security_bars(
        self,
        _category: int,
        _market: int,
        symbol: str,
        start: int,
        _count: int,
    ) -> list[dict[str, object]]:
        if start > 0:
            return []
        return [
            bar(symbol, "2026-01-02", 10.0),
            bar(symbol, "2026-01-01", 9.8),
            bar(symbol, "2025-12-31", 9.5),
        ]


class FakeEmptyTdxApi(FakeTdxApi):
    def get_security_bars(
        self,
        _category: int,
        _market: int,
        _symbol: str,
        _start: int,
        _count: int,
    ) -> list[dict[str, object]]:
        return []


class FakeTruncatedTdxApi(FakeTdxApi):
    def get_security_bars(
        self,
        _category: int,
        _market: int,
        symbol: str,
        _start: int,
        count: int,
    ) -> list[dict[str, object]]:
        return [
            bar(symbol, "2026-01-10", 10.0),
            bar(symbol, "2026-01-09", 9.9),
        ][:count]


class PagedTdxApi:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def get_security_bars(
        self,
        _category: int,
        _market: int,
        _symbol: str,
        start: int,
        count: int,
    ) -> list[dict[str, object]]:
        return self.rows[start : start + count]


def bar(symbol: str, day: str, close: float) -> dict[str, object]:
    return {
        "datetime": f"{day} 00:00",
        "open": close - 0.1,
        "high": close + 0.2,
        "low": close - 0.3,
        "close": close,
        "vol": 100000 if symbol.startswith("0") else 200000,
        "amount": 1000000 if symbol.startswith("0") else 4000000,
    }


class fake_pytdx_module:
    def __init__(self, api_class: type[object]) -> None:
        self.api_class = api_class
        self.old_parent = sys.modules.get("pytdx")
        self.old_hq = sys.modules.get("pytdx.hq")
        self.old_globals: dict[str, object] = {}

    def __enter__(self) -> None:
        parent = types.ModuleType("pytdx")
        parent.__path__ = []
        hq = types.ModuleType("pytdx.hq")
        hq.TdxHq_API = self.api_class
        sys.modules["pytdx"] = parent
        sys.modules["pytdx.hq"] = hq
        for name in ["pd", "TdxHq_API", "importlib_metadata"]:
            if name in pytdx_helpers.__dict__:
                self.old_globals[name] = pytdx_helpers.__dict__.pop(name)

    def __exit__(self, *_exc: object) -> None:
        restore_module("pytdx", self.old_parent)
        restore_module("pytdx.hq", self.old_hq)
        for name in ["pd", "TdxHq_API", "importlib_metadata"]:
            pytdx_helpers.__dict__.pop(name, None)
        pytdx_helpers.__dict__.update(self.old_globals)


def restore_module(name: str, old_module: object | None) -> None:
    if old_module is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = old_module


if __name__ == "__main__":
    unittest.main()
