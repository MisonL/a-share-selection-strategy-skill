"""Independent execution checks for walk-forward backtest artifacts."""

from __future__ import annotations

import math
from typing import Any

from lib.selection_core.a_share_selection_model_contracts import (
    TRADABILITY_MODEL_ENTRY_EXIT,
    TRADABILITY_MODEL_HOLDING_PERIOD,
)
from lib.walk_forward.date_checks import normalized_date_text


PRICE_FIELDS = ("symbol", "date", "open", "close")


def reference_price_index(
    rows: list[dict[str, str]],
) -> tuple[dict[str, list[dict[str, str]]], list[str]]:
    errors = required_column_errors(rows, PRICE_FIELDS, "prices")
    indexed: dict[str, list[dict[str, str]]] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        symbol = str(row.get("symbol", "")).strip()
        date = normalized_date_text(row.get("date", ""))
        if not symbol:
            errors.append("prices_empty_symbol")
            continue
        if date is None:
            errors.append(f"prices_invalid_date={row.get('date', '')}")
            continue
        key = (symbol, date)
        if key in seen:
            errors.append(f"prices_duplicate_symbol_date={symbol}:{date}")
            continue
        seen.add(key)
        if finite_positive(row.get("open")) is None:
            errors.append(f"prices_invalid_open={symbol}:{date}")
        if finite_positive(row.get("close")) is None:
            errors.append(f"prices_invalid_close={symbol}:{date}")
        indexed.setdefault(symbol, []).append({**row, "date": date})
    for history in indexed.values():
        history.sort(key=lambda row: row["date"])
    return indexed, sorted(set(errors))


def backtest_execution_errors(
    *,
    candidates: list[dict[str, str]],
    backtest: list[dict[str, str]],
    prices_by_symbol: dict[str, list[dict[str, str]]],
    signal_date: str,
    args: Any,
) -> list[str]:
    errors = []
    candidate_keys, candidate_errors = candidate_keys_for_signal(
        candidates, signal_date
    )
    backtest_keys, backtest_key_errors = backtest_keys_for_signal(backtest, signal_date)
    errors.extend(candidate_errors)
    errors.extend(backtest_key_errors)
    if candidate_keys != backtest_keys:
        errors.append(f"{signal_date}_candidate_backtest_keys_mismatch")
    for row in backtest:
        errors.extend(
            backtest_row_execution_errors(
                row=row,
                prices_by_symbol=prices_by_symbol,
                signal_date=signal_date,
                args=args,
            )
        )
    return sorted(set(errors))


def sized_execution_errors(
    *,
    sized: list[dict[str, str]],
    prices_by_symbol: dict[str, list[dict[str, str]]],
    signal_date: str,
    args: Any,
) -> list[str]:
    """Validate sizing execution and capital fields against the full price history."""
    errors = []
    _sized_keys, sized_key_errors = sized_keys_for_signal(sized, signal_date)
    errors.extend(sized_key_errors)
    for row in sized:
        errors.extend(
            sized_row_execution_errors(
                row=row,
                prices_by_symbol=prices_by_symbol,
                signal_date=signal_date,
                args=args,
            )
        )
    return sorted(set(errors))


def candidate_keys_for_signal(
    rows: list[dict[str, str]], signal_date: str
) -> tuple[set[tuple[str, str]], list[str]]:
    return artifact_keys(rows, signal_date, "candidates", "date")


def backtest_keys_for_signal(
    rows: list[dict[str, str]], signal_date: str
) -> tuple[set[tuple[str, str]], list[str]]:
    return artifact_keys(rows, signal_date, "backtest", "signal_date")


def sized_keys_for_signal(
    rows: list[dict[str, str]], signal_date: str
) -> tuple[set[tuple[str, str]], list[str]]:
    return artifact_keys(rows, signal_date, "sized", "date")


