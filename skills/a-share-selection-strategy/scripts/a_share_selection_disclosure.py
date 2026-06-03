"""Disclosure helpers for A-share selection prediction fields."""

from __future__ import annotations

from typing import Any


def prediction_disclosure(config: dict[str, Any]) -> dict[str, Any]:
    prediction_mode = str(config.get("score_mode", "")).lower() == "prediction-derived"
    return {
        "prediction_source": "external_unverified" if prediction_mode else "not_used",
        "prediction_input_source": "external_input" if prediction_mode else "not_used",
        "prediction_model_executed_by_score_script": False,
        "lightgbm_not_executed_by_this_script": True,
    }


def add_prediction_disclosure_fields(frame: Any, config: dict[str, Any]) -> Any:
    result = frame.copy()
    for column, value in prediction_disclosure(config).items():
        result[column] = value
    return result
