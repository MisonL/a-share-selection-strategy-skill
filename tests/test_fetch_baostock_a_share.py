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


if __name__ == "__main__":
    unittest.main()
