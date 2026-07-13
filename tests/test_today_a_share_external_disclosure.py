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

import lib.runner.run_today_a_share_selection_helpers as helpers  # noqa: E402
from lib.report_html.a_share_selection_html_report import render_report  # noqa: E402
from html_report_helpers import minimal_summary  # noqa: E402
from test_today_a_share_html_report import visible_before_technical_details  # noqa: E402
from test_today_a_share_history_end_date import minimal_history_manifest  # noqa: E402


class TodayAShareExternalDisclosureTests(unittest.TestCase):
    def test_html_discloses_partial_spot_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["spot_metadata"] = {
                "source": "eastmoney",
                "snapshot_time": "2026-06-06T09:31:00Z",
                "requested_pages": 3,
                "successful_pages": 2,
                "raw_items": 160,
                "filtered_items": 120,
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
        self.assertIn("spot_metadata.snapshot_time", report)
        self.assertIn("2026-06-06T09:31:00Z", report)
        self.assertIn("spot_metadata.requested_pages", report)
        self.assertIn(">3<", report)
        self.assertIn("spot_metadata.successful_pages", report)
        self.assertIn(">2<", report)
        self.assertIn("spot_metadata.raw_items", report)
        self.assertIn(">160<", report)
        self.assertIn("spot_metadata.filtered_items", report)
        self.assertIn(">120<", report)
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
        self.assertTrue(history["history_partial_result"])
        self.assertEqual(1, history["history_metadata_fallback_error_count"])
        self.assertEqual("hfq", history["history_adjust"])
        self.assertEqual(
            [{"symbol": "000001", "provider": "stock_zh_a_daily"}],
            history["history_metadata_symbol_providers"],
        )
        self.assertIn("history_partial_result", report)
        self.assertIn(">True<", report)
        self.assertIn("history_metadata_fallback_error_count", report)
        self.assertIn("stock_zh_a_daily", report)
        self.assertIn("hist unavailable", report)
        self.assertIn("history_adjust", report)
        self.assertIn("hfq", report)
        visible = visible_before_technical_details(report)
        self.assertIn("Partial history fetch", visible)
        self.assertIn("fallback_errors=1", visible)
        self.assertIn("cannot be described as complete history", visible)

    def test_summary_and_html_disclose_partial_history_recovery_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            write_partial_history_metadata(output)
            manifest = minimal_history_manifest(output, end_date="2026-06-06")
            manifest["allow_partial_history"] = True

            summary = helpers.summary_view(manifest, "completed")
            report = render_report(summary, {"steps": []}, language="en")

        history = summary["history_selection"]
        self.assertTrue(history["history_partial_result"])
        self.assertFalse(history["history_output_written"])
        self.assertTrue(history["history_metadata_output_written"])
        self.assertEqual("3", history["history_adjustflag"])
        self.assertEqual(1, history["history_empty_symbol_count"])
        self.assertEqual(["000001"], history["history_empty_symbols"])
        self.assertEqual(1, history["history_unprocessed_symbol_count"])
        self.assertEqual(["000002"], history["history_unprocessed_symbols"])
        self.assertTrue(history["history_rate_limit_budget_exhausted"])
        self.assertEqual(
            "total_runtime_seconds",
            history["history_rate_limit_exhaustion_reason"],
        )
        self.assertIn("history_partial_result", report)
        self.assertIn(">True<", report)
        self.assertIn("history_output_written", report)
        self.assertIn(">False<", report)
        self.assertIn("history_empty_symbol_count", report)
        self.assertIn(">1<", report)
        self.assertIn("history_empty_symbols", report)
        self.assertIn("000001", report)
        self.assertIn("history_adjustflag", report)
        self.assertIn(">3<", report)
        visible = visible_before_technical_details(report)
        self.assertIn("Partial history fetch", visible)
        self.assertIn("empty_symbols=1", visible)
        self.assertIn("unprocessed_symbols=1", visible)
        self.assertIn("rate_limit_budget_exhausted=true", visible)
        self.assertIn("rate_limit_exhaustion_reason=total_runtime_seconds", visible)
        self.assertIn("output_written=false", visible)

    def test_html_discloses_local_input_partial_metadata_before_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["input_metadata"] = {
                **base_input_metadata(),
                "requested_symbols": ["AAPL", "MSFT"],
                "symbol_count": 1,
                "failed_symbols": [{"symbol": "MSFT", "error": "timeout"}],
                "empty_symbols": [],
                "unprocessed_symbols": ["TSLA"],
                "rate_limit_budget_exhausted": True,
                "rate_limit_exhaustion_reason": "total_runtime_seconds",
                "input_partial_result": True,
                "output_written": True,
                "metadata_output_written": True,
            }

            report = render_report(summary, {"steps": []}, language="en")

        visible = visible_before_technical_details(report)
        technical = report.split('<details class="technical-details">', 1)[1]
        self.assertIn("Partial local input metadata", visible)
        self.assertIn("failed_symbols=1", visible)
        self.assertIn("unprocessed_symbols=1", visible)
        self.assertIn("rate_limit_budget_exhausted=true", visible)
        self.assertIn("rate_limit_exhaustion_reason=total_runtime_seconds", visible)
        self.assertIn("symbol_count=1/2", visible)
        self.assertIn("input_metadata.failed_symbols", technical)
        self.assertIn("input_metadata.unprocessed_symbols", technical)
        self.assertIn("input_metadata.rate_limit_budget_exhausted", technical)
        self.assertIn("input_metadata.rate_limit_exhaustion_reason", technical)
        self.assertIn("timeout", technical)

    def test_html_infers_local_input_partial_from_symbol_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["input_metadata"] = {
                **base_input_metadata(),
                "requested_symbols": ["AAPL", "MSFT", "TSLA"],
                "symbol_count": 1,
                "failed_symbols": [],
                "empty_symbols": [],
                "output_written": True,
                "metadata_output_written": True,
            }

            report = render_report(summary, {"steps": []}, language="en")

        visible = visible_before_technical_details(report)
        technical = report.split('<details class="technical-details">', 1)[1]
        self.assertIn("Partial local input metadata", visible)
        self.assertIn("symbol_count=1/3", visible)
        self.assertIn("input_metadata.requested_symbols", technical)
        self.assertIn("input_metadata.symbol_count", technical)

    def test_html_infers_local_input_partial_from_failed_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["input_metadata"] = {
                **base_input_metadata(),
                "requested_symbols": ["AAPL", "MSFT"],
                "symbol_count": 1,
                "failed_symbols": [{"symbol": "MSFT", "error": "timeout"}],
                "empty_symbols": [],
                "output_written": False,
                "metadata_output_written": True,
            }

            report = render_report(summary, {"steps": []}, language="en")

        visible = visible_before_technical_details(report)
        technical = report.split('<details class="technical-details">', 1)[1]
        self.assertIn("Partial local input metadata", visible)
        self.assertIn("failed_symbols=1", visible)
        self.assertIn("output_written=false", visible)
        self.assertIn("input_metadata.output_written", technical)
        self.assertIn(">False<", technical)


def write_history_metadata_with_fallback(output: Path) -> None:
    (output / "selected_symbols.json").write_text(
        json.dumps({"source": "explicit_symbols", "symbols": ["000001"]}),
        encoding="utf-8",
    )
    (output / "history_metadata.json").write_text(
        json.dumps(
            {
                "source": "akshare",
                "adjust": "hfq",
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
                "fallback_errors": [{"symbol": "000001", "error": "hist unavailable"}],
            }
        ),
        encoding="utf-8",
    )


def base_input_metadata() -> dict[str, object]:
    return {
        "source_type": "external_fetch",
        "source": "yfinance",
        "market": "A-share",
        "market_label_only": True,
        "source_claim_boundary": "market_label_not_source_exchange_or_calendar_proof",
    }


def write_partial_history_metadata(output: Path) -> None:
    (output / "selected_symbols.json").write_text(
        json.dumps({"source": "explicit_symbols", "symbols": ["000001"]}),
        encoding="utf-8",
    )
    (output / "history_metadata.json").write_text(
        json.dumps(
            {
                "source": "baostock",
                "adjustflag": "3",
                "end_date": "2026-06-06",
                "requested_symbols": ["000001"],
                "symbols": [
                    {
                        "symbol": "000001",
                        "rows": 0,
                        "date_min": "",
                        "date_max": "",
                    }
                ],
                "failed_symbols": [],
                "empty_symbols": ["000001"],
                "unprocessed_symbols": ["000002"],
                "rate_limit_budget_exhausted": True,
                "rate_limit_exhaustion_reason": "total_runtime_seconds",
                "fallback_errors": [],
                "partial_result": True,
                "output_written": False,
                "metadata_output_written": True,
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
