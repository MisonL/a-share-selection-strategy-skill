"""Configuration loading and validation for stock selection scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = [
    "windows",
    "weights",
    "explosion_weights",
    "thresholds",
    "output",
]
BASE_WINDOW_KEYS = [
    "momentum_short",
    "rsi",
    "macd_fast",
    "macd_slow",
    "macd_signal",
    "volatility",
    "volume_ratio",
    "short_momentum",
]
MULTI_MOMENTUM_KEYS = ["momentum_medium", "momentum_long"]
EXPLOSION_WEIGHT_KEYS = [
    "volume_ratio",
    "turnover_ratio",
    "macd_cross",
    "price_position",
    "short_momentum",
]
BASE_THRESHOLD_KEYS = [
    "min_total_score",
    "min_momentum_score",
    "min_rsi",
    "max_rsi",
    "max_volatility",
    "min_volume",
    "min_close",
]
BASE_WEIGHT_KEYS = ["momentum_score", "explosion_score", "risk_score"]


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    missing_sections = [key for key in REQUIRED_SECTIONS if key not in config]
    if missing_sections:
        raise ValueError(f"config missing section: {', '.join(missing_sections)}")
    require_keys(config["windows"], window_keys(config), "windows")
    require_keys(config["weights"], BASE_WEIGHT_KEYS, "weights")
    require_one_of(config["weights"], ["prediction_score", "trend_score"], "weights")
    require_keys(config["explosion_weights"], EXPLOSION_WEIGHT_KEYS, "explosion_weights")
    require_keys(config["thresholds"], BASE_THRESHOLD_KEYS, "thresholds")
    require_one_of(
        config["thresholds"],
        ["min_prediction_score", "min_trend_score"],
        "thresholds",
    )


def window_keys(config: dict[str, Any]) -> list[str]:
    keys = list(BASE_WINDOW_KEYS)
    if config.get("momentum_score_mode") != "momentum_1m":
        keys.extend(MULTI_MOMENTUM_KEYS)
    return keys


def require_keys(section: dict[str, Any], keys: list[str], name: str) -> None:
    missing = [key for key in keys if key not in section]
    if missing:
        raise ValueError(f"config {name} missing keys: {', '.join(missing)}")


def require_one_of(section: dict[str, Any], keys: list[str], name: str) -> None:
    if not any(key in section for key in keys):
        raise ValueError(f"config {name} require one of: {', '.join(keys)}")
