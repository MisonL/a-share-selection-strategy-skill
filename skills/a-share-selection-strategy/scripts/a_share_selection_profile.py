"""Profile-specific validation helpers for A-share selection inputs."""

from __future__ import annotations

from typing import Any

import pandas as pd

from a_share_selection_metrics import is_prediction_mode


def profile_column_errors(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    errors = threshold_column_errors(frame, config)
    errors.extend(market_column_errors(frame, config))
    if not is_prediction_mode(config):
        return errors
    if not any(column in frame.columns for column in ["prediction", "prediction_score"]):
        errors.append(
            "prediction-derived profile requires prediction or prediction_score column; "
            "provide an external prediction input instead of substituting technical "
            "indicators or fixed values"
        )
    if not any(column in frame.columns for column in ["turn", "turnover"]):
        errors.append("prediction-derived profile requires turn or turnover column")
    return errors


def market_column_errors(frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    market = config.get("universe", {}).get("market")
    if not market or "market" in frame.columns:
        return []
    if is_prediction_mode(config):
        return ["prediction-derived profile requires market column"]
    return [f"{market} profile requires market column"]


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
    prediction_mode = is_prediction_mode(config)
    errors = []
    market = str(config.get("universe", {}).get("market", ""))
    errors.extend(profile_market_errors(frame, market, prediction_mode=prediction_mode))
    market_frame = prediction_market_frame(frame, market)
    if not market_frame.empty:
        invalid_symbols = ~market_frame["symbol"].astype(str).str.fullmatch(r"\d{6}")
        invalid_count = int(invalid_symbols.sum())
        if invalid_count:
            errors.append(symbol_error_message(market, invalid_count, prediction_mode))
    if not prediction_mode:
        return errors
    prediction_frame = market_frame if not market_frame.empty else frame
    prediction_error = prediction_value_error(prediction_frame)
    if prediction_error:
        errors.append(prediction_error)
    return errors


def profile_market_errors(
    frame: pd.DataFrame,
    market: str,
    *,
    prediction_mode: bool,
) -> list[str]:
    if not market or "market" not in frame.columns:
        return []
    values = frame["market"].astype(str)
    symbols = frame["symbol"].astype(str)
    a_share_like = symbols.str.fullmatch(r"\d{6}|\d{6}\.(SZ|SH|SS|BJ)")
    invalid = (values != market) & a_share_like
    errors = []
    if invalid.any():
        errors.append(market_value_message(market, values[invalid], prediction_mode))
    if (values == market).sum() == 0:
        prefix = "prediction-derived profile" if prediction_mode else f"{market} profile"
        errors.append(f"{prefix} requires at least one {market} row")
    return errors


def market_value_message(
    market: str,
    values: pd.Series,
    prediction_mode: bool,
) -> str:
    prefix = "prediction-derived A-share rows" if prediction_mode else f"{market} rows"
    return (
        f"{prefix} must use market={market}; "
        f"invalid_market_values={format_value_counts(values)}"
    )


def symbol_error_message(
    market: str,
    invalid_count: int,
    prediction_mode: bool,
) -> str:
    if prediction_mode:
        return (
            "prediction-derived A-share symbols must be six digits; "
            f"invalid_symbols={invalid_count}; market labels do not prove "
            "A-share source or calendar"
        )
    return f"{market} symbols must be six digits; invalid_symbols={invalid_count}"


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
    conflict = prediction_column_conflict_error(frame)
    if conflict:
        return conflict
    return ""


def prediction_column_conflict_error(frame: pd.DataFrame) -> str:
    if not {"prediction", "prediction_score"}.issubset(frame.columns):
        return ""
    prediction = pd.to_numeric(frame["prediction"], errors="coerce")
    prediction_score = pd.to_numeric(frame["prediction_score"], errors="coerce")
    mismatch = (prediction - prediction_score).abs() > 1e-12
    mismatch_count = int(mismatch.sum())
    if not mismatch_count:
        return ""
    return (
        "prediction and prediction_score both exist but differ; "
        f"conflicting_rows={mismatch_count}; unify upstream prediction columns before "
        "prediction-derived scoring"
    )


def format_value_counts(values: pd.Series) -> str:
    counts = values.value_counts(dropna=False).head(10)
    return ",".join(f"{value}:{count}" for value, count in counts.items())
