#!/usr/bin/env python3
"""Report overlap and capacity gates from backtest CSV files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from stock_selection_data import parse_dates, read_table


REQUIRED_COLUMNS = ["symbol", "signal_date", "entry_date", "exit_date", "missing_data", "status"]
CAPITAL_FIELDS = ["weight", "notional", "quantity", "cash_reserved"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report portfolio position overlap gates.")
    parser.add_argument("--backtests", nargs="+", required=True, help="Backtest CSV/Parquet paths.")
    parser.add_argument("--daily-output", required=True, help="Daily open positions CSV path.")
    parser.add_argument("--overlap-output", required=True, help="Same-symbol overlap CSV path.")
    parser.add_argument("--summary-output", required=True, help="Summary JSON path.")
    parser.add_argument("--max-open-positions", type=int, default=None)
    parser.add_argument("--fail-on-symbol-overlap", action="store_true")
    parser.add_argument("--require-capital-fields", action="store_true")
    args = parser.parse_args(argv)
    try:
        frames = [read_table(Path(path)) for path in args.backtests]
        daily, overlaps, summary = build_overlap_report(frames)
        write_outputs(daily, overlaps, summary, args)
        violations = gate_violations(
            summary,
            max_open_positions=args.max_open_positions,
            fail_on_symbol_overlap=args.fail_on_symbol_overlap,
            require_capital_fields=args.require_capital_fields,
        )
        if violations:
            print_summary(summary, args.summary_output, prefix="ERROR_SUMMARY")
            print(
                "ERROR: strict gate failed; "
                + "; ".join(violations)
                + " output_written=true",
                file=sys.stderr,
            )
            return 3
    except Exception as exc:  # noqa: BLE001
        print(
            "ERROR: code=bad_input "
            f"output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(summary, args.summary_output)
    return 0


def build_overlap_report(
    frames: list[pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if not frames:
        raise ValueError("at least one backtest file is required")
    combined = prepare_trades(pd.concat(frames, ignore_index=True))
    complete = combined[is_complete_trade(combined)].copy()
    complete["entry_date"] = parse_dates(complete["entry_date"])
    complete["exit_date"] = parse_dates(complete["exit_date"])
    complete["signal_date"] = parse_dates(complete["signal_date"])
    if complete[["entry_date", "exit_date", "signal_date"]].isna().any().any():
        raise ValueError("complete trades must have parseable signal, entry, and exit dates")
    set_active_trade_context(complete)
    daily = daily_open_positions(complete)
    overlaps = same_symbol_overlaps(daily)
    summary = build_summary(combined, complete, daily, overlaps)
    return daily, overlaps, summary


def prepare_trades(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame]
    if missing:
        raise ValueError(f"backtest missing required columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("backtest data is empty")
    result = frame.copy()
    result["symbol"] = result["symbol"].astype(str)
    return result


def is_complete_trade(frame: pd.DataFrame) -> pd.Series:
    missing = frame["missing_data"].astype(str).str.lower().isin(["true", "1"])
    return (frame["status"].astype(str) == "complete") & (~missing)


def daily_open_positions(complete: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for index, row in complete.reset_index(drop=True).iterrows():
        entry = row["entry_date"]
        exit_date = row["exit_date"]
        if exit_date < entry:
            raise ValueError("exit_date must be >= entry_date")
        for date in pd.bdate_range(entry, exit_date):
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "symbol": row["symbol"],
                    "signal_date": row["signal_date"].date().isoformat(),
                    "entry_date": entry.date().isoformat(),
                    "exit_date": exit_date.date().isoformat(),
                    "trade_index": int(index),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["date", "open_positions", "symbols", "signal_dates"])
    expanded = pd.DataFrame(rows)
    return pd.DataFrame(
        {"date": date, **daily_row(group).to_dict()}
        for date, group in expanded.groupby("date", sort=True)
    )


def daily_row(group: pd.DataFrame) -> pd.Series:
    return pd.Series(
        {
            "open_positions": int(len(group)),
            "symbols": ",".join(sorted(group["symbol"].astype(str).unique())),
            "signal_dates": ",".join(sorted(group["signal_date"].astype(str).unique())),
            "trade_indices": ",".join(str(value) for value in sorted(group["trade_index"])),
        }
    )


def same_symbol_overlaps(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return empty_overlaps()
    rows = []
    for _, row in daily.iterrows():
        symbols = str(row["symbols"]).split(",") if row["symbols"] else []
        indices = [int(value) for value in str(row["trade_indices"]).split(",") if value]
        if len(symbols) == int(row["open_positions"]):
            continue
        rows.extend(overlap_rows_for_date(str(row["date"]), indices))
    return pd.DataFrame(rows) if rows else empty_overlaps()


def overlap_rows_for_date(date: str, trade_indices: list[int]) -> list[dict[str, Any]]:
    rows = []
    seen: dict[str, list[int]] = {}
    for index in trade_indices:
        symbol = str(active_trade_context[index]["symbol"])
        seen.setdefault(symbol, []).append(index)
    for symbol, indices in seen.items():
        if len(indices) <= 1:
            continue
        signal_dates = sorted(active_trade_context[index]["signal_date"] for index in indices)
        rows.append(
            {
                "date": date,
                "symbol": symbol,
                "open_positions": len(indices),
                "signal_dates": ",".join(signal_dates),
                "trade_indices": ",".join(str(index) for index in indices),
            }
        )
    return rows


active_trade_context: list[dict[str, Any]] = []


def set_active_trade_context(complete: pd.DataFrame) -> None:
    global active_trade_context
    context = complete.reset_index(drop=True).copy()
    context["signal_date"] = context["signal_date"].dt.date.astype(str)
    active_trade_context = context.to_dict("records")


def build_summary(
    combined: pd.DataFrame,
    complete: pd.DataFrame,
    daily: pd.DataFrame,
    overlaps: pd.DataFrame,
) -> dict[str, Any]:
    present = [field for field in CAPITAL_FIELDS if field in combined]
    missing = [field for field in CAPITAL_FIELDS if field not in combined]
    max_open = int(daily["open_positions"].max()) if not daily.empty else 0
    max_dates = daily.loc[daily["open_positions"] == max_open, "date"].astype(str).tolist()
    return {
        "trades": int(len(combined)),
        "complete_trades": int(len(complete)),
        "incomplete_trades": int(len(combined) - len(complete)),
        "calendar_model": "business_day_closed_interval",
        "daily_rows": int(len(daily)),
        "max_open_positions": max_open,
        "max_open_position_dates": max_dates,
        "same_symbol_overlap_rows": int(len(overlaps)),
        "same_symbol_overlap_symbols": sorted(overlaps["symbol"].unique().tolist())
        if not overlaps.empty
        else [],
        "capital_fields_present": present,
        "capital_fields_missing": missing,
        "cash_capacity_verifiable": not missing,
    }


def empty_overlaps() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["date", "symbol", "open_positions", "signal_dates", "trade_indices"]
    )


def gate_violations(
    summary: dict[str, Any],
    *,
    max_open_positions: int | None,
    fail_on_symbol_overlap: bool,
    require_capital_fields: bool,
) -> list[str]:
    violations = []
    if max_open_positions is not None and max_open_positions < 1:
        raise ValueError("max-open-positions must be >= 1")
    if max_open_positions is not None and summary["max_open_positions"] > max_open_positions:
        violations.append(
            f"max_open_positions={summary['max_open_positions']} limit={max_open_positions}"
        )
    if fail_on_symbol_overlap and summary["same_symbol_overlap_rows"]:
        violations.append(f"same_symbol_overlap_rows={summary['same_symbol_overlap_rows']}")
    if require_capital_fields and not summary["cash_capacity_verifiable"]:
        missing = ",".join(summary["capital_fields_missing"])
        violations.append(f"capital_fields_missing={missing}")
    return violations


def write_outputs(
    daily: pd.DataFrame,
    overlaps: pd.DataFrame,
    summary: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    Path(args.daily_output).parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(args.daily_output, index=False)
    overlaps.to_csv(args.overlap_output, index=False)
    Path(args.summary_output).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def print_summary(summary: dict[str, Any], output: str, prefix: str = "OK") -> None:
    print(
        f"{prefix}: trades={summary['trades']} "
        f"complete_trades={summary['complete_trades']} "
        f"incomplete_trades={summary['incomplete_trades']} "
        f"max_open_positions={summary['max_open_positions']} "
        f"same_symbol_overlap_rows={summary['same_symbol_overlap_rows']} "
        f"cash_capacity_verifiable={summary['cash_capacity_verifiable']} "
        f"calendar_model={summary['calendar_model']} "
        f"output={output}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
