"""Output helpers for stock selection candidate scoring."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def latest_turnover_value(latest: pd.Series) -> float:
    for column in ["turn", "turnover"]:
        if column in latest:
            return float(latest[column])
    return math.nan


def recommendation_for(total_score: float, config: dict[str, Any]) -> str:
    views = config.get("derived_views", {})
    high_min = float(views.get("high_signal_min", views.get("recommendation_buy_min", 0.8)))
    medium_min = float(
        views.get("medium_signal_min", views.get("recommendation_hold_min", 0.6))
    )
    if total_score >= high_min:
        return "high_signal"
    if total_score >= medium_min:
        return "medium_signal"
    return "low_signal"


def build_reasons(metrics: dict[str, float]) -> str:
    reasons: list[str] = []
    prediction = metrics.get("prediction_score", math.nan)
    if not math.isnan(prediction) and prediction >= 0.6:
        reasons.append("prediction above threshold")
    if metrics["momentum_score"] > 0:
        reasons.append("positive momentum")
    if metrics["explosion_score"] >= 1.0:
        reasons.append("short-term activity")
    if metrics["risk_score"] >= 0.5:
        reasons.append("acceptable volatility")
    if 30 <= metrics["rsi"] <= 75:
        reasons.append("rsi in range")
    return "; ".join(reasons) if reasons else "passed configured filters"


def build_risk_notes(metrics: dict[str, float], volume: float) -> str:
    notes: list[str] = []
    if metrics["volatility"] > 0.5:
        notes.append("high volatility")
    if metrics["rsi"] > 70:
        notes.append("rsi near overheated")
    if volume <= 0:
        notes.append("missing tradable volume")
    return "; ".join(notes) if notes else "no major configured risk flag"
