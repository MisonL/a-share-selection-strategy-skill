from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.gates.incremental_history_merge import normalize_date_series  # noqa: E402
from prepare_incremental_history_plan import read_price_stats  # noqa: E402


HAS_PARQUET_ENGINE = any(
    importlib.util.find_spec(name) for name in ("pyarrow", "fastparquet")
)


@unittest.skipUnless(HAS_PARQUET_ENGINE, "parquet engine is required")
class IncrementalHistoryDateContractTests(unittest.TestCase):
    def test_plan_stats_accept_datetime_parquet_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prices.parquet"
            pd.DataFrame(
                {
                    "symbol": ["000001", "000001"],
                    "date": pd.to_datetime(["2026-07-08", "2026-07-09"]),
                }
            ).to_parquet(path, index=False)

            stats = read_price_stats(path)

        self.assertEqual(2, stats["000001"]["rows"])
        self.assertEqual("2026-07-08", stats["000001"]["date_min"])
        self.assertEqual("2026-07-09", stats["000001"]["date_max"])

    def test_incremental_merge_accepts_datetime_dates(self) -> None:
        dates = normalize_date_series(
            pd.Series(pd.to_datetime(["2026-07-08", "2026-07-09"])),
            "incremental prices",
        )

        self.assertEqual(["2026-07-08", "2026-07-09"], dates.tolist())


if __name__ == "__main__":
    unittest.main()
