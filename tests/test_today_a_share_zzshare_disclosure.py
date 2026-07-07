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
from lib.runner.run_today_a_share_selection_input_metadata import (
    input_metadata_for_prices,
)  # noqa: E402
from test_today_a_share_html_report import visible_before_technical_details  # noqa: E402
from test_today_a_share_history_end_date import minimal_history_manifest  # noqa: E402


class TodayAShareZzshareDisclosureTests(unittest.TestCase):
    def test_summary_and_html_disclose_truncated_history_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            write_truncated_history_metadata(output)
            manifest = minimal_history_manifest(output, end_date="2026-06-06")
            manifest["allow_partial_history"] = True

            summary = helpers.summary_view(manifest, "completed")
            stdout = helpers.runner_disclosure_stdout(summary)
            report = render_report(summary, {"steps": []}, language="en")

        history = summary["history_selection"]
        self.assertTrue(history["history_partial_result"])
        self.assertEqual(1, history["history_possibly_truncated_symbol_count"])
        self.assertEqual(["000001"], history["history_possibly_truncated_symbols"])
        self.assertFalse(history["history_token_configured"])
        self.assertIn("history_possibly_truncated_symbol_count=1", stdout)
        self.assertIn("history_token_configured=false", stdout)
        self.assertIn("history_limit=1000", stdout)
        self.assertIn("history_max_pages=10", stdout)
        self.assertIn("history_possibly_truncated_symbol_count", report)
        self.assertIn("history_possibly_truncated_symbols", report)
        self.assertIn("history_token_configured", report)
        self.assertIn("history_limit", report)
        self.assertIn("history_max_pages", report)
        visible = visible_before_technical_details(report)
        self.assertIn("Partial history fetch", visible)
        self.assertIn("possibly_truncated_symbols=1", visible)

    def test_local_input_metadata_treats_zzshare_truncation_as_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            prices = output / "prices.csv"
            prices.write_text(
                "symbol,date,close\n000001,2026-06-05,8\n", encoding="utf-8"
            )
            write_truncated_local_metadata(output)

            metadata = input_metadata_for_prices(str(prices))
            summary = {"source_scope": "local_prices_input", "input_metadata": metadata}
            report = render_report(
                {**summary, **minimal_report_fields(output)},
                {"steps": []},
                language="en",
            )

        self.assertTrue(metadata["input_partial_result"])
        self.assertEqual("zzshare_history_fetch", metadata["source_scope"])
        self.assertFalse(metadata["token_configured"])
        self.assertEqual(1, metadata["input_possibly_truncated_symbol_count"])
        self.assertEqual(["000001"], metadata["possibly_truncated_symbols"])
        visible = visible_before_technical_details(report)
        technical = report.split('<details class="technical-details">', 1)[1]
        self.assertIn("Partial local input metadata", visible)
        self.assertIn("possibly_truncated_symbols=1", visible)
        self.assertIn("non_trading_rows=3", visible)
        self.assertIn("tradestatus_missing_rows=4", visible)
        self.assertIn("input_metadata.source_scope", technical)
        self.assertIn("input_metadata.token_configured", technical)
        self.assertIn("input_metadata.limit", technical)
        self.assertIn("input_metadata.max_pages", technical)
        self.assertIn("zzshare_history_fetch", technical)

    def test_local_input_metadata_discloses_zzshare_quality_counters(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            prices = output / "prices.csv"
            prices.write_text(
                "symbol,date,close\n000001,2026-06-05,8\n", encoding="utf-8"
            )
            write_truncated_local_metadata(output)

            metadata = input_metadata_for_prices(str(prices))
            summary = {"source_scope": "local_prices_input", "input_metadata": metadata}
            report = render_report(
                {**summary, **minimal_report_fields(output)},
                {"steps": []},
                language="en",
            )

        visible = visible_before_technical_details(report)
        technical = report.split('<details class="technical-details">', 1)[1]
        self.assertEqual(2, metadata["invalid_rows"])
        self.assertEqual(2, metadata["input_invalid_rows"])
        self.assertEqual(1, metadata["input_dropped_invalid_rows"])
        self.assertIn("invalid_rows=2 dropped_invalid_rows=1", visible)
        self.assertIn("non_trading_rows=3", visible)
        self.assertIn("tradestatus_missing_rows=4", visible)
        self.assertIn("input_metadata.invalid_rows", technical)
        self.assertIn("input_metadata.input_invalid_rows", technical)

    def test_local_input_quality_counter_alone_marks_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            prices = output / "prices.csv"
            prices.write_text(
                "symbol,date,close\n000001,2026-06-05,8\n", encoding="utf-8"
            )
            metadata = zzshare_metadata_payload()
            metadata["possibly_truncated_symbols"] = []
            metadata["dropped_invalid_rows"] = 0
            metadata["non_trading_rows"] = 1
            (output / "metadata.json").write_text(
                json.dumps(metadata), encoding="utf-8"
            )

            loaded = input_metadata_for_prices(str(prices))

        self.assertTrue(loaded["input_partial_result"])
        self.assertEqual(1, loaded["input_non_trading_rows"])

    def test_local_input_metadata_rejects_invalid_quality_counter_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            prices = output / "prices.csv"
            prices.write_text(
                "symbol,date,close\n000001,2026-06-05,8\n", encoding="utf-8"
            )
            metadata = zzshare_metadata_payload()
            metadata["invalid_rows"] = "not-a-number"
            (output / "metadata.json").write_text(
                json.dumps(metadata), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ValueError, "metadata invalid_rows must be an integer"
            ):
                input_metadata_for_prices(str(prices))


def write_truncated_history_metadata(output: Path) -> None:
    (output / "selected_symbols.json").write_text(
        json.dumps({"source": "explicit_symbols", "symbols": ["000001"]}),
        encoding="utf-8",
    )
    write_metadata(output / "history_metadata.json")


def write_truncated_local_metadata(output: Path) -> None:
    write_metadata(output / "metadata.json")


def write_metadata(path: Path) -> None:
    path.write_text(json.dumps(zzshare_metadata_payload()), encoding="utf-8")


def zzshare_metadata_payload() -> dict[str, object]:
    return {
        "source": "zzshare",
        "source_type": "external_fetch",
        "source_scope": "zzshare_history_fetch",
        "real_market_data": True,
        "source_claim_boundary": (
            "zzshare_external_api_not_broker_order_or_long_term_stability_proof"
        ),
        "data_source_note": (
            "zzshare SDK endpoint; quota and stability require external verification"
        ),
        "fields": "all",
        "token_configured": False,
        "request_interval_seconds": 2.1,
        "limit": 1000,
        "max_pages": 10,
        "end_date": "2026-06-06",
        "requested_symbols": ["000001"],
        "symbol_count": 1,
        "symbols": [
            {
                "symbol": "000001",
                "rows": 10000,
                "date_min": "2020-01-01",
                "date_max": "2026-06-05",
                "possibly_truncated": True,
            }
        ],
        "failed_symbols": [],
        "empty_symbols": [],
        "possibly_truncated_symbols": ["000001"],
        "invalid_rows": 2,
        "invalid_symbols": ["000001"],
        "invalid_row_examples": [
            {"symbol": "000001", "date": "2026-06-05", "invalid_columns": ["turn"]}
        ],
        "dropped_invalid_rows": 1,
        "non_trading_rows": 3,
        "non_trading_symbols": ["000001"],
        "non_trading_row_examples": [{"symbol": "000001", "date": "2026-06-05"}],
        "tradestatus_missing_rows": 4,
        "fallback_errors": [],
        "output_written": True,
        "metadata_output_written": True,
    }


def minimal_report_fields(output: Path) -> dict[str, object]:
    diagnostics = output / "diagnostics.csv"
    diagnostics.write_text("symbol,total_score\n000001,0.1\n", encoding="utf-8")
    return {
        "status": "completed",
        "runner": "run_today_a_share_selection",
        "requested_mode": "auto",
        "mode": "generic",
        "mode_decision": "auto_generic",
        "mode_decision_reason": "",
        "prediction_mode": False,
        "prediction_input_source": "not_used",
        "prediction_model_executed_by_runner": False,
        "prediction_claim_boundary": "not_prediction_derived",
        "lightgbm_not_used": True,
        "lightgbm_output_source": "not_used",
        "lightgbm_executed_by_runner": False,
        "source_type": "external_fetch",
        "real_market_data": True,
        "input_csv_provenance": {},
        "advice_boundary": "not_investment_advice",
        "recommendation_boundary": "ranking_signal_not_buy_sell_instruction",
        "prices_rows": 1,
        "candidate_rows": 0,
        "diagnostic_rows": 1,
        "spot_matched_symbols": 0,
        "score": {},
        "diagnostics_output": str(diagnostics),
        "diagnostics_output_written": True,
        "boundary": "not_investment_advice",
    }


if __name__ == "__main__":
    unittest.main()
