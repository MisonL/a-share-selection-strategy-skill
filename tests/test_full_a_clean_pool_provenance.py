from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/a-share-selection-strategy/scripts"
sys.path.insert(0, str(SCRIPTS))

import prepare_clean_history_pool as clean_pool  # noqa: E402
import run_today_a_share_selection as runner  # noqa: E402
import lib.gates.full_a_clean_pool_provenance as full_a_provenance  # noqa: E402
import lib.runner.run_today_a_share_selection_full_a_provenance as runner_full_a  # noqa: E402
from lib.gates.full_a_clean_pool_provenance import (  # noqa: E402
    EXCLUSION_BOUNDARY,
    HISTORY_FRESHNESS_BOUNDARY,
    MIN_FULL_A_UNIVERSE_SYMBOLS,
    UNIVERSE_BREADTH_BOUNDARY,
    build_clean_pool_provenance,
    validate_clean_pool_provenance,
)
from lib.runner.run_today_a_share_selection_full_a_provenance import (  # noqa: E402
    ARTIFACT_FAILURE_BOUNDARY,
    FILTER_EXCLUSION_BOUNDARY,
    OUTPUT_FAILURE_BOUNDARY,
    VERIFIED_BOUNDARY,
    full_market_decision,
    remove_unverified_scoring_outputs,
    validate_full_a_pre_score,
    validate_full_a_scoring_outputs,
)
from lib.runner.run_today_a_share_selection_provenance import (  # noqa: E402
    FULL_A_PROVENANCE_COLUMNS,
    provenance_fields,
)


