from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from typing import get_type_hints
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import score_candidates as scorer  # noqa: E402
import lib.selection_core.a_share_selection_candidate_fields as a_share_selection_candidate_fields  # noqa: E402
import lib.selection_core.a_share_selection_metrics as metrics  # noqa: E402
from lib.selection_core.a_share_selection_data import ACCEPTED_DATE_FORMATS, read_table  # noqa: E402
from lib.selection_core.a_share_selection_prepare import prepare_frame  # noqa: E402
from lib.selection_core.a_share_selection_spot import normalized_spot_view  # noqa: E402
from lib.selection_core.a_share_selection_symbols import stock_symbol_key  # noqa: E402
from lib.selection_core.a_share_selection_universe import apply_universe_filter  # noqa: E402
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


class AShareSelectionScriptTests(unittest.TestCase):
    def test_validate_reader_preserves_symbol_prefix_zero(self) -> None:
        frame = build_frame(days=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prices.csv"
            frame.to_csv(path, index=False)
            loaded = read_table(path)
        self.assertEqual("000002", loaded["symbol"].iloc[0])

    def test_candidate_field_type_hints_resolve_after_lazy_pandas_import(self) -> None:
        hints = get_type_hints(
            a_share_selection_candidate_fields.merge_latest_gate_fields
        )
        self.assertIn("scored", hints)
        self.assertIn("input_frame", hints)

    def test_validate_rejects_numeric_damaged_symbol(self) -> None:
        frame = build_frame()
        frame["symbol"] = "1"
        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)
        joined = "; ".join(errors)
        self.assertIn("preserve leading zeros as text", joined)
        self.assertIn("examples=", joined)
        self.assertIn("row=2", joined)
        self.assertIn("symbol=1", joined)

    def test_validate_rejects_five_digit_numeric_damaged_symbol(self) -> None:
        frame = build_frame()
        frame["symbol"] = "12345"
        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)
        joined = "; ".join(errors)
        self.assertIn("preserve leading zeros as text", joined)
        self.assertIn("examples=", joined)
        self.assertIn("symbol=12345", joined)
        self.assertIn("row=2", joined)

    def test_validate_numeric_errors_include_field_values(self) -> None:
        frame = build_frame()
        frame["open"] = frame["open"].astype("object")
        frame.loc[0, "open"] = "bad"
        frame.loc[1, "close"] = 0
        frame.loc[2, "volume"] = -1
        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)
        joined = "; ".join(errors)

        self.assertIn("column open has 1 non-numeric values", joined)
        self.assertIn("open=bad", joined)
        self.assertIn("column close has 1 non-positive values", joined)
        self.assertIn("close=0", joined)
        self.assertIn("column volume has 1 negative values", joined)
        self.assertIn("volume=-1", joined)

    def test_validate_date_and_duplicate_errors_include_examples(self) -> None:
        frame = build_frame()
        frame.loc[0, "date"] = "bad-date"
        duplicate = frame.iloc[[1]].copy()
        duplicate["date"] = pd.to_datetime(duplicate["date"]).dt.strftime("%Y%m%d")
        frame = pd.concat([frame, duplicate], ignore_index=True)
        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)
        joined = "; ".join(errors)

        self.assertIn("column date has 1 invalid values", joined)
        self.assertIn("date=bad-date", joined)
        self.assertIn("duplicate symbol/date rows", joined)
        self.assertIn("examples=", joined)
        self.assertIn("normalized_date=", joined)

    def test_validate_reports_available_errors_when_required_column_missing(
        self,
    ) -> None:
        frame = build_frame()
        frame["symbol"] = "1"
        frame = frame.drop(columns=["volume"])

        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)
        joined = "; ".join(errors)

        self.assertIn("missing required columns: volume", joined)
        self.assertIn("preserve leading zeros as text", joined)

    def test_yyyymmdd_dates_are_parsed_as_calendar_dates(self) -> None:
        config = load_config("example_config.json")
        frame = build_frame()
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y%m%d")
        candidates, summary = scorer.score_candidates(frame, config)
        self.assertEqual(2, summary["scored_symbols"])
        self.assertTrue(candidates["data_window"].str.startswith("2025-").all())

    def test_score_outputs_one_year_pct_change_from_history(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(260)
        frame = build_frame(days=260, include_turn=True)

        candidates, summary = scorer.score_candidates(frame, config)

        symbol = str(candidates.iloc[0]["symbol"])
        source = frame[frame["symbol"].astype(str).eq(symbol)].sort_values("date")
        expected = (source["close"].iloc[-1] / source["close"].iloc[-253] - 1) * 100
        diagnostics = pd.DataFrame(summary["threshold_diagnostics"])
        candidate_value = float(candidates.iloc[0]["one_year_pct_chg"])
        diagnostic_value = float(
            diagnostics[diagnostics["symbol"].astype(str).eq(symbol)][
                "one_year_pct_chg"
            ].iloc[0]
        )

        self.assertAlmostEqual(expected, candidate_value)
        self.assertAlmostEqual(expected, diagnostic_value)

    def test_parse_dates_exposes_accepted_formats(self) -> None:
        self.assertEqual(("%Y%m%d", "%Y-%m-%d"), ACCEPTED_DATE_FORMATS)

    def test_html_data_symbol_key_normalizes_hk_symbol_aliases(self) -> None:
        self.assertEqual("00700", stock_symbol_key("HK.00700"))
        self.assertEqual("00700", stock_symbol_key("00700.HK"))
        self.assertEqual("00700", stock_symbol_key("0700.HK"))
        self.assertEqual("00700", stock_symbol_key("700"))
        self.assertEqual("00700", stock_symbol_key("700.HK"))
        self.assertEqual("00700", stock_symbol_key("HK.700"))
        self.assertEqual("300001", stock_symbol_key("sz.300001"))
        self.assertEqual("430047", stock_symbol_key("bj.430047"))
        self.assertEqual("835185", stock_symbol_key("835185.BJ"))

    def test_slash_dates_are_rejected_instead_of_silently_parsed(self) -> None:
        frame = build_frame()
        frame.loc[0, "date"] = "05/20/2026"

        errors = validate_ohlcv.validate_frame(frame, min_history_rows=120)
        joined = "; ".join(errors)

        self.assertIn("column date has 1 invalid values", joined)
        self.assertIn("date=05/20/2026", joined)

    def test_empty_input_is_error(self) -> None:
        config = load_config("example_config.json")
        empty = pd.DataFrame(columns=validate_ohlcv.REQUIRED_COLUMNS)
        with self.assertRaisesRegex(ValueError, "input data is empty"):
            scorer.score_candidates(empty, config)

    def test_missing_symbol_rows_are_dropped_not_stringified(self) -> None:
        frame = build_frame()
        frame.loc[0, "symbol"] = pd.NA

        prepared = prepare_frame(frame, validate_ohlcv.parse_dates)

        self.assertNotIn("nan", set(prepared["symbol"].astype(str).str.lower()))
        self.assertEqual(len(frame) - 1, len(prepared))

    def test_validate_cli_error_includes_input_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prices.txt"
            path.write_text("not csv", encoding="utf-8")
            code, _, stderr = run_validate_cli(path)
        self.assertEqual(2, code)
        self.assertIn("unsupported input format", stderr)
        self.assertIn("input=prices.txt", stderr)

    def test_validate_cli_discloses_unverified_volume_unit(self) -> None:
        frame = build_frame()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prices.csv"
            frame.to_csv(path, index=False)
            code, stdout, stderr = run_validate_cli(path)

        self.assertEqual(0, code, stderr)
        self.assertIn("volume_unit_verification=not_verified_by_cli", stdout)
        self.assertIn("volume_must_not_be_amount_or_mixed_units", stdout)

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

    def test_prediction_cleaning_does_not_backfill_initial_missing_values(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = pd.DataFrame(
            {
                "close": [float("nan"), 8.1, 8.2],
                "volume": [float("nan"), 120000, 121000],
                "turn": [float("nan"), 1.1, 1.2],
            }
        )

        cleaned = metrics.apply_cleaning(frame.copy(), config)

        self.assertTrue(pd.isna(cleaned.loc[0, "close"]))
        self.assertTrue(pd.isna(cleaned.loc[0, "volume"]))
        self.assertTrue(pd.isna(cleaned.loc[0, "turn"]))
        self.assertEqual(8.1, cleaned.loc[1, "close"])
        self.assertEqual(120000, cleaned.loc[1, "volume"])
        self.assertEqual(1.1, cleaned.loc[1, "turn"])

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
        frame["symbol"] = frame["symbol"].map({"000002": "900001", "600001": "810002"})
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual(2, summary["raw_symbols"])
        self.assertEqual(0, summary["input_symbols"])
        self.assertEqual(2, summary["universe_filtered_symbols"])
        self.assertEqual(0, summary["candidates"])
        self.assertEqual("universe_filtered_all", summary["empty_result_reason"])

    def test_universe_filtering_handles_numeric_symbol_dtype(self) -> None:
        frame = pd.DataFrame([{"symbol": 2}, {"symbol": 600001}])
        universe = {
            "universe": {
                "symbol_prefix_allow_regex": r"^(60|68|00|30)",
                "symbol_prefix_exclude": ["8", "4"],
            }
        }

        result, summary = apply_universe_filter(frame, universe)

        self.assertEqual(["600001"], result["symbol"].tolist())
        self.assertEqual(1, summary["prefix_allow_filtered_symbols"])
        self.assertEqual(0, summary["prefix_excluded_symbols"])

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

    def test_prediction_validation_reports_missing_turn_and_invalid_market_label_symbol(
        self,
    ) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True)
        frame = frame[frame["symbol"].eq("000002")].copy()
        frame["symbol"] = "AAPL"
        frame["market"] = "A-share"
        frame = frame.drop(columns=["turn"], errors="ignore")
        errors = validate_ohlcv.validate_profile_columns(frame, config)
        joined = "; ".join(errors)

        self.assertIn("requires turn or turnover column", joined)
        self.assertIn("symbols must be six digits", joined)
        self.assertIn("market labels do not prove A-share source or calendar", joined)

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

    def test_generic_ignores_prediction_columns(self) -> None:
        config = load_config("example_config.json")
        with_prediction = build_frame(include_prediction=True, prediction_value=-0.1)
        without_prediction = with_prediction.drop(columns=["prediction_score"])

        candidates_with, summary = scorer.score_candidates(with_prediction, config)
        candidates_without, _ = scorer.score_candidates(without_prediction, config)

        self.assertEqual("not_used", summary["prediction_source"])
        self.assertEqual("not_used", summary["prediction_input_source"])
        self.assertFalse(summary["prediction_model_executed_by_score_script"])
        self.assertTrue(summary["lightgbm_not_executed_by_this_script"])
        self.assertTrue(candidates_with["prediction_score"].isna().all())
        self.assertEqual({"not_used"}, set(candidates_with["prediction_source"]))
        self.assertEqual({"not_used"}, set(candidates_with["prediction_input_source"]))
        self.assertEqual(
            candidates_without["trend_score"].tolist(),
            candidates_with["trend_score"].tolist(),
        )

    def test_prediction_valid_prediction_marks_external_source(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        _, summary = scorer.score_candidates(frame, config)
        self.assertEqual("external_unverified", summary["prediction_source"])
        self.assertEqual("external_input", summary["prediction_input_source"])
        self.assertFalse(summary["prediction_model_executed_by_score_script"])
        self.assertTrue(summary["lightgbm_not_executed_by_this_script"])
        self.assertEqual(2, summary["scored_symbols"])

    def test_prediction_candidates_carry_disclosure_fields(self) -> None:
        config = load_config("prediction_profile_config.json")
        frame = build_frame(include_prediction=True, include_turn=True)
        candidates, _summary = scorer.score_candidates(frame, config)

        self.assertEqual({"external_unverified"}, set(candidates["prediction_source"]))
        self.assertEqual({"external_input"}, set(candidates["prediction_input_source"]))
        self.assertEqual(
            {False},
            set(candidates["prediction_model_executed_by_score_script"]),
        )
        self.assertEqual(
            {True},
            set(candidates["lightgbm_not_executed_by_this_script"]),
        )

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

    def test_score_outputs_listing_board_for_candidates_and_diagnostics(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
        extra = frame[frame["symbol"].eq("000002")].copy()
        extra["symbol"] = "300001"
        extra["name"] = "ChiNext"
        extra["close"] = extra["close"] + 0.2
        frame = pd.concat([frame, extra], ignore_index=True)
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
            candidates = pd.read_csv(output_path, dtype={"symbol": str})
            diagnostics = pd.read_csv(diagnostics_path, dtype={"symbol": str})

        self.assertEqual(0, code, stderr.getvalue())
        self.assertIn("listing_board", candidates.columns)
        self.assertIn("listing_board", diagnostics.columns)
        self.assertEqual(
            {"000002": "主板", "300001": "创业板", "600001": "主板"},
            dict(zip(candidates["symbol"], candidates["listing_board"])),
        )
        self.assertEqual(
            {"000002": "主板", "300001": "创业板", "600001": "主板"},
            dict(zip(diagnostics["symbol"], diagnostics["listing_board"])),
        )

    def test_hong_kong_generic_config_scores_hk_symbols_and_boards(self) -> None:
        config = load_config("hong_kong_generic_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
        frame["symbol"] = frame["symbol"].map({"000002": "00700", "600001": "08001"})
        frame["name"] = frame["symbol"].map({"00700": "Tencent", "08001": "Gem Co"})
        frame["market"] = "HK"

        candidates, summary = scorer.score_candidates(frame, config)

        self.assertEqual(2, summary["input_symbols"])
        self.assertEqual(0, summary["market_filtered_symbols"])
        self.assertEqual(
            {"00700": "港股主板", "08001": "港股 GEM"},
            dict(zip(candidates["symbol"], candidates["listing_board"])),
        )

    def test_hong_kong_spot_aliases_match_plain_hk_symbols(self) -> None:
        config = load_config("hong_kong_generic_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
        frame["symbol"] = frame["symbol"].map({"000002": "00700", "600001": "08001"})
        frame["name"] = frame["symbol"].map({"00700": "Tencent", "08001": "Gem Co"})
        frame["market"] = "HK"
        spot = pd.DataFrame(
            [
                {"symbol": "HK.00700", "industry": "互联网服务"},
                {"symbol": "08001.HK", "industry": "软件服务"},
            ]
        )

        candidates, summary = scorer.score_candidates(frame, config, spot)
        by_symbol = {
            row["symbol"]: row["spot_industry"] for _, row in candidates.iterrows()
        }

        self.assertEqual(2, summary["spot_matched_symbols"])
        self.assertEqual("互联网服务", by_symbol["00700"])
        self.assertEqual("软件服务", by_symbol["08001"])

    def test_hong_kong_spot_aliases_match_yfinance_hk_symbols(self) -> None:
        config = load_config("hong_kong_generic_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
        frame["symbol"] = frame["symbol"].map(
            {"000002": "0700.HK", "600001": "08001.HK"}
        )
        frame["name"] = frame["symbol"].map(
            {"0700.HK": "Tencent", "08001.HK": "Gem Co"}
        )
        frame["market"] = "HK"
        spot = pd.DataFrame(
            [
                {"symbol": "HK.00700", "industry": "互联网服务"},
                {"symbol": "08001.HK", "industry": "软件服务"},
            ]
        )

        candidates, summary = scorer.score_candidates(frame, config, spot)
        by_symbol = {
            row["symbol"]: row["spot_industry"] for _, row in candidates.iterrows()
        }

        self.assertEqual(2, summary["spot_matched_symbols"])
        self.assertEqual("互联网服务", by_symbol["0700.HK"])
        self.assertEqual("软件服务", by_symbol["08001.HK"])

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

    def test_cli_discloses_unverified_volume_unit_in_outputs(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
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
            candidates = pd.read_csv(output_path, dtype={"symbol": str})
            diagnostics = pd.read_csv(diagnostics_path, dtype={"symbol": str})

        self.assertEqual(0, code, stderr.getvalue())
        self.assertIn("volume_unit_verification=not_verified_by_cli", stdout.getvalue())
        self.assertIn(
            "volume_must_not_be_amount_or_mixed_units",
            stdout.getvalue(),
        )
        self.assertEqual(
            {"not_verified_by_cli"},
            set(candidates["volume_unit_verification"]),
        )
        self.assertEqual(
            {"not_verified_by_cli"},
            set(diagnostics["volume_unit_verification"]),
        )

    def test_cli_preserves_direct_input_provenance_in_outputs(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
        frame["source_type"] = "synthetic_gate_only"
        frame["source_scope"] = "unit_test_direct_score"
        frame["real_market_data"] = False
        frame["metadata_source"] = "synthetic_gate_metadata"
        frame["source_claim_boundary"] = "synthetic_gate_only_not_real_market"
        frame["data_source_note"] = "not_real_market_data"
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
            candidates = pd.read_csv(output_path, dtype={"symbol": str})
            diagnostics = pd.read_csv(diagnostics_path, dtype={"symbol": str})

        self.assertEqual(0, code, stderr.getvalue())
        self.assertIn("source_type=synthetic_gate_only", stdout.getvalue())
        self.assertIn("real_market_data=false", stdout.getvalue())
        self.assertIn(
            "source_claim_boundary=synthetic_gate_only_not_real_market",
            stdout.getvalue(),
        )
        for output in (candidates, diagnostics):
            self.assertEqual({"synthetic_gate_only"}, set(output["source_type"]))
            self.assertEqual({"unit_test_direct_score"}, set(output["source_scope"]))
            self.assertEqual({False}, set(output["real_market_data"]))
            self.assertEqual(
                {"synthetic_gate_metadata"},
                set(output["metadata_source"]),
            )
            self.assertEqual(
                {"synthetic_gate_only_not_real_market"},
                set(output["source_claim_boundary"]),
            )
            self.assertEqual({"not_real_market_data"}, set(output["data_source_note"]))

    def test_cli_marks_partially_missing_real_provenance_as_mixed(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
        frame["source_type"] = "external_fetch"
        frame["source_scope"] = "zzshare_history_fetch"
        frame["real_market_data"] = pd.Series([True] * len(frame), dtype=object)
        frame["metadata_source"] = "manual_probe_real_claim"
        frame["source_claim_boundary"] = "zzshare_public_api_not_long_term_proven"
        frame["data_source_note"] = "subset claims real"
        frame.loc[frame.index[::2], "source_scope"] = ""
        frame.loc[frame.index[::2], "real_market_data"] = ""
        frame.loc[frame.index[::2], "metadata_source"] = ""
        frame.loc[frame.index[::2], "data_source_note"] = ""
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
            candidates = pd.read_csv(output_path, dtype={"symbol": str})
            diagnostics = pd.read_csv(diagnostics_path, dtype={"symbol": str})

        self.assertEqual(0, code, stderr.getvalue())
        self.assertIn("source_scope=mixed", stdout.getvalue())
        self.assertIn("real_market_data=mixed", stdout.getvalue())
        self.assertIn("metadata_source=mixed", stdout.getvalue())
        self.assertIn("data_source_note=mixed", stdout.getvalue())
        for output in (candidates, diagnostics):
            self.assertEqual({"mixed"}, set(output["source_scope"]))
            self.assertEqual({"mixed"}, set(output["real_market_data"]))
            self.assertEqual({"mixed"}, set(output["metadata_source"]))
            self.assertEqual({"mixed"}, set(output["data_source_note"]))

    def test_cli_preserves_as_of_metadata_in_candidates_and_diagnostics(self) -> None:
        frame = build_frame(include_turn=True)
        frame["requested_as_of_date"] = "2026-06-06"
        frame["actual_data_date"] = (
            pd.to_datetime(frame["date"]).max().date().isoformat()
        )
        frame["as_of_date_observed"] = False
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "candidates.csv"
            diagnostics_path = Path(tmpdir) / "diagnostics.csv"
            frame.to_csv(input_path, index=False)
            code, _stdout, stderr = run_score_cli(
                input_path,
                output_path,
                extra_args=["--diagnostics-output", str(diagnostics_path)],
            )
            candidates = pd.read_csv(output_path, dtype={"symbol": str})
            diagnostics = pd.read_csv(diagnostics_path, dtype={"symbol": str})

        self.assertEqual(0, code, stderr)
        self.assertEqual({"2026-06-06"}, set(candidates["requested_as_of_date"]))
        self.assertEqual({False}, set(candidates["as_of_date_observed"]))
        self.assertEqual({"2026-06-06"}, set(diagnostics["requested_as_of_date"]))
        self.assertEqual({False}, set(diagnostics["as_of_date_observed"]))

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

    def test_cli_normalizes_spot_symbol_aliases_before_merge(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
        spot = pd.DataFrame(
            [
                {"code": "sz.000002", "price": 8.88, "amount": 250000000},
                {"code": "600001.SH", "price": 9.99, "amount": 260000000},
                {"code": "bj.430047", "price": 7.77, "amount": 270000000},
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            spot_path = Path(tmpdir) / "spot.csv"
            config_path = Path(tmpdir) / "config.json"
            output_path = Path(tmpdir) / "candidates.csv"
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
                        "--spot-input",
                        str(spot_path),
                    ]
                )
            candidates = pd.read_csv(output_path)

        self.assertEqual(0, code, stderr.getvalue())
        self.assertIn("spot_matched_symbols=2", stdout.getvalue())
        selected = candidates[candidates["symbol"].astype(str).eq("2")].iloc[0]
        self.assertEqual(8.88, selected["spot_price"])
        view = normalized_spot_view(spot)
        self.assertEqual(["000002", "600001", "430047"], view["symbol"].tolist())

    def test_spot_merge_matches_numeric_scored_symbol_to_text_spot(self) -> None:
        config = load_config("example_config.json")
        config["thresholds"] = permissive_thresholds(120)
        frame = build_frame(include_turn=True)
        frame = frame[frame["symbol"].eq("600001")].copy()
        frame["symbol"] = 600001
        spot = pd.DataFrame([{"symbol": "600001", "spot_price": 8.88}])

        candidates, summary = scorer.score_candidates(frame, config, spot)

        self.assertEqual(1, summary["spot_matched_symbols"])
        selected = candidates[candidates["symbol"].astype(str).eq("600001")].iloc[0]
        self.assertEqual(8.88, selected["spot_price"])

    def test_spot_normalization_preserves_values_from_sliced_frame(self) -> None:
        spot = pd.DataFrame(
            [
                {"symbol": "skip", "spot_price": 1.0, "industry": "skip"},
                {"symbol": "000002", "spot_price": 8.88, "industry": "软件服务"},
                {"symbol": "600001", "spot_price": 9.99, "industry": "金融"},
            ]
        ).iloc[1:]

        view = normalized_spot_view(spot)

        selected = view[view["symbol"].eq("000002")].iloc[0]
        self.assertEqual(8.88, selected["spot_price"])
        self.assertEqual("软件服务", selected["spot_industry"])

    def test_ultra_short_profile_filters_prices_above_max_close(self) -> None:
        config = load_config("ultra_short_low_price_config.json")
        config["thresholds"] = permissive_thresholds(120) | {"max_close": 11.0}
        frame = build_frame(include_turn=True)

        candidates, summary = scorer.score_candidates(frame, config)

        self.assertEqual(2, summary["scored_symbols"])
        self.assertEqual(1, summary["threshold_failed_symbols"])
        self.assertEqual({"000002"}, set(candidates["symbol"]))
        self.assertEqual({"max_close": 1}, summary["threshold_failures"])

    def test_ultra_short_profile_requires_amount_turn_and_tradability_columns(
        self,
    ) -> None:
        config = load_config("ultra_short_low_price_config.json")
        frame = build_frame(include_turn=True, include_tradability=True).drop(
            columns=["amount", "turn", "tradestatus", "isST"]
        )

        with self.assertRaisesRegex(ValueError, "min_amount threshold requires amount"):
            scorer.score_candidates(frame, config)

    def test_ultra_short_profile_filters_liquidity_st_suspended_and_one_word_bar(
        self,
    ) -> None:
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
        frame = build_frame(
            include_prediction=True, prediction_value=0.1, include_turn=True
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "prices.csv"
            output_path = Path(tmpdir) / "prediction_low_pred.csv"
            diagnostics_path = Path(tmpdir) / "prediction_low_pred_diagnostics.csv"
            frame.to_csv(input_path, index=False)
            code, stdout, stderr = run_score_cli(
                input_path,
                output_path,
                config_name="prediction_profile_config.json",
                extra_args=["--diagnostics-output", str(diagnostics_path)],
            )
            self.assertEqual(0, code, stderr)
            self.assertTrue(output_path.exists())
            self.assertTrue(diagnostics_path.exists())
            self.assertIn("effective_empty_result=true", stdout)
            self.assertIn("empty_result_reason=threshold_filtered_all", stdout)
            self.assertIn("candidates=0", stdout)
            self.assertIn("prediction_source=external_unverified", stdout)
            self.assertIn("prediction_model_executed_by_score_script=false", stdout)
            diagnostics = pd.read_csv(diagnostics_path, dtype={"symbol": str})
            self.assertEqual({True}, set(diagnostics["effective_empty_result"]))
            self.assertEqual(
                {"threshold_filtered_all"},
                set(diagnostics["empty_result_reason"]),
            )


if __name__ == "__main__":
    unittest.main()
