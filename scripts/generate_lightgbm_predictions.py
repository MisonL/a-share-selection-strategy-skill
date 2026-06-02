#!/usr/bin/env python3
"""Generate LightGBM prediction_score values from local OHLCV data."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any


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
        ensure_runtime_dependencies()
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


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import numpy as numpy_module
    import pandas as pandas_module
    import lightgbm_prediction_summary as summary_module
    import stock_selection_data as data_module
    import stock_selection_metrics as metrics_module
    import validate_ohlcv as validator_module

    globals().update(
        {
            "np": numpy_module,
            "pd": pandas_module,
            "parse_dates": data_module.parse_dates,
            "read_table": data_module.read_table,
            "build_summary": summary_module.build_summary,
            "skipped_summary": summary_module.skipped_summary,
            "symbol_summary": summary_module.symbol_summary,
            "write_json_summary": summary_module.write_json_summary,
            "calculate_macd": metrics_module.calculate_macd,
            "calculate_rsi": metrics_module.calculate_rsi,
            "validate_frame": validator_module.validate_frame,
        }
    )


def generate_predictions(
    frame: pd.DataFrame,
    *,
    horizon: int,
    train_ratio: float,
    min_history_rows: int,
    model_deps: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
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
        reason_counts = skipped_reason_counts(symbol_summaries)
        reason_text = ",".join(
            f"{reason}:{count}" for reason, count in reason_counts.items()
        )
        reason_detail = f"; skipped_reasons={reason_text}" if reason_text else ""
        raise ValueError(
            f"no symbols predicted; skipped_symbols={','.join(skipped)}"
            f"{reason_detail}"
        )
    result = pd.concat(outputs, ignore_index=True)
    return result, build_summary(
        prepared,
        result,
        skipped,
        horizon,
        train_ratio,
        symbol_summaries,
        FEATURE_COLUMNS,
    )


def validate_options(horizon: int, train_ratio: float, min_history_rows: int) -> None:
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if not 0.5 <= train_ratio < 1.0:
        raise ValueError("train-ratio must be >= 0.5 and < 1.0")
    if min_history_rows < 100:
        raise ValueError("min-history-rows must be >= 100")


def skipped_reason_counts(symbol_summaries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in symbol_summaries:
        if item.get("status") != "skipped":
            continue
        reason = str(item.get("skipped_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


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
    target_threshold = float(train["target_return"].mean())
    target_label = train["target_return"] > target_threshold
    if target_label.nunique() < 2:
        raise ValueError("training target has fewer than two classes")
    scaler = model_deps["scaler"]()
    x_train = scaled_frame(scaler.fit_transform(train[FEATURE_COLUMNS]), train.index)
    model = model_deps["classifier"](**QSSS_MODEL_PARAMS)
    model.fit(x_train, target_label.astype(int))
    holdout = holdout_summary(trainable, train_size, target_threshold, scaler, model, group)
    latest = features.dropna(subset=FEATURE_COLUMNS).iloc[[-1]]
    x_latest = scaled_frame(scaler.transform(latest[FEATURE_COLUMNS]), latest.index)
    probability = float(model.predict_proba(x_latest)[0][1])
    return with_prediction(group, probability, horizon), symbol_summary(
        group,
        trainable,
        train,
        latest,
        holdout,
        probability,
        horizon,
        target_threshold,
        int(target_label.sum()),
        int(len(target_label) - target_label.sum()),
    )


def holdout_summary(
    trainable: pd.DataFrame,
    train_size: int,
    target_threshold: float,
    scaler: Any,
    model: Any,
    group: pd.DataFrame,
) -> dict[str, Any]:
    holdout = trainable.iloc[train_size:]
    labels = holdout["target_return"] > target_threshold
    summary = base_holdout_summary(holdout, labels, group)
    if len(holdout) == 0:
        return {**summary, **holdout_metric(None, "empty_holdout")}
    if labels.nunique() < 2:
        return {**summary, **holdout_metric(None, "single_class_holdout")}
    x_holdout = scaled_frame(scaler.transform(holdout[FEATURE_COLUMNS]), holdout.index)
    scores = model.predict_proba(x_holdout)[:, 1]
    return {**summary, **holdout_metric(binary_auc(labels.astype(int), scores), "")}


def base_holdout_summary(
    holdout: pd.DataFrame,
    labels: pd.Series,
    group: pd.DataFrame,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "holdout_rows": int(len(holdout)),
        "holdout_date_min": "",
        "holdout_date_max": "",
        "holdout_positive_labels": int(labels.sum()) if len(labels) else 0,
        "holdout_negative_labels": int(len(labels) - labels.sum()) if len(labels) else 0,
    }
    if len(holdout):
        dates = parse_dates(group.loc[holdout.index, "date"])
        result["holdout_date_min"] = dates.min().date().isoformat()
        result["holdout_date_max"] = dates.max().date().isoformat()
    return result


def holdout_metric(value: float | None, reason: str) -> dict[str, Any]:
    return {
        "holdout_auc": value,
        "holdout_metric_status": "computed" if reason == "" else "not_computable",
        "holdout_metric_reason": reason,
    }


def binary_auc(labels: Any, scores: Any) -> float:
    labels_array = np.asarray(labels, dtype=int)
    scores_array = np.asarray(scores, dtype=float)
    order = np.argsort(scores_array, kind="mergesort")
    ranks = np.empty(len(scores_array), dtype=float)
    sorted_scores = scores_array[order]
    start = 0
    while start < len(sorted_scores):
        end = start + 1
        while end < len(sorted_scores) and sorted_scores[end] == sorted_scores[start]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2.0
        start = end
    positives = labels_array == 1
    positive_count = int(positives.sum())
    negative_count = int(len(labels_array) - positive_count)
    if positive_count == 0 or negative_count == 0:
        raise ValueError("AUC requires both positive and negative labels")
    positive_rank_sum = float(ranks[positives].sum())
    return float(
        (positive_rank_sum - positive_count * (positive_count + 1) / 2.0)
        / (positive_count * negative_count)
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
