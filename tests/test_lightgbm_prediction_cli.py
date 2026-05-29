from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

import numpy as np


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

    def __init__(self, **_: object) -> None:
        pass

    def fit(self, features, labels) -> None:
        type(self).last_fit_rows = len(features)
        type(self).last_labels = list(labels)

    def predict_proba(self, features):
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
        _, score_summary = scorer.score_candidates(
            result,
            load_config("qsss_profile_config.json"),
        )
        self.assertEqual(2, score_summary["scored_symbols"])

    def test_cli_reports_missing_lightgbm_dependency_without_output(self) -> None:
        frame = build_frame(days=180, include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "predictions.csv"
            frame.to_csv(input_path, index=False)
            stderr = StringIO()
            with redirect_stderr(stderr):
                code = generator.main(
                    ["--input", str(input_path), "--output", str(output_path)]
                )
        if code == 0:
            self.assertTrue(output_path.exists())
            return
        self.assertEqual(2, code)
        self.assertFalse(output_path.exists())
        self.assertIn("lightgbm and scikit-learn", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
