from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_baostock_a_share as fetcher  # noqa: E402
from a_share_selection_tradability import tradability_stats  # noqa: E402


class FetchBaostockAShareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fetcher.ensure_runtime_dependencies()

    def test_parse_symbols_requires_six_digits(self) -> None:
        self.assertEqual(["000001", "600000"], fetcher.parse_symbols("000001,600000"))
        with self.assertRaisesRegex(ValueError, "six digits"):
            fetcher.parse_symbols("1")

    def test_parse_symbols_rejects_bj_prefix_instead_of_routing_to_sz(self) -> None:
        with self.assertRaisesRegex(ValueError, "bj.430047"):
            fetcher.parse_symbols("bj.430047")

    def test_collect_rows_maps_ohlcv_amount_and_name(self) -> None:
        result = FakeResult(
            [
                [
                    "2026-05-20",
                    "sz.000001",
                    "10.0",
                    "10.2",
                    "9.9",
                    "10.1",
                    "10.0",
                    "1.0000",
                    "1000",
                    "10100",
                    "0.5",
                    "1",
                    "0",
                ]
            ]
        )
        rows = fetcher.collect_rows(result, "000001", "平安银行")
        self.assertEqual("000001", rows[0]["symbol"])
        self.assertEqual("平安银行", rows[0]["name"])
        self.assertEqual("A-share", rows[0]["market"])
        self.assertEqual("1000", rows[0]["volume"])
        self.assertEqual("10100", rows[0]["amount"])
        self.assertEqual("0.5", rows[0]["turn"])
        self.assertEqual("10.0", rows[0]["preclose"])
        self.assertEqual("1", rows[0]["tradestatus"])

    def test_fetch_symbol_names_uses_baostock_stock_basic(self) -> None:
        fake = FakeBaostockBasic(
            {
                "sz.000001": FakeBasicResult([["sz.000001", "平安银行"]]),
                "sh.600000": FakeBasicResult([["sh.600000", "浦发银行"]]),
            }
        )

        lookup = fetcher.fetch_symbol_names(fake, ["000001", "600000"])

        self.assertEqual(
            {"000001": "平安银行", "600000": "浦发银行"},
            lookup["names"],
        )
        self.assertEqual("baostock_query_stock_basic", lookup["source"])
        self.assertEqual([], lookup["failed_symbols"])
        self.assertEqual([], lookup["missing_symbols"])

    def test_fetch_symbol_names_reports_missing_and_failed_names(self) -> None:
        fake = FakeBaostockBasic(
            {
                "sz.000001": FakeBasicResult([]),
                "sh.600000": FakeBasicResult([], error_code="100", error_msg="offline"),
            }
        )

        lookup = fetcher.fetch_symbol_names(fake, ["000001", "600000"])

        self.assertEqual({}, lookup["names"])
        self.assertEqual(["000001"], lookup["missing_symbols"])
        self.assertEqual(
            [{"symbol": "600000", "error": "offline"}],
            lookup["failed_symbols"],
        )

    def test_tradability_stats_handles_missing_symbol_column(self) -> None:
        frame = fetcher.pd.DataFrame([{"tradestatus": "0", "isST": "1"}])

        stats = tradability_stats(frame)

        self.assertEqual(1, stats["non_trading_rows"])
        self.assertEqual([], stats["non_trading_symbols"])
        self.assertEqual(1, stats["st_rows"])
        self.assertEqual([], stats["st_symbols"])

    def test_write_outputs_writes_metadata_json(self) -> None:
        metadata = {
            "source": "baostock",
            "rows": 1,
            "symbol_count": 1,
            "failed_symbols": [],
            "start_date": "2026-05-20",
            "end_date": "2026-05-20",
            "adjustflag": "3",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.csv"
            meta = Path(tmpdir) / "metadata.json"
            frame = fetcher.pd.DataFrame([{"symbol": "000001"}])
            fetcher.write_outputs(frame, metadata, output, meta)
            self.assertTrue(output.exists())
            saved = json.loads(meta.read_text(encoding="utf-8"))
        self.assertEqual("baostock", saved["source"])

    def test_strict_failure_removes_stale_output_and_keeps_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.csv"
            meta = Path(tmpdir) / "metadata.json"
            output.write_text("symbol,date,close\nSTALE,2026-01-01,1\n", encoding="utf-8")
            meta.write_text('{"stale": true}\n', encoding="utf-8")
            old_main = fetcher.fetch_prices
            stdout = StringIO()
            stderr = StringIO()
            try:
                def fake_fetch_prices(_args):
                    frame = fetcher.pd.DataFrame([valid_row("000001", "2026-05-20")])
                    metadata = metadata_for(["000001"], frame)
                    metadata["failed_symbols"] = [{"symbol": "000001", "error": "offline"}]
                    metadata["empty_symbols"] = ["000001"]
                    metadata["symbol_count"] = 0
                    return frame, metadata

                fetcher.fetch_prices = fake_fetch_prices  # type: ignore[assignment]
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001",
                            "--start-date",
                            "2026-05-20",
                            "--end-date",
                            "2026-05-20",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(meta),
                            "--fail-on-fetch-error",
                        ]
                    )
            finally:
                fetcher.fetch_prices = old_main  # type: ignore[assignment]

            saved = json.loads(meta.read_text(encoding="utf-8"))
            output_exists = output.exists()
            meta_exists = meta.exists()

        self.assertEqual(3, code)
        self.assertFalse(output_exists)
        self.assertTrue(meta_exists)
        self.assertEqual([{"symbol": "000001", "error": "offline"}], saved["failed_symbols"])
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("output_written=false metadata_output_written=true", stderr.getvalue())

    def test_partial_default_stdout_discloses_partial_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.csv"
            meta = Path(tmpdir) / "metadata.json"
            old_main = fetcher.fetch_prices
            stdout = StringIO()
            try:
                def fake_fetch_prices(_args):
                    frame = fetcher.pd.DataFrame([valid_row("000001", "2026-05-20")])
                    metadata = metadata_for(["000001", "600000"], frame)
                    metadata["empty_symbols"] = ["600000"]
                    metadata["symbol_count"] = 1
                    return frame, metadata

                fetcher.fetch_prices = fake_fetch_prices  # type: ignore[assignment]
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001,600000",
                            "--start-date",
                            "2026-05-20",
                            "--end-date",
                            "2026-05-20",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(meta),
                        ]
                    )
            finally:
                fetcher.fetch_prices = old_main  # type: ignore[assignment]

            saved = json.loads(meta.read_text(encoding="utf-8"))
            output_exists = output.exists()

        self.assertEqual(0, code)
        self.assertTrue(output_exists)
        self.assertTrue(saved["output_written"])
        self.assertEqual(["600000"], saved["empty_symbols"])
        self.assertTrue(stdout.getvalue().startswith("PARTIAL:"))
        self.assertIn("empty_symbols=1", stdout.getvalue())

    def test_quality_policy_reports_invalid_rows_without_dropping(self) -> None:
        frame = fetcher.pd.DataFrame(
            [
                valid_row("000001", "2026-05-20"),
                {
                    **valid_row("688981", "2025-09-01"),
                    "volume": "",
                    "amount": "",
                    "turn": "",
                    "tradestatus": "0",
                },
            ]
        )
        metadata = metadata_for(["000001", "688981"], frame)
        result, updated = fetcher.apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=False,
        )
        self.assertEqual(2, len(result))
        self.assertEqual(1, updated["invalid_rows"])
        self.assertEqual(["688981"], updated["invalid_symbols"])
        self.assertEqual(
            ["volume", "amount", "turn"],
            updated["invalid_row_examples"][0]["invalid_columns"],
        )
        self.assertIn(
            "invalid_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )
        self.assertIn(
            "non_trading_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )

    def test_quality_policy_can_explicitly_drop_invalid_rows(self) -> None:
        frame = fetcher.pd.DataFrame(
            [
                valid_row("000001", "2026-05-20"),
                {**valid_row("688981", "2025-09-01"), "volume": "", "tradestatus": "0"},
            ]
        )
        metadata = metadata_for(["000001", "688981"], frame)
        result, updated = fetcher.apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=True,
        )
        self.assertEqual(["000001"], result["symbol"].tolist())
        self.assertEqual(1, updated["dropped_invalid_rows"])
        self.assertIn("688981", updated["empty_symbols"])
        self.assertNotIn(
            "invalid_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )
        self.assertNotIn(
            "non_trading_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )
        self.assertIn(
            "empty_symbols=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )

    def test_strict_gate_rejects_non_trading_rows(self) -> None:
        frame = fetcher.pd.DataFrame(
            [{**valid_row("688981", "2025-09-01"), "tradestatus": "0"}]
        )
        metadata = metadata_for(["688981"], frame)
        _result, updated = fetcher.apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=False,
        )
        errors = fetcher.strict_gate_errors(updated, fail_on_fetch_error=True)
        self.assertIn("non_trading_rows=1", errors)
        self.assertEqual(["688981"], updated["non_trading_symbols"])

    def test_strict_gate_rejects_empty_symbol(self) -> None:
        metadata = {
            "requested_symbols": ["000001", "600000"],
            "symbol_count": 1,
            "failed_symbols": [],
            "empty_symbols": ["600000"],
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
        }
        errors = fetcher.strict_gate_errors(metadata, fail_on_fetch_error=True)
        self.assertIn("empty_symbols=1", errors)
        self.assertIn("symbol_count=1 requested_symbols=2", errors)

    def test_strict_gate_rejects_missing_stock_names(self) -> None:
        metadata = {
            "requested_symbols": ["000001", "600000"],
            "symbol_count": 2,
            "failed_symbols": [],
            "empty_symbols": [],
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "name_lookup_failed_symbols": [{"symbol": "000001", "error": "offline"}],
            "name_lookup_missing_symbols": ["600000"],
        }

        errors = fetcher.strict_gate_errors(metadata, fail_on_fetch_error=True)

        self.assertIn("name_lookup_failed_symbols=1", errors)
        self.assertIn("name_lookup_missing_symbols=1", errors)


class FakeResult:
    fields = [
        "date",
        "code",
        "open",
        "high",
        "low",
        "close",
        "preclose",
        "pctChg",
        "volume",
        "amount",
        "turn",
        "tradestatus",
        "isST",
    ]

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = rows
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeBasicResult:
    fields = ["code", "code_name"]

    def __init__(
        self,
        rows: list[list[str]],
        *,
        error_code: str = "0",
        error_msg: str = "",
    ) -> None:
        self.rows = rows
        self.error_code = error_code
        self.error_msg = error_msg
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeBaostockBasic:
    def __init__(self, results: dict[str, FakeBasicResult]) -> None:
        self.results = results

    def query_stock_basic(self, *, code: str) -> FakeBasicResult:
        return self.results[code]


def valid_row(symbol: str, date: str) -> dict[str, str]:
    return {
        "symbol": symbol,
        "name": symbol,
        "market": "A-share",
        "date": date,
        "open": "10.0",
        "high": "10.2",
        "low": "9.9",
        "close": "10.1",
        "preclose": "10.0",
        "pctChg": "1.0",
        "volume": "1000",
        "amount": "10100",
        "turn": "0.5",
        "tradestatus": "1",
        "isST": "0",
    }


def metadata_for(symbols: list[str], frame: fetcher.pd.DataFrame) -> dict:
    return {
        "source": "baostock",
        "requested_symbols": symbols,
        "start_date": "2025-01-01",
        "end_date": "2026-05-29",
        "adjustflag": "3",
        "rows": len(frame),
        "raw_rows": len(frame),
        "symbol_count": frame["symbol"].nunique(),
        "symbols": [
            fetcher.symbol_metadata_for_frame(symbol, frame)
            for symbol in symbols
        ],
        "failed_symbols": [],
        "empty_symbols": [],
        "invalid_rows": 0,
        "invalid_symbols": [],
        "invalid_row_examples": [],
        "dropped_invalid_rows": 0,
    }


if __name__ == "__main__":
    unittest.main()
