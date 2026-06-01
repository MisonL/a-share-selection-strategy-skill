#!/usr/bin/env python3
"""Allocate traceable capital fields for candidate trades."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Allocate capital fields for candidates.")
    parser.add_argument("--prices", required=True, help="Path to OHLCV CSV/Parquet.")
    parser.add_argument("--candidates", required=True, help="Path to candidates CSV/Parquet.")
    parser.add_argument("--output", required=True, help="Path to output CSV.")
    parser.add_argument("--cash-budget", type=float, required=True)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--close-tolerance", type=float, default=0.000001)
    parser.add_argument("--overwrite-capital-fields", action="store_true")
    parser.add_argument("--fail-on-unallocated", action="store_true")
    args = parser.parse_args(argv)
    try:
        ensure_runtime_dependencies()
        result, summary = allocate_capital(
            read_table(Path(args.prices)),
            read_table(Path(args.candidates)),
            cash_budget=args.cash_budget,
            lot_size=args.lot_size,
            close_tolerance=args.close_tolerance,
            overwrite_capital_fields=args.overwrite_capital_fields,
        )
        if args.fail_on_unallocated and summary["unallocated_candidates"]:
            print_summary(summary, args.output, prefix="ERROR_SUMMARY")
            print(
                "ERROR: strict gate failed; "
                f"unallocated_candidates={summary['unallocated_candidates']} "
                "output_written=false",
                file=sys.stderr,
            )
            return 3
        write_output(result, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(
            "ERROR: code=bad_input "
            f"output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(summary, args.output)
    return 0


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import stock_selection_capital as capital_module
    import stock_selection_data as data_module
    import validate_ohlcv as validator_module

    globals().update(
        {
            "pd": pandas_module,
            "CAPITAL_FIELDS": capital_module.CAPITAL_FIELDS,
            "parse_dates": data_module.parse_dates,
            "read_table": data_module.read_table,
            "validate_frame": validator_module.validate_frame,
        }
    )


def allocate_capital(
    prices: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    cash_budget: float,
    lot_size: int = 100,
    close_tolerance: float = 0.000001,
    overwrite_capital_fields: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
    validate_inputs(prices, candidates, cash_budget, lot_size, close_tolerance)
    reject_existing_capital_fields(candidates, overwrite_capital_fields)
    quotes = signal_quotes(prices)
    result = candidates.copy().reset_index(drop=True)
    result["symbol"] = result["symbol"].astype(str)
    result["_signal_date"] = parse_dates(result["date"])
    if result["_signal_date"].isna().any():
        raise ValueError("candidate dates must be parseable")
    if result.duplicated(["symbol", "_signal_date"]).any():
        raise ValueError("candidates contain duplicate symbol/date rows")
    merged = result.merge(quotes, on=["symbol", "_signal_date"], how="left", validate="many_to_one")
    if merged["signal_close"].isna().any():
        missing = int(merged["signal_close"].isna().sum())
        raise ValueError(f"missing signal close for {missing} candidates")
    validate_candidate_close(merged, close_tolerance)
    slot_cash = cash_budget / len(merged)
    merged["cash_slot"] = slot_cash
    merged["quantity"] = (
        (slot_cash / (merged["signal_close"] * lot_size)).astype(int) * lot_size
    )
    merged["cash_reserved"] = merged["quantity"] * merged["signal_close"]
    merged["notional"] = merged["cash_reserved"]
    merged["weight"] = merged["cash_reserved"] / cash_budget
    merged["capital_model"] = "equal_cash_budget_lot_floor"
    merged["cash_budget"] = float(cash_budget)
    merged["lot_size"] = int(lot_size)
    merged["unallocated"] = merged["quantity"] <= 0
    output = merged.drop(columns=["_signal_date"])
    return output, build_summary(output, cash_budget, lot_size)


def validate_inputs(
    prices: pd.DataFrame,
    candidates: pd.DataFrame,
    cash_budget: float,
    lot_size: int,
    close_tolerance: float,
) -> None:
    if cash_budget <= 0:
        raise ValueError("cash-budget must be > 0")
    if lot_size < 1:
        raise ValueError("lot-size must be >= 1")
    if close_tolerance < 0:
        raise ValueError("close-tolerance must be >= 0")
    errors = validate_frame(prices, min_history_rows=0)
    if errors:
        raise ValueError("; ".join(errors))
    missing = [column for column in ["symbol", "date"] if column not in candidates]
    if missing:
        raise ValueError(f"candidates missing required columns: {', '.join(missing)}")
    if candidates.empty:
        raise ValueError("candidates data is empty")


def reject_existing_capital_fields(
    candidates: pd.DataFrame,
    overwrite_capital_fields: bool,
) -> None:
    present = [field for field in CAPITAL_FIELDS if field in candidates]
    if present and not overwrite_capital_fields:
        raise ValueError(f"candidates already contain capital fields: {', '.join(present)}")


def signal_quotes(prices: pd.DataFrame) -> pd.DataFrame:
    result = prices.copy()
    result["symbol"] = result["symbol"].astype(str)
    result["_signal_date"] = parse_dates(result["date"])
    result["signal_close"] = pd.to_numeric(result["close"], errors="coerce")
    result = result.dropna(subset=["symbol", "_signal_date", "signal_close"])
    if (result["signal_close"] <= 0).any():
        raise ValueError("signal close must be > 0")
    quotes = result[["symbol", "_signal_date", "signal_close"]]
    if quotes.duplicated(["symbol", "_signal_date"]).any():
        raise ValueError("prices contain duplicate symbol/date rows")
    return quotes


def validate_candidate_close(frame: pd.DataFrame, tolerance: float) -> None:
    if "close" not in frame:
        return
    candidate_close = pd.to_numeric(frame["close"], errors="coerce")
    if candidate_close.isna().any():
        raise ValueError("candidate close must be numeric when provided")
    diff = (candidate_close - frame["signal_close"]).abs()
    if (diff > tolerance).any():
        raise ValueError("candidate close differs from price signal close")


def build_summary(frame: pd.DataFrame, cash_budget: float, lot_size: int) -> dict[str, Any]:
    total_reserved = float(frame["cash_reserved"].sum())
    return {
        "candidates": int(len(frame)),
        "allocated_candidates": int((frame["quantity"] > 0).sum()),
        "unallocated_candidates": int((frame["quantity"] <= 0).sum()),
        "cash_budget": float(cash_budget),
        "lot_size": int(lot_size),
        "total_cash_reserved": total_reserved,
        "cash_remaining": float(cash_budget - total_reserved),
        "max_weight": float(frame["weight"].max()),
        "capital_model": "equal_cash_budget_lot_floor",
    }


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def print_summary(summary: dict[str, Any], output: str, prefix: str = "OK") -> None:
    print(
        f"{prefix}: candidates={summary['candidates']} "
        f"allocated_candidates={summary['allocated_candidates']} "
        f"unallocated_candidates={summary['unallocated_candidates']} "
        f"cash_budget={summary['cash_budget']} "
        f"total_cash_reserved={summary['total_cash_reserved']} "
        f"cash_remaining={summary['cash_remaining']} "
        f"capital_model={summary['capital_model']} output={output}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
