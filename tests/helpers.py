from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_config(name: str) -> dict:
    return json.loads((SCRIPTS / name).read_text(encoding="utf-8"))


def build_frame(
    *,
    days: int = 130,
    include_prediction: bool = False,
    prediction_value: float = 0.72,
    prediction_column: str = "prediction_score",
    include_turn: bool = True,
    include_tradability: bool = False,
) -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2025-01-02", periods=days)
    symbols = [("000002", "Zero Prefix", 8.0), ("600001", "Shanghai", 10.0)]
    for symbol, name, base in symbols:
        for index, date in enumerate(dates):
            close = base + index * 0.018 + np.sin(index / 9) * 0.08
            row = {
                "symbol": symbol,
                "name": name,
                "market": "A-share",
                "date": date.date().isoformat(),
                "open": close * 0.997,
                "high": close * 1.012,
                "low": close * 0.988,
                "close": close,
                "volume": 120000 + index * 30,
                "amount": 150000000 + index * 100000,
            }
            if include_tradability:
                row["tradestatus"] = "1"
                row["isST"] = "0"
            if include_turn:
                row["turn"] = 1.1 + np.cos(index / 11) * 0.03
            if include_prediction:
                row[prediction_column] = prediction_value
            rows.append(row)
    return pd.DataFrame(rows)


def permissive_thresholds(min_history_rows: int) -> dict:
    return {
        "min_total_score": -10.0,
        "min_trend_score": -10.0,
        "min_momentum_score": -10.0,
        "min_rsi": 0.0,
        "max_rsi": 100.0,
        "max_volatility": 10.0,
        "min_volume": 0.0,
        "min_close": 0.0,
        "min_history_rows": min_history_rows,
    }
