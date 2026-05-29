from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import score_candidates as scorer  # noqa: E402
import validate_ohlcv  # noqa: E402


def load_config(name: str) -> dict:
    return json.loads((SCRIPTS / name).read_text(encoding="utf-8"))


def build_frame(
    *,
    days: int = 130,
    include_prediction: bool = False,
    prediction_value: float = 0.72,
    prediction_column: str = "prediction_score",
    include_turn: bool = True,
) -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2025-01-02", periods=days)
    symbols = [("000002", "Zero Prefix", 8.0), ("600001", "Shanghai", 10.0)]
    for symbol, name, base in symbols:
        for index, date in enumerate(dates):
            close = base + index * 0.018 + np.sin(index / 9) * 0.08
            row = {
                "symbol": symbol,
                "name": name,
                "market": "A-share",
                "date": date.date().isoformat(),
                "open": close * 0.997,
                "high": close * 1.012,
                "low": close * 0.988,
                "close": close,
                "volume": 120000 + index * 30,
            }
            if include_turn:
                row["turn"] = 1.1 + np.cos(index / 11) * 0.03
            if include_prediction:
                row[prediction_column] = prediction_value
            rows.append(row)
    return pd.DataFrame(rows)


def permissive_thresholds(min_history_rows: int) -> dict:
    return {
        "min_total_score": -10.0,
        "min_trend_score": -10.0,
        "min_momentum_score": -10.0,
        "min_rsi": 0.0,
        "max_rsi": 100.0,
        "max_volatility": 10.0,
        "min_volume": 0.0,
        "min_close": 0.0,
        "min_history_rows": min_history_rows,
    }


