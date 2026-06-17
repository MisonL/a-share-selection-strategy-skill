from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import score_candidates as scorer  # noqa: E402
import create_demo_data  # noqa: E402
import a_share_selection_config  # noqa: E402
from helpers import build_frame, load_config  # noqa: E402


class AShareSelectionConfigTests(unittest.TestCase):
    def test_config_validation_reports_missing_threshold_key(self) -> None:
        config = load_config("example_config.json")
        del config["thresholds"]["min_volume"]
        with self.assertRaisesRegex(ValueError, "thresholds missing keys: min_volume"):
            a_share_selection_config.validate_config(config)

    def test_config_validation_reports_missing_trend_threshold_choice(self) -> None:
        config = load_config("example_config.json")
        del config["thresholds"]["min_trend_score"]
        with self.assertRaisesRegex(ValueError, "thresholds require one of"):
            a_share_selection_config.validate_config(config)

    def test_generic_config_rejects_prediction_weight_or_threshold(self) -> None:
        config = load_config("example_config.json")
        config["weights"]["prediction_score"] = config["weights"].pop("trend_score")
        with self.assertRaisesRegex(ValueError, "generic weights must not include"):
            a_share_selection_config.validate_config(config)

        config = load_config("example_config.json")
        config["thresholds"]["min_prediction_score"] = config["thresholds"].pop(
            "min_trend_score"
        )
        with self.assertRaisesRegex(ValueError, "generic thresholds must not include"):
            a_share_selection_config.validate_config(config)

    def test_prediction_config_rejects_trend_weight_or_threshold(self) -> None:
        config = load_config("prediction_profile_config.json")
        config["weights"]["trend_score"] = config["weights"].pop("prediction_score")
        with self.assertRaisesRegex(
            ValueError,
            "prediction-derived weights must not include",
        ):
            a_share_selection_config.validate_config(config)

        config = load_config("prediction_profile_config.json")
        config["thresholds"]["min_trend_score"] = config["thresholds"].pop(
            "min_prediction_score"
        )
        with self.assertRaisesRegex(
            ValueError,
            "prediction-derived thresholds must not include",
        ):
            a_share_selection_config.validate_config(config)

    def test_config_validation_accepts_max_candidates_zero(self) -> None:
        config = load_config("example_config.json")
        config["output"]["max_candidates"] = 0
        candidates, summary = scorer.score_candidates(build_frame(), config)
        self.assertEqual(2, summary["candidates"])
        self.assertEqual(2, len(candidates))

    def test_ultra_short_low_price_config_validates(self) -> None:
        config = a_share_selection_config.load_config(
            SCRIPTS / "ultra_short_low_price_config.json"
        )

        self.assertEqual("generic-technical", config["score_mode"])
        self.assertEqual(10.0, config["thresholds"]["max_close"])
        self.assertEqual(100000000.0, config["thresholds"]["min_amount"])
        self.assertEqual(1.0, config["thresholds"]["min_turn"])
        self.assertTrue(config["thresholds"]["exclude_st"])
        self.assertEqual("1", config["thresholds"]["require_tradestatus"])
        self.assertTrue(config["thresholds"]["exclude_one_word_bar"])
        self.assertEqual("not_used", config["disclosure"]["prediction_input_source"])
        self.assertFalse(config["disclosure"]["prediction_model_executed_by_runner"])
        self.assertFalse(config["disclosure"]["prediction_model_executed_by_score_script"])
        self.assertTrue(config["disclosure"]["lightgbm_not_used"])

    def test_core_configs_carry_disclosure_boundaries(self) -> None:
        expected = {
            "example_config.json": {
                "prediction_policy": "not_used",
                "prediction_mode": False,
                "prediction_input_source": "not_used",
                "prediction_model_executed_by_runner": False,
                "prediction_model_executed_by_score_script": False,
                "lightgbm_not_used": True,
            },
            "prediction_profile_config.json": {
                "prediction_policy": "external_required",
                "prediction_mode": True,
                "prediction_input_source": "external_required",
                "prediction_model_executed_by_runner": False,
                "prediction_model_executed_by_score_script": False,
                "lightgbm_not_used": False,
            },
            "ultra_short_low_price_config.json": {
                "prediction_policy": "not_used",
                "prediction_mode": False,
                "prediction_input_source": "not_used",
                "prediction_model_executed_by_runner": False,
                "prediction_model_executed_by_score_script": False,
                "lightgbm_not_used": True,
            },
            "hong_kong_generic_config.json": {
                "prediction_policy": "not_used",
                "prediction_mode": False,
                "prediction_input_source": "not_used",
                "prediction_model_executed_by_runner": False,
                "prediction_model_executed_by_score_script": False,
                "lightgbm_not_used": True,
            },
        }
        for name, fields in expected.items():
            with self.subTest(name=name):
                config = a_share_selection_config.load_config(SCRIPTS / name)
                disclosure = config["disclosure"]
                for key, value in fields.items():
                    self.assertEqual(value, disclosure[key])
                self.assertIn("risk_note", disclosure)

    def test_openai_agent_manifest_has_required_interface_fields(self) -> None:
        text = (SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "A-Share Selection Strategy"', text)
        self.assertIn("short_description:", text)
        self.assertIn("default_prompt:", text)

    def test_evals_cover_partial_and_history_selection_disclosures(self) -> None:
        data = json.loads((SKILL_ROOT / "evals/evals.json").read_text(encoding="utf-8"))
        text = json.dumps(data, ensure_ascii=False)

        self.assertIn("coverage_claim=partial_not_full_market", text)
        self.assertIn("selected_symbols.json", text)
        self.assertIn("history_symbol_count", text)
        self.assertIn("synthetic_demo", text)

    def test_evals_cover_hidden_boundary_with_existing_candidates(self) -> None:
        data = json.loads((SKILL_ROOT / "evals/evals.json").read_text(encoding="utf-8"))
        text = json.dumps(data, ensure_ascii=False)

        self.assertIn("直接告诉我今天买哪只、卖哪只", text)
        self.assertIn("advice_boundary", text)
        self.assertIn("recommendation_boundary", text)
        self.assertIn("非投资建议", text)
        self.assertIn("非交易指令", text)
        self.assertIn("非真实成交", text)
        self.assertIn("非收益证明", text)

    def test_create_demo_data_generates_expected_files(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            code = create_demo_data.main(["--output", tmpdir, "--days", "160"])
            self.assertEqual(0, code)
            prices = Path(tmpdir) / "prices.csv"
            spot = Path(tmpdir) / "spot.csv"
            prediction = Path(tmpdir) / "prices_with_prediction.csv"
            self.assertTrue(prices.exists())
            self.assertTrue(spot.exists())
            self.assertTrue(prediction.exists())
            self.assertEqual(321, len(prices.read_text(encoding="utf-8").splitlines()))
            self.assertIn("prediction_score", prediction.read_text(encoding="utf-8").splitlines()[0])

    def test_create_demo_data_low_price_scenario_generates_gate_examples(self) -> None:
        import tempfile

        import pandas as pd

        with tempfile.TemporaryDirectory() as tmpdir:
            code = create_demo_data.main(
                [
                    "--output",
                    tmpdir,
                    "--days",
                    "160",
                    "--scenario",
                    "low-price-ultra-short",
                ]
            )
            self.assertEqual(0, code)
            prices = pd.read_csv(Path(tmpdir) / "prices.csv", dtype={"symbol": str})
            spot = pd.read_csv(Path(tmpdir) / "spot.csv", dtype={"symbol": str})

        self.assertEqual(7, prices["symbol"].nunique())
        self.assertEqual(7, spot["symbol"].nunique())
        self.assertIn("industry", spot.columns)
        self.assertEqual("软件服务", spot[spot["symbol"].eq("000002")]["industry"].iloc[0])
        latest = prices.sort_values(["symbol", "date"]).groupby("symbol").tail(1)
        self.assertIn("000003", set(latest[latest["close"] > 10.0]["symbol"]))
        self.assertIn("000004", set(latest[latest["amount"] < 100000000.0]["symbol"]))
        self.assertIn("000005", set(latest[latest["turn"] < 1.0]["symbol"]))
        self.assertEqual("1", str(latest[latest["symbol"].eq("000006")]["isST"].iloc[0]))
        self.assertEqual(
            "0",
            str(latest[latest["symbol"].eq("000007")]["tradestatus"].iloc[0]),
        )


if __name__ == "__main__":
    unittest.main()
