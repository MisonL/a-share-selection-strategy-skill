"""Portfolio-aware candidate allocation helpers."""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from a_share_selection_capital import SIZING_FIELDS
from a_share_selection_data import parse_dates
from validate_ohlcv import validate_frame


CAPITAL_MODEL = "portfolio_cash_lot_floor"
CAPITAL_COLUMNS = SIZING_FIELDS


def allocate_portfolio(
    prices: pd.DataFrame,
    candidate_frames: list[pd.DataFrame],
    *,
    expected_signal_dates: list[str] | None = None,
    cash_budget: float,
    lot_size: int,
    hold_days: int,
    max_open_positions: int,
    max_gross_weight: float,
    max_gross_notional: float,
    max_cash_reserved: float,
    fail_on_symbol_overlap: bool,
    close_tolerance: float = 0.000001,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame], pd.DataFrame, dict[str, Any]]:
    validate_args(candidate_frames, expected_signal_dates, cash_budget, lot_size, hold_days, max_open_positions, max_gross_weight, max_gross_notional, max_cash_reserved, close_tolerance)
    price_frame = prepare_prices(prices)
    raw = prepare_candidates(candidate_frames, expected_signal_dates)
    validate_candidate_closes(raw, price_frame, close_tolerance)
    selected_rows: list[dict[str, Any]] = []
    sized_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    daily: dict[str, dict[str, Any]] = {}
    for row in raw.to_dict("records"):
        decision = allocation_decision(row, price_frame, daily, cash_budget=cash_budget, lot_size=lot_size, hold_days=hold_days, max_open_positions=max_open_positions, max_gross_weight=max_gross_weight, max_gross_notional=max_gross_notional, max_cash_reserved=max_cash_reserved, fail_on_symbol_overlap=fail_on_symbol_overlap)
        if decision["skip_reason"]:
            skipped_rows.append({**row, "skip_reason": decision["skip_reason"]})
            continue
        selected_rows.append(row)
        sized_rows.append({**row, **decision["capital"]})
        update_daily(daily, decision["active_dates"], str(row["symbol"]), decision["capital"])
    options = {
        "cash_budget": cash_budget,
        "lot_size": lot_size,
        "hold_days": hold_days,
        "max_open_positions": max_open_positions,
        "max_gross_weight": max_gross_weight,
        "max_gross_notional": max_gross_notional,
        "max_cash_reserved": max_cash_reserved,
        "fail_on_symbol_overlap": fail_on_symbol_overlap,
    }
    return partition_outputs(candidate_frames, selected_rows, sized_rows, skipped_rows, raw, daily, options)


def validate_args(candidate_frames: list[pd.DataFrame], expected_signal_dates: list[str] | None, cash_budget: float, lot_size: int, hold_days: int, max_open_positions: int, max_gross_weight: float, max_gross_notional: float, max_cash_reserved: float, close_tolerance: float) -> None:
    if not candidate_frames:
        raise ValueError("at least one candidate file is required")
    if expected_signal_dates is not None and len(expected_signal_dates) != len(candidate_frames):
        raise ValueError("expected-signal-dates count must match candidate file count")
    checks = {
        "cash-budget": cash_budget,
        "max-gross-weight": max_gross_weight,
        "max-gross-notional": max_gross_notional,
        "max-cash-reserved": max_cash_reserved,
    }
    for name, value in checks.items():
        if value <= 0:
            raise ValueError(f"{name} must be > 0")
    if lot_size < 1 or hold_days < 1 or max_open_positions < 1:
        raise ValueError("lot-size, hold-days, and max-open-positions must be >= 1")
    if close_tolerance < 0:
        raise ValueError("close-tolerance must be >= 0")


def prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    errors = validate_frame(prices, min_history_rows=0)
    if errors:
        raise ValueError("; ".join(errors))
    result = prices.copy()
    result["symbol"] = result["symbol"].astype(str)
    result["date"] = parse_dates(result["date"])
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    result = result.dropna(subset=["symbol", "date", "close"])
    if (result["close"] <= 0).any():
        raise ValueError("price close must be > 0")
    if result.duplicated(["symbol", "date"]).any():
        raise ValueError("prices contain duplicate symbol/date rows")
    return result.sort_values(["symbol", "date"]).reset_index(drop=True)


