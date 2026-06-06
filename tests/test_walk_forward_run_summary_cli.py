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

import summarize_walk_forward_run as run_summary  # noqa: E402
from a_share_selection_model_contracts import (  # noqa: E402
    LIMIT_RULES_MODEL_NOT_MODELED,
    TRADABILITY_MODEL_ENTRY_EXIT,
)


class WalkForwardRunSummaryCliTests(unittest.TestCase):
    def test_cli_accepts_expected_portfolio_violations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir), portfolio_violates=True)
            output = Path(tmpdir) / "summary.json"

            code, stdout, stderr = call_cli(
                root,
                output,
                [
                    "--expected-symbol-count",
                    "2",
                    "--required-tradability-model",
                    TRADABILITY_MODEL_ENTRY_EXIT,
                    "--required-limit-rules-model",
                    LIMIT_RULES_MODEL_NOT_MODELED,
                    "--max-open-positions",
                    "2",
                    "--max-gross-weight",
                    "1.0",
                    "--max-gross-notional",
                    "1000",
                    "--max-cash-reserved",
                    "1000",
                    "--fail-on-symbol-overlap",
                    "--expect-portfolio-violations",
                ],
            )

            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertIn("OK:", stdout)
        self.assertIn("capacity_gate_pass=False", stdout)
        self.assertIn("capacity_gate_status=expected_violation_not_pass", stdout)
        self.assertIn("expected_portfolio_violations=True", stdout)
        self.assertIn("model_gates_checked=True", stdout)
        self.assertIn("claim_boundary=summary_not_external_gate", stdout)
        self.assertEqual("", stderr)
        self.assertEqual([], data["quality_errors"])
        self.assertEqual(5, len(data["portfolio"]["violations"]))
        self.assertEqual(2, data["signals"][0]["candidates"])
        self.assertFalse(data["capacity_gate_pass"])
        self.assertEqual("expected_violation_not_pass", data["capacity_gate_status"])
        self.assertTrue(data["expected_portfolio_violations"])
        self.assertEqual("summary_not_external_gate", data["claim_boundary"])
        self.assertTrue(data["required_tradability_model_checked"])
        self.assertTrue(data["required_limit_rules_model_checked"])
        self.assertTrue(data["model_gates_checked"])

    def test_cli_discloses_unchecked_model_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir), portfolio_violates=False)
            output = Path(tmpdir) / "summary.json"

            code, stdout, stderr = call_cli(root, output, ["--expected-symbol-count", "2"])

            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertIn("model_gates_checked=False", stdout)
        self.assertFalse(data["required_tradability_model_checked"])
        self.assertFalse(data["required_limit_rules_model_checked"])
        self.assertFalse(data["model_gates_checked"])

    def test_cli_fails_when_prediction_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir), skipped_symbols=1)
            output = Path(tmpdir) / "summary.json"

            code, stdout, stderr = call_cli(root, output, ["--expected-symbol-count", "2"])

            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(3, code)
        self.assertIn("ERROR_SUMMARY:", stdout)
        self.assertIn("2026-05-12_skipped_symbols=1", stderr)
        self.assertIn("2026-05-12_skipped_symbols=1", data["quality_errors"])

    def test_cli_rejects_backtest_rows_missing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            backtest = root / "2026-05-12" / "prediction_backtest.csv"
            rows = pd.read_csv(backtest, dtype={"symbol": str}).iloc[:1]
            rows.to_csv(backtest, index=False)
            output = Path(tmpdir) / "summary.json"

            code, stdout, stderr = call_cli(root, output, ["--expected-symbol-count", "2"])
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(3, code)
        self.assertIn("ERROR_SUMMARY:", stdout)
        self.assertIn("2026-05-12_backtest_rows=1 candidates=2", stderr)
        self.assertIn("2026-05-12_completed_trades=1 candidates=2", stderr)
        self.assertIn("backtest_rows", data["signals"][0])
        self.assertEqual(1, data["signals"][0]["backtest_rows"])
        self.assertIn(
            "2026-05-12_backtest_rows=1 candidates=2",
            data["quality_errors"],
        )

    def test_cli_fails_when_expected_portfolio_violation_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir), portfolio_violates=False)
            output = Path(tmpdir) / "summary.json"

            code, _, stderr = call_cli(
                root,
                output,
                [
                    "--max-open-positions",
                    "5",
                    "--max-gross-weight",
                    "2.0",
                    "--expect-portfolio-violations",
                ],
            )

        self.assertEqual(3, code)
        self.assertIn("expected_portfolio_violations_missing", stderr)

    def test_cli_reads_nested_signals_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir), signal_parent="signals")
            output = Path(tmpdir) / "summary.json"

            code, _, _ = call_cli(root, output, ["--signal-dates", "2026-05-12"])

            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertEqual("2026-05-12", data["signals"][0]["signal_date"])

    def test_cli_rejects_dropped_invalid_rows_without_explicit_allow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(
                Path(tmpdir),
                metadata_updates={
                    "invalid_rows": 10,
                    "dropped_invalid_rows": 10,
                    "raw_non_trading_rows": 10,
                    "non_trading_rows": 0,
                },
            )
            output = Path(tmpdir) / "summary.json"

            code, _stdout, stderr = call_cli(root, output, ["--expected-symbol-count", "2"])

        self.assertEqual(3, code)
        self.assertIn("metadata_invalid_rows=10", stderr)

    def test_cli_allows_explicitly_dropped_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(
                Path(tmpdir),
                metadata_updates={
                    "invalid_rows": 10,
                    "dropped_invalid_rows": 10,
                    "raw_non_trading_rows": 10,
                    "non_trading_rows": 0,
                },
            )
            output = Path(tmpdir) / "summary.json"

            code, _stdout, stderr = call_cli(
                root,
                output,
                ["--expected-symbol-count", "2", "--allow-dropped-invalid-rows"],
            )

            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual([], data["quality_errors"])


