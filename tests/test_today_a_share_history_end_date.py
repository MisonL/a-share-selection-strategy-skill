from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import lib.runner.run_today_a_share_selection_helpers as helpers  # noqa: E402
from lib.report_html.a_share_selection_html_report import render_report  # noqa: E402


class TodayAShareHistoryEndDateTests(unittest.TestCase):
    def test_history_summary_discloses_requested_end_date_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            symbols = ["000001", "600001"]
            write_history_files(
                output,
                symbols=symbols,
                end_date="2026-06-06",
                date_min="2026-01-01",
                date_max="2026-06-05",
            )
            manifest = minimal_history_manifest(
                output, end_date="2026-06-06", symbols=symbols
            )

            summary = helpers.summary_view(manifest, "completed")
            stdout = StringIO()
            with redirect_stdout(stdout):
                helpers.print_summary(manifest, output)
            report = render_report(summary, {"steps": []}, language="en")

        history = summary["history_selection"]
        self.assertEqual("2026-06-06", history["requested_end_date"])
        self.assertEqual("2026-06-05", history["history_metadata_actual_date_max"])
        self.assertEqual(0, history["history_metadata_symbols_reached_end_date_count"])
        self.assertFalse(history["history_metadata_all_symbols_reached_end_date"])
        self.assertFalse(history["history_metadata_end_date_has_rows"])
        self.assertEqual(
            [
                {
                    "symbol": "000001",
                    "date_min": "2026-01-01",
                    "date_max": "2026-06-05",
                    "rows": 120,
                },
                {
                    "symbol": "600001",
                    "date_min": "2026-01-01",
                    "date_max": "2026-06-05",
                    "rows": 120,
                },
            ],
            history["history_metadata_symbol_date_ranges"],
        )
        self.assertIn("history_requested_end_date=2026-06-06", stdout.getvalue())
        self.assertIn("history_actual_date_max=2026-06-05", stdout.getvalue())
        self.assertIn("history_symbols_reached_end_date_count=0", stdout.getvalue())
        self.assertIn("history_all_symbols_reached_end_date=false", stdout.getvalue())
        self.assertIn("history_end_date_has_rows=false", stdout.getvalue())
        self.assertIn("Requested history end date", report)
        self.assertIn("2026-06-06", report)
        self.assertIn("History actual latest date", report)
        self.assertIn("2026-06-05", report)
        self.assertIn("0/2 symbols reached the requested end date", report)
        self.assertIn("History end date has rows", report)
        self.assertIn(">False<", report)
        self.assertIn(
            "Requested 2026-06-06, actual latest 2026-06-05; 0/2 symbols reached the requested end date",
            report,
        )

    def test_history_end_date_comparison_normalizes_supported_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            write_history_files(
                output,
                symbols=["000001"],
                end_date="20260606",
                date_min="20260101",
                date_max="2026-06-06",
            )
            manifest = minimal_history_manifest(output, end_date="20260606")

            summary = helpers.summary_view(manifest, "completed")

        history = summary["history_selection"]
        self.assertEqual("2026-06-06", history["requested_end_date"])
        self.assertEqual("2026-06-06", history["history_metadata_actual_date_max"])
        self.assertEqual(1, history["history_metadata_symbols_reached_end_date_count"])
        self.assertTrue(history["history_metadata_all_symbols_reached_end_date"])
        self.assertTrue(history["history_metadata_end_date_has_rows"])

    def test_history_report_discloses_partial_end_date_reach(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            symbols = ["000001", "600001"]
            write_history_files(
                output,
                symbols=symbols,
                end_date="2026-06-06",
                date_min="2026-01-01",
                date_max="2026-06-05",
                date_max_by_symbol={"000001": "2026-06-06"},
            )
            manifest = minimal_history_manifest(
                output, end_date="2026-06-06", symbols=symbols
            )

            summary = helpers.summary_view(manifest, "completed")
            stdout = StringIO()
            with redirect_stdout(stdout):
                helpers.print_summary(manifest, output)
            report = render_report(summary, {"steps": []}, language="en")

        history = summary["history_selection"]
        self.assertEqual("2026-06-06", history["requested_end_date"])
        self.assertEqual("2026-06-06", history["history_metadata_actual_date_max"])
        self.assertEqual(1, history["history_metadata_symbols_reached_end_date_count"])
        self.assertFalse(history["history_metadata_all_symbols_reached_end_date"])
        self.assertTrue(history["history_metadata_end_date_has_rows"])
        self.assertIn("history_symbols_reached_end_date_count=1", stdout.getvalue())
        self.assertIn("history_all_symbols_reached_end_date=false", stdout.getvalue())
        self.assertIn("history_end_date_has_rows=true", stdout.getvalue())
        self.assertIn("1/2 symbols reached the requested end date", report)
        self.assertIn("history_metadata_all_symbols_reached_end_date", report)


def write_history_files(
    output: Path,
    *,
    symbols: list[str],
    end_date: str,
    date_min: str,
    date_max: str,
    date_max_by_symbol: dict[str, str] | None = None,
) -> None:
    overrides = date_max_by_symbol or {}
    (output / "prices.csv").write_text(
        f"symbol,date,close\n{symbols[0]},{date_max},9\n",
        encoding="utf-8",
    )
    (output / "selected_symbols.json").write_text(
        json.dumps({"source": "explicit_symbols", "symbols": symbols}),
        encoding="utf-8",
    )
    (output / "history_metadata.json").write_text(
        json.dumps(
            {
                "source": "baostock",
                "end_date": end_date,
                "symbols": [
                    {
                        "symbol": symbol,
                        "rows": 120,
                        "date_min": date_min,
                        "date_max": overrides.get(symbol, date_max),
                    }
                    for symbol in symbols
                ],
                "failed_symbols": [],
                "empty_symbols": [],
            }
        ),
        encoding="utf-8",
    )


def minimal_history_manifest(
    output: Path,
    *,
    end_date: str,
    symbols: list[str] | None = None,
) -> dict[str, object]:
    selected = symbols or ["000001"]
    return {
        "runner": "run_today_a_share_selection",
        "requested_mode": "auto",
        "mode": "generic",
        "mode_decision": "auto_generic",
        "mode_decision_reason": "",
        "missing_prediction_column_groups": [],
        "missing_prediction_requirement": "",
        "steps": [],
        "output_dir": str(output),
        "source_scope": "baostock_history_fetch",
        "prediction_mode": False,
        "prediction_input_source": "not_used",
        "prediction_model_executed_by_runner": False,
        "lightgbm_not_used": True,
        "lightgbm_output_source": "not_used",
        "run_outputs_initialized": True,
        "input_metadata": {},
        "end_date": end_date,
        "max_history_symbols": 0,
        "allow_partial_history": False,
        "history_symbols": selected,
    }


if __name__ == "__main__":
    unittest.main()
