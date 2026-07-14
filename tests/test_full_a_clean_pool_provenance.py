from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/a-share-selection-strategy/scripts"
sys.path.insert(0, str(SCRIPTS))

import prepare_clean_history_pool as clean_pool  # noqa: E402
from lib.gates.full_a_clean_pool_provenance import (  # noqa: E402
    EXCLUSION_BOUNDARY,
    build_clean_pool_provenance,
    validate_clean_pool_provenance,
)


class FullACleanPoolProvenanceTests(unittest.TestCase):
    def test_builds_eligible_provenance_for_exact_clean_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))

            proof = build_clean_pool_provenance(**paths)
            provenance_path = Path(tmpdir) / "provenance.json"
            write_json(proof, provenance_path)

            checked = validate_clean_pool_provenance(provenance_path)

        self.assertTrue(proof["full_market_closure_eligible"])
        self.assertEqual([], proof["clean_pool"]["removed_symbols"])
        self.assertEqual(proof, checked)

    def test_records_clean_exclusions_without_permitting_full_market_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir), removed_symbols=["300001"])

            proof = build_clean_pool_provenance(**paths)

        self.assertFalse(proof["full_market_closure_eligible"])
        self.assertEqual(EXCLUSION_BOUNDARY, proof["full_market_closure_boundary"])
        self.assertEqual(["300001"], proof["clean_pool"]["removed_symbols"])

    def test_rejects_history_metadata_that_does_not_cover_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            history_metadata = read_json(paths["history_metadata"])
            history_metadata["requested_symbols"] = ["000001", "600001"]
            write_json(history_metadata, paths["history_metadata"])

            with self.assertRaisesRegex(ValueError, "requested_symbols do not match universe"):
                build_clean_pool_provenance(**paths)

    def test_rejects_partial_universe_or_history_metadata(self) -> None:
        for artifact_name in ("universe_metadata", "history_metadata"):
            with self.subTest(artifact_name=artifact_name), tempfile.TemporaryDirectory() as tmpdir:
                paths = write_artifacts(Path(tmpdir))
                metadata = read_json(paths[artifact_name])
                metadata["partial_result"] = True
                write_json(metadata, paths[artifact_name])

                with self.assertRaisesRegex(ValueError, "requires partial_result=false"):
                    build_clean_pool_provenance(**paths)

    def test_rejects_proof_after_clean_prices_are_tampered(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            proof = build_clean_pool_provenance(**paths)
            provenance_path = Path(tmpdir) / "provenance.json"
            write_json(proof, provenance_path)
            prices = pd.read_csv(paths["clean_prices"], dtype={"symbol": str})
            prices.loc[0, "close"] = 999.0
            prices.to_csv(paths["clean_prices"], index=False)

            with self.assertRaisesRegex(ValueError, "clean_prices"):
                validate_clean_pool_provenance(provenance_path)

    def test_rejects_forged_eligibility_even_when_artifact_hashes_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir), removed_symbols=["300001"])
            proof = build_clean_pool_provenance(**paths)
            proof["full_market_closure_eligible"] = True
            provenance_path = Path(tmpdir) / "provenance.json"
            write_json(proof, provenance_path)

            with self.assertRaisesRegex(ValueError, "boundary does not match eligibility"):
                validate_clean_pool_provenance(provenance_path)

    def test_rejects_invalid_raw_quality_count_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            history_metadata = read_json(paths["history_metadata"])
            history_metadata.update(
                {
                    "raw_rows": 7,
                    "invalid_rows": 1,
                    "dropped_invalid_rows": 1,
                    "raw_quality_counter_semantics": "legacy_additive_counts",
                }
            )
            write_json(history_metadata, paths["history_metadata"])

            with self.assertRaisesRegex(ValueError, "quality counter semantics"):
                build_clean_pool_provenance(**paths)

    def test_reconciles_non_trading_rows_dropped_after_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            history_metadata = read_json(paths["history_metadata"])
            history_metadata.update(
                {
                    "raw_rows": 7,
                    "raw_non_trading_rows": 1,
                    "raw_invalid_non_trading_overlap_rows": 0,
                    "dropped_non_trading_rows": 1,
                }
            )
            write_json(history_metadata, paths["history_metadata"])

            proof = build_clean_pool_provenance(**paths)

        self.assertTrue(proof["full_market_closure_eligible"])

    def test_rejects_duplicate_symbols_in_universe_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            universe = pd.read_csv(paths["universe_input"], dtype={"symbol": str})
            universe = pd.concat([universe, universe.iloc[[0]]], ignore_index=True)
            universe.to_csv(paths["universe_input"], index=False)

            with self.assertRaisesRegex(ValueError, "duplicate symbols"):
                build_clean_pool_provenance(**paths)

    def test_rejects_metadata_alias_with_different_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            alias = Path(tmpdir) / "metadata_alias.json"
            write_json({"wrong": True}, alias)

            with self.assertRaisesRegex(ValueError, "alias does not match"):
                build_clean_pool_provenance(
                    **paths,
                    clean_metadata_alias=alias,
                )

    def test_rejects_short_history_symbols_that_do_not_match_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir), removed_symbols=["300001"])
            write_json(
                {"source": "test", "symbols": [{"symbol": "600001"}]},
                paths["short_history"],
            )

            with self.assertRaisesRegex(ValueError, "short_history symbols do not match"):
                build_clean_pool_provenance(**paths)

    def test_cli_publishes_provenance_with_clean_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = write_artifacts(root)
            output = root / "clean-output.csv"
            metadata = root / "clean-metadata.json"
            metadata_alias = root / "clean-metadata-alias.json"
            report = root / "clean-report.json"
            provenance = root / "clean-provenance.json"
            stdout = StringIO()

            with redirect_stdout(stdout):
                code = clean_pool.main(
                    [
                        "--prices-input",
                        str(paths["history_prices"]),
                        "--history-metadata",
                        str(paths["history_metadata"]),
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata),
                        "--metadata-alias-output",
                        str(metadata_alias),
                        "--report-output",
                        str(report),
                        "--universe-input",
                        str(paths["universe_input"]),
                        "--universe-metadata",
                        str(paths["universe_metadata"]),
                        "--provenance-output",
                        str(provenance),
                    ]
                )
            checked = validate_clean_pool_provenance(provenance)

        self.assertEqual(0, code)
        self.assertIn(f"provenance_output={provenance}", stdout.getvalue())
        self.assertTrue(checked["full_market_closure_eligible"])
        self.assertEqual(str(output.resolve()), checked["artifacts"]["clean_prices"]["path"])
        self.assertEqual(
            str(metadata_alias.resolve()),
            checked["artifacts"]["clean_metadata_alias"]["path"],
        )

    def test_cli_default_stdout_does_not_add_empty_provenance_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = write_artifacts(root)
            stdout = StringIO()

            with redirect_stdout(stdout):
                code = clean_pool.main(
                    [
                        "--prices-input",
                        str(paths["history_prices"]),
                        "--history-metadata",
                        str(paths["history_metadata"]),
                        "--output",
                        str(root / "clean-output.csv"),
                        "--metadata-output",
                        str(root / "clean-metadata.json"),
                        "--report-output",
                        str(root / "clean-report.json"),
                    ]
                )

        self.assertEqual(0, code)
        self.assertNotIn("provenance_output=", stdout.getvalue())

    def test_cli_publishes_exclusion_provenance_with_short_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = write_artifacts(root, removed_symbols=["300001"])
            output = root / "clean-output.csv"
            metadata = root / "clean-metadata.json"
            report = root / "clean-report.json"
            provenance = root / "clean-provenance.json"

            code = clean_pool.main(
                [
                    "--prices-input",
                    str(paths["history_prices"]),
                    "--history-metadata",
                    str(paths["history_metadata"]),
                    "--short-history",
                    str(paths["short_history"]),
                    "--output",
                    str(output),
                    "--metadata-output",
                    str(metadata),
                    "--report-output",
                    str(report),
                    "--universe-input",
                    str(paths["universe_input"]),
                    "--universe-metadata",
                    str(paths["universe_metadata"]),
                    "--provenance-output",
                    str(provenance),
                ]
            )
            checked = validate_clean_pool_provenance(provenance)

        self.assertEqual(0, code)
        self.assertFalse(checked["full_market_closure_eligible"])
        self.assertEqual(EXCLUSION_BOUNDARY, checked["full_market_closure_boundary"])
        self.assertEqual(["300001"], checked["clean_pool"]["removed_symbols"])

    def test_cli_rejects_incremental_provenance_without_persisted_merged_input(self) -> None:
        args = clean_pool.build_parser().parse_args(
            [
                "--prices-input",
                "prices.csv",
                "--history-metadata",
                "history.json",
                "--output",
                "clean.csv",
                "--metadata-output",
                "clean.json",
                "--report-output",
                "report.json",
                "--incremental-plan",
                "plan.json",
                "--incremental-prices",
                "delta.csv",
                "--incremental-metadata",
                "delta.json",
                "--universe-input",
                "universe.csv",
                "--universe-metadata",
                "universe.json",
                "--provenance-output",
                "provenance.json",
            ]
        )

        with self.assertRaisesRegex(ValueError, "cannot be combined with incremental"):
            clean_pool.build_paths(args)


