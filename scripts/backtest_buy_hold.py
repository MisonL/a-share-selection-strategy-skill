#!/usr/bin/env python3
"""Run a minimal close-to-close buy-hold backtest from local files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from stock_selection_data import parse_dates, read_table
from validate_ohlcv import validate_frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a minimal close-to-close buy-hold backtest."
    )
    parser.add_argument("--prices", required=True, help="Path to OHLCV CSV/Parquet.")
    parser.add_argument("--candidates", required=True, help="Path to candidates CSV.")
    parser.add_argument("--output", required=True, help="Path to output CSV.")
    parser.add_argument("--hold-days", "--holding-days", dest="hold_days", type=int, default=5)
    parser.add_argument("--fail-on-incomplete", action="store_true")
    args = parser.parse_args(argv)
    try:
        result, summary = run_backtest(
            read_table(Path(args.prices)),
            read_table(Path(args.candidates)),
            hold_days=args.hold_days,
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
        write_output(result, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(
            "ERROR: code=bad_input "
            f"prices={Path(args.prices).name} candidates={Path(args.candidates).name} "
            f"output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(summary, args.output)
    return 0


def run_backtest(
    prices: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    hold_days: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if hold_days < 1:
        raise ValueError("hold-days must be >= 1")
    price_errors = validate_frame(prices, min_history_rows=0)
    if price_errors:
        raise ValueError("; ".join(price_errors))
    validate_candidates(candidates)
    prepared = prepare_prices(prices)
    rows = [
        evaluate_candidate(row, prepared, hold_days)
        for _, row in candidates.iterrows()
    ]
    result = pd.DataFrame(rows)
    return result, build_summary(result, hold_days)


def validate_candidates(candidates: pd.DataFrame) -> None:
    missing = [column for column in ["symbol", "date"] if column not in candidates]
    if missing:
        raise ValueError(f"candidates missing required columns: {', '.join(missing)}")
    if candidates.empty:
        raise ValueError("candidates data is empty")


def prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    result = prices.copy()
    result["symbol"] = result["symbol"].astype(str)
    result["date"] = parse_dates(result["date"])
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    result = result.dropna(subset=["symbol", "date", "close"])
    return result.sort_values(["symbol", "date"]).reset_index(drop=True)


def evaluate_candidate(
    row: pd.Series,
    prices: pd.DataFrame,
    holding_days: int,
) -> dict[str, Any]:
    symbol = str(row["symbol"])
    signal_date = parse_dates(pd.Series([row["date"]])).iloc[0]
    history = prices[prices["symbol"] == symbol].reset_index(drop=True)
    if pd.isna(signal_date) or history.empty:
        return incomplete_row(symbol, row["date"], holding_days, "missing_entry_price")
    entry_positions = history.index[history["date"] == signal_date].tolist()
    if not entry_positions:
        return incomplete_row(symbol, signal_date.date(), holding_days, "missing_entry_price")
    entry_pos = int(entry_positions[0])
    exit_pos = entry_pos + holding_days
    if exit_pos >= len(history):
        return incomplete_row(symbol, signal_date.date(), holding_days, "missing_future_price")
    return completed_row(symbol, signal_date.date(), history, entry_pos, exit_pos, holding_days)


def completed_row(
    symbol: str,
    signal_date: Any,
    history: pd.DataFrame,
    entry_pos: int,
    exit_pos: int,
    holding_days: int,
) -> dict[str, Any]:
    entry = history.iloc[entry_pos]
    exit_row = history.iloc[exit_pos]
    entry_close = float(entry["close"])
    exit_close = float(exit_row["close"])
    return {
        **base_row(symbol, signal_date),
        "entry_date": entry["date"].date().isoformat(),
        "exit_date": exit_row["date"].date().isoformat(),
        "entry_close": entry_close,
        "exit_close": exit_close,
        "hold_days_requested": holding_days,
        "holding_period": int(exit_pos - entry_pos),
        "return": exit_close / entry_close - 1,
        "missing_data": False,
        "missing_reason": "none",
        "status": "complete",
    }


def incomplete_row(
    symbol: str,
    signal_date: Any,
    holding_days: int,
    reason: str,
) -> dict[str, Any]:
    return {
        **base_row(symbol, signal_date),
        "entry_date": "",
        "exit_date": "",
        "entry_close": pd.NA,
        "exit_close": pd.NA,
        "hold_days_requested": holding_days,
        "holding_period": pd.NA,
        "return": pd.NA,
        "missing_data": True,
        "missing_reason": reason,
        "status": "incomplete",
    }


def base_row(symbol: str, signal_date: Any) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "signal_date": str(signal_date),
        "cost_model": "excluded",
        "slippage_model": "excluded",
        "tradability_model": "not_modeled",
        "limit_rules_model": "not_modeled",
    }


def build_summary(result: pd.DataFrame, holding_days: int) -> dict[str, Any]:
    completed = int((result["missing_data"] == False).sum())
    total = int(len(result))
    return {
        "candidates": total,
        "completed_trades": completed,
        "incomplete_trades": total - completed,
        "hold_days": int(holding_days),
        "missing_reason_counts": missing_reason_counts(result),
    }


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def print_summary(summary: dict[str, Any], output: str, prefix: str = "OK") -> None:
    print(
        f"{prefix}: candidates={summary['candidates']} "
        f"completed_trades={summary['completed_trades']} "
        f"incomplete_trades={summary['incomplete_trades']} "
        f"hold_days={summary['hold_days']} output={output}"
    )
    if summary["missing_reason_counts"]:
        print(f"INFO: missing_reason_counts={summary['missing_reason_counts']}")
    print(
        "INFO: baseline=buy_hold_close_to_close costs=excluded "
        "slippage=excluded tradability_model=not_modeled "
        "suspension=missing_future_price"
    )


def missing_reason_counts(result: pd.DataFrame) -> str:
    missing = result[result["missing_data"] == True]
    if missing.empty:
        return ""
    counts = missing["missing_reason"].value_counts().sort_index()
    return ",".join(f"{reason}:{count}" for reason, count in counts.items())


if __name__ == "__main__":
    raise SystemExit(main())
