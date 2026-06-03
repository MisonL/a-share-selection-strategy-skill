from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import validate_walk_forward_artifacts as artifact_cli  # noqa: E402
from a_share_selection_model_contracts import (  # noqa: E402
    LIMIT_RULES_MODEL_NOT_MODELED,
    TRADABILITY_MODEL_ENTRY_EXIT,
)


class WalkForwardArtifactCliTests(unittest.TestCase):
    def test_cli_accepts_consistent_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            output = root / "artifact_validation.json"

            code, stdout, stderr = call_cli(root, output)
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertIn("OK:", stdout)
        self.assertEqual("", stderr)
        self.assertEqual([], report["errors"])
        self.assertEqual(2, report["total_candidates"])
        self.assertTrue(report["manifest_checked"])

    def test_cli_rejects_future_price_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            append_price_row(root / "signals/2026-05-12/prices_signal_window.csv", "2026-05-13")

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_future_price_rows", stderr)

    def test_cli_rejects_missing_sizing_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            drop_column(root / "signals/2026-05-12/prediction_sized_candidates.csv", "cash_reserved")

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_sized_missing_cash_reserved", stderr)

    def test_cli_rejects_backtest_signal_date_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rewrite_backtest_signal_date(root / "signals/2026-05-12/prediction_backtest.csv", "2026-05-09")

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_backtest_signal_date_mismatch=2026-05-09", stderr)

    def test_cli_rejects_summary_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            summary = read_json(root / "prediction_run_summary.json")
            summary["signals"][0]["candidates"] = 3
            write_json(root / "prediction_run_summary.json", summary)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("summary_2026-05-12_candidates=3", stderr)

    def test_cli_accepts_tiny_summary_equity_rounding_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            summary = read_json(root / "prediction_run_summary.json")
            summary["equity"]["final_equity"] = 0.9950000000000001
            write_json(root / "prediction_run_summary.json", summary)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(0, code)
        self.assertEqual("", stderr)

    def test_cli_rejects_null_summary_final_equity_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            summary = read_json(root / "prediction_run_summary.json")
            summary["equity"]["final_equity"] = None
            write_json(root / "prediction_run_summary.json", summary)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("summary_equity_final_mismatch", stderr)


def call_cli(root: Path, output: Path, extra_args: list[str] | None = None) -> tuple[int, str, str]:
    args = [
        "--run-dir",
        str(root),
        "--output",
        str(output),
        "--signal-dates",
        "2026-05-12",
        "--expected-symbols",
        "000001",
        "600000",
        "--expected-candidates",
        "2",
        "--expected-final-equity",
        "0.995",
        "--expected-portfolio-violations",
        "1",
        "--required-tradability-model",
        TRADABILITY_MODEL_ENTRY_EXIT,
        "--required-limit-rules-model",
        LIMIT_RULES_MODEL_NOT_MODELED,
        "--manifest-validation",
        str(root / "run_manifest_validation.json"),
    ]
    if extra_args:
        args.extend(extra_args)
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = artifact_cli.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def build_run(root: Path) -> Path:
    signal_dir = root / "signals/2026-05-12"
    signal_dir.mkdir(parents=True)
    write_json(root / "metadata.json", metadata())
    write_json(signal_dir / "prediction_summary.json", prediction())
    write_csv(signal_dir / "prices_signal_window.csv", price_rows())
    write_csv(signal_dir / "prediction_candidates.csv", candidate_rows())
    write_csv(signal_dir / "prediction_sized_candidates.csv", sized_rows())
    write_csv(signal_dir / "prediction_backtest.csv", backtest_rows())
    write_csv(root / "prediction_equity_curve.csv", equity_rows())
    write_json(root / "prediction_overlap_summary.json", overlap_summary())
    write_json(root / "prediction_run_summary.json", run_summary())
    write_json(root / "run_manifest_validation.json", manifest_validation())
    return root


