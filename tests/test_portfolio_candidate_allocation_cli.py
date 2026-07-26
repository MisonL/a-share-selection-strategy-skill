from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import allocate_portfolio_candidate_capital as cli  # noqa: E402
import lib.gates.portfolio_candidate_allocation as allocation  # noqa: E402
from helpers import build_frame  # noqa: E402


class PortfolioCandidateAllocationCliTests(unittest.TestCase):
    def test_skips_candidates_that_exceed_max_open_positions(self) -> None:
        prices = build_frame(days=40)
        date = signal_date(prices, 20)
        frames = [candidates(prices, date, ["000002", "600001"])]

        selected, sized, skipped, summary = allocate(
            prices, frames, max_open_positions=1
        )

        self.assertEqual(1, len(selected[0]))
        self.assertEqual(1, len(sized[0]))
        self.assertEqual(["max_open_positions"], skipped["skip_reason"].tolist())
        self.assertEqual({"max_open_positions": 1}, summary["skip_reason_counts"])
        self.assertEqual("portfolio_cash_lot_floor", sized[0]["capital_model"].iloc[0])
        self.assertEqual(
            "local_portfolio_allocation_not_broker_or_external_cash_capacity_proof",
            sized[0]["sizing_claim_boundary"].iloc[0],
        )
        self.assertEqual(10000.0, summary["cash_budget"])
        self.assertEqual(5, summary["hold_days"])
        self.assertIn("max_gross_weight", summary)
        self.assertEqual(1.0, summary["max_gross_weight_limit"])

    def test_skips_overlapping_symbol_when_requested(self) -> None:
        prices = build_frame(days=40)
        first = signal_date(prices, 20)
        second = signal_date(prices, 22)
        frames = [
            candidates(prices, first, ["000002"]),
            candidates(prices, second, ["000002"]),
        ]

        selected, _sized, skipped, summary = allocate(
            prices, frames, fail_on_symbol_overlap=True
        )

        self.assertEqual([1, 0], [len(frame) for frame in selected])
        self.assertEqual(["symbol_overlap"], skipped["skip_reason"].tolist())
        self.assertEqual(1, summary["signals"][1]["skipped_candidates"])

    def test_skips_when_lot_floor_cannot_fit_remaining_cash(self) -> None:
        prices = build_frame(days=40)
        date = signal_date(prices, 20)
        frames = [candidates(prices, date, ["000002"])]

        selected, sized, skipped, summary = allocate(prices, frames, cash_budget=1000.0)

        self.assertEqual(0, len(selected[0]))
        self.assertEqual(0, len(sized[0]))
        self.assertEqual(["insufficient_cash_slot"], skipped["skip_reason"].tolist())
        self.assertEqual(0, summary["allocated_candidates"])
        self.assertEqual(0.0, summary["max_gross_weight"])

    def test_sizes_and_starts_capacity_at_next_observed_open(self) -> None:
        prices = build_frame(days=40)
        signal = signal_date(prices, 20)
        history = prices[prices["symbol"] == "000002"].reset_index(drop=True)
        entry_date = history.loc[21, "date"]
        entry_open = float(history.loc[20, "close"]) * 2
        prices.loc[
            (prices["symbol"] == "000002") & (prices["date"] == entry_date), "open"
        ] = entry_open
        frame = candidates(prices, signal, ["000002"])

        selected, sized, _skipped, _summary = allocate(
            prices, [frame], cash_budget=10000.0, max_open_positions=1
        )
        prepared = allocation.prepare_prices(prices)
        raw = allocation.prepare_candidates([frame]).iloc[0].to_dict()
        decision = allocation.allocation_decision(
            raw,
            prepared,
            {},
            cash_budget=10000.0,
            lot_size=100,
            hold_days=5,
            max_open_positions=1,
            max_gross_weight=1.0,
            max_gross_notional=10000.0,
            max_cash_reserved=10000.0,
            fail_on_symbol_overlap=False,
        )

        row = sized[0].iloc[0]
        expected_quantity = int(10000.0 / (entry_open * 100)) * 100
        self.assertEqual(1, len(selected[0]))
        self.assertEqual(expected_quantity, int(row["quantity"]))
        self.assertEqual(entry_open, float(row["sizing_entry_price"]))
        self.assertEqual(str(entry_date), row["sizing_entry_date"])
        self.assertEqual(expected_quantity * entry_open, float(row["cash_reserved"]))
        self.assertEqual(str(entry_date), decision["active_dates"][0])
        self.assertGreater(str(entry_date), signal)

    def test_expected_signal_dates_reject_mixed_candidate_file_dates(self) -> None:
        prices = build_frame(days=40)
        first = signal_date(prices, 20)
        second = signal_date(prices, 21)
        frame = pd.concat(
            [
                candidates(prices, first, ["000002"]),
                candidates(prices, second, ["600001"]),
            ],
            ignore_index=True,
        )

        with self.assertRaisesRegex(ValueError, f"expected-signal-date={first}"):
            allocate(prices, [frame], expected_signal_dates=[first])

    def test_cli_writes_selected_sized_skipped_and_summary(self) -> None:
        prices = build_frame(days=40)
        date = signal_date(prices, 20)
        frame = candidates(prices, date, ["000002", "600001"])
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = write_inputs(root, prices, frame)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli.main(cli_args(root, paths, max_open_positions=1))

            selected = pd.read_csv(root / "candidates.csv", dtype={"symbol": str})
            sized = pd.read_csv(root / "sized.csv", dtype={"symbol": str})
            skipped = pd.read_csv(root / "skipped.csv", dtype={"symbol": str})
            summary = json.loads((root / "allocation_summary.json").read_text())

        self.assertEqual(0, code)
        self.assertIn(
            "OK: allocation_model=portfolio_cash_lot_floor", stdout.getvalue()
        )
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(1, len(selected))
        self.assertEqual(1, len(sized))
        self.assertEqual(["max_open_positions"], skipped["skip_reason"].tolist())
        self.assertEqual(2, summary["raw_candidates"])
        self.assertEqual(
            "local_portfolio_allocation_not_broker_or_external_cash_capacity_proof",
            summary["claim_boundary"],
        )
        self.assertIn(
            "claim_boundary=local_portfolio_allocation_not_broker_or_external_cash_capacity_proof",
            stdout.getvalue(),
        )

    def test_cli_expected_signal_dates_returns_error_without_outputs(self) -> None:
        prices = build_frame(days=40)
        first = signal_date(prices, 20)
        second = signal_date(prices, 21)
        frame = pd.concat(
            [
                candidates(prices, first, ["000002"]),
                candidates(prices, second, ["600001"]),
            ],
            ignore_index=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = write_inputs(root, prices, frame)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli.main(
                    cli_args(root, paths, max_open_positions=1)
                    + ["--expected-signal-dates", first]
                )
            selected_exists = (root / "candidates.csv").exists()

        self.assertEqual(2, code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("expected-signal-date", stderr.getvalue())
        self.assertFalse(selected_exists)

    def test_cli_rejects_raw_candidates_with_sizing_fields_without_outputs(
        self,
    ) -> None:
        prices = build_frame(days=40)
        date = signal_date(prices, 20)
        frame = candidates(prices, date, ["000002"]).assign(
            cash_budget=[1.0],
            lot_size=[1],
            capital_model=["stale_model"],
            signal_close=[7.0],
            cash_slot=[1.0],
            unallocated=[True],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = write_inputs(root, prices, frame)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = cli.main(cli_args(root, paths, max_open_positions=1))
            output_paths = [
                root / "candidates.csv",
                root / "sized.csv",
                root / "skipped.csv",
                root / "allocation_summary.json",
            ]

        self.assertEqual(2, code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("already contain sizing fields", stderr.getvalue())
        self.assertIn("capital_model", stderr.getvalue())
        self.assertTrue(all(not path.exists() for path in output_paths))

    def test_non_finite_allocation_options_are_rejected(self) -> None:
        prices = build_frame(days=40)
        date = signal_date(prices, 20)
        frame = candidates(prices, date, ["000002"])
        base = {
            "cash_budget": 10000.0,
            "lot_size": 100,
            "hold_days": 5,
            "max_open_positions": 10,
            "max_gross_weight": 1.0,
            "max_gross_notional": 10000.0,
            "max_cash_reserved": 10000.0,
            "close_tolerance": 0.000001,
            "fail_on_symbol_overlap": False,
        }
        cases = [
            ("cash_budget", "cash-budget"),
            ("lot_size", "lot-size"),
            ("hold_days", "hold-days"),
            ("max_open_positions", "max-open-positions"),
            ("max_gross_weight", "max-gross-weight"),
            ("max_gross_notional", "max-gross-notional"),
            ("max_cash_reserved", "max-cash-reserved"),
            ("close_tolerance", "close-tolerance"),
        ]
        for field, label in cases:
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(field=field, value=value):
                    options = {**base, field: value}
                    with self.assertRaisesRegex(ValueError, f"{label} must be finite"):
                        allocation.allocate_portfolio(prices, [frame], **options)

    def test_derived_lot_quantity_overflow_is_rejected(self) -> None:
        prices = pd.DataFrame(
            [
                {
                    "symbol": "000001",
                    "date": "2026-01-01",
                    "open": 1e-320,
                    "high": 1.0,
                    "low": 1e-320,
                    "close": 1.0,
                    "volume": 1.0,
                },
                {
                    "symbol": "000001",
                    "date": "2026-01-02",
                    "open": 1e-320,
                    "high": 1.0,
                    "low": 1e-320,
                    "close": 1.0,
                    "volume": 1.0,
                },
            ]
        )
        frame = pd.DataFrame([{"symbol": "000001", "date": "2026-01-01", "close": 1.0}])

        with self.assertRaisesRegex(
            ValueError, "lot quantity calculation must be finite"
        ):
            allocation.allocate_portfolio(
                prices,
                [frame],
                cash_budget=1e308,
                lot_size=1,
                hold_days=1,
                max_open_positions=1,
                max_gross_weight=1.0,
                max_gross_notional=1e308,
                max_cash_reserved=1e308,
                fail_on_symbol_overlap=False,
            )

    def test_cli_non_finite_limit_removes_stale_outputs(self) -> None:
        prices = build_frame(days=40)
        date = signal_date(prices, 20)
        frame = candidates(prices, date, ["000002"])
        for value in ["nan", "inf", "-inf"]:
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as tmpdir:
                    root = Path(tmpdir)
                    paths = write_inputs(root, prices, frame)
                    outputs = [
                        root / "candidates.csv",
                        root / "sized.csv",
                        root / "skipped.csv",
                        root / "allocation_summary.json",
                    ]
                    for output in outputs:
                        output.write_text("stale result", encoding="utf-8")
                    stderr = StringIO()
                    with redirect_stderr(stderr):
                        code = cli.main(
                            cli_args(root, paths, max_open_positions=1)
                            + ["--max-gross-weight", value]
                        )

                self.assertEqual(2, code)
                self.assertTrue(all(not output.exists() for output in outputs))
                self.assertIn("max-gross-weight must be finite", stderr.getvalue())


def allocate(
    prices: pd.DataFrame,
    frames: list[pd.DataFrame],
    *,
    cash_budget: float = 10000.0,
    max_open_positions: int = 10,
    fail_on_symbol_overlap: bool = False,
    expected_signal_dates: list[str] | None = None,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame], pd.DataFrame, dict[str, object]]:
    return allocation.allocate_portfolio(
        prices,
        frames,
        expected_signal_dates=expected_signal_dates,
        cash_budget=cash_budget,
        lot_size=100,
        hold_days=5,
        max_open_positions=max_open_positions,
        max_gross_weight=1.0,
        max_gross_notional=cash_budget,
        max_cash_reserved=cash_budget,
        fail_on_symbol_overlap=fail_on_symbol_overlap,
    )


def signal_date(prices: pd.DataFrame, index: int) -> str:
    return str(prices[prices["symbol"] == "000002"].iloc[index]["date"])


def candidates(prices: pd.DataFrame, date: str, symbols: list[str]) -> pd.DataFrame:
    rows = []
    for rank, symbol in enumerate(symbols, start=1):
        row = prices[(prices["symbol"] == symbol) & (prices["date"] == date)].iloc[0]
        rows.append(
            {"rank": rank, "symbol": symbol, "date": date, "close": row["close"]}
        )
    return pd.DataFrame(rows)


def write_inputs(
    root: Path, prices: pd.DataFrame, frame: pd.DataFrame
) -> dict[str, Path]:
    paths = {"prices": root / "prices.csv", "raw": root / "raw.csv"}
    prices.to_csv(paths["prices"], index=False)
    frame.to_csv(paths["raw"], index=False)
    return paths


def cli_args(
    root: Path, paths: dict[str, Path], *, max_open_positions: int
) -> list[str]:
    return [
        "--prices",
        str(paths["prices"]),
        "--raw-candidates",
        str(paths["raw"]),
        "--candidate-outputs",
        str(root / "candidates.csv"),
        "--sized-outputs",
        str(root / "sized.csv"),
        "--skipped-output",
        str(root / "skipped.csv"),
        "--summary-output",
        str(root / "allocation_summary.json"),
        "--cash-budget",
        "10000",
        "--hold-days",
        "5",
        "--max-open-positions",
        str(max_open_positions),
        "--max-gross-weight",
        "1.0",
        "--max-gross-notional",
        "10000",
        "--max-cash-reserved",
        "10000",
    ]


if __name__ == "__main__":
    unittest.main()