def run_score_cli(
    input_path: Path,
    output_path: Path,
    *,
    config_name: str = "example_config.json",
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = scorer.main(
            [
                "--input",
                str(input_path),
                "--config",
                str(SCRIPTS / config_name),
                "--output",
                str(output_path),
            ]
        )
    return code, stdout.getvalue(), stderr.getvalue()


def run_validate_cli(input_path: Path) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = validate_ohlcv.main(["--input", str(input_path)])
    return code, stdout.getvalue(), stderr.getvalue()


class StockSelectionScriptTests(unittest.TestCase):
    def test_validate_reader_preserves_symbol_prefix_zero(self) -> None:
        frame = build_frame(days=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prices.csv"
            frame.to_csv(path, index=False)
            loaded = validate_ohlcv.read_table(path)
        self.assertEqual("000002", loaded["symbol"].iloc[0])

    def test_empty_input_is_error(self) -> None:
        config = load_config("example_config.json")
        empty = pd.DataFrame(columns=validate_ohlcv.REQUIRED_COLUMNS)
        with self.assertRaisesRegex(ValueError, "input data is empty"):
            scorer.score_candidates(empty, config)

    def test_validate_cli_error_includes_input_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prices.txt"
            path.write_text("not csv", encoding="utf-8")
            code, _, stderr = run_validate_cli(path)
        self.assertEqual(2, code)
        self.assertIn("unsupported input format", stderr)
        self.assertIn("input=prices.txt", stderr)

    def test_score_rejects_negative_price(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame()
        frame.loc[0, "close"] = -1
        with self.assertRaisesRegex(ValueError, "non-positive values"):
            scorer.score_candidates(frame, config)

    def test_score_rejects_duplicate_symbol_date(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame()
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate symbol/date rows"):
            scorer.score_candidates(frame, config)

    def test_short_history_is_error_when_nothing_can_score(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame(days=119)
        with self.assertRaisesRegex(ValueError, "fewer than 120 rows"):
            scorer.score_candidates(frame, config)

    def test_missing_turn_in_generic_mode_is_reported(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame(include_turn=False)
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(
            "neutral_series_missing_turnover",
            summary["turnover_assumption"],
        )

    def test_qsss_turnover_alias_scores(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame = frame.rename(columns={"turn": "turnover"})
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(2, summary["scored_symbols"])
        self.assertEqual(0, summary["failed_symbols"])

    def test_universe_filtering_reports_all_filtered_symbols(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame["symbol"] = frame["symbol"].map(
            {"000002": "900001", "600001": "810002"}
        )
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(2, summary["raw_symbols"])
        self.assertEqual(0, summary["input_symbols"])
        self.assertEqual(2, summary["universe_filtered_symbols"])
        self.assertEqual(0, summary["candidates"])

    def test_explosion_score_is_zero_below_volume_window(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(10)
        frame = build_frame(days=10)
        candidates, summary = scorer.score_candidates(frame, config)
        self.assertEqual(2, summary["scored_symbols"])
        self.assertGreater(len(candidates), 0)
        self.assertTrue((candidates["explosion_score"] == 0).all())

    def test_max_candidates_does_not_count_as_threshold_failure(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(120)
        config["output"]["max_candidates"] = 1
        frame = build_frame()
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(0, summary["threshold_failed_symbols"])
        self.assertEqual(1, summary["candidates"])

    def test_qsss_requires_prediction_column(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_turn=True)
        with self.assertRaisesRegex(ValueError, "prediction or prediction_score"):
            scorer.score_candidates(frame, config)

    def test_qsss_requires_market_column(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame = frame.drop(columns=["market"])
        with self.assertRaisesRegex(ValueError, "requires market column"):
            scorer.score_candidates(frame, config)

    def test_qsss_rejects_invalid_prediction_range(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(
            include_prediction=True,
            prediction_value=1.2,
            include_turn=True,
        )
        with self.assertRaisesRegex(ValueError, "invalid values"):
            scorer.score_candidates(frame, config)

    def test_qsss_rejects_missing_prediction_values(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame["prediction_score"] = np.nan
        with self.assertRaisesRegex(ValueError, "prediction_score has"):
            scorer.score_candidates(frame, config)

    def test_generic_rejects_invalid_prediction_range(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame(include_prediction=True, prediction_value=-0.1)
        with self.assertRaisesRegex(ValueError, "prediction_score has"):
            scorer.score_candidates(frame, config)

    def test_qsss_valid_prediction_marks_external_source(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual("external_unverified", summary["prediction_source"])
        self.assertEqual(2, summary["scored_symbols"])

    def test_universe_market_filter_is_applied(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame["market"] = "HK"
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(0, summary["input_symbols"])
        self.assertEqual(2, summary["universe_filtered_symbols"])

    def test_cli_success_writes_candidates_csv(self) -> None:
        frame = build_frame(include_turn=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "candidates.csv"
            frame.to_csv(input_path, index=False)
            code, stdout, stderr = run_score_cli(input_path, output_path)
            self.assertEqual(0, code, stderr)
            self.assertTrue(output_path.exists())
            self.assertIn("raw_symbols=2", stdout)
            self.assertIn(f"input={input_path.name}", stdout)
            self.assertIn("turnover_assumption=neutral_series_missing_turnover", stdout)
            self.assertIn("turn/turnover missing", stderr)

    def test_cli_missing_qsss_prediction_returns_error(self) -> None:
        frame = build_frame(include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "qsss.csv"
            frame.to_csv(input_path, index=False)
            code, _, stderr = run_score_cli(
                input_path,
                output_path,
                config_name="qsss_profile_config.json",
            )
            self.assertEqual(2, code)
            self.assertFalse(output_path.exists())
            self.assertIn("prediction or prediction_score", stderr)
            self.assertIn(f"input={input_path.name}", stderr)

    def test_cli_low_prediction_reports_effective_empty_result(self) -> None:
        config = load_config("qsss_profile_config.json")
        frame = build_frame(include_prediction=True, prediction_value=0.1, include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "qsss_low_pred.csv"
            frame.to_csv(input_path, index=False)
            code, stdout, stderr = run_score_cli(
                input_path,
                output_path,
                config_name="qsss_profile_config.json",
            )
            self.assertEqual(0, code, stderr)
            self.assertTrue(output_path.exists())
            self.assertIn("effective_empty_result=true", stdout)
            self.assertIn("candidates=0", stdout)
            self.assertIn("prediction_source=external_unverified", stdout)

if __name__ == "__main__":
    unittest.main()
