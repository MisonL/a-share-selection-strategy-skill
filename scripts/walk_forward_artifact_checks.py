"""Checks for walk-forward artifact contents."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


CAPITAL_FIELDS = ("weight", "notional", "quantity", "cash_reserved")
PRICE_COLUMNS = (
    "symbol", "date", "open", "high", "low", "close", "volume", "amount",
    "turn", "tradestatus", "isST",
)
SIZED_COLUMNS = (
    "cash_budget", "lot_size", "capital_model", "signal_close", "cash_slot",
    "quantity", "cash_reserved", "notional", "weight", "unallocated",
)


def build_artifact_report(run_dir: Path, args: Any, validator: str) -> dict[str, Any]:
    dates = list(args.signal_dates)
    symbols = list(args.expected_symbols)
    errors = count_errors(dates, args.expected_candidates)
    summary = load_json(run_dir / "qsss_run_summary.json")
    errors += metadata_errors(load_json(run_dir / "metadata.json"), symbols)
    errors += summary_errors(summary, dates, args.expected_candidates)
    totals = validate_signal_artifacts(run_dir, dates, symbols, args, errors)
    errors += equity_errors(run_dir / "qsss_equity_curve.csv", summary, dates, args, totals)
    errors += overlap_errors(load_json(run_dir / "qsss_overlap_summary.json"), summary, args)
    manifest_checked = bool(args.manifest_validation)
    if args.manifest_validation:
        errors += manifest_errors(load_json(Path(args.manifest_validation)), dates)
    return report_view(run_dir, validator, dates, totals, summary, manifest_checked, errors)


def count_errors(dates: list[str], expected: list[int]) -> list[str]:
    if len(expected) != len(dates):
        return [f"expected_candidates_count={len(expected)} signal_dates={len(dates)}"]
    return []


def metadata_errors(metadata: dict[str, Any], symbols: list[str]) -> list[str]:
    errors = []
    actual = [item.get("symbol") for item in metadata.get("symbols", [])]
    expected = {"source": "baostock", "adjustflag": "3"}
    for key, value in expected.items():
        if metadata.get(key) != value:
            errors.append(f"metadata_{key}={metadata.get(key)}")
    if metadata.get("requested_symbols") != symbols or actual != symbols:
        errors.append("metadata_symbols_mismatch")
    if int(metadata.get("rows", 0)) <= 0 or int(metadata.get("raw_rows", 0)) <= 0:
        errors.append(f"metadata_rows={metadata.get('rows')} raw_rows={metadata.get('raw_rows')}")
    if int(metadata.get("symbol_count", 0)) != len(symbols):
        errors.append(f"metadata_symbol_count={metadata.get('symbol_count')}")
    for key in ["failed_symbols", "empty_symbols"]:
        if metadata.get(key):
            errors.append(f"metadata_{key}={len(metadata[key])}")
    for key in invalid_metadata_keys():
        if int(metadata.get(key, 0)) != 0:
            errors.append(f"metadata_{key}={metadata.get(key)}")
    return errors


def invalid_metadata_keys() -> tuple[str, ...]:
    return (
        "invalid_rows", "dropped_invalid_rows", "raw_non_trading_rows",
        "non_trading_rows", "raw_tradestatus_missing_rows", "tradestatus_missing_rows",
    )


def summary_errors(summary: dict[str, Any], dates: list[str], expected: list[int]) -> list[str]:
    errors = []
    if summary.get("quality_errors") != []:
        errors.append(f"quality_errors={summary.get('quality_errors')}")
    signals = summary.get("signals", [])
    if [item.get("signal_date") for item in signals] != dates:
        errors.append("summary_signal_dates_mismatch")
    for index, signal in enumerate(signals):
        if index < len(expected) and signal.get("candidates") != expected[index]:
            errors.append(f"summary_{signal.get('signal_date')}_candidates={signal.get('candidates')}")
        if signal.get("completed_trades") != signal.get("candidates"):
            errors.append(f"summary_{signal.get('signal_date')}_completed_mismatch")
    return errors


def validate_signal_artifacts(
    run_dir: Path,
    dates: list[str],
    symbols: list[str],
    args: Any,
    errors: list[str],
) -> dict[str, int]:
    totals = {"candidates": 0, "completed_trades": 0}
    for index, date in enumerate(dates):
        signal_dir = run_dir / "signals" / date
        expected = args.expected_candidates[index] if index < len(args.expected_candidates) else 0
        candidates = read_csv(signal_dir / "qsss_candidates.csv")
        sized = read_csv(signal_dir / "qsss_sized_candidates.csv")
        backtest = read_csv(signal_dir / "qsss_backtest.csv")
        errors += price_window_errors(read_csv(signal_dir / "prices_signal_window.csv"), date, symbols)
        errors += prediction_errors(load_json(signal_dir / "prediction_summary.json"), date, len(symbols))
        errors += candidate_errors(candidates, date, symbols, expected, "candidates")
        errors += candidate_errors(sized, date, symbols, expected, "sized")
        errors += sized_errors(sized, date, args)
        errors += backtest_errors(backtest, date, expected, args)
        totals["candidates"] += len(candidates)
        totals["completed_trades"] += count_complete(backtest)
    return totals


def price_window_errors(rows: list[dict[str, str]], signal_date: str, symbols: list[str]) -> list[str]:
    errors = required_column_errors(rows, PRICE_COLUMNS, f"{signal_date}_prices")
    if sorted({row.get("symbol", "") for row in rows}) != symbols:
        errors.append(f"{signal_date}_price_symbols_mismatch")
    if any(row.get("date", "") > signal_date for row in rows):
        errors.append(f"{signal_date}_future_price_rows")
    return errors


def prediction_errors(summary: dict[str, Any], signal_date: str, symbol_count: int) -> list[str]:
    errors = []
    expected = {"raw_symbols": symbol_count, "predicted_symbols": symbol_count, "skipped_symbols": 0}
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
    bad_dates = [row.get("date") for row in rows if row.get("date") != signal_date]
    if bad_dates:
        errors.append(f"{signal_date}_{label}_date_mismatch={bad_dates[0]}")
    if not set(row.get("symbol", "") for row in rows).issubset(set(symbols)):
        errors.append(f"{signal_date}_{label}_symbol_outside_pool")
    return errors


def sized_errors(rows: list[dict[str, str]], signal_date: str, args: Any) -> list[str]:
    errors = required_column_errors(rows, SIZED_COLUMNS, f"{signal_date}_sized")
    for row in rows:
        if row.get("capital_model") != "equal_cash_budget_lot_floor":
            errors.append(f"{signal_date}_capital_model={row.get('capital_model')}")
        if float_value(row.get("cash_budget")) != args.cash_budget:
            errors.append(f"{signal_date}_cash_budget={row.get('cash_budget')}")
        if int(float_value(row.get("lot_size"))) != args.lot_size:
            errors.append(f"{signal_date}_lot_size={row.get('lot_size')}")
        if row.get("unallocated", "").lower() not in ("false", "0"):
            errors.append(f"{signal_date}_unallocated={row.get('unallocated')}")
    return errors


def backtest_errors(rows: list[dict[str, str]], date: str, expected: int, args: Any) -> list[str]:
    errors = required_column_errors(rows, (*CAPITAL_FIELDS, "status", "missing_data"), f"{date}_backtest")
    if count_complete(rows) != expected:
        errors.append(f"{date}_completed_trades={count_complete(rows)} expected={expected}")
    for row in rows:
        errors += backtest_row_errors(row, date, args)
    return errors


def backtest_row_errors(row: dict[str, str], date: str, args: Any) -> list[str]:
    errors = []
    checks = {
        "status": "complete",
        "missing_data": "False",
        "tradability_model": args.required_tradability_model,
        "limit_rules_model": args.required_limit_rules_model,
        "hold_days_requested": str(args.hold_days),
    }
    for key, expected in checks.items():
        if row.get(key) != expected:
            errors.append(f"{date}_{key}={row.get(key)}")
    if float_value(row.get("cost_bps")) != args.cost_bps:
        errors.append(f"{date}_cost_bps={row.get('cost_bps')}")
    if float_value(row.get("slippage_bps")) != args.slippage_bps:
        errors.append(f"{date}_slippage_bps={row.get('slippage_bps')}")
    return errors


def equity_errors(
    path: Path,
    summary: dict[str, Any],
    dates: list[str],
    args: Any,
    totals: dict[str, int],
) -> list[str]:
    rows = read_csv(path)
    errors = required_column_errors(rows, ("signal_date", "positions", "incomplete_trades", "equity"), "equity")
    if [row.get("signal_date") for row in rows] != dates:
        errors.append("equity_signal_dates_mismatch")
    if sum_int(rows, "positions") != totals["completed_trades"]:
        errors.append(f"equity_positions={sum_int(rows, 'positions')}")
    if sum_int(rows, "incomplete_trades") != 0:
        errors.append(f"equity_incomplete_trades={sum_int(rows, 'incomplete_trades')}")
    final = float_value(rows[-1].get("equity")) if rows else 0.0
    if abs(final - args.expected_final_equity) > args.final_equity_tolerance:
        errors.append(f"equity_final_equity={final}")
    if summary.get("equity", {}).get("final_equity") != final:
        errors.append("summary_equity_final_mismatch")
    return errors


def overlap_errors(overlap: dict[str, Any], summary: dict[str, Any], args: Any) -> list[str]:
    errors = []
    violations = summary.get("portfolio", {}).get("violations", [])
    if len(violations) != args.expected_portfolio_violations:
        errors.append(f"portfolio_violations={len(violations)}")
    for key in ["cash_capacity_verifiable", "weight_capacity_verifiable"]:
        if overlap.get(key) is not True:
            errors.append(f"portfolio_{key}={overlap.get(key)}")
    if overlap.get("capital_fields_missing"):
        errors.append(f"portfolio_capital_fields_missing={overlap.get('capital_fields_missing')}")
    if overlap != summary.get("portfolio", {}).get("summary"):
        errors.append("portfolio_summary_mismatch")
    return errors


def manifest_errors(manifest: dict[str, Any], dates: list[str]) -> list[str]:
    errors = []
    if manifest.get("validator") != "validate_walk_forward_manifest":
        errors.append(f"manifest_validator={manifest.get('validator')}")
    if manifest.get("errors") != []:
        errors.append(f"manifest_errors={len(manifest.get('errors', []))}")
    if manifest.get("signals") != dates:
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
    errors: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "validator": validator,
        "run_dir": str(run_dir),
        "signals": dates,
        "signals_checked": len(dates),
        "total_candidates": totals["candidates"],
        "total_completed_trades": totals["completed_trades"],
        "final_equity": summary.get("equity", {}).get("final_equity"),
        "portfolio_violations": len(summary.get("portfolio", {}).get("violations", [])),
        "manifest_checked": manifest_checked,
        "errors": errors,
    }


def required_column_errors(rows: list[dict[str, str]], columns: tuple[str, ...], label: str) -> list[str]:
    fieldnames = set(rows[0]) if rows else set()
    return [f"{label}_missing_{column}" for column in columns if column not in fieldnames]


def count_complete(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if row.get("status") == "complete" and row.get("missing_data") == "False")


def sum_int(rows: list[dict[str, str]], key: str) -> int:
    return sum(int(float_value(row.get(key))) for row in rows)


def float_value(value: str | None) -> float:
    return float(value or 0.0)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
