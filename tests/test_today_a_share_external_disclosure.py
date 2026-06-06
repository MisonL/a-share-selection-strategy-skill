from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import run_today_a_share_selection_helpers as helpers  # noqa: E402
from a_share_selection_html_report import render_report  # noqa: E402
from html_report_helpers import minimal_summary  # noqa: E402
from test_today_a_share_history_end_date import minimal_history_manifest  # noqa: E402


class TodayAShareExternalDisclosureTests(unittest.TestCase):
    def test_html_discloses_partial_spot_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["spot_metadata"] = {
                "source": "eastmoney",
                "partial_result": True,
                "coverage_claim": "partial_not_full_market",
                "failed_pages": [{"page": 2, "error": "timeout"}],
                "allowed_failure_actions": [
                    "use_partial_snapshot_only_with_partial_result_disclosure"
                ],
            }

            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("spot_metadata.partial_result", report)
        self.assertIn(">True<", report)
        self.assertIn("spot_metadata.coverage_claim", report)
        self.assertIn("partial_not_full_market", report)
        self.assertIn("spot_metadata.failed_pages", report)
        self.assertIn("timeout", report)
        self.assertIn("spot_metadata.allowed_failure_actions", report)

    def test_html_surfaces_partial_spot_warning_outside_raw_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["spot_metadata"] = {
                "partial_result": True,
                "coverage_claim": "partial_not_full_market",
            }

            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn("部分实时快照", report)
        self.assertIn("不能写成实时全市场扫描完成", report)

    def test_summary_and_html_disclose_history_fallback_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            write_history_metadata_with_fallback(output)
            manifest = minimal_history_manifest(output, end_date="2026-06-06")
            manifest["allow_partial_history"] = True

            summary = helpers.summary_view(manifest, "completed")
            report = render_report(summary, {"steps": []}, language="en")

        history = summary["history_selection"]
        self.assertEqual(1, history["history_metadata_fallback_error_count"])
        self.assertEqual(
            [{"symbol": "000001", "provider": "stock_zh_a_daily"}],
            history["history_metadata_symbol_providers"],
        )
        self.assertIn("history_metadata_fallback_error_count", report)
        self.assertIn("stock_zh_a_daily", report)
        self.assertIn("hist unavailable", report)


def write_history_metadata_with_fallback(output: Path) -> None:
    (output / "selected_symbols.json").write_text(
        json.dumps({"source": "explicit_symbols", "symbols": ["000001"]}),
        encoding="utf-8",
    )
    (output / "history_metadata.json").write_text(
        json.dumps(
            {
                "source": "akshare",
                "end_date": "2026-06-06",
                "symbols": [
                    {
                        "symbol": "000001",
                        "provider": "stock_zh_a_daily",
                        "rows": 120,
                        "date_min": "2026-01-01",
                        "date_max": "2026-06-05",
                    }
                ],
                "failed_symbols": [],
                "empty_symbols": [],
                "fallback_errors": [
                    {"symbol": "000001", "error": "hist unavailable"}
                ],
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