class FullACleanPoolProvenanceTests(unittest.TestCase):
    def test_builds_eligible_provenance_for_exact_clean_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(
                Path(tmpdir), universe_size=MIN_FULL_A_UNIVERSE_SYMBOLS
            )

            proof = build_clean_pool_provenance(**paths)
            provenance_path = Path(tmpdir) / "provenance.json"
            write_json(proof, provenance_path)

            checked = validate_clean_pool_provenance(provenance_path)

        self.assertTrue(proof["full_market_closure_eligible"])
        self.assertEqual([], proof["clean_pool"]["removed_symbols"])
        self.assertEqual(proof, checked)

    def test_small_self_consistent_universe_is_not_full_market_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))

            proof = build_clean_pool_provenance(**paths)

        self.assertFalse(proof["full_market_closure_eligible"])
        self.assertEqual(UNIVERSE_BREADTH_BOUNDARY, proof["full_market_closure_boundary"])
        self.assertFalse(proof["universe"]["full_a_breadth_eligible"])
        self.assertEqual(
            MIN_FULL_A_UNIVERSE_SYMBOLS,
            proof["universe"]["minimum_full_a_symbol_count"],
        )

    def test_rejects_incomplete_baostock_universe_metadata_contract(self) -> None:
        cases = [
            ("source", "other", "source must be baostock"),
            ("raw_row_count", 1, "raw_row_count does not match"),
            ("attempted_dates", [], "resolved attempt is invalid"),
        ]
        for field, value, error in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmpdir:
                paths = write_artifacts(Path(tmpdir))
                metadata = read_json(paths["universe_metadata"])
                metadata[field] = value
                write_json(metadata, paths["universe_metadata"])

                with self.assertRaisesRegex(ValueError, error):
                    build_clean_pool_provenance(**paths)

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

    def test_accepts_baostock_metadata_without_zzshare_failure_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            metadata = read_json(paths["history_metadata"])
            metadata["source"] = "baostock"
            metadata["source_scope"] = "baostock_history_fetch"
            metadata.pop("possibly_truncated_symbols")
            metadata.pop("unprocessed_symbols")
            write_json(metadata, paths["history_metadata"])

            proof = build_clean_pool_provenance(**paths)

        self.assertEqual("baostock", proof["history"]["source"])
        self.assertEqual([], proof["clean_pool"]["removed_symbols"])

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

    def test_rejects_clean_content_not_derived_from_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            clean = pd.read_csv(paths["clean_prices"], dtype={"symbol": str})
            clean.loc[0, "close"] = 999.0
            clean.to_csv(paths["clean_prices"], index=False)

            with self.assertRaisesRegex(ValueError, "content does not match history"):
                build_clean_pool_provenance(**paths)

    def test_rejects_clean_column_order_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            clean = pd.read_csv(paths["clean_prices"], dtype={"symbol": str})
            columns = [clean.columns[-1], *clean.columns[:-1]]
            clean[columns].to_csv(paths["clean_prices"], index=False)

            with self.assertRaisesRegex(ValueError, "columns do not match"):
                build_clean_pool_provenance(**paths)

    def test_history_symbol_before_as_of_date_blocks_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(
                Path(tmpdir),
                universe_size=MIN_FULL_A_UNIVERSE_SYMBOLS,
            )
            make_symbol_stale(paths, "000001")

            proof = build_clean_pool_provenance(**paths)

        self.assertFalse(proof["full_market_closure_eligible"])
        self.assertEqual(
            HISTORY_FRESHNESS_BOUNDARY,
            proof["full_market_closure_boundary"],
        )
        self.assertEqual(1, proof["history"]["symbols_before_as_of_date_count"])
        self.assertEqual(["000001"], proof["history"]["symbols_before_as_of_date"])

    def test_rejects_legacy_provenance_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            proof = build_clean_pool_provenance(**paths)
            proof["schema_version"] = 1
            provenance_path = Path(tmpdir) / "provenance.json"
            write_json(proof, provenance_path)

            with self.assertRaisesRegex(ValueError, "schema_version is invalid"):
                validate_clean_pool_provenance(provenance_path)

    def test_validation_hashes_each_bound_artifact_before_and_after_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            proof = build_clean_pool_provenance(**paths)
            provenance_path = Path(tmpdir) / "provenance.json"
            write_json(proof, provenance_path)

            with patch.object(
                full_a_provenance,
                "artifact_fingerprint",
                wraps=full_a_provenance.artifact_fingerprint,
            ) as fingerprint:
                validate_clean_pool_provenance(provenance_path)

        self.assertEqual(len(proof["artifacts"]) * 2, fingerprint.call_count)

    def test_validation_rejects_artifact_changed_between_fingerprints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            proof = build_clean_pool_provenance(**paths)
            provenance_path = Path(tmpdir) / "provenance.json"
            write_json(proof, provenance_path)
            history_changed = Path(paths["history_prices"]).read_bytes().replace(
                b"10.5", b"99.5", 1
            )
            clean_changed = Path(paths["clean_prices"]).read_bytes().replace(
                b"10.5", b"99.5", 1
            )
            calls = 0
            real_fingerprint = full_a_provenance.artifact_fingerprint

            def fingerprint_with_swap(path: Path, display_path: Path | None = None):
                nonlocal calls
                calls += 1
                result = real_fingerprint(path, display_path)
                if calls == len(proof["artifacts"]):
                    Path(paths["history_prices"]).write_bytes(history_changed)
                    Path(paths["clean_prices"]).write_bytes(clean_changed)
                return result

            with patch.object(
                full_a_provenance,
                "artifact_fingerprint",
                side_effect=fingerprint_with_swap,
            ), self.assertRaisesRegex(ValueError, "changed during validation"):
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

        self.assertEqual("valid", proof["validation_status"])

    def test_rejects_duplicate_symbols_in_universe_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            universe = pd.read_csv(paths["universe_input"], dtype={"symbol": str})
            universe = pd.concat([universe, universe.iloc[[0]]], ignore_index=True)
            universe.to_csv(paths["universe_input"], index=False)

            with self.assertRaisesRegex(ValueError, "duplicate symbols"):
                build_clean_pool_provenance(**paths)

    def test_rejects_universe_snapshot_date_that_differs_from_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_artifacts(Path(tmpdir))
            metadata = read_json(paths["universe_metadata"])
            metadata["resolved_snapshot_date"] = "2026-07-10"
            write_json(metadata, paths["universe_metadata"])

            with self.assertRaisesRegex(ValueError, "does not match history as_of_date"):
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
            paths = write_artifacts(
                root, universe_size=MIN_FULL_A_UNIVERSE_SYMBOLS
            )
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

    def test_runner_allows_full_market_claim_after_exact_final_scoring_validation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture = write_runner_artifacts(root, full_universe=True)
            output = root / "run"

            code, stdout, stderr = call_full_a_runner(fixture, output)
            manifest = read_json(output / "run_manifest.json")
            summary = read_json(output / "summary.json")
            diagnostic_rows = read_csv_rows(output / "diagnostics.csv")

        self.assertEqual(0, code, stderr)
        self.assertTrue(manifest["full_market_claim_allowed"])
        self.assertEqual(VERIFIED_BOUNDARY, manifest["full_market_claim_boundary"])
        self.assertEqual("full_a_provenance_verified", manifest["coverage_class"])
        self.assertEqual("valid", manifest["full_a_provenance_validation_status"])
        self.assertEqual("2026-07-11", manifest["full_a_provenance_as_of_date"])
        self.assertEqual(
            MIN_FULL_A_UNIVERSE_SYMBOLS,
            manifest["full_a_provenance_diagnostic_symbol_count"],
        )
        self.assertTrue(summary["full_market_claim_allowed"])
        self.assertTrue(summary["full_a_provenance_final_scoring_validated"])
        self.assertEqual("2026-07-11", summary["full_a_provenance_as_of_date"])
        self.assertIn("full_a_provenance_validation_status=valid", stdout)
        self.assertIn("full_a_provenance_as_of_date=2026-07-11", stdout)
        self.assertTrue(
            all(row["full_market_claim_allowed"] == "True" for row in diagnostic_rows)
        )
        self.assertTrue(
            all(row["full_a_provenance_validation_status"] == "valid" for row in diagnostic_rows)
        )

    def test_runner_keeps_claim_false_for_valid_clean_pool_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture = write_runner_artifacts(
                root,
                removed_symbols=["300001"],
            )
            output = root / "run"

            code, _stdout, stderr = call_full_a_runner(fixture, output)
            manifest = read_json(output / "run_manifest.json")

        self.assertEqual(0, code, stderr)
        self.assertFalse(manifest["full_market_claim_allowed"])
        self.assertEqual(EXCLUSION_BOUNDARY, manifest["full_market_claim_boundary"])
        self.assertEqual("local_input", manifest["coverage_class"])
        self.assertFalse(manifest["full_a_provenance_closure_eligible"])
        self.assertEqual(2, manifest["full_a_provenance_diagnostic_symbol_count"])

    def test_runner_keeps_claim_false_when_final_filter_removes_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture = write_runner_artifacts(root, full_universe=True)
            final_prices = root / "filtered.csv"
            frame = pd.read_csv(fixture["prices_input"], dtype={"symbol": str})
            frame.loc[frame["symbol"] != "600001"].to_csv(final_prices, index=False)
            input_symbol_count = int(frame["symbol"].nunique())
            manifest = {
                "prices_filter_spot_symbol_count": input_symbol_count,
                "prices_filter_input_symbol_count": input_symbol_count,
                "prices_filter_kept_symbol_count": input_symbol_count - 1,
                "prices_filter_removed_symbol_count": 1,
                "prices_filter_removed_symbols": ["600001"],
                "prices_filter_output_written": True,
                "prices_filter_spot_universe": True,
                "prices_filter_min_symbol_latest_date": "2026-07-11",
            }

            evidence = validate_full_a_pre_score(
                provenance_path=fixture["provenance"],
                prices_input=fixture["prices_input"],
                spot_input=fixture["spot_input"],
                final_prices=final_prices,
                manifest=manifest,
            )
            diagnostics = root / "diagnostics.csv"
            candidates = root / "candidates.csv"
            remaining = sorted(set(frame["symbol"]) - {"600001"})
            diagnostics.write_text(
                "symbol\n" + "\n".join(remaining) + "\n",
                encoding="utf-8",
            )
            candidates.write_text("symbol\n", encoding="utf-8")
            manifest.update(evidence)
            manifest.update(
                validate_full_a_scoring_outputs(
                    final_prices=final_prices,
                    candidates=candidates,
                    diagnostics=diagnostics,
                )
            )
            manifest.update(full_market_decision(manifest))

        self.assertFalse(manifest["full_market_claim_allowed"])
        self.assertEqual(FILTER_EXCLUSION_BOUNDARY, manifest["full_market_claim_boundary"])
        self.assertEqual(1, manifest["full_a_provenance_final_filter_removed_symbol_count"])
        self.assertEqual(["600001"], manifest["full_a_provenance_final_filter_removed_symbols"])

    def test_default_runner_provenance_schema_does_not_gain_optional_full_a_fields(
        self,
    ) -> None:
        args = runner.build_parser().parse_args(
            ["--prices-input", "prices.csv", "--output-dir", "run"]
        )
        manifest = runner.initial_manifest(args)
        fields = provenance_fields(manifest)

        self.assertNotIn("full_a_provenance_requested", manifest)
        self.assertTrue(all(column not in fields for column in FULL_A_PROVENANCE_COLUMNS))

    def test_runner_rejects_provenance_without_required_explicit_controls(self) -> None:
        base = [
            "--prices-input",
            "prices.csv",
            "--spot-input",
            "spot.csv",
            "--full-a-provenance",
            "proof.json",
            "--output-dir",
            "run",
        ]
        cases = [
            (base, "filter-prices-to-spot-universe"),
            ([*base, "--filter-prices-to-spot-universe"], "min-symbol-latest-date"),
            (
                [
                    *base,
                    "--filter-prices-to-spot-universe",
                    "--min-symbol-latest-date",
                    "2026-07-11",
                    "--plan-only",
                ],
                "plan-only",
            ),
            (
                [
                    *base,
                    "--filter-prices-to-spot-universe",
                    "--min-symbol-latest-date",
                    "2026-07-11",
                    "--fetch-spot",
                    "baostock_universe",
                ],
                "fetch-spot",
            ),
        ]
        for argv, error in cases:
            with self.subTest(error=error):
                args = runner.build_parser().parse_args(argv)
                with self.assertRaisesRegex(ValueError, error):
                    runner.validate_full_a_provenance_options(args)

    def test_runner_rejects_provenance_bound_to_different_prices_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture = write_runner_artifacts(root)
            alternate = root / "alternate.csv"
            alternate.write_bytes(Path(fixture["prices_input"]).read_bytes())
            fixture["prices_input"] = alternate
            output = root / "run"

            code, _stdout, _stderr = call_full_a_runner(fixture, output)
            manifest = read_json(output / "run_manifest.json")

        self.assertEqual(2, code)
        self.assertFalse(manifest["full_market_claim_allowed"])
        self.assertEqual(ARTIFACT_FAILURE_BOUNDARY, manifest["full_market_claim_boundary"])
        self.assertEqual("failed", manifest["full_a_provenance_validation_status"])
        self.assertFalse((output / "candidates.csv").exists())

    def test_runner_rejects_freshness_threshold_before_provenance_as_of_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture = write_runner_artifacts(root)
            output = root / "run"

            code, _stdout, stderr = call_full_a_runner(
                fixture,
                output,
                min_latest_date="1990-01-01",
            )
            manifest = read_json(output / "run_manifest.json")

        self.assertEqual(2, code)
        self.assertIn("must match full-A provenance as_of_date", stderr)
        self.assertFalse(manifest["full_market_claim_allowed"])
        self.assertEqual(ARTIFACT_FAILURE_BOUNDARY, manifest["full_market_claim_boundary"])
        self.assertEqual("failed", manifest["full_a_provenance_validation_status"])
        self.assertFalse((output / "candidates.csv").exists())

    def test_runner_removes_scoring_outputs_when_post_score_proof_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture = write_runner_artifacts(root)
            output = root / "run"

            with patch.object(
                runner_full_a,
                "validate_full_a_scoring_outputs",
                side_effect=ValueError("forced output mismatch"),
            ):
                code, _stdout, _stderr = call_full_a_runner(fixture, output)
            manifest = read_json(output / "run_manifest.json")

        self.assertEqual(2, code)
        self.assertFalse(manifest["full_market_claim_allowed"])
        self.assertEqual(OUTPUT_FAILURE_BOUNDARY, manifest["full_market_claim_boundary"])
        self.assertEqual("failed", manifest["full_a_provenance_validation_status"])
        self.assertFalse((output / "candidates.csv").exists())
        self.assertFalse((output / "diagnostics.csv").exists())
        self.assertEqual([], manifest["full_a_provenance_output_cleanup_errors"])

    def test_scoring_output_cleanup_errors_are_recorded(self) -> None:
        manifest: dict[str, object] = {}
        candidates = Path("candidates.csv")
        diagnostics = Path("diagnostics.csv")

        with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
            remove_unverified_scoring_outputs(manifest, candidates, diagnostics)

        self.assertEqual(
            [
                "candidates.csv:permission denied",
                "diagnostics.csv:permission denied",
            ],
            manifest["full_a_provenance_output_cleanup_errors"],
        )

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


