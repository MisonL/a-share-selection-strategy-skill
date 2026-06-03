"""Shared model-name contracts for A-share selection artifacts."""

from __future__ import annotations


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
