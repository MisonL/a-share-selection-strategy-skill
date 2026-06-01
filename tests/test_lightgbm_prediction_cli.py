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
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import generate_lightgbm_predictions as generator  # noqa: E402
import score_candidates as scorer  # noqa: E402
from helpers import build_frame, load_config  # noqa: E402


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
    def test_prediction_uses_train_split_only_and_scores_qsss_input(self) -> None:
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
            load_config("qsss_profile_config.json"),
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
        self.assertIn("close.shift(-horizon)", saved["label_definition"])
        self.assertEqual("predicted", saved["symbols"][0]["status"])
        self.assertGreater(saved["symbols"][0]["train_rows"], 0)
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
        self.assertIn("close.shift(-horizon)", saved["symbols"][0]["label_definition"])

    def test_cli_reports_missing_lightgbm_dependency_without_output(self) -> None:
        frame = build_frame(days=180, include_turn=True)
        original_loader = generator.load_model_dependencies
        generator.load_model_dependencies = lambda: (_ for _ in ()).throw(
            RuntimeError("LightGBM prediction requires lightgbm and scikit-learn")
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
            self.assertIn("lightgbm and scikit-learn", stderr.getvalue())
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


if __name__ == "__main__":
    unittest.main()
