"""Metric helpers for A-share selection candidate scoring."""

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


import math
from typing import Any

import numpy as np
import pandas as pd

from lib.selection_core.a_share_selection_output import (
    build_reasons,
    build_risk_notes,
    latest_turnover_value,
    recommendation_for,
)


ONE_YEAR_TRADING_DAYS = 252


def score_symbol(group: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    cleaning = config.get("cleaning", {})
    data = apply_cleaning(group.copy(), config) if cleaning else group
    close = data["close"].astype(float)
    volume = data["volume"].astype(float)
    metrics = compute_metrics(data, close, volume, config)
    latest = group.iloc[-1]
    cleaned_latest = data.iloc[-1]
    ma15 = calculate_ma(close, 15)
    explosion_line = config.get("derived_views", {}).get("explosion_score_min", 1.5)
    ma15_line = config.get("derived_views", {}).get("low_ma15_max", 15.0)
    low_ma15 = bool(ma15 <= float(ma15_line))
    explosion_focus = bool(metrics["explosion_score"] > float(explosion_line))
    signal_tier = recommendation_for(metrics["total_score"], config)
    return {
        "symbol": str(latest["symbol"]),
        "name": display_name(latest, str(latest["symbol"])),
        "market": str(latest.get("market", "")),
        "date": iso_date(latest["date"]),
        "close": float(latest["close"]),
        "one_year_pct_chg": one_year_pct_change(close),
        "volume": float(latest["volume"]),
        "turn": latest_turnover_value(latest),
        "requested_as_of_date": latest.get("requested_as_of_date", ""),
        "actual_data_date": latest.get("actual_data_date", ""),
        "as_of_date_observed": latest.get("as_of_date_observed", ""),
        "rsi": metrics["rsi"],
        "volatility": metrics["volatility"],
        "macd": metrics["macd"],
        "macd_status": metrics["macd_status"],
        "momentum_score": metrics["momentum_score"],
        "trend_score": metrics["trend_score"],
        "prediction_score": metrics["prediction_score"],
        "prediction_model": latest.get("prediction_model", ""),
        "prediction_horizon_days": latest.get("prediction_horizon_days", ""),
        "prediction_scope": latest.get("prediction_scope", ""),
        "prediction_model_quality_scope": latest.get(
            "prediction_model_quality_scope", ""
        ),
        "explosion_score": metrics["explosion_score"],
        "risk_score": metrics["risk_score"],
        "total_score": metrics["total_score"],
        "ma15": ma15,
        "low_ma15_flag": low_ma15,
        "explosion_focus_flag": explosion_focus,
        "low_price_explosion_flag": bool(low_ma15 and explosion_focus),
        "signal_tier": signal_tier,
        "recommendation": signal_tier,
        "key_reasons": build_reasons(metrics),
        "risk_notes": build_risk_notes(metrics, float(cleaned_latest["volume"])),
        "data_window": f"{group['date'].iloc[0].date()} to {group['date'].iloc[-1].date()}",
    }


def display_name(row: pd.Series, symbol: str) -> str:
    value = row.get("name", "")
    if pd.isna(value) or not str(value).strip():
        return symbol
    return str(value)


def compute_metrics(
    data: pd.DataFrame,
    close: pd.Series,
    volume: pd.Series,
    config: dict[str, Any],
) -> dict[str, float]:
    windows = config["windows"]
    rsi = calculate_latest_rsi(close, int(windows["rsi"]))
    macd, signal = calculate_latest_macd(
        close,
        int(windows["macd_fast"]),
        int(windows["macd_slow"]),
        int(windows["macd_signal"]),
    )
    momentum = momentum_score(close, windows, config)
    volatility = calculate_latest_volatility(close, int(windows["volatility"]))
    prediction = resolve_prediction(data, config)
    trend = prediction if not math.isnan(prediction) else clamp01(0.5 + momentum)
    risk = risk_score(volatility, config)
    explosion = calculate_explosion_score(
        close=close,
        volume=volume,
        turnover=resolve_turnover(data, strict=is_prediction_mode(config)),
        macd=macd,
        signal=signal,
        windows=windows,
        weights=config["explosion_weights"],
    )
    total = weighted_total(trend, momentum, explosion, risk, config["weights"])
    return {
        "rsi": rsi,
        "volatility": volatility,
        "macd": float(macd.iloc[-1]),
        "macd_status": macd_status(macd, signal),
        "momentum_score": momentum,
        "trend_score": trend,
        "prediction_score": prediction,
        "explosion_score": explosion,
        "risk_score": risk,
        "total_score": total,
    }


def is_prediction_mode(config: dict[str, Any]) -> bool:
    return str(config.get("score_mode", "")).lower() == "prediction-derived"


def risk_score(volatility: float, config: dict[str, Any]) -> float:
    score = 1.0 - max(volatility, 0.0)
    if is_prediction_mode(config):
        return score
    return clamp01(score)


def iso_date(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError("date must be parseable")
    return parsed.date().isoformat()


def apply_cleaning(data: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    cleaning = config.get("cleaning", {})
    sigma = float(cleaning.get("clip_sigma", 0))
    for column in cleaning.get("clip_columns", []):
        if column in data.columns and sigma > 0:
            series = data[column].astype(float)
            median = float(series.median())
            std = float(series.std())
            if not math.isnan(std):
                data[column] = series.clip(median - sigma * std, median + sigma * std)
    fill_columns = [
        column for column in cleaning.get("fill_columns", []) if column in data
    ]
    if fill_columns:
        data[fill_columns] = data[fill_columns].ffill()
    return data


def resolve_prediction(data: pd.DataFrame, config: dict[str, Any]) -> float:
    if not is_prediction_mode(config):
        return math.nan
    columns = ["prediction_score", "prediction"]
    available = [column for column in columns if column in data.columns]
    if not available:
        raise ValueError(
            "prediction-derived score mode requires prediction or prediction_score"
        )
    value = latest_numeric(data[available[0]])
    if math.isnan(value) or value < 0 or value > 1:
        raise ValueError("prediction score must be a number between 0 and 1")
    return value


def latest_numeric(series: pd.Series) -> float:
    value = pd.to_numeric(series, errors="coerce").iloc[-1]
    return float(value) if pd.notna(value) else math.nan


def calculate_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50).clip(0, 100)


def calculate_latest_rsi(close: pd.Series, period: int) -> float:
    values = close.to_numpy(dtype=float, copy=False)
    delta = np.diff(values)[-period:]
    if not len(delta):
        return 50.0
    gain = float(np.maximum(delta, 0.0).mean())
    loss = float(np.maximum(-delta, 0.0).mean())
    if loss == 0.0 or not math.isfinite(loss):
        return 50.0
    return float(min(max(100.0 - (100.0 / (1.0 + gain / loss)), 0.0), 100.0))


def calculate_macd(
    close: pd.Series, fast: int, slow: int, signal_window: int
) -> tuple[pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False, min_periods=1).mean()
    ema_slow = close.ewm(span=slow, adjust=False, min_periods=1).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_window, adjust=False, min_periods=1).mean()
    return macd, signal


def calculate_latest_macd(
    close: pd.Series, fast: int, slow: int, signal_window: int
) -> tuple[pd.Series, pd.Series]:
    values = close.to_numpy(dtype=float, copy=False)
    if not len(values):
        return pd.Series(dtype=float), pd.Series(dtype=float)
    fast_alpha = 2.0 / (fast + 1.0)
    slow_alpha = 2.0 / (slow + 1.0)
    signal_alpha = 2.0 / (signal_window + 1.0)
    fast_ema = slow_ema = float(values[0])
    latest_macd = latest_signal = 0.0
    previous_macd = previous_signal = 0.0
    for value in values[1:]:
        previous_macd = latest_macd
        previous_signal = latest_signal
        fast_ema = (1.0 - fast_alpha) * fast_ema + fast_alpha * float(value)
        slow_ema = (1.0 - slow_alpha) * slow_ema + slow_alpha * float(value)
        latest_macd = fast_ema - slow_ema
        latest_signal = (
            (1.0 - signal_alpha) * latest_signal + signal_alpha * latest_macd
        )
    if len(values) == 1:
        return pd.Series([latest_macd]), pd.Series([latest_signal])
    return (
        pd.Series([previous_macd, latest_macd]),
        pd.Series([previous_signal, latest_signal]),
    )


def calculate_volatility(close: pd.Series, window: int) -> float:
    series = close.pct_change().rolling(window, min_periods=5).std() * math.sqrt(252)
    return min(max(latest_filled(series), 0.0), 2.0)


def calculate_latest_volatility(close: pd.Series, window: int) -> float:
    if window < 5:
        return calculate_volatility(close, window)
    values = close.to_numpy(dtype=float, copy=False)
    if len(values) < 6:
        return calculate_volatility(close, window)
    tail = values[-window - 1 :]
    changes = tail[1:] / tail[:-1] - 1.0
    value = float(np.std(changes, ddof=1) * math.sqrt(ONE_YEAR_TRADING_DAYS))
    if math.isnan(value):
        value = 0.0
    return min(max(value, 0.0), 2.0)


def momentum_score(
    close: pd.Series, windows: dict[str, Any], config: dict[str, Any]
) -> float:
    if config.get("momentum_score_mode") == "momentum_1m":
        return pct_change_at(close, int(windows["momentum_short"]))
    values = [
        pct_change_at(close, int(windows["momentum_short"])),
        pct_change_at(close, int(windows["momentum_medium"])),
        pct_change_at(close, int(windows["momentum_long"])),
    ]
    return float(np.nanmean(values))


def pct_change_at(series: pd.Series, window: int) -> float:
    if len(series) <= window:
        return 0.0
    base = float(series.iloc[-window - 1])
    return 0.0 if base <= 0 else float(series.iloc[-1] / base - 1)


def one_year_pct_change(close: pd.Series) -> float:
    if len(close) <= ONE_YEAR_TRADING_DAYS:
        return math.nan
    # 252 completed sessions back requires the current close plus 252 prior closes.
    base = float(close.iloc[-ONE_YEAR_TRADING_DAYS - 1])
    if base <= 0 or math.isnan(base):
        return math.nan
    return float((float(close.iloc[-1]) / base - 1.0) * 100.0)


def calculate_explosion_score(
    *,
    close: pd.Series,
    volume: pd.Series,
    turnover: pd.Series,
    macd: pd.Series,
    signal: pd.Series,
    windows: dict[str, Any],
    weights: dict[str, Any],
) -> float:
    volume_window = int(windows["volume_ratio"])
    short_window = int(windows["short_momentum"])
    if len(close) < volume_window:
        return 0.0
    return float(
        ratio_score(volume, volume_window) * float(weights["volume_ratio"])
        + ratio_score(turnover, volume_window) * float(weights["turnover_ratio"])
        + macd_cross_score(macd, signal) * float(weights["macd_cross"])
        + (1 - price_position(close, volume_window)) * float(weights["price_position"])
        + short_momentum_score(close, short_window) * float(weights["short_momentum"])
    )


def ratio_score(series: pd.Series, window: int) -> float:
    base = float(series.iloc[-window:].mean())
    value = float(series.iloc[-1])
    if base <= 0 or math.isnan(base):
        return 0.0
    return float(min(max(value / base, 0.0), 5.0))


def price_position(close: pd.Series, window: int) -> float:
    price_slice = close.iloc[-window:]
    price_range = float(price_slice.max() - price_slice.min())
    if price_range <= 0:
        return 0.5
    return float((close.iloc[-1] - price_slice.min()) / price_range)


def macd_status(macd: pd.Series, signal: pd.Series) -> str:
    if len(macd) < 2:
        return "unknown"
    last_diff = float(macd.iloc[-1] - signal.iloc[-1])
    prev_diff = float(macd.iloc[-2] - signal.iloc[-2])
    if last_diff > 0 and prev_diff <= 0:
        return "golden_cross"
    if last_diff < 0 and prev_diff >= 0:
        return "dead_cross"
    if last_diff > 0:
        return "bullish"
    if last_diff < 0:
        return "bearish"
    return "neutral"


def macd_cross_score(macd: pd.Series, signal: pd.Series) -> float:
    last_diff = float(macd.iloc[-1] - signal.iloc[-1])
    prev_diff = float(macd.iloc[-2] - signal.iloc[-2]) if len(macd) >= 2 else 0.0
    return 1.0 if last_diff > 0 and prev_diff < 0 else 0.0


def short_momentum_score(close: pd.Series, window: int) -> float:
    if len(close) < window:
        return 0.5
    raw = 0.0
    if float(close.iloc[-window]) > 0:
        raw = float(close.iloc[-1] / close.iloc[-window] - 1)
    return float((min(max(raw * 100, -20), 20) + 20) / 40)


def resolve_turnover(data: pd.DataFrame, strict: bool = False) -> pd.Series:
    if "turnover" in data.columns:
        return data["turnover"].astype(float)
    if "turn" in data.columns:
        return data["turn"].astype(float)
    if strict:
        raise ValueError(
            "prediction-derived score mode requires turn or turnover column"
        )
    return pd.Series(np.ones(len(data)), index=data.index, dtype=float)


def weighted_total(
    trend: float,
    momentum: float,
    explosion: float,
    risk: float,
    weights: dict[str, Any],
) -> float:
    trend_weight = float(weights.get("prediction_score", weights.get("trend_score", 0)))
    return float(
        trend * trend_weight
        + momentum * float(weights["momentum_score"])
        + explosion * float(weights["explosion_score"])
        + risk * float(weights["risk_score"])
    )


def clamp01(value: float) -> float:
    return 0.0 if math.isnan(value) else float(min(max(value, 0.0), 1.0))


def latest_filled(series: pd.Series) -> float:
    filled = series.fillna(series.mean())
    value = float(filled.iloc[-1])
    return 0.0 if math.isnan(value) else value


def calculate_ma(close: pd.Series, window: int) -> float:
    if len(close) < window:
        return math.nan
    return float(close.rolling(window=window).mean().iloc[-1])