def artifact_keys(
    rows: list[dict[str, str]],
    signal_date: str,
    label: str,
    date_field: str,
) -> tuple[set[tuple[str, str]], list[str]]:
    keys: set[tuple[str, str]] = set()
    errors = []
    expected_date = normalized_date_text(signal_date)
    for row in rows:
        symbol = str(row.get("symbol", "")).strip()
        date = normalized_date_text(row.get(date_field, ""))
        if not symbol or date is None:
            errors.append(f"{signal_date}_{label}_invalid_key")
            continue
        key = (symbol, date)
        if key in keys:
            errors.append(f"{signal_date}_{label}_duplicate_symbol={symbol}")
            continue
        keys.add(key)
        if expected_date is None or date != expected_date:
            errors.append(
                f"{signal_date}_{label}_signal_date_mismatch={row.get(date_field, '')}"
            )
    return keys, errors


def backtest_row_execution_errors(
    *,
    row: dict[str, str],
    prices_by_symbol: dict[str, list[dict[str, str]]],
    signal_date: str,
    args: Any,
) -> list[str]:
    symbol, expected_signal_date, key_errors = backtest_identity_errors(
        row, signal_date
    )
    if key_errors:
        return key_errors
    errors = backtest_execution_contract_errors(row, signal_date, args)
    window, window_errors = backtest_reference_window(
        prices_by_symbol, symbol, expected_signal_date, signal_date, args
    )
    if window_errors:
        return [*errors, *window_errors]
    entry, exit_row, entry_pos, exit_pos = window
    errors.extend(
        entry_exit_date_errors(row, entry, exit_row, expected_signal_date, signal_date)
    )
    expected_entry, expected_exit, actual_entry, price_errors = entry_exit_price_errors(
        row, entry, exit_row, signal_date, args
    )
    errors.extend(price_errors)
    errors.extend(
        sizing_field_errors(
            row=row,
            expected_entry_date=entry["date"],
            expected_entry_price=expected_entry,
            expected_signal_date=expected_signal_date,
            signal_date=signal_date,
            args=args,
            execution_entry_price=actual_entry,
        )
    )
    errors.extend(holding_period_errors(row, entry_pos, exit_pos, signal_date, args))
    if expected_entry is not None and expected_exit is not None:
        expected_gross = expected_exit / expected_entry - 1.0
        expected_return = expected_gross - (args.cost_bps + args.slippage_bps) / 10000.0
        errors.extend(
            return_errors(row, signal_date, expected_gross, expected_return, args)
        )
    history = prices_by_symbol[symbol]
    errors.extend(tradability_errors(history, entry_pos, exit_pos, signal_date, args))
    return errors


def backtest_identity_errors(
    row: dict[str, str], signal_date: str
) -> tuple[str, str, list[str]]:
    symbol = str(row.get("symbol", "")).strip()
    row_signal_date = normalized_date_text(row.get("signal_date", ""))
    expected_signal_date = normalized_date_text(signal_date)
    if not symbol or row_signal_date is None or expected_signal_date is None:
        return symbol, "", [f"{signal_date}_backtest_invalid_key"]
    if row_signal_date != expected_signal_date:
        return (
            symbol,
            expected_signal_date,
            [
                f"{signal_date}_backtest_signal_date_mismatch={row.get('signal_date', '')}"
            ],
        )
    return symbol, expected_signal_date, []


def backtest_execution_contract_errors(
    row: dict[str, str], signal_date: str, args: Any
) -> list[str]:
    checks = {
        "execution_model": args.required_execution_model,
        "entry_price_field": "open",
        "exit_price_field": "close",
    }
    return [
        f"{signal_date}_{field}={row.get(field)}"
        for field, expected in checks.items()
        if row.get(field) != expected
    ]


def backtest_reference_window(
    prices_by_symbol: dict[str, list[dict[str, str]]],
    symbol: str,
    expected_signal_date: str,
    signal_date: str,
    args: Any,
) -> tuple[tuple[dict[str, str], dict[str, str], int, int] | None, list[str]]:
    history = prices_by_symbol.get(symbol, [])
    signal_pos = index_for_date(history, expected_signal_date)
    if signal_pos is None:
        return None, [f"{signal_date}_price_signal_missing={symbol}"]
    entry_pos = signal_pos + 1
    exit_pos = signal_pos + args.hold_days
    if entry_pos >= len(history):
        return None, [f"{signal_date}_missing_next_observed_bar={symbol}"]
    if exit_pos >= len(history):
        return None, [f"{signal_date}_missing_future_price={symbol}"]
    return (history[entry_pos], history[exit_pos], entry_pos, exit_pos), []


