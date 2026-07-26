from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.selection_core.a_share_selection_model_contracts import (  # noqa: E402
    EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
    LIMIT_RULES_MODEL_NOT_MODELED,
    PREDICTION_LABEL_DEFINITION,
    PREDICTION_LABEL_EXECUTION_MODEL,
    TRADABILITY_MODEL_ENTRY_EXIT,
    TRADABILITY_MODEL_HOLDING_PERIOD,
    TRADABILITY_MODEL_NONE,
    tradability_model,
)
from lib.selection_core.a_share_selection_sizing_contracts import (  # noqa: E402
    BACKTEST_CAPITAL_FIELDS,
    CAPITAL_FIELDS,
    SIZING_EXECUTION_MODEL,
    SIZING_FIELDS,
)


class AShareSelectionModelContractsTests(unittest.TestCase):
    def test_model_names_match_published_artifact_contract(self) -> None:
        self.assertEqual("not_modeled", TRADABILITY_MODEL_NONE)
        self.assertEqual("tradestatus_entry_exit_only", TRADABILITY_MODEL_ENTRY_EXIT)
        self.assertEqual(
            "tradestatus_holding_period_bars",
            TRADABILITY_MODEL_HOLDING_PERIOD,
        )
        self.assertEqual("not_modeled", LIMIT_RULES_MODEL_NOT_MODELED)
        self.assertEqual(
            "signal_close_next_observed_open_to_close",
            EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
        )
        self.assertEqual(
            EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
            PREDICTION_LABEL_EXECUTION_MODEL,
        )
        self.assertEqual(
            "target_return = close.shift(-horizon) / open.shift(-1) - 1; "
            "class = target_return > train_mean",
            PREDICTION_LABEL_DEFINITION,
        )

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

    def test_sizing_contract_is_pure_and_reexported_by_capital_helpers(self) -> None:
        from lib.selection_core import a_share_selection_capital as capital

        self.assertEqual(
            ["weight", "notional", "quantity", "cash_reserved"], CAPITAL_FIELDS
        )
        self.assertEqual(
            EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
            SIZING_EXECUTION_MODEL,
        )
        self.assertEqual(SIZING_FIELDS, BACKTEST_CAPITAL_FIELDS)
        self.assertIs(CAPITAL_FIELDS, capital.CAPITAL_FIELDS)
        self.assertIs(SIZING_FIELDS, capital.SIZING_FIELDS)

    def test_next_observed_open_entry_uses_row_position_not_index_label(self) -> None:
        from lib.selection_core.a_share_selection_capital import (
            next_observed_open_entry,
        )

        history = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
                "open": [10.0, 11.0, 12.0],
            },
            index=[100, 200, 300],
        )

        entry, reason = next_observed_open_entry(history, pd.Timestamp("2026-01-02"))

        self.assertEqual("", reason)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(0, entry.signal_position)
        self.assertEqual(1, entry.entry_position)
        self.assertEqual("2026-01-05", entry.entry_date)
        self.assertEqual(11.0, entry.entry_price)


if __name__ == "__main__":
    unittest.main()
