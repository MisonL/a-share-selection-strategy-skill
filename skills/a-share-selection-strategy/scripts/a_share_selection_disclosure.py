"""Disclosure helpers for A-share selection prediction fields."""

from __future__ import annotations

from typing import Any


ADVICE_BOUNDARY = "not_investment_advice_not_trade_instruction_not_real_fill_not_return_proof"
RECOMMENDATION_BOUNDARY = "ranking_signal_not_buy_sell_instruction"
VOLUME_UNIT_VERIFICATION = "not_verified_by_cli"


def prediction_disclosure(config: dict[str, Any]) -> dict[str, Any]:
    prediction_mode = str(config.get("score_mode", "")).lower() == "prediction-derived"
    return {
        "prediction_source": "external_unverified" if prediction_mode else "not_used",
        "prediction_input_source": "external_input" if prediction_mode else "not_used",
        "prediction_model_executed_by_score_script": False,
        "lightgbm_not_executed_by_this_script": True,
        "volume_unit_verification": VOLUME_UNIT_VERIFICATION,
        "advice_boundary": ADVICE_BOUNDARY,
        "recommendation_boundary": RECOMMENDATION_BOUNDARY,
    }


def add_prediction_disclosure_fields(frame: Any, config: dict[str, Any]) -> Any:
    result = frame.copy()
    for column, value in prediction_disclosure(config).items():
        result[column] = value
    return result

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
