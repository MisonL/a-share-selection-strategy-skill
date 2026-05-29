from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import score_candidates as scorer  # noqa: E402
import stock_selection_config  # noqa: E402
from test_stock_selection_scripts import build_frame  # noqa: E402


def load_config(name: str) -> dict:
    return json.loads((SCRIPTS / name).read_text(encoding="utf-8"))


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


if __name__ == "__main__":
    unittest.main()