def write_runner_artifacts(
    root: Path,
    removed_symbols: list[str] | None = None,
    *,
    full_universe: bool = False,
) -> dict[str, Path]:
    paths = write_artifacts(
        root,
        removed_symbols=removed_symbols,
        universe_size=(MIN_FULL_A_UNIVERSE_SYMBOLS if full_universe else 3),
    )
    for key in ("history_prices", "clean_prices"):
        path = Path(paths[key])
        frame = pd.read_csv(path, dtype={"symbol": str})
        frame["name"] = "Stock " + frame["symbol"]
        frame["market"] = "A-share"
        frame["amount"] = 200_000_000.0
        frame["turn"] = 2.0
        frame["isST"] = "0"
        frame["tradestatus"] = "1"
        frame.to_csv(path, index=False)
    provenance = root / "full_a_clean_pool_provenance.json"
    write_json(build_clean_pool_provenance(**paths), provenance)
    config = read_json(
        ROOT
        / "skills/a-share-selection-strategy/configs/ultra_short_low_price_config.json"
    )
    config["thresholds"]["min_history_rows"] = 1
    config_path = root / "runner_config.json"
    write_json(config, config_path)
    return {
        "prices_input": Path(paths["clean_prices"]),
        "spot_input": Path(paths["universe_input"]),
        "provenance": provenance,
        "config": config_path,
    }


