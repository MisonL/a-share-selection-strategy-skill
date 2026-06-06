from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import generate_lightgbm_predictions as generator  # noqa: E402
import score_candidates as scorer  # noqa: E402
from helpers import build_frame, load_config, permissive_thresholds  # noqa: E402


class RecordingScaler:
    def __init__(self) -> None:
        self.fit_rows = 0

    def fit_transform(self, frame):
        self.fit_rows = len(frame)
        return frame.to_numpy(dtype=float)

    def transform(self, frame):
        return frame.to_numpy(dtype=float)


class RecordingClassifier:
    last_fit_rows = 0
    last_labels: list[int] = []
    saw_feature_columns = False

    def __init__(self, **_: object) -> None:
        pass

    def fit(self, features, labels) -> None:
        type(self).last_fit_rows = len(features)
        type(self).last_labels = list(labels)
        type(self).saw_feature_columns = list(features.columns) == generator.FEATURE_COLUMNS

    def predict_proba(self, features):
        type(self).saw_feature_columns = (
            type(self).saw_feature_columns
            and list(features.columns) == generator.FEATURE_COLUMNS
        )
        return np.array([[0.27, 0.73] for _ in range(len(features))])


class LightgbmPredictionCliTests(unittest.TestCase):
    def test_prediction_uses_train_split_only_and_scores_prediction_input(self) -> None:
        frame = build_frame(days=180, include_turn=True)
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        result, summary = generator.generate_predictions(
            frame,
            horizon=5,
            train_ratio=0.8,
            min_history_rows=150,
            model_deps=deps,
        )

        self.assertEqual(2, summary["predicted_symbols"])
        self.assertEqual(0, summary["skipped_symbols"])
        self.assertTrue(result["prediction_score"].between(0, 1).all())
        self.assertEqual({5}, set(result["prediction_horizon_days"]))
        self.assertEqual({"lightgbm"}, set(result["prediction_model"]))
        self.assertGreater(RecordingClassifier.last_fit_rows, 0)
        self.assertLess(RecordingClassifier.last_fit_rows, len(frame))
        self.assertEqual({0, 1}, set(RecordingClassifier.last_labels))
        self.assertTrue(RecordingClassifier.saw_feature_columns)
        _, score_summary = scorer.score_candidates(
            result,
            load_config("prediction_profile_config.json"),
        )
        self.assertEqual(2, score_summary["scored_symbols"])
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "summary.json"
            generator.write_json_summary(summary, summary_path)
            saved = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(2, len(saved["symbols"]))
        self.assertEqual(generator.FEATURE_COLUMNS, saved["feature_columns"])
        self.assertEqual("time_series_train_prefix", saved["split_method"])
        self.assertEqual("train_split_only", saved["scaler_fit_scope"])
        self.assertEqual("latest_probability_repeated_for_scoring", saved["prediction_scope"])
        self.assertEqual("generation_audit_only", saved["model_quality_scope"])
        self.assertEqual("not_computed", saved["model_quality_metrics"]["holdout_auc"])
        self.assertEqual("not_computed", saved["model_quality_metrics"]["holdout_ic"])
        self.assertEqual(
            "not_evaluated",
            saved["model_quality_metrics"]["probability_calibration"],
        )
        self.assertEqual(
            "not_proven",
            saved["model_quality_metrics"]["full_market_generalization"],
        )
        self.assertIn("close.shift(-horizon)", saved["label_definition"])
        self.assertEqual("predicted", saved["symbols"][0]["status"])
        self.assertGreater(saved["symbols"][0]["train_rows"], 0)
        self.assertGreater(saved["symbols"][0]["holdout_rows"], 0)
        self.assertGreaterEqual(
            saved["symbols"][0]["trainable_rows"],
            saved["symbols"][0]["train_rows"],
        )
        self.assertLessEqual(
            saved["symbols"][0]["train_date_min"],
            saved["symbols"][0]["train_date_max"],
        )
        self.assertEqual(saved["symbols"][0]["date_max"], saved["symbols"][0]["latest_feature_date"])
        self.assertGreater(saved["symbols"][0]["target_positive_labels"], 0)
        self.assertGreater(saved["symbols"][0]["target_negative_labels"], 0)
        self.assertLessEqual(
            saved["symbols"][0]["train_date_max"],
            saved["symbols"][0]["holdout_date_min"],
        )
        self.assertLessEqual(
            saved["symbols"][0]["holdout_date_max"],
            saved["symbols"][0]["latest_feature_date"],
        )
        self.assertEqual("not_computable", saved["symbols"][0]["holdout_metric_status"])
        self.assertEqual("single_class_holdout", saved["symbols"][0]["holdout_metric_reason"])
        self.assertIsNone(saved["symbols"][0]["holdout_auc"])
        self.assertIn("close.shift(-horizon)", saved["symbols"][0]["label_definition"])

    def test_cli_rejects_rows_after_as_of_date_without_output(self) -> None:
        frame = build_frame(days=180, include_turn=True)
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        original_loader = generator.load_model_dependencies
        generator.load_model_dependencies = lambda: deps
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "prices.csv"
                output_path = Path(tmpdir) / "predictions.csv"
                summary_path = Path(tmpdir) / "summary.json"
                frame.to_csv(input_path, index=False)
                stderr = StringIO()
                with redirect_stderr(stderr):
                    code = generator.main(
                        [
                            "--input",
                            str(input_path),
                            "--output",
                            str(output_path),
                            "--summary-output",
                            str(summary_path),
                            "--as-of-date",
                            "2025-07-01",
                        ]
                    )

            self.assertEqual(2, code)
            self.assertFalse(output_path.exists())
            self.assertFalse(summary_path.exists())
            self.assertIn("rows_after_as_of_date", stderr.getvalue())
            self.assertIn("output_written=false", stderr.getvalue())
        finally:
            generator.load_model_dependencies = original_loader

    def test_cli_records_as_of_boundary_on_success(self) -> None:
        frame = build_frame(days=180, include_turn=True)
        as_of_date = str(sorted(frame["date"].unique())[-1])
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        original_loader = generator.load_model_dependencies
        generator.load_model_dependencies = lambda: deps
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "prices.csv"
                output_path = Path(tmpdir) / "predictions.csv"
                summary_path = Path(tmpdir) / "summary.json"
                frame.to_csv(input_path, index=False)
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = generator.main(
                        [
                            "--input",
                            str(input_path),
                            "--output",
                            str(output_path),
                            "--summary-output",
                            str(summary_path),
                            "--as-of-date",
                            as_of_date,
                        ]
                    )
                predictions = pd.read_csv(output_path, dtype={"symbol": str})
                saved = json.loads(summary_path.read_text(encoding="utf-8"))

            self.assertEqual(0, code, stderr.getvalue())
            self.assertEqual({as_of_date}, set(predictions["requested_as_of_date"]))
            self.assertEqual({as_of_date}, set(predictions["actual_data_date"]))
            self.assertEqual({True}, set(predictions["as_of_date_observed"]))
            self.assertEqual(as_of_date, saved["requested_as_of_date"])
            self.assertEqual(as_of_date, saved["actual_data_date"])
            self.assertTrue(saved["as_of_date_observed"])
            self.assertIn(f"requested_as_of_date={as_of_date}", stdout.getvalue())
        finally:
            generator.load_model_dependencies = original_loader

    def test_prediction_scoring_preserves_generation_provenance_outputs(self) -> None:
        frame = build_frame(days=180, include_turn=True)
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        predictions, _summary = generator.generate_predictions(
            frame,
            horizon=5,
            train_ratio=0.8,
            min_history_rows=150,
            model_deps=deps,
        )
        config = load_config("prediction_profile_config.json")
        config["thresholds"]["min_prediction_score"] = 0.0
        config["thresholds"]["min_history_rows"] = 120
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "predictions.csv"
            config_path = root / "config.json"
            output_path = root / "candidates.csv"
            diagnostics_path = root / "diagnostics.csv"
            predictions.to_csv(input_path, index=False)
            config_path.write_text(json.dumps(config), encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = scorer.main(
                    [
                        "--input",
                        str(input_path),
                        "--config",
                        str(config_path),
                        "--output",
                        str(output_path),
                        "--diagnostics-output",
                        str(diagnostics_path),
                    ]
                )
            candidates = pd.read_csv(output_path, dtype={"symbol": str})
            diagnostics = pd.read_csv(diagnostics_path, dtype={"symbol": str})

        self.assertEqual(0, code, stderr.getvalue())
        for frame_out in (candidates, diagnostics):
            self.assertEqual({"lightgbm"}, set(frame_out["prediction_model"]))
            self.assertEqual({5}, set(frame_out["prediction_horizon_days"]))
            self.assertEqual(
                {"latest_probability_repeated_for_scoring"},
                set(frame_out["prediction_scope"]),
            )

    def test_prediction_records_computed_holdout_auc_when_labels_vary(self) -> None:
        frame = oscillating_frame(days=180)
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        _result, summary = generator.generate_predictions(
            frame,
            horizon=5,
            train_ratio=0.8,
            min_history_rows=150,
            model_deps=deps,
        )

        first = summary["symbols"][0]
        self.assertGreater(first["holdout_positive_labels"], 0)
        self.assertGreater(first["holdout_negative_labels"], 0)
        self.assertEqual("computed", first["holdout_metric_status"])
        self.assertEqual("", first["holdout_metric_reason"])
        self.assertGreaterEqual(first["holdout_auc"], 0.0)
        self.assertLessEqual(first["holdout_auc"], 1.0)

    def test_cli_reports_missing_lightgbm_dependency_without_output(self) -> None:
        frame = build_frame(days=180, include_turn=True)
        original_loader = generator.load_model_dependencies
        generator.load_model_dependencies = lambda: (_ for _ in ()).throw(
            generator.PredictionDependencyError(
                "LightGBM prediction requires lightgbm and scikit-learn"
            )
        )
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "prices.csv"
                output_path = Path(tmpdir) / "predictions.csv"
                summary_path = Path(tmpdir) / "summary.json"
                frame.to_csv(input_path, index=False)
                stderr = StringIO()
                with redirect_stderr(stderr):
                    code = generator.main(
                        [
                            "--input",
                            str(input_path),
                            "--output",
                            str(output_path),
                            "--summary-output",
                            str(summary_path),
                        ]
                    )
            self.assertEqual(2, code)
            self.assertFalse(output_path.exists())
            self.assertFalse(summary_path.exists())
            self.assertIn("code=dependency_error", stderr.getvalue())
            self.assertIn("lightgbm and scikit-learn", stderr.getvalue())
        finally:
            generator.load_model_dependencies = original_loader

    def test_cli_success_stdout_discloses_generation_quality_boundary(self) -> None:
        frame = build_frame(days=180, include_turn=True)
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        original_loader = generator.load_model_dependencies
        generator.load_model_dependencies = lambda: deps
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "prices.csv"
                output_path = Path(tmpdir) / "predictions.csv"
                summary_path = Path(tmpdir) / "summary.json"
                frame.to_csv(input_path, index=False)
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = generator.main(
                        [
                            "--input",
                            str(input_path),
                            "--output",
                            str(output_path),
                            "--summary-output",
                            str(summary_path),
                        ]
                    )

            self.assertEqual(0, code, stderr.getvalue())
            self.assertIn("model_quality_scope=generation_audit_only", stdout.getvalue())
            self.assertIn("full_market_generalization=not_proven", stdout.getvalue())
        finally:
            generator.load_model_dependencies = original_loader

    def test_cli_all_skipped_reports_reasons_without_output(self) -> None:
        frame = build_frame(days=120, include_turn=True)
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        original_loader = generator.load_model_dependencies
        generator.load_model_dependencies = lambda: deps
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "prices.csv"
                output_path = Path(tmpdir) / "predictions.csv"
                summary_path = Path(tmpdir) / "summary.json"
                frame.to_csv(input_path, index=False)
                stderr = StringIO()
                with redirect_stderr(stderr):
                    code = generator.main(
                        [
                            "--input",
                            str(input_path),
                            "--output",
                            str(output_path),
                            "--summary-output",
                            str(summary_path),
                            "--min-history-rows",
                            "150",
                        ]
                    )
            self.assertEqual(2, code)
            self.assertFalse(output_path.exists())
            self.assertFalse(summary_path.exists())
            self.assertIn("all_skipped=true", stderr.getvalue())
            self.assertIn("skipped_reasons=insufficient_history:2", stderr.getvalue())
        finally:
            generator.load_model_dependencies = original_loader

    def test_cli_all_skipped_removes_stale_outputs(self) -> None:
        frame = build_frame(days=120, include_turn=True)
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        original_loader = generator.load_model_dependencies
        generator.load_model_dependencies = lambda: deps
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "prices.csv"
                output_path = Path(tmpdir) / "predictions.csv"
                summary_path = Path(tmpdir) / "summary.json"
                frame.to_csv(input_path, index=False)
                output_path.write_text("stale prediction rows\n", encoding="utf-8")
                summary_path.write_text('{"stale": true}\n', encoding="utf-8")
                stderr = StringIO()
                with redirect_stderr(stderr):
                    code = generator.main(
                        [
                            "--input",
                            str(input_path),
                            "--output",
                            str(output_path),
                            "--summary-output",
                            str(summary_path),
                            "--min-history-rows",
                            "150",
                        ]
                    )

            self.assertEqual(2, code)
            self.assertFalse(output_path.exists())
            self.assertFalse(summary_path.exists())
            self.assertIn("skipped_reasons=insufficient_history:2", stderr.getvalue())
        finally:
            generator.load_model_dependencies = original_loader

    def test_cli_fail_on_skipped_returns_error_without_output(self) -> None:
        full_history = build_frame(days=180, include_turn=True)
        short_history = build_frame(days=120, include_turn=True)
        short_history = short_history[short_history["symbol"] == "600001"]
        frame = full_history[full_history["symbol"] == "000002"]
        frame = pd.concat([frame, short_history], ignore_index=True)
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        original_loader = generator.load_model_dependencies
        generator.load_model_dependencies = lambda: deps
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "prices.csv"
                output_path = Path(tmpdir) / "predictions.csv"
                frame.to_csv(input_path, index=False)
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = generator.main(
                        [
                            "--input",
                            str(input_path),
                            "--output",
                            str(output_path),
                            "--min-history-rows",
                            "150",
                            "--fail-on-skipped",
                        ]
                    )
            self.assertEqual(3, code)
            self.assertFalse(output_path.exists())
            self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
            self.assertIn("skipped_symbols=1", stdout.getvalue())
            self.assertIn("output_not_written=true", stderr.getvalue())
        finally:
            generator.load_model_dependencies = original_loader

    def test_cli_fail_on_skipped_removes_stale_prediction_output(self) -> None:
        full_history = build_frame(days=180, include_turn=True)
        short_history = build_frame(days=120, include_turn=True)
        short_history = short_history[short_history["symbol"] == "600001"]
        frame = full_history[full_history["symbol"] == "000002"]
        frame = pd.concat([frame, short_history], ignore_index=True)
        deps = {"classifier": RecordingClassifier, "scaler": RecordingScaler}
        original_loader = generator.load_model_dependencies
        generator.load_model_dependencies = lambda: deps
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "prices.csv"
                output_path = Path(tmpdir) / "predictions.csv"
                summary_path = Path(tmpdir) / "summary.json"
                frame.to_csv(input_path, index=False)
                output_path.write_text("stale prediction rows\n", encoding="utf-8")
                summary_path.write_text('{"stale": true}\n', encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = generator.main(
                        [
                            "--input",
                            str(input_path),
                            "--output",
                            str(output_path),
                            "--summary-output",
                            str(summary_path),
                            "--min-history-rows",
                            "150",
                            "--fail-on-skipped",
                        ]
                    )

            self.assertEqual(3, code)
            self.assertFalse(output_path.exists())
            self.assertFalse(summary_path.exists())
            self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
            self.assertIn("output_not_written=true", stderr.getvalue())
        finally:
            generator.load_model_dependencies = original_loader


def oscillating_frame(days: int) -> pd.DataFrame:
    frame = build_frame(days=days, include_turn=True)
    dates = sorted(frame["date"].unique())
    wave = {
        date: 10.0 + np.sin(index / 3.0) * 0.6 + np.cos(index / 5.0) * 0.3
        for index, date in enumerate(dates)
    }
    for symbol_offset, symbol in enumerate(sorted(frame["symbol"].unique())):
        mask = frame["symbol"] == symbol
        adjusted = frame.loc[mask, "date"].map(wave).astype(float) + symbol_offset
        frame.loc[mask, "close"] = adjusted
        frame.loc[mask, "open"] = adjusted * 0.997
        frame.loc[mask, "high"] = adjusted * 1.012
        frame.loc[mask, "low"] = adjusted * 0.988
    return frame


if __name__ == "__main__":
    unittest.main()