def write_artifacts(root: Path, removed_symbols: list[str] | None = None) -> dict[str, Path | None]:
    symbols = ["000001", "300001", "600001"]
    removed = sorted(removed_symbols or [])
    dates = ["2026-07-10", "2026-07-11"]
    universe_input = root / "universe.csv"
    universe_metadata = root / "universe_metadata.json"
    history_prices = root / "history.csv"
    history_metadata = root / "history_metadata.json"
    clean_prices = root / "clean.csv"
    clean_metadata = root / "clean_metadata.json"
    clean_report = root / "clean_report.json"
    short_history = root / "short_history.json" if removed else None

    pd.DataFrame({"symbol": symbols, "name": ["A", "B", "C"]}).to_csv(
        universe_input, index=False
    )
    history = pd.DataFrame(
        [
            {
                "symbol": symbol,
                "date": date,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100.0,
            }
            for symbol in symbols
            for date in dates
        ]
    )
    history.to_csv(history_prices, index=False)
    clean = history.loc[~history["symbol"].isin(removed)].copy()
    clean.to_csv(clean_prices, index=False)
    records = symbol_records(history, symbols)
    clean_symbols = [symbol for symbol in symbols if symbol not in removed]
    clean_records = symbol_records(clean, clean_symbols)
    reason_counts = {
        "empty_history": 0,
        "failed_fetch": 0,
        "possibly_truncated": 0,
        "short_history": len(removed),
        "unprocessed_fetch": 0,
    }
    write_json(
        {
            "source": "baostock",
            "source_scope": "baostock_universe_snapshot",
            "partial_result": False,
            "output_written": True,
            "metadata_output_written": True,
            "symbol_count": len(symbols),
        },
        universe_metadata,
    )
    write_json(
        {
            "source": "zzshare",
            "source_scope": "zzshare_history_fetch",
            "partial_result": False,
            "output_written": True,
            "metadata_output_written": True,
            "symbol_count": len(symbols),
            "rows": len(history),
            "raw_rows": len(history),
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "dropped_non_trading_rows": 0,
            "raw_non_trading_rows": 0,
            "raw_invalid_non_trading_overlap_rows": 0,
            "raw_quality_counter_semantics": "raw_dimension_counts_not_additive",
            "requested_symbols": symbols,
            "symbols": records,
            "failed_symbols": [],
            "empty_symbols": [],
            "possibly_truncated_symbols": [],
            "unprocessed_symbols": [],
        },
        history_metadata,
    )
    write_json(
        {
            "source": "zzshare",
            "source_scope": "clean_history_pool",
            "partial_result": bool(removed),
            "output_written": True,
            "metadata_output_written": True,
            "symbol_count": len(clean_symbols),
            "rows": len(clean),
            "requested_symbols": clean_symbols,
            "symbols": clean_records,
            "clean_pool_source_prices": str(history_prices),
            "clean_pool_removed_symbols": removed,
            "clean_pool_removed_symbol_count": len(removed),
            "clean_pool_reason_counts": reason_counts,
        },
        clean_metadata,
    )
    if short_history is not None:
        write_json(
            {"source": "test", "symbols": [{"symbol": symbol} for symbol in removed]},
            short_history,
        )
    write_json(
        {
            "source": "clean_history_pool_report",
            "history_metadata": str(history_metadata),
            "short_history": str(short_history) if short_history else "",
            "raw_rows": len(history),
            "raw_symbol_count": len(symbols),
            "clean_rows": len(clean),
            "clean_symbol_count": len(clean_symbols),
            "removed_symbols": removed,
            "removed_symbol_count": len(removed),
            "reason_symbols": {
                "empty_history": [],
                "failed_fetch": [],
                "possibly_truncated": [],
                "short_history": removed,
                "unprocessed_fetch": [],
            },
            "reason_counts": reason_counts,
        },
        clean_report,
    )
    return {
        "universe_input": universe_input,
        "universe_metadata": universe_metadata,
        "history_prices": history_prices,
        "history_metadata": history_metadata,
        "clean_prices": clean_prices,
        "clean_metadata": clean_metadata,
        "clean_report": clean_report,
        "short_history": short_history,
    }


def symbol_records(frame: pd.DataFrame, symbols: list[str]) -> list[dict[str, object]]:
    return [
        {
            "symbol": symbol,
            "rows": int(len(frame.loc[frame["symbol"] == symbol])),
            "date_min": "2026-07-10",
            "date_max": "2026-07-11",
        }
        for symbol in symbols
    ]


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(data: dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
