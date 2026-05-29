"""Summary helpers for LightGBM prediction generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from stock_selection_data import parse_dates


def symbol_summary(
    group: pd.DataFrame,
    trainable: pd.DataFrame,
    train_size: int,
    probability: float,
    horizon: int,
) -> dict[str, Any]:
    return {
        **symbol_base_summary(group),
        "status": "predicted",
        "trainable_rows": int(len(trainable)),
        "train_rows": int(train_size),
        "prediction_score": float(probability),
        "prediction_horizon_days": int(horizon),
        "skipped_reason": "",
    }


def skipped_summary(group: pd.DataFrame, reason: str) -> dict[str, Any]:
    return {
        **symbol_base_summary(group),
        "status": "skipped",
        "trainable_rows": 0,
        "train_rows": 0,
        "prediction_score": None,
        "prediction_horizon_days": None,
        "skipped_reason": reason,
    }


def symbol_base_summary(group: pd.DataFrame) -> dict[str, Any]:
    dates = parse_dates(group["date"])
    return {
        "symbol": str(group["symbol"].iloc[0]),
        "date_min": dates.min().date().isoformat(),
        "date_max": dates.max().date().isoformat(),
        "input_rows": int(len(group)),
    }


def build_summary(
    prepared: pd.DataFrame,
    result: pd.DataFrame,
    skipped: list[str],
    horizon: int,
    train_ratio: float,
    symbol_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "raw_symbols": int(prepared["symbol"].nunique()),
        "predicted_symbols": int(result["symbol"].nunique()),
        "skipped_symbols": len(skipped),
        "skipped_symbol_examples": skipped[:10],
        "horizon": horizon,
        "train_ratio": train_ratio,
        "symbols": symbol_summaries,
    }


def write_json_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
