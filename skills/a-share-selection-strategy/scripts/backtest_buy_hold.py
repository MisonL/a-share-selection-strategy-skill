#!/usr/bin/env python3
"""Run a minimal close-to-close buy-hold backtest from local files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BacktestOptions:
    holding_days: int
    cost_bps: float
    slippage_bps: float
    require_tradable_bars: bool
    require_holding_period_tradable: bool = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a minimal close-to-close buy-hold backtest. This is a local "
            "baseline, not a promise of future returns or real tradability. "
            "Without --fail-on-incomplete, incomplete output is not a successful backtest."
        )
    )
    parser.add_argument("--prices", required=True, help="Path to OHLCV CSV/Parquet.")
    parser.add_argument("--candidates", required=True, help="Path to candidates CSV.")
    parser.add_argument("--output", required=True, help="Path to output CSV.")
    parser.add_argument("--hold-days", "--holding-days", dest="hold_days", type=int, default=5)
    parser.add_argument("--cost-bps", type=float, default=0.0, help="Round-trip cost in basis points.")
    parser.add_argument("--slippage-bps", type=float, default=0.0, help="Round-trip slippage in basis points.")
    parser.add_argument("--require-tradable-bars", action="store_true")
    parser.add_argument(
        "--require-tradable-holding-period",
        action="store_true",
        help="Require tradestatus=1 for every observed bar from entry through exit.",
    )
    parser.add_argument(
        "--expected-signal-date",
        help="Require every candidate date to match this signal date.",
    )
    parser.add_argument("--fail-on-incomplete", action="store_true")
    args = parser.parse_args(argv)
    try:
        ensure_runtime_dependencies()
        result, summary = run_backtest(
            read_table(Path(args.prices)),
            read_table(Path(args.candidates)),
            hold_days=args.hold_days,
            cost_bps=args.cost_bps,
            slippage_bps=args.slippage_bps,
            require_tradable_bars=args.require_tradable_bars,
            require_holding_period_tradable=args.require_tradable_holding_period,
            expected_signal_date=args.expected_signal_date,
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


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import a_share_selection_backtest_rows as row_module
    import a_share_selection_capital as capital_module
    import a_share_selection_data as data_module
    import a_share_selection_tradability as tradability_module
    import validate_ohlcv as validator_module

    globals().update(
        {
            "pd": pandas_module,
            "LIMIT_RULES_MODEL": row_module.LIMIT_RULES_MODEL,
            "add_candidate_capital_fields": capital_module.add_candidate_capital_fields,
            "build_summary": row_module.build_summary,
            "completed_or_incomplete_row": row_module.completed_or_incomplete_row,
            "incomplete_row": row_module.incomplete_row,
            "parse_dates": data_module.parse_dates,
            "read_table": data_module.read_table,
            "tradability_failure_reason": tradability_module.tradability_failure_reason,
            "validate_frame": validator_module.validate_frame,
        }
    )


def run_backtest(
    prices: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    hold_days: int,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    require_tradable_bars: bool = False,
    require_holding_period_tradable: bool = False,
    expected_signal_date: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
    if hold_days < 1:
        raise ValueError("hold-days must be >= 1")
    if cost_bps < 0:
        raise ValueError("cost-bps must be >= 0")
    if slippage_bps < 0:
        raise ValueError("slippage-bps must be >= 0")
    price_errors = validate_frame(prices, min_history_rows=0)
    if price_errors:
        raise ValueError("; ".join(price_errors))
    validate_candidates(candidates)
    validate_expected_signal_date(candidates, expected_signal_date)
    prepared = prepare_prices(prices)
    options = BacktestOptions(
        holding_days=hold_days,
        cost_bps=cost_bps,
        slippage_bps=slippage_bps,
        require_tradable_bars=require_tradable_bars,
        require_holding_period_tradable=require_holding_period_tradable,
    )
    rows = [
        evaluate_candidate(row, prepared, options)
        for _, row in candidates.iterrows()
    ]
    result = add_candidate_capital_fields(pd.DataFrame(rows), candidates)
    return result, build_summary(
        result,
        hold_days,
        cost_bps,
        slippage_bps,
        options.require_tradable_bars,
        require_holding_period_tradable=options.require_holding_period_tradable,
    )


def validate_candidates(candidates: pd.DataFrame) -> None:
    missing = [column for column in ["symbol", "date"] if column not in candidates]
    if missing:
        raise ValueError(f"candidates missing required columns: {', '.join(missing)}")
    if candidates.empty:
        raise ValueError("candidates data is empty")


def validate_expected_signal_date(candidates: pd.DataFrame, expected: str | None) -> None:
    if expected is None:
        return
    expected_date = parse_dates(pd.Series([expected])).iloc[0]
    if pd.isna(expected_date):
        raise ValueError("expected-signal-date must be parseable")
    actual_dates = parse_dates(candidates["date"])
    if actual_dates.isna().any():
        raise ValueError("candidate dates must be parseable")
    expected_text = expected_date.date().isoformat()
    actual = sorted(actual_dates.dt.date.astype(str).unique())
    if actual != [expected_text]:
        raise ValueError(
            f"candidate dates must match expected-signal-date={expected_text}; "
            f"found={','.join(actual)}"
        )


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
    options: BacktestOptions,
) -> dict[str, Any]:
    symbol = str(row["symbol"])
    signal_date = parse_dates(pd.Series([row["date"]])).iloc[0]
    history = prices[prices["symbol"] == symbol].reset_index(drop=True)
    if pd.isna(signal_date) or history.empty:
        return missing_entry_row(row, symbol=symbol, options=options)
    entry_pos = entry_position(history, signal_date)
    if entry_pos is None:
        return missing_entry_row(
            row,
            symbol=symbol,
            options=options,
            signal_date=signal_date.date(),
        )
    failure = future_or_tradability_failure(
        history,
        entry_pos,
        options,
    )
    if failure["reason"]:
        return incomplete_row(
            symbol=symbol,
            signal_date=signal_date.date(),
            holding_days=options.holding_days,
            reason=failure["reason"],
            cost_bps=options.cost_bps,
            slippage_bps=options.slippage_bps,
            require_tradable_bars=options.require_tradable_bars,
            require_holding_period_tradable=options.require_holding_period_tradable,
        )
    return completed_from_signal(
        symbol=symbol,
        signal_date=signal_date,
        history=history,
        entry_pos=entry_pos,
        exit_pos=failure["exit_pos"],
        options=options,
    )


def missing_entry_row(
    row: pd.Series,
    *,
    symbol: str,
    options: BacktestOptions,
    signal_date: Any | None = None,
) -> dict[str, Any]:
    return incomplete_row(
        symbol=symbol,
        signal_date=signal_date or row["date"],
        holding_days=options.holding_days,
        reason="missing_entry_price",
        cost_bps=options.cost_bps,
        slippage_bps=options.slippage_bps,
        require_tradable_bars=options.require_tradable_bars,
        require_holding_period_tradable=options.require_holding_period_tradable,
    )


def completed_from_signal(
    *,
    symbol: str,
    signal_date: Any,
    history: pd.DataFrame,
    entry_pos: int,
    exit_pos: int,
    options: BacktestOptions,
) -> dict[str, Any]:
    return completed_or_incomplete_row(
        symbol=symbol,
        signal_date=signal_date.date(),
        history=history,
        entry_pos=entry_pos,
        exit_pos=exit_pos,
        holding_days=options.holding_days,
        cost_bps=options.cost_bps,
        slippage_bps=options.slippage_bps,
        require_tradable_bars=options.require_tradable_bars,
        require_holding_period_tradable=options.require_holding_period_tradable,
    )


def entry_position(history: pd.DataFrame, signal_date: Any) -> int | None:
    positions = history.index[history["date"] == signal_date].tolist()
    if not positions:
        return None
    return int(positions[0])


def future_or_tradability_failure(
    history: pd.DataFrame,
    entry_pos: int,
    options: BacktestOptions,
) -> dict[str, Any]:
    exit_pos = entry_pos + options.holding_days
    if exit_pos >= len(history):
        return {"reason": "missing_future_price", "exit_pos": exit_pos}
    if options.require_tradable_bars or options.require_holding_period_tradable:
        reason = tradability_failure_reason(
            history,
            entry_pos,
            exit_pos,
            require_holding_period=options.require_holding_period_tradable,
        )
        if reason:
            return {"reason": reason, "exit_pos": exit_pos}
    return {"reason": "", "exit_pos": exit_pos}


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def print_summary(summary: dict[str, Any], output: str, prefix: str = "OK") -> None:
    print(
        f"{prefix}: candidates={summary['candidates']} "
        f"completed_trades={summary['completed_trades']} "
        f"incomplete_trades={summary['incomplete_trades']} "
        f"hold_days={summary['hold_days']} "
        f"cost_bps={summary['cost_bps']} "
        f"slippage_bps={summary['slippage_bps']} "
        f"tradability_required={summary['tradability_required']} "
        f"tradability_model={summary['tradability_model']} output={output}"
    )
    if summary["missing_reason_counts"]:
        print(f"INFO: missing_reason_counts={summary['missing_reason_counts']}")
    if prefix == "OK" and summary["incomplete_trades"]:
        print(
            "WARNING: "
            f"incomplete_trades={summary['incomplete_trades']} "
            "claim_boundary=incomplete_output_not_successful_backtest "
            "use --fail-on-incomplete for strict gates"
        )
    print(
        "INFO: baseline=buy_hold_close_to_close "
        "cost_model=round_trip_bps slippage_model=round_trip_bps "
        f"tradability_model={summary['tradability_model']} "
        "suspension=missing_future_price "
        "tradability_gate=optional_tradestatus "
        f"limit_rules_model={LIMIT_RULES_MODEL}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