def metadata() -> dict[str, object]:
    return {
        "source": "baostock",
        "adjustflag": "3",
        "requested_symbols": ["000001", "600000"],
        "symbols": [{"symbol": "000001"}, {"symbol": "600000"}],
        "rows": 4,
        "raw_rows": 4,
        "symbol_count": 2,
        "failed_symbols": [],
        "empty_symbols": [],
        "invalid_rows": 0,
        "dropped_invalid_rows": 0,
        "raw_non_trading_rows": 0,
        "non_trading_rows": 0,
        "raw_tradestatus_missing_rows": 0,
        "tradestatus_missing_rows": 0,
    }


def prediction() -> dict[str, int]:
    return {"raw_symbols": 2, "predicted_symbols": 2, "skipped_symbols": 0}


def price_rows() -> list[dict[str, object]]:
    return [price_row("000001"), price_row("600000")]


def price_row(symbol: str, date: str = "2026-05-12") -> dict[str, object]:
    return {
        "symbol": symbol,
        "date": date,
        "open": 10.0,
        "high": 11.0,
        "low": 9.0,
        "close": 10.5,
        "volume": 100000,
        "amount": 1000000,
        "turn": 1.1,
        "tradestatus": 1,
        "isST": 0,
    }


def candidate_rows() -> list[dict[str, object]]:
    return [
        {"symbol": "000001", "date": "2026-05-12", "close": 10.5, "total_score": 0.8},
        {"symbol": "600000", "date": "2026-05-12", "close": 10.5, "total_score": 0.7},
    ]


def sized_rows() -> list[dict[str, object]]:
    rows = []
    for row in candidate_rows():
        rows.append(
            {
                **row,
                "cash_budget": 1000000.0,
                "lot_size": 100,
                "capital_model": "equal_cash_budget_lot_floor",
                "signal_close": 10.5,
                "cash_slot": 500000.0,
                "quantity": 100,
                "cash_reserved": 1050.0,
                "notional": 1050.0,
                "weight": 0.00105,
                "unallocated": False,
            }
        )
    return rows


def backtest_rows() -> list[dict[str, object]]:
    rows = []
    for row in candidate_rows():
        rows.append(
            {
                "symbol": row["symbol"],
                "signal_date": "2026-05-12",
                "status": "complete",
                "missing_data": False,
                "tradability_model": TRADABILITY_MODEL_ENTRY_EXIT,
                "limit_rules_model": LIMIT_RULES_MODEL_NOT_MODELED,
                "hold_days_requested": 5,
                "cost_bps": 10.0,
                "slippage_bps": 5.0,
                "weight": 0.00105,
                "notional": 1050.0,
                "quantity": 100,
                "cash_reserved": 1050.0,
            }
        )
    return rows


def equity_rows() -> list[dict[str, object]]:
    return [{"signal_date": "2026-05-12", "positions": 2, "incomplete_trades": 0, "equity": 0.995}]


def overlap_summary() -> dict[str, object]:
    return {
        "cash_capacity_verifiable": True,
        "weight_capacity_verifiable": True,
        "capital_fields_missing": [],
        "same_symbol_overlap_rows": 1,
    }


def run_summary() -> dict[str, object]:
    return {
        "quality_errors": [],
        "signals": [
            {"signal_date": "2026-05-12", "candidates": 2, "completed_trades": 2}
        ],
        "equity": {"final_equity": 0.995},
        "portfolio": {"summary": overlap_summary(), "violations": ["same_symbol_overlap_rows=1"]},
    }


def manifest_validation() -> dict[str, object]:
    return {
        "validator": "validate_walk_forward_manifest",
        "errors": [],
        "signals": ["2026-05-12"],
        "steps_checked": 10,
    }


def append_price_row(path: Path, date: str) -> None:
    rows = pd.read_csv(path, dtype={"symbol": str})
    rows = pd.concat([rows, pd.DataFrame([price_row("000001", date)])], ignore_index=True)
    rows.to_csv(path, index=False)


def drop_column(path: Path, column: str) -> None:
    rows = pd.read_csv(path, dtype={"symbol": str})
    rows = rows.drop(columns=[column])
    rows.to_csv(path, index=False)


def rewrite_backtest_signal_date(path: Path, signal_date: str) -> None:
    rows = pd.read_csv(path, dtype={"symbol": str})
    rows.loc[0, "signal_date"] = signal_date
    rows.to_csv(path, index=False)


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
