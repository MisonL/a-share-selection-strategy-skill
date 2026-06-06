#!/usr/bin/env python3
"""Summarize and gate a real walk-forward run directory."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from walk_forward_metadata_checks import metadata_gate_errors


DATE_DIR = re.compile(r"\d{4}-\d{2}-\d{2}")
METADATA_FIELDS = (
    "source", "start_date", "end_date", "adjustflag", "rows", "raw_rows",
    "symbol_count", "failed_symbols", "empty_symbols", "invalid_rows",
    "dropped_invalid_rows", "raw_non_trading_rows", "non_trading_rows",
    "raw_tradestatus_missing_rows", "tradestatus_missing_rows",
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = Path(args.output)
    try:
        ensure_runtime_dependencies()
        summary = build_run_summary(Path(args.run_dir), args)
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
        print(
            f"ERROR: code=bad_input output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(summary, output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize a walk-forward run directory.")
    parser.add_argument("--run-dir", required=True, help="Run directory containing metadata.json.")
    parser.add_argument("--output", required=True, help="Output summary JSON path.")
    parser.add_argument("--signal-dates", nargs="*", help="Expected YYYY-MM-DD signal dates.")
    parser.add_argument("--expected-symbol-count", type=int)
    parser.add_argument("--required-tradability-model")
    parser.add_argument("--required-limit-rules-model")
    parser.add_argument("--max-open-positions", type=int)
    parser.add_argument("--max-gross-weight", type=float)
    parser.add_argument("--max-gross-notional", type=float)
    parser.add_argument("--max-cash-reserved", type=float)
    parser.add_argument("--fail-on-symbol-overlap", action="store_true")
    parser.add_argument("--expect-portfolio-violations", action="store_true")
    parser.add_argument("--allow-dropped-invalid-rows", action="store_true")
    return parser


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import a_share_selection_data as data_module

    globals().update(
        {
            "pd": pandas_module,
            "read_table": data_module.read_table,
        }
    )


def build_run_summary(run_dir: Path, options: argparse.Namespace) -> dict[str, Any]:
    ensure_runtime_dependencies()
    metadata = load_json(run_dir / "metadata.json")
    signals = [signal_summary(path) for path in signal_dirs(run_dir, options.signal_dates)]
    equity = equity_summary(run_dir / "prediction_equity_curve.csv")
    portfolio = portfolio_summary(run_dir / "prediction_overlap_summary.json", options)
    summary = {
        "run_dir": str(run_dir),
        "metadata": metadata_view(metadata),
        "allocation": load_json(run_dir / "prediction_allocation_summary.json") if (run_dir / "prediction_allocation_summary.json").exists() else None,
        "signals": signals,
        "equity": equity,
        "portfolio": portfolio,
        "expected_portfolio_violations": bool(options.expect_portfolio_violations),
        "capacity_gate_pass": not bool(portfolio["violations"]),
        "required_tradability_model_checked": bool(options.required_tradability_model),
        "required_limit_rules_model_checked": bool(options.required_limit_rules_model),
        "model_gates_checked": bool(
            options.required_tradability_model and options.required_limit_rules_model
        ),
        "claim_boundary": "summary_not_external_gate",
    }
    summary["quality_errors"] = quality_errors(summary, metadata, options)
    return summary


def signal_dirs(run_dir: Path, signal_dates: list[str] | None) -> list[Path]:
    base = signal_base(run_dir)
    if signal_dates:
        paths = [base / signal_date for signal_date in signal_dates]
    else:
        paths = sorted(path for path in base.iterdir() if DATE_DIR.fullmatch(path.name))
    if not paths:
        raise ValueError("no signal date directories found")
    missing = [path.name for path in paths if not path.is_dir()]
    if missing:
        raise FileNotFoundError(f"missing signal date directories: {', '.join(missing)}")
    return paths


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
    }


def equity_summary(path: Path) -> dict[str, Any]:
    ensure_runtime_dependencies()
    frame = read_table(path)
    require_columns(
        frame, ["signal_date", "positions", "incomplete_trades", "equity", "drawdown"]
    )
    if frame.empty:
        raise ValueError("equity curve is empty")
    final = frame.iloc[-1]
    final_equity = float(final["equity"])
    return {
        "periods": int(len(frame)),
        "positions": int(pd.to_numeric(frame["positions"], errors="raise").sum()),
        "incomplete_trades": int(pd.to_numeric(frame["incomplete_trades"], errors="raise").sum()),
        "final_equity": final_equity,
        "total_return": final_equity - 1.0,
        "max_drawdown": float(pd.to_numeric(frame["drawdown"], errors="raise").min()),
    }


def portfolio_summary(path: Path, gate: argparse.Namespace) -> dict[str, Any]:
    summary = load_json(path)
    violations = portfolio_violations(summary, gate)
    return {"summary": summary, "violations": violations}


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
        errors.append(f"equity_incomplete_trades={summary['equity']['incomplete_trades']}")
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
        errors.append(f"{signal['signal_date']}_skipped_symbols={signal['skipped_symbols']}")
    if signal["candidates"] <= 0:
        errors.append(f"{signal['signal_date']}_empty_candidates")
    if signal["completed_trades"] <= 0:
        errors.append(f"{signal['signal_date']}_no_completed_trades")
    if signal["incomplete_trades"]:
        errors.append(f"{signal['signal_date']}_incomplete_trades={signal['incomplete_trades']}")
    errors.extend(model_errors(signal, options))
    return errors


def model_errors(signal: dict[str, Any], options: argparse.Namespace) -> list[str]:
    errors = []
    if options.required_tradability_model:
        models = signal["tradability_models"]
        if models != [options.required_tradability_model]:
            errors.append(f"{signal['signal_date']}_tradability_models={','.join(models)}")
    if options.required_limit_rules_model:
        models = signal["limit_rules_models"]
        if models != [options.required_limit_rules_model]:
            errors.append(f"{signal['signal_date']}_limit_rules_models={','.join(models)}")
    return errors


def portfolio_violations(summary: dict[str, Any], gate: argparse.Namespace) -> list[str]:
    violations = []
    if gate.max_open_positions is not None:
        if int(summary["max_open_positions"]) > gate.max_open_positions:
            limit = gate.max_open_positions
            violations.append(f"max_open_positions={summary['max_open_positions']} limit={limit}")
    add_float_violation(
        violations, summary, key="max_gross_weight", limit=gate.max_gross_weight
    )
    add_float_violation(
        violations, summary, key="max_gross_notional", limit=gate.max_gross_notional
    )
    add_float_violation(
        violations, summary, key="max_cash_reserved", limit=gate.max_cash_reserved
    )
    if gate.fail_on_symbol_overlap and int(summary.get("same_symbol_overlap_rows", 0)):
        violations.append(f"same_symbol_overlap_rows={summary['same_symbol_overlap_rows']}")
    return violations


def add_float_violation(
    violations: list[str],
    summary: dict[str, Any],
    *,
    key: str,
    limit: float | None,
) -> None:
    if limit is not None and float(summary.get(key, 0.0)) > limit:
        violations.append(f"{key}={summary[key]} limit={limit}")


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
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
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
        f"model_gates_checked={summary['model_gates_checked']} "
        f"quality_errors={len(summary['quality_errors'])} "
        f"claim_boundary=summary_not_external_gate output={output}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
