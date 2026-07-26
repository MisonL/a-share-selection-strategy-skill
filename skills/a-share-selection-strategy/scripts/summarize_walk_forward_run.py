#!/usr/bin/env python3
"""Summarize and gate a real walk-forward run directory."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from lib.selection_core.a_share_selection_model_contracts import (
    EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
)
from lib.selection_core.a_share_selection_cli_numeric import (
    normalize_negative_non_finite_option_values,
)
from lib.selection_core.a_share_selection_sizing_contracts import (
    require_finite_non_negative_number,
    require_finite_number,
    require_integer_at_least,
)
from lib.gates.a_share_selection_output_safety import (
    prepare_output_paths,
    remove_output_files,
)
from lib.walk_forward.metadata_checks import metadata_gate_errors


DATE_DIR = re.compile(r"\d{4}-\d{2}-\d{2}")
METADATA_FIELDS = (
    "source",
    "start_date",
    "end_date",
    "adjustflag",
    "rows",
    "raw_rows",
    "symbol_count",
    "failed_symbols",
    "empty_symbols",
    "invalid_rows",
    "dropped_invalid_rows",
    "raw_non_trading_rows",
    "non_trading_rows",
    "raw_tradestatus_missing_rows",
    "tradestatus_missing_rows",
)
NUMERIC_OPTIONS = (
    "--max-open-positions",
    "--max-gross-weight",
    "--max-gross-notional",
    "--max-cash-reserved",
)
OVERLAP_INTEGER_CAPACITY_FIELDS = {
    "max_open_positions": "max-open-positions",
    "same_symbol_overlap_rows": "same-symbol-overlap-rows",
}
OVERLAP_DECIMAL_CAPACITY_FIELDS = {
    "max_gross_weight": "max-gross-weight",
    "max_gross_notional": "max-gross-notional",
    "max_cash_reserved": "max-cash-reserved",
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(
        normalize_negative_non_finite_option_values(argv, NUMERIC_OPTIONS)
    )
    run_dir = Path(args.run_dir)
    output = Path(args.output)
    output_prepared = False
    try:
        prepare_output_paths([output], summary_input_paths(run_dir, args))
        output_prepared = True
        validate_capacity_options(args)
        summary = build_run_summary(run_dir, args)
        write_json(summary, output)
        if summary["quality_errors"]:
            print_summary(summary, output, prefix="ERROR_SUMMARY")
            print(
                "ERROR: strict gate failed; "
                + "; ".join(summary["quality_errors"])
                + " output_written=true",
                file=sys.stderr,
            )
            return 3
    except Exception as exc:  # noqa: BLE001
        if output_prepared:
            remove_output_files([output])
        print(
            f"ERROR: code=bad_input output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(summary, output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize a walk-forward run directory."
    )
    parser.add_argument(
        "--run-dir", required=True, help="Run directory containing metadata.json."
    )
    parser.add_argument("--output", required=True, help="Output summary JSON path.")
    parser.add_argument(
        "--signal-dates", nargs="*", help="Expected YYYY-MM-DD signal dates."
    )
    parser.add_argument("--expected-symbol-count", type=int)
    parser.add_argument("--required-tradability-model")
    parser.add_argument("--required-limit-rules-model")
    parser.add_argument(
        "--required-execution-model",
        choices=[EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE],
    )
    parser.add_argument("--max-open-positions")
    parser.add_argument("--max-gross-weight")
    parser.add_argument("--max-gross-notional")
    parser.add_argument("--max-cash-reserved")
    parser.add_argument("--fail-on-symbol-overlap", action="store_true")
    parser.add_argument(
        "--expect-portfolio-violations",
        action="store_true",
        help="Allow known violations only, not a capacity pass.",
    )
    parser.add_argument("--allow-dropped-invalid-rows", action="store_true")
    return parser


def validate_capacity_options(options: argparse.Namespace) -> None:
    if options.max_open_positions is not None:
        options.max_open_positions = require_integer_at_least(
            options.max_open_positions,
            "max-open-positions",
            0,
        )
    for attribute, name in OVERLAP_DECIMAL_CAPACITY_FIELDS.items():
        value = getattr(options, attribute)
        if value is not None:
            setattr(
                options,
                attribute,
                require_finite_non_negative_number(value, name),
            )


def summary_input_paths(
    run_dir: Path,
    options: argparse.Namespace,
) -> list[Path]:
    paths = [
        run_dir / "metadata.json",
        run_dir / "prediction_equity_curve.csv",
        run_dir / "prediction_overlap_summary.json",
        run_dir / "prediction_allocation_summary.json",
    ]
    for signal_dir in declared_signal_dirs(run_dir, options.signal_dates):
        paths.extend(
            [
                signal_dir / "prediction_summary.json",
                signal_dir / "prediction_candidates.csv",
                signal_dir / "prediction_backtest.csv",
            ]
        )
    return paths


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import lib.selection_core.a_share_selection_data as data_module

    globals().update(
        {
            "pd": pandas_module,
            "read_table": data_module.read_table,
        }
    )


def build_run_summary(run_dir: Path, options: argparse.Namespace) -> dict[str, Any]:
    ensure_runtime_dependencies()
    metadata = load_json(run_dir / "metadata.json")
    signals = [
        signal_summary(path) for path in signal_dirs(run_dir, options.signal_dates)
    ]
    execution_models = sorted(
        {model for signal in signals for model in signal["execution_models"]}
    )
    equity = equity_summary(run_dir / "prediction_equity_curve.csv")
    portfolio = portfolio_summary(run_dir / "prediction_overlap_summary.json", options)
    summary = {
        "run_dir": str(run_dir),
        "metadata": metadata_view(metadata),
        "allocation": load_json(run_dir / "prediction_allocation_summary.json")
        if (run_dir / "prediction_allocation_summary.json").exists()
        else None,
        "signals": signals,
        "execution_models": execution_models,
        "execution_model": (
            execution_models[0] if len(execution_models) == 1 else None
        ),
        "required_execution_model": options.required_execution_model,
        "equity": equity,
        "portfolio": portfolio,
        "expected_portfolio_violations": bool(options.expect_portfolio_violations),
        "capacity_gate_pass": not bool(portfolio["violations"]),
        "capacity_gate_status": capacity_gate_status(
            portfolio["violations"],
            expect_portfolio_violations=options.expect_portfolio_violations,
        ),
        "required_tradability_model_checked": bool(options.required_tradability_model),
        "required_limit_rules_model_checked": bool(options.required_limit_rules_model),
        "required_execution_model_checked": bool(options.required_execution_model),
        "model_gates_checked": bool(
            options.required_tradability_model
            and options.required_limit_rules_model
            and options.required_execution_model
        ),
        "claim_boundary": "summary_not_external_gate",
    }
    summary["quality_errors"] = quality_errors(summary, metadata, options)
    summary["verdict"] = summary_verdict(summary)
    return summary


def summary_verdict(summary: dict[str, Any]) -> str:
    if summary["quality_errors"]:
        return "strict_gate_failed"
    if summary["capacity_gate_status"] == "expected_violation_not_pass":
        return "known_portfolio_violation_reproduced_not_capacity_pass"
    if summary["capacity_gate_status"] == "failed_not_pass":
        return "capacity_gate_failed"
    if not summary["model_gates_checked"]:
        return "enabled_gates_passed_model_gates_unchecked"
    return "enabled_gates_passed_not_external_proof"


def capacity_gate_status(
    violations: list[str],
    *,
    expect_portfolio_violations: bool,
) -> str:
    if not violations:
        return "pass"
    if expect_portfolio_violations:
        return "expected_violation_not_pass"
    return "failed_not_pass"


def signal_dirs(run_dir: Path, signal_dates: list[str] | None) -> list[Path]:
    paths = declared_signal_dirs(run_dir, signal_dates)
    if not paths:
        raise ValueError("no signal date directories found")
    missing = [path.name for path in paths if not path.is_dir()]
    if missing:
        raise FileNotFoundError(
            f"missing signal date directories: {', '.join(missing)}"
        )
    return paths


def declared_signal_dirs(run_dir: Path, signal_dates: list[str] | None) -> list[Path]:
    base = signal_base(run_dir)
    if signal_dates:
        return [base / signal_date for signal_date in signal_dates]
    if not base.is_dir():
        return []
    return sorted(path for path in base.iterdir() if DATE_DIR.fullmatch(path.name))


def signal_base(run_dir: Path) -> Path:
    signals = run_dir / "signals"
    return signals if signals.is_dir() else run_dir


def signal_summary(signal_dir: Path) -> dict[str, Any]:
    ensure_runtime_dependencies()
    prediction = load_json(signal_dir / "prediction_summary.json")
    candidates = read_table(signal_dir / "prediction_candidates.csv")
    backtest = read_table(signal_dir / "prediction_backtest.csv")
    require_columns(backtest, ["return", "missing_data", "status"])
    complete = complete_trades(backtest)
    returns = pd.to_numeric(complete["return"], errors="coerce").dropna()
    return {
        "signal_date": signal_dir.name,
        "raw_symbols": int(prediction.get("raw_symbols", 0)),
        "predicted_symbols": int(prediction.get("predicted_symbols", 0)),
        "skipped_symbols": int(prediction.get("skipped_symbols", 0)),
        "candidates": int(len(candidates)),
        "backtest_rows": int(len(backtest)),
        "completed_trades": int(len(complete)),
        "incomplete_trades": int(len(backtest) - len(complete)),
        "mean_return": float(returns.mean()) if not returns.empty else None,
        "min_return": float(returns.min()) if not returns.empty else None,
        "max_return": float(returns.max()) if not returns.empty else None,
        "tradability_models": sorted(
            backtest.get("tradability_model", pd.Series()).dropna().unique()
        ),
        "limit_rules_models": sorted(
            backtest.get("limit_rules_model", pd.Series()).dropna().unique()
        ),
        "execution_models": sorted(
            backtest.get("execution_model", pd.Series()).dropna().unique()
        ),
    }


def equity_summary(path: Path) -> dict[str, Any]:
    ensure_runtime_dependencies()
    frame = read_table(path)
    require_columns(
        frame, ["signal_date", "positions", "incomplete_trades", "equity", "drawdown"]
    )
    if frame.empty:
        raise ValueError("equity curve is empty")
    equity = finite_numeric_values(frame["equity"], "equity curve equity")
    drawdown = finite_numeric_values(frame["drawdown"], "equity curve drawdown")
    final_equity = float(equity.iloc[-1])
    return {
        "periods": int(len(frame)),
        "positions": int(pd.to_numeric(frame["positions"], errors="raise").sum()),
        "incomplete_trades": int(
            pd.to_numeric(frame["incomplete_trades"], errors="raise").sum()
        ),
        "final_equity": final_equity,
        "total_return": final_equity - 1.0,
        "max_drawdown": float(drawdown.min()),
    }


def finite_numeric_values(values: Any, name: str) -> Any:
    return values.map(lambda value: require_finite_number(value, name))


def portfolio_summary(path: Path, gate: argparse.Namespace) -> dict[str, Any]:
    summary = load_json(path)
    capacity_values = overlap_capacity_values(summary)
    violations = portfolio_violations(capacity_values, gate)
    return {"summary": summary, "violations": violations}


def overlap_capacity_values(summary: Any) -> dict[str, float | int]:
    if not isinstance(summary, dict):
        raise ValueError("prediction overlap summary must be a JSON object")
    values: dict[str, float | int] = {}
    for key, name in OVERLAP_INTEGER_CAPACITY_FIELDS.items():
        values[key] = overlap_integer_capacity_value(summary, key, name)
    for key, name in OVERLAP_DECIMAL_CAPACITY_FIELDS.items():
        values[key] = overlap_decimal_capacity_value(summary, key, name)
    return values


def overlap_integer_capacity_value(summary: dict[str, Any], key: str, name: str) -> int:
    value = overlap_json_number(summary, key, name)
    return require_integer_at_least(value, name, 0)


def overlap_decimal_capacity_value(
    summary: dict[str, Any], key: str, name: str
) -> float:
    value = overlap_json_number(summary, key, name)
    return require_finite_non_negative_number(value, name)


def overlap_json_number(summary: dict[str, Any], key: str, name: str) -> int | float:
    if key not in summary:
        raise ValueError(f"{name} is required")
    value = summary[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a JSON number")
    return value


def quality_errors(
    summary: dict[str, Any],
    metadata: dict[str, Any],
    options: argparse.Namespace,
) -> list[str]:
    errors = metadata_errors(
        metadata,
        options.expected_symbol_count,
        allow_dropped_invalid_rows=options.allow_dropped_invalid_rows,
    )
    for signal in summary["signals"]:
        errors.extend(signal_errors(signal, options))
    if summary["equity"]["incomplete_trades"]:
        errors.append(
            f"equity_incomplete_trades={summary['equity']['incomplete_trades']}"
        )
    violations = summary["portfolio"]["violations"]
    if options.expect_portfolio_violations and not violations:
        errors.append("expected_portfolio_violations_missing")
    if not options.expect_portfolio_violations:
        errors.extend(f"portfolio_{violation}" for violation in violations)
    return errors


def metadata_errors(
    metadata: dict[str, Any],
    expected_symbol_count: int | None,
    *,
    allow_dropped_invalid_rows: bool,
) -> list[str]:
    return metadata_gate_errors(
        metadata,
        expected_symbol_count,
        allow_dropped_invalid_rows=allow_dropped_invalid_rows,
    )


def signal_errors(signal: dict[str, Any], options: argparse.Namespace) -> list[str]:
    errors = []
    if signal["raw_symbols"] != signal["predicted_symbols"]:
        errors.append(f"{signal['signal_date']}_prediction_symbol_mismatch")
    if signal["skipped_symbols"]:
        errors.append(
            f"{signal['signal_date']}_skipped_symbols={signal['skipped_symbols']}"
        )
    if signal["candidates"] <= 0:
        errors.append(f"{signal['signal_date']}_empty_candidates")
    if signal["completed_trades"] <= 0:
        errors.append(f"{signal['signal_date']}_no_completed_trades")
    if signal["backtest_rows"] != signal["candidates"]:
        errors.append(
            f"{signal['signal_date']}_backtest_rows={signal['backtest_rows']} "
            f"candidates={signal['candidates']}"
        )
    if signal["completed_trades"] != signal["candidates"]:
        errors.append(
            f"{signal['signal_date']}_completed_trades={signal['completed_trades']} "
            f"candidates={signal['candidates']}"
        )
    if signal["incomplete_trades"]:
        errors.append(
            f"{signal['signal_date']}_incomplete_trades={signal['incomplete_trades']}"
        )
    errors.extend(model_errors(signal, options))
    return errors


def model_errors(signal: dict[str, Any], options: argparse.Namespace) -> list[str]:
    errors = []
    if options.required_tradability_model:
        models = signal["tradability_models"]
        if models != [options.required_tradability_model]:
            errors.append(
                f"{signal['signal_date']}_tradability_models={','.join(models)}"
            )
    if options.required_limit_rules_model:
        models = signal["limit_rules_models"]
        if models != [options.required_limit_rules_model]:
            errors.append(
                f"{signal['signal_date']}_limit_rules_models={','.join(models)}"
            )
    if options.required_execution_model:
        models = signal["execution_models"]
        if models != [options.required_execution_model]:
            errors.append(
                f"{signal['signal_date']}_execution_models={','.join(models)}"
            )
    return errors


def portfolio_violations(
    capacity_values: dict[str, float | int], gate: argparse.Namespace
) -> list[str]:
    violations = []
    if gate.max_open_positions is not None:
        if capacity_values["max_open_positions"] > gate.max_open_positions:
            limit = gate.max_open_positions
            violations.append(
                f"max_open_positions={capacity_values['max_open_positions']} limit={limit}"
            )
    add_float_violation(
        violations,
        capacity_values,
        key="max_gross_weight",
        limit=gate.max_gross_weight,
    )
    add_float_violation(
        violations,
        capacity_values,
        key="max_gross_notional",
        limit=gate.max_gross_notional,
    )
    add_float_violation(
        violations,
        capacity_values,
        key="max_cash_reserved",
        limit=gate.max_cash_reserved,
    )
    if gate.fail_on_symbol_overlap and capacity_values["same_symbol_overlap_rows"]:
        violations.append(
            f"same_symbol_overlap_rows={capacity_values['same_symbol_overlap_rows']}"
        )
    return violations


def add_float_violation(
    violations: list[str],
    capacity_values: dict[str, float | int],
    *,
    key: str,
    limit: float | None,
) -> None:
    if limit is not None and capacity_values[key] > limit:
        violations.append(f"{key}={capacity_values[key]} limit={limit}")


def complete_trades(frame: pd.DataFrame) -> pd.DataFrame:
    ensure_runtime_dependencies()
    missing = missing_data_mask(frame["missing_data"])
    return frame[(frame["status"].astype(str) == "complete") & (~missing)]


def missing_data_mask(values: Any) -> Any:
    numeric = pd.to_numeric(values, errors="coerce")
    text = values.astype(str).str.strip().str.lower()
    return numeric.eq(1) | text.isin(["true", "1"])


def require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in frame]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def metadata_view(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: metadata.get(key) for key in METADATA_FIELDS if key in metadata}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def print_summary(summary: dict[str, Any], output: Path, prefix: str = "OK") -> None:
    print(
        f"{prefix}: signals={len(summary['signals'])} "
        f"candidates={sum(item['candidates'] for item in summary['signals'])} "
        f"completed_trades={sum(item['completed_trades'] for item in summary['signals'])} "
        f"incomplete_trades={sum(item['incomplete_trades'] for item in summary['signals'])} "
        f"portfolio_violations={len(summary['portfolio']['violations'])} "
        f"expected_portfolio_violations={summary['expected_portfolio_violations']} "
        f"capacity_gate_pass={summary['capacity_gate_pass']} "
        f"capacity_gate_status={summary['capacity_gate_status']} "
        f"model_gates_checked={summary['model_gates_checked']} "
        f"execution_model={summary['execution_model']} "
        f"required_execution_model_checked={summary['required_execution_model_checked']} "
        f"quality_errors={len(summary['quality_errors'])} "
        f"verdict={summary['verdict']} "
        f"claim_boundary=summary_not_external_gate output={output}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