def entry_exit_date_errors(
    row: dict[str, str],
    entry: dict[str, str],
    exit_row: dict[str, str],
    expected_signal_date: str,
    signal_date: str,
) -> list[str]:
    errors = []
    entry_date = normalized_date_text(row.get("entry_date", ""))
    exit_date = normalized_date_text(row.get("exit_date", ""))
    if entry_date != entry["date"]:
        errors.append(f"{signal_date}_entry_date={row.get('entry_date')}")
    if entry_date is None or entry_date <= expected_signal_date:
        errors.append(f"{signal_date}_entry_not_after_signal={row.get('entry_date')}")
    if exit_date != exit_row["date"]:
        errors.append(f"{signal_date}_exit_date={row.get('exit_date')}")
    if exit_date is None or entry_date is None or exit_date < entry_date:
        errors.append(f"{signal_date}_exit_before_entry={row.get('exit_date')}")
    return errors


def entry_exit_price_errors(
    row: dict[str, str],
    entry: dict[str, str],
    exit_row: dict[str, str],
    signal_date: str,
    args: Any,
) -> tuple[float | None, float | None, float | None, list[str]]:
    symbol = str(row.get("symbol", ""))
    expected_entry = finite_positive(entry.get("open"))
    expected_exit = finite_positive(exit_row.get("close"))
    actual_entry = finite_positive(row.get("entry_price"))
    actual_exit = finite_positive(row.get("exit_price"))
    errors = []
    if expected_entry is None:
        errors.append(f"{signal_date}_invalid_reference_entry_open={symbol}")
    if expected_exit is None:
        errors.append(f"{signal_date}_invalid_reference_exit_close={symbol}")
    if actual_entry is None:
        errors.append(f"{signal_date}_entry_price={row.get('entry_price')}")
    elif expected_entry is not None and not close_enough(
        actual_entry, expected_entry, args
    ):
        errors.append(f"{signal_date}_entry_price_mismatch={symbol}")
    if actual_exit is None:
        errors.append(f"{signal_date}_exit_price={row.get('exit_price')}")
    elif expected_exit is not None and not close_enough(
        actual_exit, expected_exit, args
    ):
        errors.append(f"{signal_date}_exit_price_mismatch={symbol}")
    return expected_entry, expected_exit, actual_entry, errors


def holding_period_errors(
    row: dict[str, str],
    entry_pos: int,
    exit_pos: int,
    signal_date: str,
    args: Any,
) -> list[str]:
    expected_period = exit_pos - entry_pos
    expected_bars = expected_period + 1
    errors = []
    if integer_value(row.get("holding_period")) != expected_period:
        errors.append(f"{signal_date}_holding_period={row.get('holding_period')}")
    if integer_value(row.get("holding_observed_bars")) != expected_bars:
        errors.append(
            f"{signal_date}_holding_observed_bars={row.get('holding_observed_bars')}"
        )
    if integer_value(row.get("hold_days_requested")) != args.hold_days:
        errors.append(
            f"{signal_date}_hold_days_requested={row.get('hold_days_requested')}"
        )
    return errors


