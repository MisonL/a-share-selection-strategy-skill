from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

from a_share_selection_html_report import render_report  # noqa: E402
from html_report_helpers import minimal_summary  # noqa: E402


class TodayAShareHtmlReportModesTests(unittest.TestCase):
    def test_unresolved_failure_does_not_claim_generic_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary.update(
                {
                    "status": "failed",
                    "requested_mode": "auto",
                    "mode": "unresolved",
                    "mode_decision": "unresolved",
                    "mode_decision_reason": "",
                    "prediction_mode": False,
                    "failed_steps": [],
                    "source_scope": "unresolved",
                    "candidate_rows": 0,
                    "diagnostic_rows": 0,
                    "prices_output": str(Path(tmpdir) / "prices.csv"),
                    "prices_output_written": False,
                    "candidates_output": str(Path(tmpdir) / "candidates.csv"),
                    "candidates_output_written": False,
                    "diagnostics_output": str(Path(tmpdir) / "diagnostics.csv"),
                    "diagnostics_output_written": False,
                    "boundary": "Generic technical mode; not prediction-derived and not LightGBM-backed.",
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("Mode unresolved", report)
        self.assertIn("Source scope unresolved", report)
        self.assertIn("failed before a scoring mode was resolved", report)
        self.assertIn("failed before mode resolution or scoring completed", report)
        self.assertIn("cannot prove that scoring, filtering, ranking", report)
        self.assertIn("Machine boundary", report)
        self.assertIn("cannot claim generic or prediction-derived scoring", report)
        self.assertNotIn("Generic technical scoring", report)
        self.assertNotIn("Generic technical mode", report)
        self.assertNotIn("filtered local A-share price data", report)
        self.assertNotIn("Auto mode selected the generic technical path", report)
        self.assertNotIn("Local file plus external snapshot or fetch", report)
        self.assertNotIn("./prices.csv", report)
        self.assertNotIn("./candidates.csv", report)
        self.assertNotIn("./diagnostics.csv", report)

    def test_generic_failure_does_not_claim_completed_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary.update(
                {
                    "status": "failed",
                    "requested_mode": "generic",
                    "mode": "generic",
                    "mode_decision": "explicit_generic",
                    "mode_decision_reason": "user_requested_generic",
                    "prediction_mode": False,
                    "failed_steps": ["validate"],
                    "candidate_rows": 0,
                    "diagnostic_rows": 0,
                    "candidates_output_written": False,
                    "diagnostics_output_written": False,
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("Generic scoring not completed", report)
        self.assertIn("validation or scoring did not complete", report)
        self.assertIn("did not complete scoring, filtering, or ranking", report)
        self.assertIn("cannot prove that technical scoring, filtering, ranking", report)
        self.assertNotIn("Generic technical scoring", report)
        self.assertNotIn("filtered local A-share price data", report)
        self.assertNotIn("ranked the rows that passed", report)
        self.assertNotIn("Generic mode was requested explicitly.", report)

    def test_generic_strict_gate_failure_reports_scoring_reached(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary.update(
                {
                    "status": "failed",
                    "requested_mode": "generic",
                    "mode": "generic",
                    "mode_decision": "explicit_generic",
                    "mode_decision_reason": "user_requested_generic",
                    "prediction_mode": False,
                    "failed_steps": ["score"],
                    "candidate_rows": 0,
                    "diagnostic_rows": 0,
                    "candidates_output_written": False,
                    "diagnostics_output_written": False,
                }
            )
            report = render_report(summary, strict_gate_manifest("generic"), language="en")

        self.assertIn("Generic technical scoring", report)
        self.assertIn("Generic scoring reached a strict-gate failure", report)
        self.assertIn("strict gate failed before a completed candidate output", report)
        self.assertIn("configured technical gates were applied", report)
        self.assertNotIn("Generic scoring not completed", report)

    def test_prediction_mode_missing_columns_report_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary.update(prediction_summary_overrides())
            summary["missing_prediction_column_groups"] = ["prediction"]
            summary["missing_prediction_requirement"] = "prediction_or_prediction_score"
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("Prediction mode was requested, but required prediction columns are missing.", report)
        self.assertIn("本次请求外部预测列评分，但输入缺少必需预测列。", report)
        self.assertIn("Missing required prediction columns", report)
        self.assertIn("validation failed before scoring", report)
        self.assertIn("It did not consume prediction columns, rank candidates", report)
        self.assertNotIn("Read from input columns", report)
        self.assertNotIn("supplied prediction columns were consumed", report)

    def test_prediction_mode_failed_validate_without_missing_groups_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary.update(prediction_summary_overrides())
            summary["failed_steps"] = ["validate"]
            report = render_report(summary, validate_failure_manifest(), language="en")

        self.assertIn("did not reach a successful scoring step", report)
        self.assertIn("Not consumed because scoring did not complete", report)
        self.assertIn("It did not consume prediction columns or rank candidates.", report)
        self.assertNotIn("Read from input columns", report)

    def test_prediction_strict_gate_failure_reports_consumed_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary.update(prediction_summary_overrides())
            summary["failed_steps"] = ["score"]
            report = render_report(summary, strict_gate_manifest("prediction"), language="en")

        self.assertIn("Read from input columns", report)
        self.assertIn("reached scoring and consumed supplied prediction columns", report)
        self.assertIn("scoring reached a strict-gate failure", report)
        self.assertIn("supplied prediction columns were consumed", report)
        self.assertNotIn("Not consumed because scoring did not complete", report)


def prediction_summary_overrides() -> dict[str, object]:
    return {
        "status": "failed",
        "prediction_mode": True,
        "requested_mode": "prediction",
        "mode": "prediction",
        "mode_decision": "explicit",
        "mode_decision_reason": "user_requested_prediction",
        "missing_prediction_column_groups": [],
        "missing_prediction_requirement": "",
        "prediction_input_source": "external_input",
    }


def validate_failure_manifest() -> dict[str, object]:
    return {
        "steps": [
            {
                "step": "validate",
                "returncode": 1,
                "allowed_returncodes": [0],
                "stderr": "prediction-derived profile requires prediction",
            }
        ]
    }


def strict_gate_manifest(mode: str) -> dict[str, object]:
    stdout = (
        "ERROR_SUMMARY: raw_symbols=2 input_symbols=2 scored_symbols=2 "
        "threshold_failed_symbols=2 candidates=0 effective_empty_result=true "
        "output=candidates.csv"
    )
    if mode == "prediction":
        stdout = (
            "ERROR_SUMMARY: raw_symbols=2 input_symbols=2 invalid_or_dropped_symbols=0 "
            "universe_filtered_symbols=0 market_filtered_symbols=0 "
            "prefix_allow_filtered_symbols=0 prefix_excluded_symbols=0 "
            "insufficient_history_symbols=0 scored_symbols=2 failed_symbols=0 "
            "threshold_failed_symbols=2 candidates=0 prediction_source=external_unverified "
            "prediction_input_source=external_input prediction_model_executed_by_score_script=false "
            "lightgbm_not_executed_by_this_script=true effective_empty_result=true output=candidates.csv"
        )
    return {
        "steps": [
            {"step": "validate", "returncode": 0, "allowed_returncodes": [0]},
            {"step": "score", "returncode": 3, "allowed_returncodes": [0], "stdout": stdout},
        ]
    }


if __name__ == "__main__":
    unittest.main()
