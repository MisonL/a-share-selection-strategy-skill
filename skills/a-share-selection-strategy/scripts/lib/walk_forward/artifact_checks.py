"""Checks for walk-forward artifact contents."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from lib.walk_forward.backtest_checks import (
    backtest_execution_errors,
    reference_price_index,
    sized_execution_errors,
)
from lib.selection_core.a_share_selection_sizing_contracts import SIZING_FIELDS
from lib.walk_forward.metadata_checks import metadata_gate_errors
from lib.walk_forward.price_checks import signal_price_errors
from lib.walk_forward.allocation_checks import allocation_errors
from lib.walk_forward.date_checks import (
    date_after,
    normalized_date_text,
    same_calendar_date,
    same_date_list,
)


CAPITAL_FIELDS = ("weight", "notional", "quantity", "cash_reserved")
BACKTEST_FIELDS = (
    "symbol",
    "signal_date",
    "execution_model",
    "entry_date",
    "exit_date",
    "entry_price",
    "entry_price_field",
    "exit_price",
    "exit_price_field",
    "gross_return",
    "return",
    *SIZING_FIELDS,
    "status",
    "missing_data",
    "tradability_model",
    "limit_rules_model",
    "hold_days_requested",
    "holding_observed_bars",
    "holding_period",
    "cost_bps",
    "slippage_bps",
)
BACKTEST_NUMERIC_FIELDS = (
    "entry_price",
    "exit_price",
    "gross_return",
    "return",
    "cost_bps",
    "slippage_bps",
    "cash_budget",
    "lot_size",
    "signal_close",
    "cash_slot",
    "quantity",
    "cash_reserved",
    "notional",
    "weight",
    "sizing_entry_price",
)
OBSOLETE_BACKTEST_FIELDS = ("entry_close", "exit_close")
PRICE_COLUMNS = (
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turn",
    "tradestatus",
    "isST",
)
SIZED_COLUMNS = tuple(SIZING_FIELDS)
OVERLAP_INTEGER_CAPACITY_FIELDS = (
    "max_open_positions",
    "same_symbol_overlap_rows",
)
OVERLAP_DECIMAL_CAPACITY_FIELDS = (
    "max_gross_weight",
    "max_gross_notional",
    "max_cash_reserved",
)


def build_artifact_report(run_dir: Path, args: Any, validator: str) -> dict[str, Any]:
    dates = list(args.signal_dates)
    symbols = list(args.expected_symbols)
    errors = count_errors(dates, args.expected_candidates)
    summary = load_json(run_dir / "prediction_run_summary.json")
    errors += metadata_errors(load_json(run_dir / "metadata.json"), symbols, args)
    overlap = load_json(run_dir / "prediction_overlap_summary.json")
    overlap_is_object = isinstance(overlap, dict)
    if overlap_is_object:
        errors += allocation_errors(
            run_dir=run_dir,
            summary=summary,
            overlap=overlap,
            args=args,
            load_json=load_json,
            read_csv=read_csv,
        )
    errors += summary_errors(
        summary,
        dates,
        args.expected_candidates,
        args.required_execution_model,
    )
    prices_by_symbol, price_errors = reference_price_index(
        read_csv(run_dir / "prices.csv")
    )
    errors += price_errors
    totals = validate_signal_artifacts(
        run_dir, dates, symbols, args, errors, prices_by_symbol
    )
    errors += equity_errors(
        run_dir / "prediction_equity_curve.csv", summary, dates, args, totals
    )
    capacity_errors = (
        overlap_capacity_errors(overlap)
        if overlap_is_object
        else ["portfolio_overlap_summary_not_object"]
    )
    errors += overlap_errors(overlap, summary, args, capacity_errors)
    manifest_path = manifest_validation_path(run_dir, args)
    manifest_checked = manifest_path is not None
    if manifest_path is not None:
        errors += manifest_errors(load_json(manifest_path), dates)
    return report_view(
        run_dir,
        validator,
        dates,
        totals,
        summary,
        manifest_checked,
        args.required_execution_model,
        args.expected_portfolio_violations > 0,
        not capacity_errors,
        errors,
    )


def manifest_validation_path(run_dir: Path, args: Any) -> Path | None:
    if args.manifest_validation:
        return Path(args.manifest_validation)
    default_path = run_dir / "run_manifest_validation.json"
    return default_path if default_path.is_file() else None


def count_errors(dates: list[str], expected: list[int]) -> list[str]:
    if len(expected) != len(dates):
        return [f"expected_candidates_count={len(expected)} signal_dates={len(dates)}"]
    return []


def metadata_errors(
    metadata: dict[str, Any], symbols: list[str], args: Any
) -> list[str]:
    errors = []
    actual = [item.get("symbol") for item in metadata.get("symbols", [])]
    expected = {"source": "baostock", "adjustflag": "3"}
    for key, value in expected.items():
        if metadata.get(key) != value:
            errors.append(f"metadata_{key}={metadata.get(key)}")
    if metadata.get("requested_symbols") != symbols or actual != symbols:
        errors.append("metadata_symbols_mismatch")
    errors += metadata_gate_errors(
        metadata,
        len(symbols),
        allow_dropped_invalid_rows=args.allow_dropped_invalid_rows,
    )
    return errors


def summary_errors(
    summary: dict[str, Any],
    dates: list[str],
    expected: list[int],
    required_execution_model: str,
) -> list[str]:
    errors = []
    if summary.get("quality_errors") != []:
        errors.append(f"quality_errors={summary.get('quality_errors')}")
    if summary.get("execution_model") != required_execution_model:
        errors.append(f"summary_execution_model={summary.get('execution_model')}")
    signals = summary.get("signals", [])
    if not same_date_list([item.get("signal_date", "") for item in signals], dates):
        errors.append("summary_signal_dates_mismatch")
    for index, signal in enumerate(signals):
        if index < len(expected) and signal.get("candidates") != expected[index]:
            errors.append(
                f"summary_{signal.get('signal_date')}_candidates={signal.get('candidates')}"
            )
        if signal.get("completed_trades") != signal.get("candidates"):
            errors.append(f"summary_{signal.get('signal_date')}_completed_mismatch")
    return errors


def validate_signal_artifacts(
    run_dir: Path,
    dates: list[str],
    symbols: list[str],
    args: Any,
    errors: list[str],
    prices_by_symbol: dict[str, list[dict[str, str]]],
) -> dict[str, int]:
    totals = {"candidates": 0, "completed_trades": 0}
    for index, date in enumerate(dates):
        signal_dir = run_dir / "signals" / date
        expected = (
            args.expected_candidates[index]
            if index < len(args.expected_candidates)
            else 0
        )
        candidates = read_csv(signal_dir / "prediction_candidates.csv")
        sized = read_csv(signal_dir / "prediction_sized_candidates.csv")
        backtest = read_csv(signal_dir / "prediction_backtest.csv")
        prices = read_csv(signal_dir / "prices_signal_window.csv")
        errors += price_window_errors(prices, date, symbols)
        errors += prediction_errors(
            load_json(signal_dir / "prediction_summary.json"), date, len(symbols)
        )
        errors += candidate_errors(candidates, date, symbols, expected, "candidates")
        errors += candidate_errors(sized, date, symbols, expected, "sized")
        errors += signal_price_errors(candidates, sized, prices, date)
        errors += sized_errors(sized, date, args)
        errors += sized_execution_errors(
            sized=sized,
            prices_by_symbol=prices_by_symbol,
            signal_date=date,
            args=args,
        )
        errors += raw_candidate_errors(run_dir, date, len(candidates), args)
        errors += backtest_errors(
            backtest, candidates, prices_by_symbol, date, expected, args
        )
        errors += sizing_artifact_consistency_errors(sized, backtest, date, args)
        totals["candidates"] += len(candidates)
        totals["completed_trades"] += count_complete(backtest)
    return totals


def price_window_errors(
    rows: list[dict[str, str]], signal_date: str, symbols: list[str]
) -> list[str]:
    errors = required_column_errors(rows, PRICE_COLUMNS, f"{signal_date}_prices")
    if {row.get("symbol", "") for row in rows} != set(symbols):
        errors.append(f"{signal_date}_price_symbols_mismatch")
    if any(date_after(row.get("date", ""), signal_date) for row in rows):
        errors.append(f"{signal_date}_future_price_rows")
    return errors


def prediction_errors(
    summary: dict[str, Any], signal_date: str, symbol_count: int
) -> list[str]:
    errors = []
    expected = {
        "raw_symbols": symbol_count,
        "predicted_symbols": symbol_count,
        "skipped_symbols": 0,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"{signal_date}_prediction_{key}={summary.get(key)}")
    return errors


def candidate_errors(
    rows: list[dict[str, str]],
    signal_date: str,
    symbols: list[str],
    expected: int,
    label: str,
) -> list[str]:
    errors = []
    if len(rows) != expected:
        errors.append(f"{signal_date}_{label}_rows={len(rows)} expected={expected}")
    bad_dates = [
        row.get("date")
        for row in rows
        if not same_calendar_date(row.get("date", ""), signal_date)
    ]
    if bad_dates:
        errors.append(f"{signal_date}_{label}_date_mismatch={bad_dates[0]}")
    if not set(row.get("symbol", "") for row in rows).issubset(set(symbols)):
        errors.append(f"{signal_date}_{label}_symbol_outside_pool")
    return errors


def sized_errors(rows: list[dict[str, str]], signal_date: str, args: Any) -> list[str]:
    errors = required_column_errors(rows, SIZED_COLUMNS, f"{signal_date}_sized")
    expected_boundary = sizing_claim_boundary(args.required_allocation_model)
    for row in rows:
        if row.get("capital_model") != args.required_allocation_model:
            errors.append(f"{signal_date}_capital_model={row.get('capital_model')}")
        if float_value(row.get("cash_budget")) != args.cash_budget:
            errors.append(f"{signal_date}_cash_budget={row.get('cash_budget')}")
        if int(float_value(row.get("lot_size"))) != args.lot_size:
            errors.append(f"{signal_date}_lot_size={row.get('lot_size')}")
        if row.get("unallocated", "").lower() not in ("false", "0"):
            errors.append(f"{signal_date}_unallocated={row.get('unallocated')}")
        if row.get("sizing_claim_boundary") != expected_boundary:
            errors.append(
                f"{signal_date}_sizing_claim_boundary="
                f"{row.get('sizing_claim_boundary')}"
            )
        if row.get("sizing_execution_model") != args.required_execution_model:
            errors.append(
                f"{signal_date}_sizing_execution_model="
                f"{row.get('sizing_execution_model')}"
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
    return errors


def sizing_claim_boundary(allocation_model: str) -> str:
    if allocation_model == "portfolio_cash_lot_floor":
        return "local_portfolio_allocation_not_broker_or_external_cash_capacity_proof"
    return "local_sizing_not_broker_order"


SIZING_NUMERIC_FIELDS = frozenset(
    {
        "cash_budget",
        "lot_size",
        "signal_close",
        "cash_slot",
        "quantity",
        "cash_reserved",
        "notional",
        "weight",
        "sizing_entry_price",
    }
)


def sizing_artifact_consistency_errors(
    sized: list[dict[str, str]],
    backtest: list[dict[str, str]],
    signal_date: str,
    args: Any,
) -> list[str]:
    sized_by_key, sized_errors = sizing_rows_by_key(sized, signal_date, "sized", "date")
    backtest_by_key, backtest_errors = sizing_rows_by_key(
        backtest, signal_date, "backtest", "signal_date"
    )
    errors = [*sized_errors, *backtest_errors]
    if set(sized_by_key) != set(backtest_by_key):
        errors.append(f"{signal_date}_sized_backtest_keys_mismatch")
    for key in set(sized_by_key) & set(backtest_by_key):
        for field in SIZING_FIELDS:
            if not sizing_field_matches(
                field,
                sized_by_key[key].get(field),
                backtest_by_key[key].get(field),
                args,
            ):
                errors.append(f"{signal_date}_sizing_field_mismatch={field}:{key[0]}")
    return sorted(set(errors))


def sizing_rows_by_key(
    rows: list[dict[str, str]],
    signal_date: str,
    label: str,
    date_field: str,
) -> tuple[dict[tuple[str, str], dict[str, str]], list[str]]:
    expected_date = normalized_date_text(signal_date)
    result: dict[tuple[str, str], dict[str, str]] = {}
    errors = []
    for row in rows:
        symbol = str(row.get("symbol", "")).strip()
        date = normalized_date_text(row.get(date_field, ""))
        if not symbol or date is None:
            errors.append(f"{signal_date}_{label}_invalid_sizing_key")
            continue
        if expected_date is None or date != expected_date:
            errors.append(
                f"{signal_date}_{label}_sizing_signal_date_mismatch="
                f"{row.get(date_field, '')}"
            )
            continue
        key = (symbol, date)
        if key in result:
            errors.append(f"{signal_date}_{label}_duplicate_sizing_symbol={symbol}")
            continue
        result[key] = row
    return result, errors


def sizing_field_matches(field: str, left: object, right: object, args: Any) -> bool:
    if field in SIZING_NUMERIC_FIELDS:
        left_value = finite_number(left)
        right_value = finite_number(right)
        return (
            left_value is not None
            and right_value is not None
            and abs(left_value - right_value) <= args.backtest_value_tolerance
        )
    if field == "sizing_entry_date":
        return same_calendar_date(str(left or ""), str(right or ""))
    if field == "unallocated":
        return str(left).strip().lower() == str(right).strip().lower()
    return str(left or "") == str(right or "")


def raw_candidate_errors(
    run_dir: Path, date: str, selected_count: int, args: Any
) -> list[str]:
    if args.required_allocation_model != "portfolio_cash_lot_floor":
        return []
    rows = read_csv(run_dir / "signals" / date / "prediction_raw_candidates.csv")
    return [f"{date}_raw_candidates_lt_selected"] if len(rows) < selected_count else []


def backtest_errors(
    rows: list[dict[str, str]],
    candidates: list[dict[str, str]],
    prices_by_symbol: dict[str, list[dict[str, str]]],
    date: str,
    expected: int,
    args: Any,
) -> list[str]:
    errors = required_column_errors(rows, BACKTEST_FIELDS, f"{date}_backtest")
    if len(rows) != expected:
        errors.append(f"{date}_backtest_rows={len(rows)} expected={expected}")
    bad_dates = [
        row.get("signal_date")
        for row in rows
        if not same_calendar_date(row.get("signal_date", ""), date)
    ]
    if bad_dates:
        errors.append(f"{date}_backtest_signal_date_mismatch={bad_dates[0]}")
    if count_complete(rows) != expected:
        errors.append(
            f"{date}_completed_trades={count_complete(rows)} expected={expected}"
        )
    for row in rows:
        errors += backtest_row_errors(row, date, args)
    errors += backtest_execution_errors(
        candidates=candidates,
        backtest=rows,
        prices_by_symbol=prices_by_symbol,
        signal_date=date,
        args=args,
    )
    return errors


def backtest_row_errors(row: dict[str, str], date: str, args: Any) -> list[str]:
    errors = []
    checks = {
        "status": "complete",
        "missing_data": "False",
        "execution_model": args.required_execution_model,
        "tradability_model": args.required_tradability_model,
        "limit_rules_model": args.required_limit_rules_model,
        "hold_days_requested": str(args.hold_days),
        "entry_price_field": "open",
        "exit_price_field": "close",
        "sizing_execution_model": args.required_execution_model,
        "sizing_entry_price_field": "open",
        "sizing_skip_reason": "",
    }
    for key, expected in checks.items():
        if row.get(key) != expected:
            errors.append(f"{date}_{key}={row.get(key)}")
    for key in BACKTEST_NUMERIC_FIELDS:
        errors += numeric_field_errors(row, key, date)
    for field in OBSOLETE_BACKTEST_FIELDS:
        if field in row:
            errors.append(f"{date}_backtest_obsolete_{field}")
    if safe_float(row.get("cost_bps")) != args.cost_bps:
        errors.append(f"{date}_cost_bps={row.get('cost_bps')}")
    if safe_float(row.get("slippage_bps")) != args.slippage_bps:
        errors.append(f"{date}_slippage_bps={row.get('slippage_bps')}")
    return errors


def numeric_field_errors(row: dict[str, str], key: str, date: str) -> list[str]:
    if key not in row:
        return []
    try:
        value = float_value(row.get(key))
    except (TypeError, ValueError):
        return [f"{date}_{key}={row.get(key)}"]
    if not math.isfinite(value):
        return [f"{date}_{key}={row.get(key)}"]
    return []


def safe_float(value: str | None) -> float | None:
    try:
        return float_value(value)
    except (TypeError, ValueError):
        return None


def equity_errors(
    path: Path,
    summary: dict[str, Any],
    dates: list[str],
    args: Any,
    totals: dict[str, int],
) -> list[str]:
    rows = read_csv(path)
    errors = required_column_errors(
        rows, ("signal_date", "positions", "incomplete_trades", "equity"), "equity"
    )
    if not same_date_list([row.get("signal_date", "") for row in rows], dates):
        errors.append("equity_signal_dates_mismatch")
    if sum_int(rows, "positions") != totals["completed_trades"]:
        errors.append(f"equity_positions={sum_int(rows, 'positions')}")
    if sum_int(rows, "incomplete_trades") != 0:
        errors.append(f"equity_incomplete_trades={sum_int(rows, 'incomplete_trades')}")
    invalid_curve_values = [
        row.get("equity") for row in rows if finite_number(row.get("equity")) is None
    ]
    if invalid_curve_values:
        errors.append(f"equity_invalid_equity={invalid_curve_values[0]}")
    final = finite_number(rows[-1].get("equity")) if rows else 0.0
    if final is None:
        errors.append(f"equity_final_equity_invalid={rows[-1].get('equity')}")
    elif abs(final - args.expected_final_equity) > args.final_equity_tolerance:
        errors.append(f"equity_final_equity={final}")
    summary_final = finite_number(summary.get("equity", {}).get("final_equity"))
    if summary_final is None:
        errors.append(
            "summary_equity_final_equity_invalid="
            f"{summary.get('equity', {}).get('final_equity')}"
        )
    elif final is not None and abs(summary_final - final) > args.final_equity_tolerance:
        errors.append("summary_equity_final_mismatch")
    return errors


def overlap_errors(
    overlap: Any,
    summary: dict[str, Any],
    args: Any,
    capacity_errors: list[str] | None = None,
) -> list[str]:
    errors = (
        list(capacity_errors)
        if capacity_errors is not None
        else overlap_capacity_errors(overlap)
    )
    if not isinstance(overlap, dict):
        return errors
    violations = summary.get("portfolio", {}).get("violations", [])
    if len(violations) != args.expected_portfolio_violations:
        errors.append(f"portfolio_violations={len(violations)}")
    for key in ["cash_capacity_verifiable", "weight_capacity_verifiable"]:
        if overlap.get(key) is not True:
            errors.append(f"portfolio_{key}={overlap.get(key)}")
    if overlap.get("capital_fields_missing"):
        errors.append(
            f"portfolio_capital_fields_missing={overlap.get('capital_fields_missing')}"
        )
    if overlap != summary.get("portfolio", {}).get("summary"):
        errors.append("portfolio_summary_mismatch")
    return errors


def overlap_capacity_errors(overlap: Any) -> list[str]:
    if not isinstance(overlap, dict):
        return ["portfolio_overlap_summary_not_object"]
    errors = []
    for field in OVERLAP_INTEGER_CAPACITY_FIELDS:
        error = overlap_capacity_field_error(overlap, field, integer=True)
        if error:
            errors.append(error)
    for field in OVERLAP_DECIMAL_CAPACITY_FIELDS:
        error = overlap_capacity_field_error(overlap, field, integer=False)
        if error:
            errors.append(error)
    return errors


def overlap_capacity_field_error(
    overlap: dict[str, Any], field: str, *, integer: bool
) -> str | None:
    prefix = f"portfolio_{field}"
    if field not in overlap or overlap[field] is None:
        return f"{prefix}_missing"
    value = overlap[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"{prefix}_non_numeric"
    if not math.isfinite(value):
        return f"{prefix}_non_finite"
    if value < 0:
        return f"{prefix}_negative"
    if integer and not float(value).is_integer():
        return f"{prefix}_non_integer"
    return None


def manifest_errors(manifest: dict[str, Any], dates: list[str]) -> list[str]:
    errors = []
    if manifest.get("validator") != "validate_walk_forward_manifest":
        errors.append(f"manifest_validator={manifest.get('validator')}")
    if manifest.get("errors") != []:
        errors.append(f"manifest_errors={len(manifest.get('errors', []))}")
    if not same_date_list([str(item) for item in manifest.get("signals", [])], dates):
        errors.append("manifest_signals_mismatch")
    if int(manifest.get("steps_checked", 0)) <= 0:
        errors.append(f"manifest_steps_checked={manifest.get('steps_checked')}")
    return errors


def report_view(
    run_dir: Path,
    validator: str,
    dates: list[str],
    totals: dict[str, int],
    summary: dict[str, Any],
    manifest_checked: bool,
    execution_model: str,
    expected_portfolio_violations: bool,
    capacity_inputs_valid: bool,
    errors: list[str],
) -> dict[str, Any]:
    portfolio_violations = len(summary.get("portfolio", {}).get("violations", []))
    capacity_gate_pass = capacity_inputs_valid and portfolio_violations == 0
    if capacity_gate_pass:
        capacity_gate_status = "pass"
    elif capacity_inputs_valid and expected_portfolio_violations:
        capacity_gate_status = "expected_violation_not_pass"
    else:
        capacity_gate_status = "failed_not_pass"
    verdict = artifact_verdict(errors, capacity_gate_status)
    return {
        "schema_version": 1,
        "validator": validator,
        "run_dir": str(run_dir),
        "signals": dates,
        "signals_checked": len(dates),
        "total_candidates": totals["candidates"],
        "total_completed_trades": totals["completed_trades"],
        "final_equity": finite_number(summary.get("equity", {}).get("final_equity")),
        "execution_model": execution_model,
        "portfolio_violations": portfolio_violations,
        "expected_portfolio_violations": expected_portfolio_violations,
        "capacity_gate_pass": capacity_gate_pass,
        "capacity_gate_status": capacity_gate_status,
        "verdict": verdict,
        "claim_boundary": "artifact_validation_not_external_gate",
        "manifest_checked": manifest_checked,
        "errors": errors,
    }


def artifact_verdict(errors: list[str], capacity_gate_status: str) -> str:
    if errors:
        return "artifact_validation_failed"
    if capacity_gate_status == "expected_violation_not_pass":
        return "known_portfolio_violation_reproduced_not_capacity_pass"
    if capacity_gate_status == "failed_not_pass":
        return "capacity_gate_failed"
    return "artifacts_pass_enabled_gates_not_external_proof"


def required_column_errors(
    rows: list[dict[str, str]], columns: tuple[str, ...], label: str
) -> list[str]:
    fieldnames = set(rows[0]) if rows else set()
    return [
        f"{label}_missing_{column}" for column in columns if column not in fieldnames
    ]


def count_complete(rows: list[dict[str, str]]) -> int:
    return sum(
        1
        for row in rows
        if row.get("status") == "complete" and row.get("missing_data") == "False"
    )


def sum_int(rows: list[dict[str, str]], key: str) -> int:
    return sum(int(float_value(row.get(key))) for row in rows)


def float_value(value: str | None) -> float:
    return float(value or 0.0)


def finite_number(value: object) -> float | None:
    try:
        numeric = float(str(value))
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    import json

    return json.loads(path.read_text(encoding="utf-8"))
