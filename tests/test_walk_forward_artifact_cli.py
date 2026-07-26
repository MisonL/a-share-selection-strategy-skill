from __future__ import annotations

import json
import os
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
from lib.selection_core.a_share_selection_model_contracts import (  # noqa: E402
    EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
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
        self.assertIn(
            f"execution_model={EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE}",
            stdout,
        )
        self.assertIn("manifest_checked=True", stdout)
        self.assertIn(
            "verdict=known_portfolio_violation_reproduced_not_capacity_pass", stdout
        )
        self.assertIn("claim_boundary=artifact_validation_not_external_gate", stdout)
        self.assertEqual("", stderr)
        self.assertEqual([], report["errors"])
        self.assertEqual(2, report["total_candidates"])
        self.assertEqual(
            EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
            report["execution_model"],
        )
        self.assertTrue(report["manifest_checked"])
        self.assertEqual(
            "known_portfolio_violation_reproduced_not_capacity_pass",
            report["verdict"],
        )

    def test_cli_rejects_future_price_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            append_price_row(
                root / "signals/2026-05-12/prices_signal_window.csv", "2026-05-13"
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_future_price_rows", stderr)

    def test_cli_rejects_mixed_format_future_price_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rename_signal_dir(root, "2026-05-12", "20260512")
            append_price_row(
                root / "signals/20260512/prices_signal_window.csv", "2026-05-13"
            )

            code, _stdout, stderr = call_cli(
                root,
                root / "artifact_validation.json",
                ["--signal-dates", "20260512"],
            )

        self.assertEqual(3, code)
        self.assertIn("20260512_future_price_rows", stderr)

    def test_cli_discloses_capacity_gate_failure_for_expected_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            output = root / "artifact_validation.json"

            code, stdout, stderr = call_cli(root, output)
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertIn("capacity_gate_pass=False", stdout)
        self.assertIn("capacity_gate_status=expected_violation_not_pass", stdout)
        self.assertIn("expected_portfolio_violations=True", stdout)
        self.assertFalse(report["capacity_gate_pass"])
        self.assertEqual("expected_violation_not_pass", report["capacity_gate_status"])
        self.assertTrue(report["expected_portfolio_violations"])

    def test_cli_reports_clear_pass_verdict_without_portfolio_violations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir), portfolio_violations=0)
            output = root / "artifact_validation.json"

            code, stdout, stderr = call_cli(
                root,
                output,
                ["--expected-portfolio-violations", "0"],
            )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertIn("verdict=artifacts_pass_enabled_gates_not_external_proof", stdout)
        self.assertTrue(report["capacity_gate_pass"])
        self.assertEqual("pass", report["capacity_gate_status"])
        self.assertEqual(
            "artifacts_pass_enabled_gates_not_external_proof", report["verdict"]
        )

    def test_cli_rejects_missing_sizing_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            drop_column(
                root / "signals/2026-05-12/prediction_sized_candidates.csv",
                "cash_reserved",
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_sized_missing_cash_reserved", stderr)

    def test_cli_rejects_backtest_signal_date_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rewrite_backtest_signal_date(
                root / "signals/2026-05-12/prediction_backtest.csv", "2026-05-09"
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_backtest_signal_date_mismatch=2026-05-09", stderr)

    def test_cli_rejects_same_day_backtest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rewrite_column(
                root / "signals/2026-05-12/prediction_backtest.csv",
                "entry_date",
                "2026-05-12",
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_entry_date=2026-05-12", stderr)
        self.assertIn("2026-05-12_entry_not_after_signal=2026-05-12", stderr)

    def test_cli_rejects_tampered_backtest_entry_price(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rewrite_column(
                root / "signals/2026-05-12/prediction_backtest.csv",
                "entry_price",
                99.0,
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_entry_price_mismatch=000001", stderr)

    def test_cli_rejects_output_aliases_without_overwriting_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            target = root / "prices.csv"
            original = target.read_bytes()
            relative_output = os.path.relpath(target, start=Path.cwd())
            symlink_output = root / "prices-link.csv"
            symlink_output.symlink_to(target)
            hardlink_output = root / "prices-hardlink.csv"
            os.link(target, hardlink_output)

            for output in (target, relative_output, symlink_output, hardlink_output):
                with self.subTest(output=str(output)):
                    code, stdout, stderr = call_cli(root, Path(output))

                    self.assertEqual(2, code)
                    self.assertEqual("", stdout)
                    self.assertEqual(original, target.read_bytes())
                    self.assertIn("output path must differ from input paths", stderr)
            self.assertTrue(symlink_output.is_symlink())
            self.assertTrue(os.path.samefile(target, hardlink_output))

    def test_cli_rejects_invalid_numeric_options_before_validation(self) -> None:
        cases = [
            ("--expected-candidates", "-1", "expected-candidates"),
            ("--backtest-value-tolerance", "nan", "backtest-value-tolerance"),
            ("--backtest-value-tolerance", "inf", "backtest-value-tolerance"),
            ("--backtest-value-tolerance", "-inf", "backtest-value-tolerance"),
            ("--backtest-value-tolerance", "-1", "backtest-value-tolerance"),
            ("--final-equity-tolerance", "inf", "final-equity-tolerance"),
            ("--expected-final-equity", "nan", "expected-final-equity"),
            (
                "--expected-portfolio-violations",
                "-1",
                "expected-portfolio-violations",
            ),
            ("--cash-budget", "nan", "cash-budget"),
            ("--cash-budget", "0", "cash-budget"),
            ("--lot-size", "inf", "lot-size"),
            ("--lot-size", "0", "lot-size"),
            ("--hold-days", "-1", "hold-days"),
            ("--cost-bps", "-inf", "cost-bps"),
            ("--slippage-bps", "-1", "slippage-bps"),
        ]
        for option, value, name in cases:
            with self.subTest(option=option, value=value):
                with tempfile.TemporaryDirectory() as tmpdir:
                    root = build_run(Path(tmpdir))
                    output = root / "artifact_validation.json"
                    rewrite_column(
                        root / "signals/2026-05-12/prediction_backtest.csv",
                        "entry_price",
                        99.0,
                    )

                    code, stdout, stderr = call_cli(
                        root,
                        output,
                        [option, value],
                    )

                    self.assertFalse(output.exists())
                self.assertEqual(2, code)
                self.assertEqual("", stdout)
                self.assertIn(f"{name} must be", stderr)

    def test_cli_rejects_sizing_entry_price_that_differs_from_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rewrite_column(
                root / "signals/2026-05-12/prediction_sized_candidates.csv",
                "sizing_entry_price",
                10.5,
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_sizing_entry_price_mismatch=000001", stderr)

    def test_cli_rejects_cash_reserved_that_uses_signal_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            path = root / "signals/2026-05-12/prediction_sized_candidates.csv"
            rewrite_column(path, "cash_reserved", 1050.0)
            rewrite_column(path, "notional", 1050.0)
            rewrite_column(path, "weight", 0.00105)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_cash_reserved_entry_price_mismatch", stderr)

    def test_cli_rejects_sized_cash_slot_that_differs_from_backtest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rewrite_column(
                root / "signals/2026-05-12/prediction_sized_candidates.csv",
                "cash_slot",
                499000.0,
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_sizing_field_mismatch=cash_slot:000001", stderr)

    def test_cli_rejects_tampered_backtest_exit_price(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rewrite_column(
                root / "signals/2026-05-12/prediction_backtest.csv",
                "exit_price",
                99.0,
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_exit_price_mismatch=000001", stderr)

    def test_cli_rejects_candidate_and_backtest_key_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rewrite_column(
                root / "signals/2026-05-12/prediction_backtest.csv",
                "symbol",
                "000003",
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_candidate_backtest_keys_mismatch", stderr)
        self.assertIn("2026-05-12_price_signal_missing=000003", stderr)

    def test_cli_rejects_missing_backtest_return_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            drop_column(root / "signals/2026-05-12/prediction_backtest.csv", "return")

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_backtest_missing_return", stderr)

    def test_cli_rejects_non_numeric_backtest_return_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            rewrite_column(
                root / "signals/2026-05-12/prediction_backtest.csv",
                "return",
                "not-a-number",
            )

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("2026-05-12_return=not-a-number", stderr)

    def test_cli_rejects_summary_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            summary = read_json(root / "prediction_run_summary.json")
            summary["signals"][0]["candidates"] = 3
            write_json(root / "prediction_run_summary.json", summary)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("summary_2026-05-12_candidates=3", stderr)

    def test_cli_rejects_summary_execution_model_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            summary = read_json(root / "prediction_run_summary.json")
            summary["execution_model"] = "close_to_close"
            write_json(root / "prediction_run_summary.json", summary)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("summary_execution_model=close_to_close", stderr)

    def test_cli_accepts_tiny_summary_equity_rounding_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            summary = read_json(root / "prediction_run_summary.json")
            summary["equity"]["final_equity"] = 0.9950000000000001
            write_json(root / "prediction_run_summary.json", summary)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(0, code)
        self.assertEqual("", stderr)

    def test_cli_rejects_invalid_equity_curve_values(self) -> None:
        cases = [
            ("nan", "nan"),
            ("positive_infinity", "inf"),
            ("negative_infinity", "-inf"),
            ("text", "not-a-number"),
        ]
        for label, value in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmpdir:
                    root = build_run(Path(tmpdir))
                    output = root / "artifact_validation.json"
                    rewrite_column(
                        root / "prediction_equity_curve.csv", "equity", value
                    )

                    code, _stdout, stderr = call_cli(root, output)
                    report = read_strict_json(output)

                self.assertEqual(3, code)
                self.assertIn("equity_invalid_equity=", stderr)
                self.assertIn("equity_final_equity_invalid=", stderr)
                self.assertIsInstance(report["final_equity"], float)

    def test_cli_rejects_invalid_summary_final_equity_with_standard_json_report(
        self,
    ) -> None:
        cases = [
            ("null", None),
            ("nan", float("nan")),
            ("positive_infinity", float("inf")),
            ("negative_infinity", float("-inf")),
            ("text", "not-a-number"),
        ]
        for label, value in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmpdir:
                    root = build_run(Path(tmpdir))
                    output = root / "artifact_validation.json"
                    summary = read_json(root / "prediction_run_summary.json")
                    summary["equity"]["final_equity"] = value
                    write_json(root / "prediction_run_summary.json", summary)

                    code, _stdout, stderr = call_cli(root, output)
                    report = read_strict_json(output)

                self.assertEqual(3, code)
                self.assertIn("summary_equity_final_equity_invalid=", stderr)
                self.assertIsNone(report["final_equity"])

    def test_cli_rejects_invalid_overlap_capacity_with_standard_json_report(
        self,
    ) -> None:
        cases = (
            (
                "max_open_positions",
                float("nan"),
                "portfolio_max_open_positions_non_finite",
            ),
            (
                "same_symbol_overlap_rows",
                float("inf"),
                "portfolio_same_symbol_overlap_rows_non_finite",
            ),
            (
                "max_gross_weight",
                float("-inf"),
                "portfolio_max_gross_weight_non_finite",
            ),
            (
                "max_gross_notional",
                "nan",
                "portfolio_max_gross_notional_non_numeric",
            ),
            (
                "max_cash_reserved",
                True,
                "portfolio_max_cash_reserved_non_numeric",
            ),
        )
        for field, value, expected_error in cases:
            with (
                self.subTest(field=field, value=value),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                root = build_run(Path(tmpdir), portfolio_violations=0)
                overlap_path = root / "prediction_overlap_summary.json"
                overlap = read_json(overlap_path)
                overlap[field] = value
                write_json(overlap_path, overlap)
                output = root / "artifact_validation.json"

                code, _stdout, stderr = call_cli(
                    root,
                    output,
                    ["--expected-portfolio-violations", "0"],
                )
                report = read_strict_json(output)

            self.assertEqual(3, code)
            self.assertIn(expected_error, stderr)
            self.assertIn(expected_error, report["errors"])
            self.assertFalse(report["capacity_gate_pass"])
            self.assertEqual("failed_not_pass", report["capacity_gate_status"])
            self.assertEqual("artifact_validation_failed", report["verdict"])

    def test_cli_rejects_non_object_overlap_with_standard_failure_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir), portfolio_violations=0)
            overlap_path = root / "prediction_overlap_summary.json"
            write_json(overlap_path, ["invalid"])
            output = root / "artifact_validation.json"

            code, _stdout, stderr = call_cli(
                root,
                output,
                ["--expected-portfolio-violations", "0"],
            )
            report = read_strict_json(output)

        self.assertEqual(3, code)
        self.assertIn("portfolio_overlap_summary_not_object", stderr)
        self.assertIn("portfolio_overlap_summary_not_object", report["errors"])
        self.assertFalse(report["capacity_gate_pass"])
        self.assertEqual("failed_not_pass", report["capacity_gate_status"])
        self.assertEqual("artifact_validation_failed", report["verdict"])

    def test_write_json_rejects_non_finite_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "artifact_validation.json"
            with self.assertRaises(ValueError):
                artifact_cli.write_json({"value": float("nan")}, output)
            self.assertFalse(output.exists())

    def test_cli_auto_checks_existing_manifest_validation_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            manifest = read_json(root / "run_manifest_validation.json")
            manifest["errors"] = ["step_failed"]
            write_json(root / "run_manifest_validation.json", manifest)

            code, stdout, stderr = call_cli(
                root,
                root / "artifact_validation.json",
                include_manifest_validation=False,
            )

        self.assertEqual(3, code)
        self.assertIn("manifest_checked=True", stdout)
        self.assertIn("manifest_errors=1", stderr)


def call_cli(
    root: Path,
    output: Path,
    extra_args: list[str] | None = None,
    *,
    include_manifest_validation: bool = True,
) -> tuple[int, str, str]:
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
    ]
    if include_manifest_validation:
        args.extend(
            ["--manifest-validation", str(root / "run_manifest_validation.json")]
        )
    if extra_args:
        args.extend(extra_args)
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = artifact_cli.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def build_run(root: Path, *, portfolio_violations: int = 1) -> Path:
    signal_dir = root / "signals/2026-05-12"
    signal_dir.mkdir(parents=True)
    write_json(root / "metadata.json", metadata())
    write_json(signal_dir / "prediction_summary.json", prediction())
    write_csv(signal_dir / "prices_signal_window.csv", price_rows())
    write_csv(root / "prices.csv", full_price_rows())
    write_csv(signal_dir / "prediction_candidates.csv", candidate_rows())
    write_csv(signal_dir / "prediction_sized_candidates.csv", sized_rows())
    write_csv(signal_dir / "prediction_backtest.csv", backtest_rows())
    write_csv(root / "prediction_equity_curve.csv", equity_rows())
    write_json(
        root / "prediction_overlap_summary.json", overlap_summary(portfolio_violations)
    )
    write_json(root / "prediction_run_summary.json", run_summary(portfolio_violations))
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


def full_price_rows() -> list[dict[str, object]]:
    rows = []
    for symbol in ["000001", "600000"]:
        for offset, date in enumerate(
            [
                "2026-05-12",
                "2026-05-13",
                "2026-05-14",
                "2026-05-15",
                "2026-05-18",
                "2026-05-19",
            ]
        ):
            row = price_row(symbol, date)
            if offset:
                row["open"] = 10.0
                row["close"] = 9.965 if offset == 5 else 10.1
            rows.append(row)
    return rows


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
                "cash_reserved": 1000.0,
                "notional": 1000.0,
                "weight": 0.001,
                "sizing_claim_boundary": "local_sizing_not_broker_order",
                "unallocated": False,
                "sizing_execution_model": EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
                "sizing_entry_date": "2026-05-13",
                "sizing_entry_price": 10.0,
                "sizing_entry_price_field": "open",
                "sizing_skip_reason": "",
            }
        )
    return rows


def backtest_rows() -> list[dict[str, object]]:
    rows = []
    for row in candidate_rows():
        entry_price = 10.0
        exit_price = 9.965
        gross_return = exit_price / entry_price - 1.0
        rows.append(
            {
                "symbol": row["symbol"],
                "signal_date": "2026-05-12",
                "execution_model": EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
                "entry_date": "2026-05-13",
                "exit_date": "2026-05-19",
                "entry_price": entry_price,
                "entry_price_field": "open",
                "exit_price": exit_price,
                "exit_price_field": "close",
                "gross_return": gross_return,
                "return": gross_return - 0.0015,
                "status": "complete",
                "missing_data": False,
                "tradability_model": TRADABILITY_MODEL_ENTRY_EXIT,
                "limit_rules_model": LIMIT_RULES_MODEL_NOT_MODELED,
                "hold_days_requested": 5,
                "holding_observed_bars": 5,
                "holding_period": 4,
                "cost_bps": 10.0,
                "slippage_bps": 5.0,
                "cash_budget": 1000000.0,
                "lot_size": 100,
                "capital_model": "equal_cash_budget_lot_floor",
                "signal_close": 10.5,
                "cash_slot": 500000.0,
                "quantity": 100,
                "cash_reserved": 1000.0,
                "notional": 1000.0,
                "weight": 0.001,
                "sizing_claim_boundary": "local_sizing_not_broker_order",
                "unallocated": False,
                "sizing_execution_model": EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
                "sizing_entry_date": "2026-05-13",
                "sizing_entry_price": 10.0,
                "sizing_entry_price_field": "open",
                "sizing_skip_reason": "",
            }
        )
    return rows


def equity_rows() -> list[dict[str, object]]:
    return [
        {
            "signal_date": "2026-05-12",
            "positions": 2,
            "incomplete_trades": 0,
            "equity": 0.995,
        }
    ]


def overlap_summary(portfolio_violations: int = 1) -> dict[str, object]:
    return {
        "cash_capacity_verifiable": True,
        "weight_capacity_verifiable": True,
        "capital_fields_missing": [],
        "max_open_positions": 2,
        "max_gross_weight": 0.0021,
        "max_gross_notional": 2100.0,
        "max_cash_reserved": 2100.0,
        "same_symbol_overlap_rows": portfolio_violations,
    }


def run_summary(portfolio_violations: int = 1) -> dict[str, object]:
    violations = []
    if portfolio_violations:
        violations.append(f"same_symbol_overlap_rows={portfolio_violations}")
    return {
        "quality_errors": [],
        "execution_model": EXECUTION_MODEL_SIGNAL_CLOSE_NEXT_OBSERVED_OPEN_TO_CLOSE,
        "signals": [
            {"signal_date": "2026-05-12", "candidates": 2, "completed_trades": 2}
        ],
        "equity": {"final_equity": 0.995},
        "portfolio": {
            "summary": overlap_summary(portfolio_violations),
            "violations": violations,
        },
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
    rows = pd.concat(
        [rows, pd.DataFrame([price_row("000001", date)])], ignore_index=True
    )
    rows.to_csv(path, index=False)


def rename_signal_dir(root: Path, source: str, target: str) -> None:
    (root / "signals" / source).rename(root / "signals" / target)


def drop_column(path: Path, column: str) -> None:
    rows = pd.read_csv(path, dtype={"symbol": str})
    rows = rows.drop(columns=[column])
    rows.to_csv(path, index=False)


def rewrite_backtest_signal_date(path: Path, signal_date: str) -> None:
    rows = pd.read_csv(path, dtype={"symbol": str})
    rows.loc[0, "signal_date"] = signal_date
    rows.to_csv(path, index=False)


def rewrite_column(path: Path, column: str, value: object) -> None:
    rows = pd.read_csv(path, dtype={"symbol": str})
    rows[column] = rows[column].astype("object")
    rows.loc[0, column] = value
    rows.to_csv(path, index=False)


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_strict_json(path: Path) -> dict[str, object]:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_non_standard_json_constant,
    )


def reject_non_standard_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
