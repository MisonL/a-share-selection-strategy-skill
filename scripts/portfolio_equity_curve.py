#!/usr/bin/env python3
"""Build a simple equal-weight equity curve from backtest CSV files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from stock_selection_data import parse_dates, read_table


REQUIRED_COLUMNS = ["signal_date", "return", "missing_data", "status"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an equal-weight equity curve from backtest outputs."
    )
    parser.add_argument("--backtests", nargs="+", required=True, help="Backtest CSV/Parquet paths.")
    parser.add_argument("--output", required=True, help="Output equity curve CSV path.")
    parser.add_argument("--initial-equity", type=float, default=1.0)
    parser.add_argument("--fail-on-incomplete", action="store_true")
    args = parser.parse_args(argv)
    try:
        frames = [read_table(Path(path)) for path in args.backtests]
        curve, summary = build_equity_curve(
            frames,
            initial_equity=args.initial_equity,
        )
        if args.fail_on_incomplete and summary["incomplete_trades"]:
            print_summary(summary, args.output, prefix="ERROR_SUMMARY")
            print(
                "ERROR: strict gate failed; "
                f"incomplete_trades={summary['incomplete_trades']} "
                "output_not_written=true",
                file=sys.stderr,
            )
            return 3
        write_output(curve, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(
            "ERROR: code=bad_input "
            f"output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(summary, args.output)
    return 0


def build_equity_curve(
    frames: list[pd.DataFrame],
    *,
    initial_equity: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if initial_equity <= 0:
        raise ValueError("initial-equity must be > 0")
    if not frames:
        raise ValueError("at least one backtest file is required")
    periods = [period_row(frame) for frame in frames]
    curve = pd.DataFrame(periods).sort_values("signal_date").reset_index(drop=True)
    curve["equity"] = initial_equity * (1 + curve["mean_return"]).cumprod()
    curve["running_peak"] = curve["equity"].cummax().clip(lower=initial_equity)
    curve["drawdown"] = curve["equity"] / curve["running_peak"] - 1
    return curve, build_summary(curve, initial_equity)


def period_row(frame: pd.DataFrame) -> dict[str, Any]:
    validate_frame(frame)
    prepared = frame.copy()
    prepared["signal_date"] = parse_dates(prepared["signal_date"])
    prepared["return"] = pd.to_numeric(prepared["return"], errors="coerce")
    if prepared["signal_date"].isna().any():
        raise ValueError("signal_date must be parseable")
    complete = prepared[is_complete_trade(prepared)]
    if complete.empty:
        raise ValueError("backtest period has no complete trades")
    signal_dates = complete["signal_date"].dt.date.astype(str).unique()
    if len(signal_dates) != 1:
        raise ValueError("each backtest file must contain exactly one signal_date")
    incomplete = int(len(prepared) - len(complete))
    return {
        "signal_date": signal_dates[0],
        "positions": int(len(complete)),
        "mean_return": float(complete["return"].mean()),
        "incomplete_trades": incomplete,
        "weighting": "equal_weight_completed_trades",
    }


def validate_frame(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame]
    if missing:
        raise ValueError(f"backtest missing required columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("backtest data is empty")


def is_complete_trade(frame: pd.DataFrame) -> pd.Series:
    missing = frame["missing_data"].astype(str).str.lower().isin(["true", "1"])
    return (frame["status"].astype(str) == "complete") & (~missing)


def build_summary(curve: pd.DataFrame, initial_equity: float) -> dict[str, Any]:
    final_equity = float(curve["equity"].iloc[-1])
    trough_index = int(curve["drawdown"].idxmin())
    trough_date = str(curve.loc[trough_index, "signal_date"])
    if float(curve.loc[trough_index, "drawdown"]) == 0:
        peak_date = "START"
    else:
        peak_date = peak_date_for_drawdown(curve, trough_index, initial_equity)
    return {
        "periods": int(len(curve)),
        "positions": int(curve["positions"].sum()),
        "incomplete_trades": int(curve["incomplete_trades"].sum()),
        "initial_equity": float(initial_equity),
        "final_equity": final_equity,
        "total_return": final_equity / float(initial_equity) - 1,
        "max_drawdown": float(curve["drawdown"].min()),
        "max_drawdown_peak_date": peak_date,
        "max_drawdown_trough_date": trough_date,
    }


def peak_date_for_drawdown(
    curve: pd.DataFrame,
    trough_index: int,
    initial_equity: float,
) -> str:
    peak_value = float(curve.loc[trough_index, "running_peak"])
    if peak_value == float(initial_equity):
        return "START"
    peak_rows = curve.loc[:trough_index]
    matching = peak_rows[peak_rows["equity"] == peak_value]
    if matching.empty:
        return "START"
    return str(matching.iloc[-1]["signal_date"])


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def print_summary(summary: dict[str, Any], output: str, prefix: str = "OK") -> None:
    print(
        f"{prefix}: periods={summary['periods']} "
        f"positions={summary['positions']} "
        f"incomplete_trades={summary['incomplete_trades']} "
        f"initial_equity={summary['initial_equity']} "
        f"final_equity={summary['final_equity']} "
        f"total_return={summary['total_return']} "
        f"max_drawdown={summary['max_drawdown']} "
        f"max_drawdown_peak_date={summary['max_drawdown_peak_date']} "
        f"max_drawdown_trough_date={summary['max_drawdown_trough_date']} "
        f"output={output}"
    )
    print("INFO: portfolio_model=equal_weight_completed_trades")


if __name__ == "__main__":
    raise SystemExit(main())
