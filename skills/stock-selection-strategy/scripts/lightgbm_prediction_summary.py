"""Summary helpers for LightGBM prediction generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from stock_selection_data import parse_dates

MODEL_QUALITY_SCOPE = "generation_audit_only"
MODEL_QUALITY_METRICS = {
    "holdout_auc": "not_computed",
    "holdout_ic": "not_computed",
    "probability_calibration": "not_evaluated",
    "return_bucket_analysis": "not_computed",
    "cross_window_stability": "not_evaluated",
    "cross_year_generalization": "not_evaluated",
    "cross_market_generalization": "not_evaluated",
    "full_market_generalization": "not_proven",
}


def symbol_summary(
    group: pd.DataFrame,
    trainable: pd.DataFrame,
    train: pd.DataFrame,
    latest: pd.DataFrame,
    holdout: dict[str, Any],
    probability: float,
    horizon: int,
    target_threshold: float,
    positive_labels: int,
    negative_labels: int,
) -> dict[str, Any]:
    train_dates = parse_dates(group.loc[train.index, "date"])
    latest_dates = parse_dates(group.loc[latest.index, "date"])
    return {
        **symbol_base_summary(group),
        "status": "predicted",
        "trainable_rows": int(len(trainable)),
        "train_rows": int(len(train)),
        "train_date_min": train_dates.min().date().isoformat(),
        "train_date_max": train_dates.max().date().isoformat(),
        "latest_feature_date": latest_dates.iloc[0].date().isoformat(),
        "target_threshold": float(target_threshold),
        "target_positive_labels": int(positive_labels),
        "target_negative_labels": int(negative_labels),
        **holdout,
        "prediction_score": float(probability),
        "prediction_horizon_days": int(horizon),
        "label_definition": "target_return = close.shift(-horizon) / close - 1; class = target_return > train_mean",
        "skipped_reason": "",
    }


def skipped_summary(group: pd.DataFrame, reason: str) -> dict[str, Any]:
    return {
        **symbol_base_summary(group),
        "status": "skipped",
        "trainable_rows": 0,
        "train_rows": 0,
        "holdout_rows": 0,
        "holdout_date_min": "",
        "holdout_date_max": "",
        "holdout_positive_labels": 0,
        "holdout_negative_labels": 0,
        "holdout_auc": None,
        "holdout_metric_status": "not_computable",
        "holdout_metric_reason": "symbol_skipped",
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
    feature_columns: list[str],
) -> dict[str, Any]:
    return {
        "raw_symbols": int(prepared["symbol"].nunique()),
        "predicted_symbols": int(result["symbol"].nunique()),
        "skipped_symbols": len(skipped),
        "skipped_symbol_examples": skipped[:10],
        "horizon": horizon,
        "train_ratio": train_ratio,
        "feature_columns": list(feature_columns),
        "split_method": "time_series_train_prefix",
        "scaler_fit_scope": "train_split_only",
        "prediction_scope": "latest_probability_repeated_for_scoring",
        "model_quality_scope": MODEL_QUALITY_SCOPE,
        "model_quality_metrics": dict(MODEL_QUALITY_METRICS),
        "label_definition": "target_return = close.shift(-horizon) / close - 1; class = target_return > train_mean",
        "symbols": symbol_summaries,
    }


def write_json_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