def sized_row_execution_errors(
    *,
    row: dict[str, str],
    prices_by_symbol: dict[str, list[dict[str, str]]],
    signal_date: str,
    args: Any,
) -> list[str]:
    errors = []
    symbol = str(row.get("symbol", "")).strip()
    row_signal_date = normalized_date_text(row.get("date", ""))
    expected_signal_date = normalized_date_text(signal_date)
    if not symbol or row_signal_date is None or expected_signal_date is None:
        return [f"{signal_date}_sized_invalid_key"]
    if row_signal_date != expected_signal_date:
        return [f"{signal_date}_sized_signal_date_mismatch={row.get('date', '')}"]
    history = prices_by_symbol.get(symbol, [])
    signal_pos = index_for_date(history, expected_signal_date)
    if signal_pos is None:
        return [f"{signal_date}_sized_price_signal_missing={symbol}"]
    entry_pos = signal_pos + 1
    if entry_pos >= len(history):
        return [f"{signal_date}_sized_missing_next_observed_bar={symbol}"]
    entry = history[entry_pos]
    expected_entry = finite_positive(entry.get("open"))
    if expected_entry is None:
        return [f"{signal_date}_sized_invalid_reference_entry_open={symbol}"]
    errors.extend(
        sizing_field_errors(
            row=row,
            expected_entry_date=entry["date"],
            expected_entry_price=expected_entry,
            expected_signal_date=expected_signal_date,
            signal_date=signal_date,
            args=args,
        )
    )
    return errors


def sizing_field_errors(
    *,
    row: dict[str, str],
    expected_entry_date: str,
    expected_entry_price: float | None,
    expected_signal_date: str,
    signal_date: str,
    args: Any,
    execution_entry_price: float | None = None,
) -> list[str]:
    errors = []
    if row.get("sizing_execution_model") != args.required_execution_model:
        errors.append(
            f"{signal_date}_sizing_execution_model={row.get('sizing_execution_model')}"
        )
    if row.get("sizing_entry_price_field") != "open":
        errors.append(
            f"{signal_date}_sizing_entry_price_field="
            f"{row.get('sizing_entry_price_field')}"
        )
    if row.get("sizing_skip_reason", ""):
        errors.append(
            f"{signal_date}_sizing_skip_reason={row.get('sizing_skip_reason')}"
        )
    sizing_date = normalized_date_text(row.get("sizing_entry_date", ""))
    if sizing_date != expected_entry_date:
        errors.append(f"{signal_date}_sizing_entry_date={row.get('sizing_entry_date')}")
    if sizing_date is None or sizing_date <= expected_signal_date:
        errors.append(
            f"{signal_date}_sizing_entry_not_after_signal={row.get('sizing_entry_date')}"
        )
    sizing_price = finite_positive(row.get("sizing_entry_price"))
    if sizing_price is None:
        errors.append(
            f"{signal_date}_sizing_entry_price={row.get('sizing_entry_price')}"
        )
    elif expected_entry_price is not None and not close_enough(
        sizing_price, expected_entry_price, args
    ):
        errors.append(f"{signal_date}_sizing_entry_price_mismatch={row.get('symbol')}")
    if (
        execution_entry_price is not None
        and sizing_price is not None
        and not close_enough(execution_entry_price, sizing_price, args)
    ):
        errors.append(
            f"{signal_date}_backtest_sizing_entry_price_mismatch={row.get('symbol')}"
        )
    errors.extend(capital_equation_errors(row, sizing_price, signal_date, args))
    return errors


