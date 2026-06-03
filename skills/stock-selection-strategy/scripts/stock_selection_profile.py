"""Profile-specific validation helpers for stock selection inputs."""

from __future__ import annotations

from typing import Any

import pandas as pd

from stock_selection_metrics import is_prediction_mode


def profile_column_errors(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    errors = threshold_column_errors(frame, config)
    if not is_prediction_mode(config):
        return errors
    if config.get("universe", {}).get("market") and "market" not in frame.columns:
        errors.append("prediction-derived profile requires market column")
    if not any(column in frame.columns for column in ["prediction", "prediction_score"]):
        errors.append("prediction-derived profile requires prediction or prediction_score column")
    if not any(column in frame.columns for column in ["turn", "turnover"]):
        errors.append("prediction-derived profile requires turn or turnover column")
    return errors


def threshold_column_errors(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    thresholds = config.get("thresholds", {})
    errors = []
    if "min_amount" in thresholds and "amount" not in frame.columns:
        errors.append("configured min_amount threshold requires amount column")
    if "min_turn" in thresholds and not any(
        column in frame.columns for column in ["turn", "turnover"]
    ):
        errors.append("configured min_turn threshold requires turn or turnover column")
    if thresholds.get("exclude_st") and "isST" not in frame.columns:
        errors.append("configured exclude_st threshold requires isST column")
    if thresholds.get("require_tradestatus") and "tradestatus" not in frame.columns:
        errors.append("configured require_tradestatus threshold requires tradestatus column")
    if thresholds.get("exclude_one_word_bar"):
        required = ["open", "high", "low", "close"]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            errors.append(
                "configured exclude_one_word_bar threshold requires OHLC columns: "
                + ",".join(missing)
            )
    return errors


def prediction_value_errors(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    if not is_prediction_mode(config):
        return []
    errors = []
    market = str(config.get("universe", {}).get("market", ""))
    errors.extend(prediction_market_errors(frame, market))
    market_frame = prediction_market_frame(frame, market)
    if not market_frame.empty:
        invalid_symbols = ~market_frame["symbol"].astype(str).str.fullmatch(r"\d{6}")
        invalid_count = int(invalid_symbols.sum())
        if invalid_count:
            errors.append(
                "prediction-derived A-share symbols must be six digits; "
                f"invalid_symbols={invalid_count}"
            )
    prediction_frame = market_frame if not market_frame.empty else frame
    prediction_error = prediction_value_error(prediction_frame)
    if prediction_error:
        errors.append(prediction_error)
    return errors


def prediction_market_errors(frame: pd.DataFrame, market: str) -> list[str]:
    if not market or "market" not in frame.columns:
        return []
    values = frame["market"].astype(str)
    symbols = frame["symbol"].astype(str)
    a_share_like = symbols.str.fullmatch(r"\d{6}|\d{6}\.(SZ|SH|SS|BJ)")
    invalid = (values != market) & a_share_like
    errors = []
    if invalid.any():
        errors.append(
            f"prediction-derived A-share rows must use market={market}; "
            f"invalid_market_values={format_value_counts(values[invalid])}"
        )
    if (values == market).sum() == 0:
        errors.append(f"prediction-derived profile requires at least one {market} row")
    return errors


def prediction_market_frame(frame: pd.DataFrame, market: str) -> pd.DataFrame:
    if not market or "market" not in frame.columns:
        return frame.iloc[0:0]
    return frame[frame["market"].astype(str) == market]


def prediction_value_error(frame: pd.DataFrame) -> str:
    for column in ["prediction", "prediction_score"]:
        if column not in frame.columns:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        invalid_count = int(values.isna().sum() + ((values < 0) | (values > 1)).sum())
        if invalid_count:
            return (
                f"{column} has {invalid_count} invalid values; "
                "prediction values must be numbers between 0 and 1"
            )
    return ""


def format_value_counts(values: pd.Series) -> str:
    counts = values.value_counts(dropna=False).head(10)
    return ",".join(f"{value}:{count}" for value, count in counts.items())
