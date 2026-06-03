from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import score_candidates as scorer  # noqa: E402
from stock_selection_data import read_table  # noqa: E402
import validate_ohlcv  # noqa: E402
from helpers import build_frame, load_config, permissive_thresholds  # noqa: E402


def run_score_cli(
    input_path: Path,
    output_path: Path,
    *,
    config_name: str = "example_config.json",
    extra_args: list[str] | None = None,
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        args = [
            "--input",
            str(input_path),
            "--config",
            str(SCRIPTS / config_name),
            "--output",
            str(output_path),
        ]
        if extra_args:
            args.extend(extra_args)
        code = scorer.main(args)
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
            loaded = read_table(path)
        self.assertEqual("000002", loaded["symbol"].iloc[0])

    def test_validate_rejects_numeric_damaged_symbol(self) -> None:
        frame = build_frame()
        frame["symbol"] = "1"
        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)
        self.assertIn("preserve leading zeros as text", "; ".join(errors))

    def test_yyyymmdd_dates_are_parsed_as_calendar_dates(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame()
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y%m%d")
        candidates, summary = scorer.score_candidates(frame, config)
        self.assertEqual(2, summary["scored_symbols"])
        self.assertTrue(candidates["data_window"].str.startswith("2025-").all())

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

    def test_score_rejects_duplicate_calendar_date_formats(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame()
        duplicate = frame.iloc[[0]].copy()
        duplicate["date"] = pd.to_datetime(duplicate["date"]).dt.strftime("%Y%m%d")
        frame = pd.concat([frame, duplicate], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate symbol/date rows"):
            scorer.score_candidates(frame, config)

    def test_short_history_is_error_when_nothing_can_score(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame(days=119)
        with self.assertRaisesRegex(ValueError, "insufficient_history_symbols=2"):
            scorer.score_candidates(frame, config)

    def test_missing_turn_in_generic_mode_is_reported(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame(include_turn=False)
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(
            "neutral_series_missing_turnover",
            summary["turnover_assumption"],
        )

    def test_prediction_turnover_alias_scores(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame = frame.rename(columns={"turn": "turnover"})
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(2, summary["scored_symbols"])
        self.assertEqual(0, summary["failed_symbols"])

    def test_prediction_candidate_output_keeps_raw_signal_close(self) -> None:
        config = load_config("prediction_profile_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_prediction=True, include_turn=True)
        mask = frame["symbol"].eq("000002")
        last_index = frame[mask].index[-1]
        frame.loc[last_index - 1, "close"] = 70.0
        frame.loc[last_index, "close"] = 77.19

        candidates, _summary = scorer.score_candidates(frame, config)
        output = candidates[candidates["symbol"].eq("000002")].iloc[0]

        self.assertEqual(77.19, output["close"])

    def test_universe_filtering_reports_all_filtered_symbols(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame["symbol"] = frame["symbol"].map(
            {"000002": "900001", "600001": "810002"}
        )
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(2, summary["raw_symbols"])
        self.assertEqual(0, summary["input_symbols"])
        self.assertEqual(2, summary["universe_filtered_symbols"])
        self.assertEqual(0, summary["candidates"])
        self.assertEqual("universe_filtered_all", summary["empty_result_reason"])

    def test_explosion_score_is_zero_below_volume_window(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(10)
        frame = build_frame(days=10)
        candidates, summary = scorer.score_candidates(frame, config)
        self.assertEqual(2, summary["scored_symbols"])
        self.assertGreater(len(candidates), 0)
        self.assertTrue((candidates["explosion_score"] == 0).all())
        self.assertTrue(
            set(candidates["recommendation"]).issubset(
                {"high_signal", "medium_signal", "low_signal"}
            )
        )
        self.assertEqual(
            candidates["signal_tier"].tolist(),
            candidates["recommendation"].tolist(),
        )

    def test_max_candidates_does_not_count_as_threshold_failure(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(120)
        config["output"]["max_candidates"] = 1
        frame = build_frame()
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(0, summary["threshold_failed_symbols"])
        self.assertEqual(1, summary["candidates"])

    def test_prediction_requires_prediction_column(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_turn=True, include_tradability=True)
        with self.assertRaisesRegex(ValueError, "prediction or prediction_score"):
            scorer.score_candidates(frame, config)

    def test_prediction_requires_market_column(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame = frame.drop(columns=["market"])
        with self.assertRaisesRegex(ValueError, "requires market column"):
            scorer.score_candidates(frame, config)

    def test_prediction_rejects_invalid_prediction_range(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(
            include_prediction=True,
            prediction_value=1.2,
            include_turn=True,
        )
        with self.assertRaisesRegex(ValueError, "invalid values"):
            scorer.score_candidates(frame, config)

    def test_prediction_rejects_missing_prediction_values(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame["prediction_score"] = float("nan")
        with self.assertRaisesRegex(ValueError, "prediction_score has"):
            scorer.score_candidates(frame, config)

    def test_generic_rejects_invalid_prediction_range(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame(include_prediction=True, prediction_value=-0.1)
        with self.assertRaisesRegex(ValueError, "prediction_score has"):
            scorer.score_candidates(frame, config)

    def test_prediction_valid_prediction_marks_external_source(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual("external_unverified", summary["prediction_source"])
        self.assertEqual(2, summary["scored_symbols"])

    def test_universe_market_filter_is_applied(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        frame["market"] = "HK"
        with self.assertRaisesRegex(ValueError, "requires at least one A-share row"):
            scorer.score_candidates(frame, config)

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
            self.assertIn("generic mode: turn/turnover missing", stderr)
            self.assertIn("no prediction-derived turnover gate is applied", stderr)

    def test_cli_writes_threshold_diagnostics_csv(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"]["min_total_score"] = 999
        frame = build_frame(include_turn=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            config_path = Path(tmpdir) / "config.json"
            output_path = Path(tmpdir) / "candidates.csv"
            diagnostics_path = Path(tmpdir) / "diagnostics.csv"
            frame.to_csv(input_path, index=False)
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
            diagnostics = pd.read_csv(diagnostics_path)
            output_exists = output_path.exists()

        self.assertEqual(0, code, stderr.getvalue())
        self.assertTrue(output_exists)
        self.assertEqual(2, len(diagnostics))
        self.assertEqual({False}, set(diagnostics["passed_thresholds"]))
        self.assertEqual({False}, set(diagnostics["selected_candidate"]))
        self.assertTrue(
            diagnostics["failed_thresholds"].str.contains("min_total_score").all()
        )
        self.assertTrue(
            diagnostics["failed_thresholds_zh"].str.contains("综合评分不足").all()
        )
        self.assertEqual({"未通过阈值"}, set(diagnostics["selection_status"]))
        self.assertTrue(diagnostics["short_reason"].str.contains("综合评分不足").all())
        self.assertIn("effective_empty_result=true", stdout.getvalue())

    def test_cli_merges_spot_input_into_candidates_and_diagnostics(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
        spot = pd.DataFrame(
            [
                {
                    "symbol": "000002",
                    "price": 8.88,
                    "pct_chg": 3.2,
                    "amount": 250000000,
                    "industry": "软件服务",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            spot_path = Path(tmpdir) / "spot.csv"
            config_path = Path(tmpdir) / "config.json"
            output_path = Path(tmpdir) / "candidates.csv"
            diagnostics_path = Path(tmpdir) / "diagnostics.csv"
            frame.to_csv(input_path, index=False)
            spot.to_csv(spot_path, index=False)
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
                        "--spot-input",
                        str(spot_path),
                    ]
                )
            candidates = pd.read_csv(output_path)
            diagnostics = pd.read_csv(diagnostics_path)

        self.assertEqual(0, code, stderr.getvalue())
        self.assertIn("spot_rows=1", stdout.getvalue())
        selected = candidates[candidates["symbol"].astype(str).eq("2")].iloc[0]
        self.assertEqual(8.88, selected["spot_price"])
        diagnostic = diagnostics[diagnostics["symbol"].astype(str).eq("2")].iloc[0]
        self.assertEqual("软件服务", diagnostic["spot_industry"])

    def test_ultra_short_profile_filters_prices_above_max_close(self) -> None:
        config = load_config("ultra_short_low_price_config.json")
        config["thresholds"] = permissive_thresholds(120) | {"max_close": 11.0}
        frame = build_frame(include_turn=True)

        candidates, summary = scorer.score_candidates(frame, config)

        self.assertEqual(2, summary["scored_symbols"])
        self.assertEqual(1, summary["threshold_failed_symbols"])
        self.assertEqual({"000002"}, set(candidates["symbol"]))
        self.assertEqual({"max_close": 1}, summary["threshold_failures"])

    def test_ultra_short_profile_requires_amount_turn_and_tradability_columns(self) -> None:
        config = load_config("ultra_short_low_price_config.json")
        frame = build_frame(include_turn=True, include_tradability=True).drop(
            columns=["amount", "turn", "tradestatus", "isST"]
        )

        with self.assertRaisesRegex(ValueError, "min_amount threshold requires amount"):
            scorer.score_candidates(frame, config)

    def test_ultra_short_profile_filters_liquidity_st_suspended_and_one_word_bar(self) -> None:
        config = load_config("ultra_short_low_price_config.json")
        config["thresholds"] = permissive_thresholds(120) | {
            "min_amount": 100000000.0,
            "min_turn": 1.0,
            "max_close": 20.0,
            "exclude_st": True,
            "require_tradestatus": "1",
            "exclude_one_word_bar": True,
        }
        frame = build_frame(include_turn=True, include_tradability=True)
        latest_000002 = frame[frame["symbol"].eq("000002")].index[-1]
        latest_600001 = frame[frame["symbol"].eq("600001")].index[-1]
        frame.loc[latest_000002, "amount"] = 1.0
        frame.loc[latest_000002, "turn"] = 0.1
        frame.loc[latest_600001, "tradestatus"] = "0"
        frame.loc[latest_600001, "isST"] = "1"
        for column in ["open", "high", "low"]:
            frame.loc[latest_600001, column] = frame.loc[latest_600001, "close"]

        candidates, summary = scorer.score_candidates(frame, config)

        self.assertEqual(0, len(candidates))
        self.assertEqual(2, summary["threshold_failed_symbols"])
        self.assertEqual(
            {
                "exclude_one_word_bar": 1,
                "exclude_st": 1,
                "min_amount": 1,
                "min_turn": 1,
                "require_tradestatus": 1,
            },
            summary["threshold_failures"],
        )

    def test_cli_missing_prediction_column_returns_error(self) -> None:
        frame = build_frame(include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "prediction.csv"
            frame.to_csv(input_path, index=False)
            code, _, stderr = run_score_cli(
                input_path,
                output_path,
                config_name="prediction_profile_config.json",
            )
            self.assertEqual(2, code)
            self.assertFalse(output_path.exists())
            self.assertIn("prediction or prediction_score", stderr)
            self.assertIn(f"input={input_path.name}", stderr)
            self.assertIn("code=bad_input", stderr)

    def test_cli_low_prediction_reports_effective_empty_result(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, prediction_value=0.1, include_turn=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "prediction_low_pred.csv"
            frame.to_csv(input_path, index=False)
            code, stdout, stderr = run_score_cli(
                input_path,
                output_path,
                config_name="prediction_profile_config.json",
            )
            self.assertEqual(0, code, stderr)
            self.assertTrue(output_path.exists())
            self.assertIn("effective_empty_result=true", stdout)
            self.assertIn("empty_result_reason=threshold_filtered_all", stdout)
            self.assertIn("candidates=0", stdout)
            self.assertIn("prediction_source=external_unverified", stdout)
            self.assertIn("prediction_model_executed_by_score_script=false", stdout)

if __name__ == "__main__":
    unittest.main()