def call_cli(root: Path, output: Path, extra_args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = run_summary.main(["--run-dir", str(root), "--output", str(output), *extra_args])
    return code, stdout.getvalue(), stderr.getvalue()


def build_run(
    root: Path,
    *,
    portfolio_violates: bool = False,
    skipped_symbols: int = 0,
    signal_parent: str = "",
    metadata_updates: dict[str, object] | None = None,
) -> Path:
    metadata = {
        "source": "baostock",
        "start_date": "2026-05-01",
        "end_date": "2026-05-20",
        "adjustflag": "3",
        "rows": 20,
        "raw_rows": 20,
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
    if metadata_updates:
        metadata.update(metadata_updates)
    write_json(
        root / "metadata.json",
        metadata,
    )
    write_signal_dir(root / signal_parent / "2026-05-12", skipped_symbols)
    write_equity(root / "prediction_equity_curve.csv")
    write_json(root / "prediction_overlap_summary.json", overlap_summary(portfolio_violates))
    return root


def write_signal_dir(path: Path, skipped_symbols: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    write_json(
        path / "prediction_summary.json",
        {"raw_symbols": 2, "predicted_symbols": 2 - skipped_symbols, "skipped_symbols": skipped_symbols},
    )
    pd.DataFrame([{"symbol": "000001"}, {"symbol": "000002"}]).to_csv(
        path / "prediction_candidates.csv",
        index=False,
    )
    pd.DataFrame(
        [
            backtest_row("000001", -0.02),
            backtest_row("000002", 0.01),
        ]
    ).to_csv(path / "prediction_backtest.csv", index=False)


def backtest_row(symbol: str, value: float) -> dict[str, object]:
    return {
        "symbol": symbol,
        "signal_date": "2026-05-12",
        "return": value,
        "missing_data": False,
        "status": "complete",
        "tradability_model": TRADABILITY_MODEL_ENTRY_EXIT,
        "limit_rules_model": LIMIT_RULES_MODEL_NOT_MODELED,
    }


class CompleteTradesTests(unittest.TestCase):
    def test_numeric_missing_data_flag_excludes_trade(self) -> None:
        frame = pd.DataFrame([backtest_row("000001", 0.01)])
        frame["missing_data"] = 1.0

        complete = run_summary.complete_trades(frame)

        self.assertTrue(complete.empty)


def write_equity(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "signal_date": "2026-05-12",
                "positions": 2,
                "incomplete_trades": 0,
                "equity": 0.995,
                "drawdown": -0.005,
            }
        ]
    ).to_csv(path, index=False)


def overlap_summary(portfolio_violates: bool) -> dict[str, object]:
    if portfolio_violates:
        return {
            "max_open_positions": 3,
            "max_gross_weight": 1.2,
            "max_gross_notional": 1200.0,
            "max_cash_reserved": 1200.0,
            "same_symbol_overlap_rows": 1,
        }
    return {
        "max_open_positions": 2,
        "max_gross_weight": 0.8,
        "max_gross_notional": 800.0,
        "max_cash_reserved": 800.0,
        "same_symbol_overlap_rows": 0,
    }


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
