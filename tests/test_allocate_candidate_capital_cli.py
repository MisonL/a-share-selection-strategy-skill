from __future__ import annotations

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

import allocate_candidate_capital as allocator  # noqa: E402
from helpers import build_frame  # noqa: E402


class AllocateCandidateCapitalCliTests(unittest.TestCase):
    def test_allocates_equal_cash_lot_floor_from_signal_close(self) -> None:
        prices = build_frame(days=130)
        first = prices[prices["symbol"] == "000002"].iloc[20]
        second = prices[prices["symbol"] == "600001"].iloc[20]
        candidates = pd.DataFrame(
            [
                {"symbol": "000002", "date": first["date"], "close": first["close"]},
                {"symbol": "600001", "date": second["date"], "close": second["close"]},
            ]
        )

        result, summary = allocator.allocate_capital(
            prices,
            candidates,
            cash_budget=10000,
            lot_size=100,
        )

        expected_first = int((5000 / (float(first["close"]) * 100))) * 100
        expected_second = int((5000 / (float(second["close"]) * 100))) * 100
        self.assertEqual([expected_first, expected_second], result["quantity"].tolist())
        self.assertEqual(float(first["close"]), float(result["signal_close"].iloc[0]))
        self.assertEqual(float(second["close"]), float(result["signal_close"].iloc[1]))
        self.assertEqual(result["notional"].tolist(), result["cash_reserved"].tolist())
        self.assertLessEqual(float(result["cash_reserved"].sum()), 10000.0)
        self.assertEqual(2, summary["allocated_candidates"])
        self.assertEqual(0, summary["unallocated_candidates"])
        self.assertEqual("equal_cash_budget_lot_floor", summary["capital_model"])

    def test_cli_strict_unallocated_returns_error_without_output(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]
        with tempfile.TemporaryDirectory() as tmpdir:
            prices_path = Path(tmpdir) / "prices.csv"
            candidates_path = Path(tmpdir) / "candidates.csv"
            output_path = Path(tmpdir) / "allocated.csv"
            prices.to_csv(prices_path, index=False)
            candidate.to_csv(candidates_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = allocator.main(
                    [
                        "--prices",
                        str(prices_path),
                        "--candidates",
                        str(candidates_path),
                        "--output",
                        str(output_path),
                        "--cash-budget",
                        "1",
                        "--fail-on-unallocated",
                    ]
                )

        self.assertEqual(3, code)
        self.assertFalse(output_path.exists())
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("unallocated_candidates=1", stderr.getvalue())

    def test_cli_success_discloses_local_sizing_boundary(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]
        with tempfile.TemporaryDirectory() as tmpdir:
            prices_path = Path(tmpdir) / "prices.csv"
            candidates_path = Path(tmpdir) / "candidates.csv"
            output_path = Path(tmpdir) / "allocated.csv"
            prices.to_csv(prices_path, index=False)
            candidate.to_csv(candidates_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = allocator.main(
                    [
                        "--prices",
                        str(prices_path),
                        "--candidates",
                        str(candidates_path),
                        "--output",
                        str(output_path),
                        "--cash-budget",
                        "100000",
                        "--lot-size",
                        "100",
                    ]
                )
            output_exists = output_path.exists()
            output = pd.read_csv(output_path)

        self.assertEqual(0, code, stderr.getvalue())
        self.assertTrue(output_exists)
        self.assertIn("lot_size=100", stdout.getvalue())
        self.assertIn(
            "claim_boundary=local_sizing_not_broker_order",
            stdout.getvalue(),
        )
        self.assertEqual(
            ["local_sizing_not_broker_order"],
            output["sizing_claim_boundary"].unique().tolist(),
        )

    def test_cli_non_strict_unallocated_warns_in_stdout(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]
        with tempfile.TemporaryDirectory() as tmpdir:
            prices_path = Path(tmpdir) / "prices.csv"
            candidates_path = Path(tmpdir) / "candidates.csv"
            output_path = Path(tmpdir) / "allocated.csv"
            prices.to_csv(prices_path, index=False)
            candidate.to_csv(candidates_path, index=False)
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = allocator.main(
                    [
                        "--prices",
                        str(prices_path),
                        "--candidates",
                        str(candidates_path),
                        "--output",
                        str(output_path),
                        "--cash-budget",
                        "1",
                    ]
                )
            output_exists = output_path.exists()

        self.assertEqual(0, code, stderr.getvalue())
        self.assertTrue(output_exists)
        self.assertIn("WARNING: unallocated_candidates=1", stdout.getvalue())
        self.assertIn("--fail-on-unallocated", stdout.getvalue())

    def test_missing_signal_close_is_rejected(self) -> None:
        prices = build_frame(days=130)
        candidate = pd.DataFrame([{"symbol": "000002", "date": "2030-01-01"}])

        with self.assertRaisesRegex(ValueError, "missing signal close"):
            allocator.allocate_capital(prices, candidate, cash_budget=10000)

    def test_existing_capital_fields_require_explicit_overwrite(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]
        candidate = candidate.assign(weight=[0.2])

        with self.assertRaisesRegex(ValueError, "already contain sizing fields"):
            allocator.allocate_capital(prices, candidate, cash_budget=10000)

        result, _ = allocator.allocate_capital(
            prices,
            candidate,
            cash_budget=10000,
            overwrite_capital_fields=True,
        )
        self.assertIn("capital_model", result)

    def test_existing_sizing_fields_require_explicit_overwrite(self) -> None:
        prices = build_frame(days=130)
        source = prices[prices["symbol"] == "000002"].iloc[[20]]
        close = float(source["close"].iloc[0])
        candidate = source[["symbol", "date", "close"]].assign(
            cash_budget=[1.0],
            lot_size=[1],
            capital_model=["stale_model"],
            signal_close=[close],
            cash_slot=[1.0],
            unallocated=[True],
        )

        with self.assertRaisesRegex(ValueError, "already contain sizing fields"):
            allocator.allocate_capital(prices, candidate, cash_budget=10000)

    def test_overwrite_sizing_fields_drops_stale_values_before_merge(self) -> None:
        prices = build_frame(days=130)
        source = prices[prices["symbol"] == "000002"].iloc[[20]]
        close = float(source["close"].iloc[0])
        candidate = source[["symbol", "date", "close"]].assign(
            cash_budget=[1.0],
            lot_size=[1],
            capital_model=["stale_model"],
            signal_close=[close],
            cash_slot=[1.0],
            quantity=[1],
            cash_reserved=[1.0],
            notional=[1.0],
            weight=[0.01],
            unallocated=[True],
        )

        result, summary = allocator.allocate_capital(
            prices,
            candidate,
            cash_budget=10000,
            lot_size=100,
            overwrite_capital_fields=True,
        )

        self.assertEqual("equal_cash_budget_lot_floor", result["capital_model"].iloc[0])
        self.assertEqual(10000.0, float(result["cash_budget"].iloc[0]))
        self.assertEqual(100, int(result["lot_size"].iloc[0]))
        self.assertEqual(close, float(result["signal_close"].iloc[0]))
        self.assertNotEqual(1, int(result["quantity"].iloc[0]))
        self.assertEqual("equal_cash_budget_lot_floor", summary["capital_model"])

    def test_candidate_close_must_match_signal_close(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]
        candidate = candidate.assign(close=[999.0])

        with self.assertRaisesRegex(ValueError, "candidate close differs"):
            allocator.allocate_capital(prices, candidate, cash_budget=10000)

    def test_duplicate_candidate_signal_is_rejected(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20, 20]][["symbol", "date"]]

        with self.assertRaisesRegex(ValueError, "duplicate symbol/date"):
            allocator.allocate_capital(prices, candidate, cash_budget=10000)

    def test_invalid_budget_or_lot_size_is_rejected(self) -> None:
        prices = build_frame(days=130)
        candidate = prices[prices["symbol"] == "000002"].iloc[[20]][["symbol", "date"]]

        with self.assertRaisesRegex(ValueError, "cash-budget"):
            allocator.allocate_capital(prices, candidate, cash_budget=0)
        with self.assertRaisesRegex(ValueError, "lot-size"):
            allocator.allocate_capital(prices, candidate, cash_budget=10000, lot_size=0)
        with self.assertRaisesRegex(ValueError, "close-tolerance"):
            allocator.allocate_capital(prices, candidate, cash_budget=10000, close_tolerance=-1)


if __name__ == "__main__":
    unittest.main()
