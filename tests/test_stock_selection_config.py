from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import score_candidates as scorer  # noqa: E402
import create_demo_data  # noqa: E402
import stock_selection_config  # noqa: E402
from helpers import build_frame, load_config  # noqa: E402


class StockSelectionConfigTests(unittest.TestCase):
    def test_config_validation_reports_missing_threshold_key(self) -> None:
        config = load_config("example_config.json")
        del config["thresholds"]["min_volume"]
        with self.assertRaisesRegex(ValueError, "thresholds missing keys: min_volume"):
            stock_selection_config.validate_config(config)

    def test_config_validation_reports_missing_trend_threshold_choice(self) -> None:
        config = load_config("example_config.json")
        del config["thresholds"]["min_trend_score"]
        with self.assertRaisesRegex(ValueError, "thresholds require one of"):
            stock_selection_config.validate_config(config)

    def test_config_validation_accepts_max_candidates_zero(self) -> None:
        config = load_config("example_config.json")
        config["output"]["max_candidates"] = 0
        candidates, summary = scorer.score_candidates(build_frame(), config)
        self.assertEqual(2, summary["candidates"])
        self.assertEqual(2, len(candidates))

    def test_ultra_short_low_price_config_validates(self) -> None:
        config = stock_selection_config.load_config(
            SCRIPTS / "ultra_short_low_price_config.json"
        )

        self.assertEqual("generic-technical", config["score_mode"])
        self.assertEqual(10.0, config["thresholds"]["max_close"])
        self.assertEqual(100000000.0, config["thresholds"]["min_amount"])
        self.assertEqual(1.0, config["thresholds"]["min_turn"])
        self.assertTrue(config["thresholds"]["exclude_st"])
        self.assertEqual("1", config["thresholds"]["require_tradestatus"])
        self.assertTrue(config["thresholds"]["exclude_one_word_bar"])
        self.assertTrue(config["disclosure"]["lightgbm_not_used"])

    def test_openai_agent_manifest_has_required_interface_fields(self) -> None:
        text = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Stock Selection Strategy"', text)
        self.assertIn("short_description:", text)
        self.assertIn("default_prompt:", text)

    def test_create_demo_data_generates_expected_files(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            code = create_demo_data.main(["--output", tmpdir, "--days", "160"])
            self.assertEqual(0, code)
            prices = Path(tmpdir) / "prices.csv"
            prediction = Path(tmpdir) / "prices_with_prediction.csv"
            self.assertTrue(prices.exists())
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

        self.assertEqual(7, prices["symbol"].nunique())
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
