#!/usr/bin/env python3
"""Generate LightGBM prediction_score values from local OHLCV data."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stock_selection_data import parse_dates, read_table
from lightgbm_prediction_summary import (
    build_summary,
    skipped_summary,
    symbol_summary,
    write_json_summary,
)
from stock_selection_metrics import calculate_macd, calculate_rsi
from validate_ohlcv import validate_frame


FEATURE_COLUMNS = [
    "momentum_1m",
    "momentum_3m",
    "momentum_6m",
    "volatility",
    "vol_ratio",
    "rsi",
    "macd",
    "signal",
]
BASE_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
QSSS_MODEL_PARAMS = {
    "n_estimators": 100,
    "num_leaves": 31,
    "min_child_samples": 5,
    "max_depth": 5,
    "learning_rate": 0.1,
    "random_state": 42,
    "verbose": -1,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate LightGBM prediction_score for local OHLCV data."
    )
    parser.add_argument("--input", required=True, help="Path to CSV or Parquet file.")
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    parser.add_argument("--horizon", type=int, default=5, help="Forward return horizon.")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--min-history-rows", type=int, default=150)
    parser.add_argument("--summary-output", help="Optional JSON summary output path.")
    parser.add_argument("--fail-on-skipped", action="store_true")
    args = parser.parse_args(argv)
    try:
        result, summary = generate_predictions(
            read_table(Path(args.input)),
            horizon=args.horizon,
            train_ratio=args.train_ratio,
            min_history_rows=args.min_history_rows,
        )
        if args.fail_on_skipped and summary["skipped_symbols"]:
            print_summary(summary, args.output, prefix="ERROR_SUMMARY")
            print(
                "ERROR: strict gate failed; "
                f"skipped_symbols={summary['skipped_symbols']} output_not_written=true",
                file=sys.stderr,
            )
            return 3
        write_output(result, Path(args.output))
        if args.summary_output:
            write_json_summary(summary, Path(args.summary_output))
    except Exception as exc:  # noqa: BLE001
        print(
            "ERROR: code=bad_input "
            f"input={Path(args.input).name} output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(summary, args.output)
    return 0


def generate_predictions(
    frame: pd.DataFrame,
    *,
    horizon: int,
    train_ratio: float,
    min_history_rows: int,
    model_deps: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    validate_options(horizon, train_ratio, min_history_rows)
    errors = validate_frame(frame, min_history_rows=0)
    if errors:
        raise ValueError("; ".join(errors))
    model_deps = model_deps or load_model_dependencies()
    prepared = prepare_frame(frame)
    outputs = []
    skipped = []
    symbol_summaries = []
    for symbol, group in prepared.groupby("symbol", sort=False):
        if len(group) < min_history_rows:
            reason = "insufficient_history"
            skipped.append(str(symbol))
            symbol_summaries.append(skipped_summary(group, reason))
            continue
        try:
            output, symbol_summary = predict_symbol(group, horizon, train_ratio, model_deps)
            outputs.append(output)
            symbol_summaries.append(symbol_summary)
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"{symbol}:{exc}")
            symbol_summaries.append(skipped_summary(group, str(exc)))
    if not outputs:
        raise ValueError(f"no symbols predicted; skipped_symbols={','.join(skipped)}")
    result = pd.concat(outputs, ignore_index=True)
    return result, build_summary(
        prepared,
        result,
        skipped,
        horizon,
        train_ratio,
        symbol_summaries,
    )


def validate_options(horizon: int, train_ratio: float, min_history_rows: int) -> None:
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if not 0.5 <= train_ratio < 1.0:
        raise ValueError("train-ratio must be >= 0.5 and < 1.0")
    if min_history_rows < 100:
        raise ValueError("min-history-rows must be >= 100")


def load_model_dependencies() -> dict[str, Any]:
    try:
        from lightgbm import LGBMClassifier
        from sklearn.preprocessing import StandardScaler
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "LightGBM prediction requires lightgbm and scikit-learn"
        ) from exc
    return {"classifier": LGBMClassifier, "scaler": StandardScaler}


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["symbol"] = result["symbol"].astype(str)
    result["date"] = parse_dates(result["date"])
    numeric_columns = ["open", "high", "low", "close", "volume", "turn", "turnover"]
    for column in numeric_columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=BASE_COLUMNS)
    result = result[(result[["open", "high", "low", "close"]] > 0).all(axis=1)]
    result = result[result["volume"] >= 0]
    return result.sort_values(["symbol", "date"]).reset_index(drop=True)


def predict_symbol(
    group: pd.DataFrame,
    horizon: int,
    train_ratio: float,
    model_deps: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    features = build_feature_frame(group, horizon)
    trainable = features.dropna(subset=[*FEATURE_COLUMNS, "target_return"])
    if len(trainable) < 50:
        raise ValueError("fewer than 50 trainable rows after feature cleanup")
    train_size = max(1, int(len(trainable) * train_ratio))
    train = trainable.iloc[:train_size]
    target_label = train["target_return"] > train["target_return"].mean()
    if target_label.nunique() < 2:
        raise ValueError("training target has fewer than two classes")
    scaler = model_deps["scaler"]()
    x_train = scaled_frame(scaler.fit_transform(train[FEATURE_COLUMNS]), train.index)
    model = model_deps["classifier"](**QSSS_MODEL_PARAMS)
    model.fit(x_train, target_label.astype(int))
    latest = features.dropna(subset=FEATURE_COLUMNS).iloc[[-1]]
    x_latest = scaled_frame(scaler.transform(latest[FEATURE_COLUMNS]), latest.index)
    probability = float(model.predict_proba(x_latest)[0][1])
    return with_prediction(group, probability, horizon), symbol_summary(
        group,
        trainable,
        train_size,
        probability,
        horizon,
    )


def scaled_frame(values: Any, index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(values, columns=FEATURE_COLUMNS, index=index)


def build_feature_frame(group: pd.DataFrame, horizon: int) -> pd.DataFrame:
    data = group.copy()
    data["turn_value"] = turnover_series(data)
    for column in ["close", "volume", "turn_value"]:
        data[column] = data[column].replace(0, np.nan).ffill().bfill()
    close = data["close"].astype(float)
    volume = data["volume"].astype(float)
    macd, signal = calculate_macd(close, 12, 26, 9)
    features = pd.DataFrame(index=data.index)
    features["momentum_1m"] = close.pct_change(20)
    features["momentum_3m"] = close.pct_change(60)
    features["momentum_6m"] = close.pct_change(120)
    features["volatility"] = close.pct_change().rolling(20, min_periods=5).std()
    features["volatility"] = features["volatility"] * math.sqrt(252)
    features["vol_ratio"] = volume / volume.rolling(20, min_periods=5).mean()
    features["rsi"] = calculate_rsi(close, 14)
    features["macd"] = macd
    features["signal"] = signal
    features["target_return"] = close.shift(-horizon) / close - 1
    return features.replace([np.inf, -np.inf], np.nan)


def turnover_series(data: pd.DataFrame) -> pd.Series:
    if "turn" in data.columns:
        return data["turn"].astype(float)
    if "turnover" in data.columns:
        return data["turnover"].astype(float)
    raise ValueError("LightGBM prediction requires turn or turnover column")


def with_prediction(group: pd.DataFrame, probability: float, horizon: int) -> pd.DataFrame:
    output = group.copy()
    output["prediction_score"] = min(max(probability, 0.0), 1.0)
    output["prediction_horizon_days"] = int(horizon)
    output["prediction_model"] = "lightgbm"
    output["prediction_scope"] = "latest_probability_repeated_for_scoring"
    return output


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def print_summary(summary: dict[str, Any], output: str, prefix: str = "OK") -> None:
    print(
        f"{prefix}: raw_symbols={summary['raw_symbols']} "
        f"predicted_symbols={summary['predicted_symbols']} "
        f"skipped_symbols={summary['skipped_symbols']} "
        f"horizon={summary['horizon']} train_ratio={summary['train_ratio']} "
        f"output={output}"
    )
    if summary["skipped_symbol_examples"]:
        print(
            "INFO: skipped_symbol_examples="
            f"{','.join(summary['skipped_symbol_examples'])}"
        )
    print("INFO: split=time_series scaler_fit=train_split_only model=lightgbm")


if __name__ == "__main__":
    raise SystemExit(main())
