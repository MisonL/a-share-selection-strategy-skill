"""Command builders for portfolio-aware walk-forward steps."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ALLOCATION_MODEL_EQUAL = "equal_cash_budget_lot_floor"
ALLOCATION_MODEL_PORTFOLIO = "portfolio_cash_lot_floor"


def portfolio_allocate_command(args: Any, output: Path, signals: list[Any]) -> list[str]:
    command = script_command("allocate_portfolio_candidate_capital.py", "--prices", output / "prices.csv")
    command.extend(["--raw-candidates", *[str(signal.paths["raw_candidates"]) for signal in signals]])
    command.extend(["--candidate-outputs", *[str(signal.paths["candidates"]) for signal in signals]])
    command.extend(["--sized-outputs", *[str(signal.paths["sized"]) for signal in signals]])
    command.extend(["--skipped-output", str(output / "qsss_skipped_candidates.csv")])
    command.extend(["--summary-output", str(output / "qsss_allocation_summary.json")])
    command.extend(["--cash-budget", str(args.cash_budget), "--lot-size", str(args.lot_size)])
    command.extend(["--hold-days", str(args.hold_days), "--max-open-positions", str(args.max_open_positions)])
    command.extend(["--max-gross-weight", str(args.max_gross_weight)])
    command.extend(["--max-gross-notional", str(args.max_gross_notional)])
    command.extend(["--max-cash-reserved", str(args.max_cash_reserved)])
    if args.fail_on_symbol_overlap:
        command.append("--fail-on-symbol-overlap")
    return command


def script_command(script: str, *parts: object) -> list[str]:
    scripts = Path(__file__).resolve().parent
    return [sys.executable, str(scripts / script), *[str(part) for part in parts]]