def prepare_candidates(frames: list[pd.DataFrame], expected_signal_dates: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for source_index, frame in enumerate(frames):
        missing = [column for column in ["symbol", "date"] if column not in frame]
        if missing:
            raise ValueError(f"candidates missing required columns: {', '.join(missing)}")
        reject_existing_sizing_fields(frame)
        current = frame.copy().reset_index(drop=True)
        current["symbol"] = current["symbol"].astype(str)
        current["_source_index"] = source_index
        current["_row_order"] = range(len(current))
        current["_signal_date"] = parse_dates(current["date"])
        validate_source_signal_date(current, source_index, expected_signal_dates)
        rows.append(current)
    raw = pd.concat(rows, ignore_index=True)
    if raw.empty:
        raise ValueError("candidates data is empty")
    if raw["_signal_date"].isna().any():
        raise ValueError("candidate dates must be parseable")
    if raw.duplicated(["symbol", "_signal_date"]).any():
        raise ValueError("candidates contain duplicate symbol/date rows")
    sort_columns = [name for name in ["_signal_date", "rank", "_source_index", "_row_order"] if name in raw]
    return raw.sort_values(sort_columns).reset_index(drop=True)


def reject_existing_sizing_fields(frame: pd.DataFrame) -> None:
    present = [field for field in SIZING_FIELDS if field in frame]
    if present:
        raise ValueError(f"candidates already contain sizing fields: {', '.join(present)}")


def validate_source_signal_date(
    frame: pd.DataFrame,
    source_index: int,
    expected_signal_dates: list[str] | None,
) -> None:
    if expected_signal_dates is None:
        return
    actual_dates = frame["_signal_date"]
    if actual_dates.isna().any():
        raise ValueError("candidate dates must be parseable")
    expected = parse_dates(pd.Series([expected_signal_dates[source_index]])).iloc[0]
    if pd.isna(expected):
        raise ValueError("expected-signal-dates must be parseable")
    expected_text = expected.date().isoformat()
    actual = sorted(actual_dates.dt.date.astype(str).unique())
    if actual != [expected_text]:
        raise ValueError(
            f"candidate file {source_index} dates must match expected-signal-date={expected_text}; "
            f"found={','.join(actual)}"
        )


def validate_candidate_closes(raw: pd.DataFrame, prices: pd.DataFrame, tolerance: float) -> None:
    if "close" not in raw:
        return
    quotes = prices.rename(columns={"date": "_signal_date", "close": "signal_close"})
    merged = raw.merge(quotes[["symbol", "_signal_date", "signal_close"]], on=["symbol", "_signal_date"], how="left")
    if merged["signal_close"].isna().any():
        raise ValueError("missing signal close for candidates")
    candidate_close = pd.to_numeric(merged["close"], errors="coerce")
    if candidate_close.isna().any():
        raise ValueError("candidate close must be numeric when provided")
    if ((candidate_close - merged["signal_close"]).abs() > tolerance).any():
        raise ValueError("candidate close differs from price signal close")


def allocation_decision(row: dict[str, Any], prices: pd.DataFrame, daily: dict[str, dict[str, Any]], *, cash_budget: float, lot_size: int, hold_days: int, max_open_positions: int, max_gross_weight: float, max_gross_notional: float, max_cash_reserved: float, fail_on_symbol_overlap: bool) -> dict[str, Any]:
    history = prices[prices["symbol"] == str(row["symbol"])].reset_index(drop=True)
    entry_positions = history.index[history["date"] == row["_signal_date"]].tolist()
    if not entry_positions:
        return skip("missing_entry_price")
    entry_pos = int(entry_positions[0])
    exit_pos = entry_pos + hold_days
    if exit_pos >= len(history):
        return skip("missing_future_price")
    active_dates = business_dates(history.iloc[entry_pos]["date"], history.iloc[exit_pos]["date"])
    reason = capacity_skip_reason(row, active_dates, daily, max_open_positions, fail_on_symbol_overlap)
    if reason:
        return skip(reason)
    remaining = remaining_cash(active_dates, daily, cash_budget, max_gross_weight, max_gross_notional, max_cash_reserved)
    signal_close = float(history.iloc[entry_pos]["close"])
    slot = min(cash_budget / max_open_positions, remaining)
    quantity = int(slot / (signal_close * lot_size)) * lot_size
    if quantity <= 0:
        return skip("insufficient_cash_slot")
    cash_reserved = float(quantity * signal_close)
    capital = capital_fields(cash_budget, lot_size, signal_close, slot, quantity, cash_reserved)
    return {"skip_reason": "", "active_dates": active_dates, "capital": capital}


def capacity_skip_reason(row: dict[str, Any], active_dates: list[str], daily: dict[str, dict[str, Any]], max_open_positions: int, fail_on_symbol_overlap: bool) -> str:
    symbol = str(row["symbol"])
    for date in active_dates:
        state = daily.get(date, empty_day())
        if state["open_positions"] >= max_open_positions:
            return "max_open_positions"
        if fail_on_symbol_overlap and symbol in state["symbols"]:
            return "symbol_overlap"
    return ""


def remaining_cash(active_dates: list[str], daily: dict[str, dict[str, Any]], cash_budget: float, max_gross_weight: float, max_gross_notional: float, max_cash_reserved: float) -> float:
    limit = min(cash_budget, max_gross_weight * cash_budget, max_gross_notional, max_cash_reserved)
    values = []
    for date in active_dates:
        state = daily.get(date, empty_day())
        used = max(float(state["gross_notional"]), float(state["cash_reserved"]))
        values.append(limit - used)
    return max(0.0, min(values))


def capital_fields(cash_budget: float, lot_size: int, signal_close: float, slot: float, quantity: int, cash_reserved: float) -> dict[str, Any]:
    return {
        "cash_budget": float(cash_budget),
        "lot_size": int(lot_size),
        "capital_model": CAPITAL_MODEL,
        "signal_close": signal_close,
        "cash_slot": float(slot),
        "quantity": int(quantity),
        "cash_reserved": cash_reserved,
        "notional": cash_reserved,
        "weight": cash_reserved / cash_budget,
        "unallocated": False,
    }


def update_daily(daily: dict[str, dict[str, Any]], active_dates: list[str], symbol: str, capital: dict[str, Any]) -> None:
    for date in active_dates:
        state = daily.setdefault(date, empty_day())
        state["open_positions"] += 1
        state["gross_notional"] += float(capital["notional"])
        state["cash_reserved"] += float(capital["cash_reserved"])
        state["symbols"].add(symbol)


def partition_outputs(frames: list[pd.DataFrame], selected_rows: list[dict[str, Any]], sized_rows: list[dict[str, Any]], skipped_rows: list[dict[str, Any]], raw: pd.DataFrame, daily: dict[str, dict[str, Any]], options: dict[str, Any]) -> tuple[list[pd.DataFrame], list[pd.DataFrame], pd.DataFrame, dict[str, Any]]:
    selected = partition_rows(frames, selected_rows)
    sized = partition_rows(frames, sized_rows, extra_columns=CAPITAL_COLUMNS)
    skipped = public_frame(skipped_rows)
    return selected, sized, skipped, build_summary(raw, selected, skipped_rows, daily, options)


def partition_rows(frames: list[pd.DataFrame], rows: list[dict[str, Any]], extra_columns: list[str] | None = None) -> list[pd.DataFrame]:
    result = []
    for source_index, frame in enumerate(frames):
        current = [row for row in rows if row.get("_source_index") == source_index]
        result.append(public_frame(current, columns=list(frame.columns) + (extra_columns or [])))
    return result


def build_summary(raw: pd.DataFrame, selected: list[pd.DataFrame], skipped_rows: list[dict[str, Any]], daily: dict[str, dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    reason_counts = Counter(row["skip_reason"] for row in skipped_rows)
    summary = {
        "schema_version": 1,
        "allocation_model": CAPITAL_MODEL,
        "raw_candidates": int(len(raw)),
        "allocated_candidates": int(sum(len(frame) for frame in selected)),
        "skipped_candidates": int(len(skipped_rows)),
        "skip_reason_counts": dict(sorted(reason_counts.items())),
        "signals": signal_counts(raw, selected, skipped_rows),
        "max_open_positions": max((state["open_positions"] for state in daily.values()), default=0),
        "max_gross_weight": max((state["gross_notional"] / options["cash_budget"] for state in daily.values()), default=0.0),
        "max_gross_notional": max((state["gross_notional"] for state in daily.values()), default=0.0),
        "max_cash_reserved": max((state["cash_reserved"] for state in daily.values()), default=0.0),
    }
    summary.update(option_fields(options))
    return summary


def option_fields(options: dict[str, Any]) -> dict[str, Any]:
    return {
        "cash_budget": options["cash_budget"],
        "lot_size": options["lot_size"],
        "hold_days": options["hold_days"],
        "max_open_positions_limit": options["max_open_positions"],
        "max_gross_weight_limit": options["max_gross_weight"],
        "max_gross_notional_limit": options["max_gross_notional"],
        "max_cash_reserved_limit": options["max_cash_reserved"],
        "fail_on_symbol_overlap": options["fail_on_symbol_overlap"],
    }


def signal_counts(raw: pd.DataFrame, selected: list[pd.DataFrame], skipped_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for source_index, group in raw.groupby("_source_index", sort=True):
        result.append(
            {
                "signal_date": str(group["_signal_date"].iloc[0].date()),
                "raw_candidates": int(len(group)),
                "allocated_candidates": int(len(selected[int(source_index)])),
                "skipped_candidates": sum(1 for row in skipped_rows if row["_source_index"] == source_index),
            }
        )
    return result


def public_frame(rows: list[dict[str, Any]], columns: list[str] | None = None) -> pd.DataFrame:
    clean = [{key: value for key, value in row.items() if not str(key).startswith("_")} for row in rows]
    return pd.DataFrame(clean, columns=columns)


def business_dates(entry: Any, exit_date: Any) -> list[str]:
    return [date.date().isoformat() for date in pd.bdate_range(entry, exit_date)]


def empty_day() -> dict[str, Any]:
    return {"open_positions": 0, "gross_notional": 0.0, "cash_reserved": 0.0, "symbols": set()}


def skip(reason: str) -> dict[str, Any]:
    return {"skip_reason": reason, "active_dates": [], "capital": {}}
