from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tests.test_walk_forward_artifact_cli import (
    build_run,
    call_cli,
    candidate_rows,
    read_json,
    write_csv,
    write_json,
)


class WalkForwardArtifactPortfolioCliTests(unittest.TestCase):
    def test_cli_accepts_portfolio_allocation_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            allocation = allocation_summary()
            write_json(root / "qsss_allocation_summary.json", allocation)
            write_csv(root / "qsss_skipped_candidates.csv", skipped_rows())
            write_csv(root / "signals/2026-05-12/qsss_raw_candidates.csv", raw_candidate_rows())
            summary = read_json(root / "qsss_run_summary.json")
            summary["allocation"] = allocation
            write_json(root / "qsss_run_summary.json", summary)
            set_capital_model(root / "signals/2026-05-12/qsss_sized_candidates.csv")

            code, _stdout, stderr = call_cli(
                root,
                root / "artifact_validation.json",
                ["--required-allocation-model", "portfolio_cash_lot_floor"],
            )

        self.assertEqual(0, code)
        self.assertEqual("", stderr)


def raw_candidate_rows() -> list[dict[str, object]]:
    return [
        *candidate_rows(),
        {"symbol": "000003", "date": "2026-05-12", "close": 10.5, "total_score": 0.6},
    ]


def skipped_rows() -> list[dict[str, object]]:
    return [{"symbol": "000003", "date": "2026-05-12", "rank": 3, "skip_reason": "max_open_positions"}]


def allocation_summary() -> dict[str, object]:
    return {
        "schema_version": 1,
        "allocation_model": "portfolio_cash_lot_floor",
        "raw_candidates": 3,
        "allocated_candidates": 2,
        "skipped_candidates": 1,
        "skip_reason_counts": {"max_open_positions": 1},
        "signals": [{"signal_date": "2026-05-12", "raw_candidates": 3, "allocated_candidates": 2, "skipped_candidates": 1}],
        "cash_budget": 1000000.0,
        "lot_size": 100,
        "hold_days": 5,
        "max_open_positions": 2,
        "max_gross_weight": 0.0021,
        "max_gross_notional": 2100.0,
        "max_cash_reserved": 2100.0,
        "max_open_positions_limit": 2,
        "max_gross_weight_limit": 1.0,
        "max_gross_notional_limit": 1000000.0,
        "max_cash_reserved_limit": 1000000.0,
        "fail_on_symbol_overlap": True,
    }


def set_capital_model(path: Path) -> None:
    rows = pd.read_csv(path, dtype={"symbol": str})
    rows["capital_model"] = "portfolio_cash_lot_floor"
    rows.to_csv(path, index=False)


if __name__ == "__main__":
    unittest.main()