def capital_equation_errors(
    row: dict[str, str],
    sizing_price: float | None,
    signal_date: str,
    args: Any,
) -> list[str]:
    quantity = integer_value(row.get("quantity"))
    lot_size = integer_value(row.get("lot_size"))
    cash_reserved = finite_number(row.get("cash_reserved"))
    notional = finite_number(row.get("notional"))
    weight = finite_number(row.get("weight"))
    cash_budget = finite_positive(row.get("cash_budget"))
    cash_slot = finite_positive(row.get("cash_slot"))
    errors = []
    if quantity is None or quantity <= 0:
        errors.append(f"{signal_date}_quantity={row.get('quantity')}")
    if lot_size is None or lot_size < 1:
        errors.append(f"{signal_date}_lot_size={row.get('lot_size')}")
    elif quantity is not None and quantity > 0 and quantity % lot_size != 0:
        errors.append(f"{signal_date}_quantity_not_lot_multiple")
    if cash_reserved is None or cash_reserved < 0:
        errors.append(f"{signal_date}_cash_reserved={row.get('cash_reserved')}")
    if (
        notional is None
        or cash_reserved is None
        or not close_enough(notional, cash_reserved, args)
    ):
        errors.append(f"{signal_date}_notional_cash_reserved_mismatch")
    if cash_budget is None or weight is None or cash_reserved is None:
        errors.append(f"{signal_date}_weight_or_budget_invalid")
    elif not close_enough(weight, cash_reserved / cash_budget, args):
        errors.append(f"{signal_date}_weight_cash_reserved_mismatch")
    if (
        cash_slot is None
        or cash_reserved is None
        or cash_reserved > cash_slot + args.backtest_value_tolerance
    ):
        errors.append(f"{signal_date}_cash_reserved_exceeds_slot")
    elif (
        cash_budget is not None
        and cash_slot > cash_budget + args.backtest_value_tolerance
    ):
        errors.append(f"{signal_date}_cash_slot_exceeds_budget")
    if (
        cash_budget is not None
        and cash_reserved is not None
        and cash_reserved > cash_budget + args.backtest_value_tolerance
    ):
        errors.append(f"{signal_date}_cash_reserved_exceeds_budget")
    if quantity is not None and sizing_price is not None and cash_reserved is not None:
        if not close_enough(cash_reserved, quantity * sizing_price, args):
            errors.append(f"{signal_date}_cash_reserved_entry_price_mismatch")
    return errors


def index_for_date(history: list[dict[str, str]], date: str) -> int | None:
    for index, row in enumerate(history):
        if row["date"] == date:
            return index
    return None


def return_errors(
    row: dict[str, str],
    signal_date: str,
    expected_gross: float,
    expected_return: float,
    args: Any,
) -> list[str]:
    errors = []
    gross = finite_number(row.get("gross_return"))
    if gross is None or not close_enough(gross, expected_gross, args):
        errors.append(f"{signal_date}_gross_return={row.get('gross_return')}")
    net = finite_number(row.get("return"))
    if net is None or not close_enough(net, expected_return, args):
        errors.append(f"{signal_date}_return={row.get('return')}")
    return errors


def tradability_errors(
    history: list[dict[str, str]],
    entry_pos: int,
    exit_pos: int,
    signal_date: str,
    args: Any,
) -> list[str]:
    model = args.required_tradability_model
    if model not in (TRADABILITY_MODEL_ENTRY_EXIT, TRADABILITY_MODEL_HOLDING_PERIOD):
        return []
    required_rows = [history[entry_pos], history[exit_pos]]
    if model == TRADABILITY_MODEL_HOLDING_PERIOD:
        required_rows = history[entry_pos : exit_pos + 1]
    if any(
        "tradestatus" not in row or row.get("tradestatus", "") == ""
        for row in required_rows
    ):
        return [f"{signal_date}_backtest_missing_tradestatus"]
    if model == TRADABILITY_MODEL_ENTRY_EXIT:
        if not tradable(history[entry_pos].get("tradestatus")):
            return [f"{signal_date}_backtest_non_tradable_entry"]
        if not tradable(history[exit_pos].get("tradestatus")):
            return [f"{signal_date}_backtest_non_tradable_exit"]
        return []
    if not all(tradable(row.get("tradestatus")) for row in required_rows):
        return [f"{signal_date}_backtest_non_tradable_holding_period"]
    return []


def tradable(value: object) -> bool:
    return str(value).strip() == "1"


def required_column_errors(
    rows: list[dict[str, str]], columns: tuple[str, ...], label: str
) -> list[str]:
    fieldnames = set(rows[0]) if rows else set()
    return [
        f"{label}_missing_{column}" for column in columns if column not in fieldnames
    ]


def finite_positive(value: object) -> float | None:
    numeric = finite_number(value)
    return numeric if numeric is not None and numeric > 0 else None


def finite_number(value: object) -> float | None:
    try:
        numeric = float(str(value))
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def integer_value(value: object) -> int | None:
    number = finite_number(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def close_enough(left: float, right: float, args: Any) -> bool:
    return abs(left - right) <= args.backtest_value_tolerance
