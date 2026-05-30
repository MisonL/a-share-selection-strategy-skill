from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_baostock_a_share as fetcher  # noqa: E402


class FetchBaostockAShareTests(unittest.TestCase):
    def test_parse_symbols_requires_six_digits(self) -> None:
        self.assertEqual(["000001", "600000"], fetcher.parse_symbols("000001,600000"))
        with self.assertRaisesRegex(ValueError, "six digits"):
            fetcher.parse_symbols("1")

    def test_collect_rows_maps_ohlcv_and_amount(self) -> None:
        result = FakeResult(
            [
                [
                    "2026-05-20",
                    "sz.000001",
                    "10.0",
                    "10.2",
                    "9.9",
                    "10.1",
                    "1000",
                    "10100",
                    "0.5",
                ]
            ]
        )
        rows = fetcher.collect_rows(result, "000001")
        self.assertEqual("000001", rows[0]["symbol"])
        self.assertEqual("A-share", rows[0]["market"])
        self.assertEqual("1000", rows[0]["volume"])
        self.assertEqual("10100", rows[0]["amount"])
        self.assertEqual("0.5", rows[0]["turn"])

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

    def test_quality_policy_reports_invalid_rows_without_dropping(self) -> None:
        frame = fetcher.pd.DataFrame(
            [
                valid_row("000001", "2026-05-20"),
                {
                    **valid_row("688981", "2025-09-01"),
                    "volume": "",
                    "amount": "",
                    "turn": "",
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

    def test_quality_policy_can_explicitly_drop_invalid_rows(self) -> None:
        frame = fetcher.pd.DataFrame(
            [
                valid_row("000001", "2026-05-20"),
                {**valid_row("688981", "2025-09-01"), "volume": ""},
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
        self.assertIn(
            "empty_symbols=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )

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


class FakeResult:
    fields = ["date", "code", "open", "high", "low", "close", "volume", "amount", "turn"]

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = rows
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


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
        "volume": "1000",
        "amount": "10100",
        "turn": "0.5",
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
