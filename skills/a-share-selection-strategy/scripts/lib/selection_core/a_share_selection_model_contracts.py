"""Shared model-name contracts for A-share selection artifacts."""

from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _SCRIPT_PATH = Path(__file__).resolve()
    _SCRIPTS_DIR = next(
        parent for parent in _SCRIPT_PATH.parents if parent.name == "scripts"
    )
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from lib.a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)


TRADABILITY_MODEL_NONE = "not_modeled"
TRADABILITY_MODEL_ENTRY_EXIT = "tradestatus_entry_exit_only"
TRADABILITY_MODEL_HOLDING_PERIOD = "tradestatus_holding_period_bars"
LIMIT_RULES_MODEL_NOT_MODELED = "not_modeled"


def tradability_model(
    require_entry_exit_tradable: bool,
    *,
    require_holding_period_tradable: bool = False,
) -> str:
    if require_holding_period_tradable:
        return TRADABILITY_MODEL_HOLDING_PERIOD
    if require_entry_exit_tradable:
        return TRADABILITY_MODEL_ENTRY_EXIT
    return TRADABILITY_MODEL_NONE
