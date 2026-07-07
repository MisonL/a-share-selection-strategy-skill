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
