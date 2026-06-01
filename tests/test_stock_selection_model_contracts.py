from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from stock_selection_model_contracts import (  # noqa: E402
    LIMIT_RULES_MODEL_NOT_MODELED,
    TRADABILITY_MODEL_ENTRY_EXIT,
    TRADABILITY_MODEL_HOLDING_PERIOD,
    TRADABILITY_MODEL_NONE,
    tradability_model,
)


class StockSelectionModelContractsTests(unittest.TestCase):
    def test_model_names_match_published_artifact_contract(self) -> None:
        self.assertEqual("not_modeled", TRADABILITY_MODEL_NONE)
        self.assertEqual("tradestatus_entry_exit_only", TRADABILITY_MODEL_ENTRY_EXIT)
        self.assertEqual(
            "tradestatus_holding_period_bars",
            TRADABILITY_MODEL_HOLDING_PERIOD,
        )
        self.assertEqual("not_modeled", LIMIT_RULES_MODEL_NOT_MODELED)

    def test_tradability_model_prefers_holding_period_gate(self) -> None:
        self.assertEqual(TRADABILITY_MODEL_NONE, tradability_model(False))
        self.assertEqual(TRADABILITY_MODEL_ENTRY_EXIT, tradability_model(True))
        self.assertEqual(
            TRADABILITY_MODEL_HOLDING_PERIOD,
            tradability_model(False, require_holding_period_tradable=True),
        )
        self.assertEqual(
            TRADABILITY_MODEL_HOLDING_PERIOD,
            tradability_model(True, require_holding_period_tradable=True),
        )


if __name__ == "__main__":
    unittest.main()
