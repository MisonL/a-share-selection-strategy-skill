from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.fetch.zzshare_a_share_checkpoint_frames import (  # noqa: E402
    completed_part_symbols,
)
from lib.fetch.zzshare_rate_limit import retry_after_seconds  # noqa: E402
from lib.gates.incremental_history_merge import normalize_history_frame  # noqa: E402
from lib.runner.run_today_a_share_selection_prices_sidecar import (  # noqa: E402
    artifact_table_summary,
)
from lib.selection_core.a_share_selection_universe import (  # noqa: E402
    apply_universe_filter,
)
import prepare_clean_history_pool as clean_history_pool  # noqa: E402


class ReviewDataIntegrityRegressionTests(unittest.TestCase):
    def test_empty_checkpoint_request_restores_no_completed_symbols(self) -> None:
        symbols = {
            "000001": {"status": "completed", "part": "prices_part_00001.csv"}
        }

        self.assertEqual({}, completed_part_symbols(symbols, set()))

    def test_incremental_merge_rejects_numeric_or_missing_symbols(self) -> None:
        for symbol in (pd.NA, 1, "1"):
            frame = pd.DataFrame({"symbol": [symbol], "date": ["2026-07-09"]})
            with self.assertRaisesRegex(ValueError, "symbol"):
                normalize_history_frame(frame, "history")

    def test_sidecar_rejects_numeric_parquet_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prices.parquet"
            pd.DataFrame(
                {"symbol": [1], "date": ["2026-07-09"], "close": [10.0]}
            ).to_parquet(path, index=False)

            with self.assertRaisesRegex(ValueError, "symbol"):
                artifact_table_summary(path)

    def test_retry_after_rejects_non_finite_numeric_values(self) -> None:
        self.assertEqual(0.0, retry_after_seconds("NaN"))
        self.assertEqual(0.0, retry_after_seconds("Infinity"))

    def test_universe_filter_counts_normalized_symbols(self) -> None:
        frame = pd.DataFrame(
            {"symbol": [600000, "600000"], "market": ["A-share", "HK"]}
        )
        _result, summary = apply_universe_filter(
            frame,
            {"universe": {"market": "A-share", "symbol_prefix_allow_regex": r"^6"}},
        )

        self.assertEqual(0, summary["market_filtered_symbols"])

    def test_universe_filter_exclude_counts_normalized_symbols(self) -> None:
        frame = pd.DataFrame({"symbol": [600000, "600000"]})
        _result, summary = apply_universe_filter(
            frame,
            {"universe": {"symbol_prefix_exclude": ["6"]}},
        )

        self.assertEqual(1, summary["prefix_excluded_symbols"])

    def test_clean_history_publish_rolls_back_all_outputs_on_publish_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "clean_prices.csv"
            metadata_output = root / "clean_metadata.json"
            metadata_alias = root / "metadata_alias.json"
            report_output = root / "clean_report.json"
            old_contents = {
                output: "old-prices\n",
                metadata_output: '{"old": "metadata"}\n',
                metadata_alias: '{"old": "alias"}\n',
                report_output: '{"old": "report"}\n',
            }
            for path, content in old_contents.items():
                path.write_text(content, encoding="utf-8")
            paths = {
                "output": output,
                "metadata_output": metadata_output,
                "metadata_alias_output": metadata_alias,
                "report_output": report_output,
                "history_metadata": root / "history_metadata.json",
                "short_history": None,
            }
            clean = pd.DataFrame(
                {"symbol": ["000001"], "date": ["2026-07-09"], "close": [10.0]}
            )
            original_replace = Path.replace

            def fail_report_publish(source: Path, target: Path) -> Path:
                if Path(target) == report_output and ".stage." in source.name:
                    raise OSError("report publish failed")
                return original_replace(source, target)

            with (
                patch.object(
                    clean_history_pool,
                    "build_report",
                    return_value={"fresh": True},
                ),
                patch.object(Path, "replace", new=fail_report_publish),
                self.assertRaisesRegex(OSError, "report publish failed"),
            ):
                clean_history_pool.write_outputs(
                    paths,
                    clean,
                    {"fresh": True},
                    {},
                    clean,
                    None,
                )

            for path, content in old_contents.items():
                self.assertEqual(content, path.read_text(encoding="utf-8"))
            self.assertFalse(list(root.glob(".*.stage.*")))
            self.assertFalse(list(root.glob(".*.previous")))


if __name__ == "__main__":
    unittest.main()