def call_full_a_runner(
    fixture: dict[str, Path],
    output: Path,
    *,
    min_latest_date: str = "2026-07-11",
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = runner.main(
            [
                "--prices-input",
                str(fixture["prices_input"]),
                "--spot-input",
                str(fixture["spot_input"]),
                "--full-a-provenance",
                str(fixture["provenance"]),
                "--filter-prices-to-spot-universe",
                "--min-symbol-latest-date",
                min_latest_date,
                "--min-history-rows",
                "1",
                "--config",
                str(fixture["config"]),
                "--output-dir",
                str(output),
                "--no-html-report",
            ]
        )
    return code, stdout.getvalue(), stderr.getvalue()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_artifacts(
    root: Path,
    removed_symbols: list[str] | None = None,
    *,
    universe_size: int = 3,
) -> dict[str, Path | None]:
    symbols = test_universe_symbols(universe_size)
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

    pd.DataFrame(
        {"symbol": symbols, "name": [f"Stock {symbol}" for symbol in symbols]}
    ).to_csv(
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
            "source_type": "external_fetch",
            "source_scope": "baostock_universe_snapshot",
            "real_market_data": True,
            "partial_result": False,
            "output_written": True,
            "metadata_output_written": True,
            "raw_items": len(symbols),
            "filtered_items": len(symbols),
            "symbol_count": len(symbols),
            "raw_row_count": len(symbols) + 5,
            "excluded_count": 5,
            "error": "",
            "fetch_errors": [],
            "fetch_error_count": 0,
            "allowed_failure_actions": [],
            "coverage_claim": "symbol_universe_snapshot_not_realtime_spot_proof",
            "source_claim_boundary": (
                "baostock_universe_snapshot_not_realtime_spot_or_full_market_proof"
            ),
            "output": str(universe_input),
            "metadata_output": str(universe_metadata),
            "resolved_snapshot_date": "2026-07-11",
            "attempted_dates": [
                {
                    "date": "2026-07-11",
                    "error": "",
                    "raw_rows": len(symbols) + 5,
                    "symbol_count": len(symbols),
                }
            ],
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
            "end_date": "2026-07-11",
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


def test_universe_symbols(count: int) -> list[str]:
    if count < 3:
        raise ValueError("test universe requires at least three symbols")
    symbols = ["000001", "300001", "600001"]
    for prefix in ("000", "001", "002", "003", "300", "301", "600"):
        for suffix in range(1, 1_000):
            symbol = f"{prefix}{suffix:03d}"
            if symbol not in symbols:
                symbols.append(symbol)
            if len(symbols) == count:
                return symbols
    raise ValueError("test universe size exceeds generated symbol capacity")


def make_symbol_stale(paths: dict[str, Path | None], symbol: str) -> None:
    history = pd.read_csv(paths["history_prices"], dtype={"symbol": str})
    latest = history["date"].astype(str).max()
    stale = history.loc[
        ~(
            (history["symbol"].astype(str) == symbol)
            & (history["date"].astype(str) == latest)
        )
    ].reset_index(drop=True)
    stale.to_csv(paths["history_prices"], index=False)
    stale.to_csv(paths["clean_prices"], index=False)
    for key in ("history_metadata", "clean_metadata"):
        metadata = read_json(paths[key])
        metadata["rows"] = len(stale)
        if key == "history_metadata":
            metadata["raw_rows"] = len(stale)
        for record in metadata["symbols"]:
            if record["symbol"] == symbol:
                record["rows"] = 1
                record["date_max"] = "2026-07-10"
        write_json(metadata, paths[key])
    report = read_json(paths["clean_report"])
    report["raw_rows"] = len(stale)
    report["clean_rows"] = len(stale)
    write_json(report, paths["clean_report"])


def symbol_records(frame: pd.DataFrame, symbols: list[str]) -> list[dict[str, object]]:
    counts = frame.groupby("symbol", sort=False).size().to_dict()
    return [
        {
            "symbol": symbol,
            "rows": int(counts.get(symbol, 0)),
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
