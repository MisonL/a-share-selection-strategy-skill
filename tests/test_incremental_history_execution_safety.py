from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.gates.incremental_history_artifacts import (  # noqa: E402
    combine_metadata,
    publish_output_pair,
    validate_bucket_artifacts,
)
from lib.gates.incremental_history_execution import (  # noqa: E402
    build_fetch_command,
    execution_contract,
    execute_plan,
)
from lib.gates.incremental_history_merge import merge_incremental_history  # noqa: E402
from lib.gates.incremental_history_plan import (  # noqa: E402
    build_fetch_buckets,
    validate_bucket_coverage,
)
from execute_incremental_history_plan import build_config, build_parser  # noqa: E402
from prepare_incremental_history_plan import build_parser as build_plan_parser  # noqa: E402
from tests.test_recovery_and_safety_helpers import (  # noqa: E402
    incremental_execution_config,
    incremental_execution_plan,
    write_bucket_artifacts,
)


def write_audited_non_trading_bucket(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Path], dict[str, Any]]:
    bucket = {
        "bucket_id": "fetch-001-delta-stale_history",
        "fetch_mode": "delta",
        "reason": "stale_history",
        "start_date": "2026-07-08",
        "end_date": "2026-07-14",
        "symbols": ["301234"],
        "symbol_count": 1,
    }
    paths = {
        "prices": root / "prices.csv",
        "metadata": root / "metadata.json",
    }
    paths["prices"].write_text("symbol,date,close\n", encoding="utf-8")
    metadata = {
        "source": "baostock",
        "output_written": True,
        "metadata_output_written": True,
        "requested_symbols": ["301234"],
        "symbols": [
            {"symbol": "301234", "rows": 0, "date_min": "", "date_max": ""}
        ],
        "raw_symbols": [
            {
                "symbol": "301234",
                "rows": 5,
                "date_min": "2026-07-08",
                "date_max": "2026-07-14",
            }
        ],
        "rows": 0,
        "symbol_count": 0,
        "failed_symbols": [],
        "empty_symbols": ["301234"],
        "non_trading_only_empty_symbols": ["301234"],
        "possibly_truncated_symbols": [],
        "unprocessed_symbols": [],
        "invalid_rows": 5,
        "dropped_invalid_rows": 5,
        "tradestatus_missing_rows": 0,
        "partial_result": True,
        "rate_limit_budget_exhausted": False,
    }
    paths["metadata"].write_text(json.dumps(metadata), encoding="utf-8")
    return bucket, paths, metadata


class IncrementalHistoryExecutionSafetyTests(unittest.TestCase):
    def test_incremental_plan_default_bucket_size_is_measured_safe_value(self) -> None:
        args = build_plan_parser().parse_args(
            [
                "--spot-input",
                "spot.csv",
                "--prices-input",
                "prices.parquet",
                "--history-metadata",
                "metadata.json",
                "--target-end-date",
                "2026-07-14",
                "--output",
                "plan.json",
            ]
        )

        self.assertEqual(200, args.max_bucket_symbols)

    def test_incremental_plan_splits_large_groups_into_resumable_buckets(self) -> None:
        records = [
            {
                "symbol": f"{index:06d}",
                "reason": "stale_history",
                "fetch_mode": "delta",
                "suggested_start_date": "2026-07-14",
            }
            for index in range(1201)
        ]

        buckets = build_fetch_buckets(
            records,
            "2026-07-14",
            max_bucket_symbols=500,
        )

        self.assertEqual([500, 500, 201], [item["symbol_count"] for item in buckets])
        self.assertEqual(3, len({item["bucket_id"] for item in buckets}))
        validate_bucket_coverage(
            [record["symbol"] for record in records],
            buckets,
        )

    def test_bucket_accepts_only_fully_dropped_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bucket = {
                "bucket_id": "fetch-001-delta-stale_history",
                "fetch_mode": "delta",
                "reason": "stale_history",
                "start_date": "2026-07-14",
                "end_date": "2026-07-14",
                "symbols": ["000001"],
                "symbol_count": 1,
            }
            paths = {
                "prices": root / "prices.csv",
                "metadata": root / "metadata.json",
            }
            paths["prices"].write_text(
                "symbol,date,close\n000001,2026-07-14,10.0\n",
                encoding="utf-8",
            )
            metadata = {
                "source": "baostock",
                "output_written": True,
                "metadata_output_written": True,
                "requested_symbols": ["000001"],
                "symbols": [
                    {
                        "symbol": "000001",
                        "rows": 1,
                        "date_min": "2026-07-14",
                        "date_max": "2026-07-14",
                    }
                ],
                "rows": 1,
                "symbol_count": 1,
                "failed_symbols": [],
                "empty_symbols": [],
                "possibly_truncated_symbols": [],
                "unprocessed_symbols": [],
                "invalid_rows": 2,
                "dropped_invalid_rows": 2,
                "tradestatus_missing_rows": 0,
                "partial_result": False,
                "rate_limit_budget_exhausted": False,
            }
            paths["metadata"].write_text(json.dumps(metadata), encoding="utf-8")

            validate_bucket_artifacts(bucket, paths, "baostock")
            metadata["dropped_invalid_rows"] = 1
            paths["metadata"].write_text(json.dumps(metadata), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "do not match"):
                validate_bucket_artifacts(bucket, paths, "baostock")

    def test_bucket_accepts_audited_non_trading_empty_only_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bucket, paths, metadata = write_audited_non_trading_bucket(Path(tmpdir))

            metadata["raw_symbols"][0]["date_max"] = "2026-07-13"
            paths["metadata"].write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not reach target"):
                validate_bucket_artifacts(
                    bucket,
                    paths,
                    "baostock",
                    allow_non_trading_empty=True,
                )

            metadata["raw_symbols"][0]["date_max"] = "2026-07-14"
            paths["metadata"].write_text(json.dumps(metadata), encoding="utf-8")
            validate_bucket_artifacts(
                bucket,
                paths,
                "baostock",
                allow_non_trading_empty=True,
            )

            with self.assertRaisesRegex(ValueError, "empty_symbols"):
                validate_bucket_artifacts(bucket, paths, "baostock")

    def test_non_trading_empty_keeps_baostock_name_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bucket, paths, metadata = write_audited_non_trading_bucket(Path(tmpdir))
            metadata["missing_name_policy"] = "query"
            metadata["name_lookup_missing_symbols"] = ["301234"]
            paths["metadata"].write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "name_lookup_missing_symbols"):
                validate_bucket_artifacts(
                    bucket,
                    paths,
                    "baostock",
                    allow_non_trading_empty=True,
                )

            metadata["missing_name_policy"] = "blank"
            paths["metadata"].write_text(json.dumps(metadata), encoding="utf-8")
            validate_bucket_artifacts(
                bucket,
                paths,
                "baostock",
                allow_non_trading_empty=True,
            )

    def test_non_trading_empty_does_not_allow_failed_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bucket, paths, metadata = write_audited_non_trading_bucket(Path(tmpdir))
            metadata["failed_symbols"] = ["301234"]
            paths["metadata"].write_text(json.dumps(metadata), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "failed_symbols"):
                validate_bucket_artifacts(
                    bucket,
                    paths,
                    "baostock",
                    allow_non_trading_empty=True,
                )

    def test_non_trading_empty_rejects_malformed_raw_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bucket, paths, metadata = write_audited_non_trading_bucket(Path(tmpdir))
            metadata["missing_name_policy"] = "query"
            metadata["name_lookup_missing_symbols"] = []
            valid_raw_record = dict(metadata["raw_symbols"][0])
            for raw_records, message in (
                ([valid_raw_record, "malformed"], "records must be objects"),
                ([valid_raw_record, dict(valid_raw_record)], "duplicate symbol"),
            ):
                metadata["raw_symbols"] = raw_records
                paths["metadata"].write_text(
                    json.dumps(metadata), encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, message):
                    validate_bucket_artifacts(
                        bucket,
                        paths,
                        "baostock",
                        allow_non_trading_empty=True,
                    )

    def test_baostock_options_are_forwarded_and_contract_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            names_input = root / "spot.csv"
            names_input.write_text(
                "symbol,name\n000001,Ping An Bank\n600000,SPDB\n",
                encoding="utf-8",
            )
            plan = incremental_execution_plan()
            args = build_parser().parse_args(
                [
                    "--plan",
                    str(root / "plan.json"),
                    "--provider",
                    "baostock",
                    "--full-start-date",
                    "2024-01-01",
                    "--output-dir",
                    str(root / "output"),
                    "--baostock-names-input",
                    str(names_input),
                    "--baostock-missing-name-policy",
                    "fail",
                    "--baostock-non-trading-policy",
                    "drop",
                    "--baostock-drop-invalid-rows",
                    "--baostock-allow-non-trading-empty",
                ]
            )
            config = build_config(args, (root / "plan.json").resolve(), plan)
            paths = {
                "symbols": root / "symbols.txt",
                "prices": root / "prices.csv",
                "metadata": root / "metadata.json",
                "checkpoint": root / "checkpoint",
            }

            command = build_fetch_command(plan["fetch_buckets"][0], paths, config)
            contract = execution_contract(plan, config)
            first_fingerprint = contract["baostock"]["names_input_fingerprint"]
            names_input.write_text(
                "symbol,name\n000001,Ping An Bank\n600000,SPDB Updated\n",
                encoding="utf-8",
            )
            changed_contract = execution_contract(plan, config)

        self.assertIn("--names-input", command)
        self.assertIn("--missing-name-policy", command)
        self.assertIn("--non-trading-policy", command)
        self.assertIn("--drop-invalid-rows", command)
        self.assertNotIn("--fail-on-fetch-error", command)
        self.assertEqual(3, contract["schema_version"])
        self.assertEqual("fail", contract["baostock"]["missing_name_policy"])
        self.assertEqual("drop", contract["baostock"]["non_trading_policy"])
        self.assertTrue(contract["baostock"]["allow_non_trading_empty"])
        self.assertNotEqual(
            first_fingerprint,
            changed_contract["baostock"]["names_input_fingerprint"],
        )

    def test_baostock_options_reject_other_provider_and_missing_input(self) -> None:
        plan = incremental_execution_plan()
        other_provider = build_parser().parse_args(
            [
                "--plan",
                "plan.json",
                "--provider",
                "zzshare",
                "--full-start-date",
                "2024-01-01",
                "--output-dir",
                "output",
                "--baostock-non-trading-policy",
                "keep",
            ]
        )
        missing_names = build_parser().parse_args(
            [
                "--plan",
                "plan.json",
                "--provider",
                "baostock",
                "--full-start-date",
                "2024-01-01",
                "--output-dir",
                "output",
                "--baostock-missing-name-policy",
                "fail",
            ]
        )

        with self.assertRaisesRegex(ValueError, "only valid with --provider baostock"):
            build_config(other_provider, Path("plan.json").resolve(), plan)
        with self.assertRaisesRegex(ValueError, "requires --baostock-names-input"):
            build_config(missing_names, Path("plan.json").resolve(), plan)

    def test_baostock_non_trading_empty_requires_drop_policy(self) -> None:
        plan = incremental_execution_plan()
        for policy_args in ([], ["--baostock-non-trading-policy", "keep"]):
            args = build_parser().parse_args(
                [
                    "--plan",
                    "plan.json",
                    "--provider",
                    "baostock",
                    "--full-start-date",
                    "2024-01-01",
                    "--output-dir",
                    "output",
                    "--baostock-allow-non-trading-empty",
                    *policy_args,
                ]
            )

            with self.assertRaisesRegex(
                ValueError,
                "--baostock-allow-non-trading-empty requires "
                "--baostock-non-trading-policy drop",
            ):
                build_config(args, Path("plan.json").resolve(), plan)

        missing_invalid_drop = build_parser().parse_args(
            [
                "--plan",
                "plan.json",
                "--provider",
                "baostock",
                "--full-start-date",
                "2024-01-01",
                "--output-dir",
                "output",
                "--baostock-non-trading-policy",
                "drop",
                "--baostock-allow-non-trading-empty",
            ]
        )
        with self.assertRaisesRegex(
            ValueError,
            "--baostock-allow-non-trading-empty requires "
            "--baostock-drop-invalid-rows",
        ):
            build_config(
                missing_invalid_drop,
                Path("plan.json").resolve(),
                plan,
            )

    def test_combined_metadata_preserves_baostock_name_metrics(self) -> None:
        metadata = combine_metadata(
            {"fetch_symbols": ["000001", "600000"]},
            [
                {
                    "symbols": [{"symbol": "000001", "rows": 1}],
                    "name_lookup_count": 1,
                    "names_input_count": 1,
                    "name_query_count": 0,
                    "name_lookup_failed_symbols": [],
                    "name_lookup_missing_symbols": [],
                },
                {
                    "symbols": [{"symbol": "600000", "rows": 1}],
                    "name_lookup_count": 1,
                    "names_input_count": 1,
                    "name_query_count": 0,
                    "name_lookup_failed_symbols": [],
                    "name_lookup_missing_symbols": [],
                },
            ],
            "baostock",
            rows=2,
        )

        self.assertEqual(2, metadata["name_lookup_count"])
        self.assertEqual(2, metadata["names_input_count"])
        self.assertEqual(0, metadata["name_query_count"])
        self.assertEqual([], metadata["name_lookup_failed_symbols"])
        self.assertEqual([], metadata["name_lookup_missing_symbols"])

    def test_combined_metadata_preserves_dropped_invalid_row_audit(self) -> None:
        metadata = combine_metadata(
            {"fetch_symbols": ["000001"]},
            [
                {
                    "symbols": [{"symbol": "000001", "rows": 1}],
                    "invalid_rows": 2,
                    "dropped_invalid_rows": 2,
                    "invalid_symbols": ["000001"],
                    "invalid_row_examples": [
                        {
                            "symbol": "000001",
                            "date": "2026-07-13",
                            "invalid_columns": ["volume"],
                        }
                    ],
                }
            ],
            "baostock",
            rows=1,
        )

        self.assertEqual(2, metadata["invalid_rows"])
        self.assertEqual(2, metadata["dropped_invalid_rows"])
        self.assertEqual(["000001"], metadata["invalid_symbols"])
        self.assertEqual(1, len(metadata["invalid_row_examples"]))

    def test_verified_merge_retains_base_for_audited_no_trading_update(self) -> None:
        columns = ["symbol", "date", "open", "high", "low", "close", "volume"]
        base = pd.DataFrame(
            [
                ["301234", "2026-07-07", 10, 10, 10, 10, 100],
                ["600000", "2026-07-13", 8, 8, 8, 8, 200],
            ],
            columns=columns,
        )
        delta = pd.DataFrame(
            [["600000", "2026-07-14", 8.1, 8.2, 8.0, 8.1, 220]],
            columns=columns,
        )
        plan = {
            "source": "incremental_history_plan",
            "claim_boundary": "incremental_history_plan_only_not_history_fetch_success",
            "target_end_date": "2026-07-14",
            "fetch_symbols": ["301234", "600000"],
        }
        incremental_metadata = {
            "source": "baostock_incremental_bucket_execution",
            "provider": "baostock",
            "output_written": True,
            "metadata_output_written": True,
            "requested_symbols": ["301234", "600000"],
            "symbols": [
                {"symbol": "301234", "rows": 0, "date_min": "", "date_max": ""},
                {
                    "symbol": "600000",
                    "rows": 1,
                    "date_min": "2026-07-14",
                    "date_max": "2026-07-14",
                },
            ],
            "raw_symbols": [
                {
                    "symbol": "301234",
                    "rows": 5,
                    "date_min": "2026-07-08",
                    "date_max": "2026-07-14",
                },
                {
                    "symbol": "600000",
                    "rows": 1,
                    "date_min": "2026-07-14",
                    "date_max": "2026-07-14",
                },
            ],
            "failed_symbols": [],
            "empty_symbols": ["301234"],
            "non_trading_only_empty_symbols": ["301234"],
            "no_trading_update_symbols": ["301234"],
            "possibly_truncated_symbols": [],
            "unprocessed_symbols": [],
            "invalid_rows": 5,
            "dropped_invalid_rows": 5,
            "partial_result": False,
            "partial_result_semantics": (
                "false_means_no_unaudited_gaps_"
                "audited_no_trading_updates_disclosed_separately"
            ),
            "rate_limit_budget_exhausted": False,
        }

        merged, metadata, report = merge_incremental_history(
            base,
            {
                "symbols": [
                    {
                        "symbol": "301234",
                        "rows": 1,
                        "date_min": "2026-07-07",
                        "date_max": "2026-07-07",
                    },
                    {
                        "symbol": "600000",
                        "rows": 1,
                        "date_min": "2026-07-13",
                        "date_max": "2026-07-13",
                    },
                ]
            },
            plan,
            delta,
            incremental_metadata,
        )

        self.assertEqual(3, len(merged))
        self.assertEqual(
            "2026-07-07",
            merged.loc[merged["symbol"].eq("301234"), "date"].max(),
        )
        self.assertEqual(["301234"], report["no_trading_update_symbols"])
        self.assertEqual(
            ["301234"],
            metadata["incremental_no_trading_update_symbols"],
        )
        self.assertEqual(
            "false_means_no_unaudited_gaps_"
            "audited_no_trading_updates_disclosed_separately",
            metadata["incremental_partial_result_semantics"],
        )
        self.assertEqual("2026-07-07", metadata["date_min"])
        self.assertEqual("2026-07-14", metadata["date_max"])
        self.assertEqual("2026-07-14", metadata["end_date"])

        tampered_metadata = {
            **incremental_metadata,
            "raw_symbols": [
                {
                    "symbol": "301234",
                    "rows": 5,
                    "date_min": "2026-07-08",
                    "date_max": "2026-07-13",
                },
                incremental_metadata["raw_symbols"][1],
            ],
        }
        with self.assertRaisesRegex(ValueError, "does not reach target"):
            merge_incremental_history(
                base,
                {"symbols": []},
                plan,
                delta,
                tampered_metadata,
            )

    def test_publish_output_pair_rolls_back_when_second_publish_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first_target = root / "prices.csv"
            second_target = root / "metadata.json"
            first_staged = root / ".prices.csv.stage"
            second_staged = root / ".metadata.json.stage"
            first_target.write_text("old-prices\n", encoding="utf-8")
            second_target.write_text("old-metadata\n", encoding="utf-8")
            first_staged.write_text("new-prices\n", encoding="utf-8")
            second_staged.write_text("new-metadata\n", encoding="utf-8")
            original_replace = Path.replace

            def controlled_replace(source: Path, target: Path) -> Path:
                if source == second_staged and Path(target) == second_target:
                    raise OSError("second publish failed")
                return original_replace(source, target)

            with (
                patch.object(Path, "replace", new=controlled_replace),
                self.assertRaisesRegex(OSError, "second publish failed"),
            ):
                publish_output_pair(
                    [
                        (first_staged, first_target),
                        (second_staged, second_target),
                    ],
                    "rollback-test",
                )

            first_value = first_target.read_text(encoding="utf-8")
            second_value = second_target.read_text(encoding="utf-8")

        self.assertEqual("old-prices\n", first_value)
        self.assertEqual("old-metadata\n", second_value)

    def test_noop_plan_rejects_verified_merge_arguments(self) -> None:
        plan = {
            "source": "incremental_history_plan",
            "claim_boundary": "incremental_history_plan_only_not_history_fetch_success",
            "target_end_date": "2026-07-09",
            "fetch_symbols": [],
            "fetch_buckets": [],
        }
        args = build_parser().parse_args(
            [
                "--plan",
                "plan.json",
                "--provider",
                "zzshare",
                "--output-dir",
                "output",
                "--base-prices",
                "base.csv",
                "--base-metadata",
                "base.json",
                "--merged-output",
                "merged.csv",
                "--merged-metadata-output",
                "merged.json",
                "--merge-report-output",
                "merge-report.json",
            ]
        )

        with self.assertRaisesRegex(ValueError, "no fetch buckets"):
            build_config(args, Path("plan.json").resolve(), plan)

    def test_resume_ignores_nonsemantic_plan_observation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first_plan = incremental_execution_plan()
            first_plan.update(
                {
                    "generated_at": "2026-07-13T01:00:00Z",
                    "plan_duration_seconds": 1.25,
                    "plan_symbols_per_second": 1.6,
                }
            )
            config = incremental_execution_config(root)

            def executor(command: list[str]) -> int:
                write_bucket_artifacts(command, rows=1)
                return 0

            execute_plan(first_plan, config, executor)
            second_plan = json.loads(json.dumps(first_plan))
            second_plan.update(
                {
                    "generated_at": "2026-07-13T02:00:00Z",
                    "plan_duration_seconds": 4.5,
                    "plan_symbols_per_second": 0.44,
                }
            )
            config["resume"] = True
            calls: list[list[str]] = []

            manifest = execute_plan(second_plan, config, calls.append)

        self.assertEqual([], calls)
        self.assertEqual("complete", manifest["status"])
        self.assertEqual(2, manifest["reused_bucket_count"])

    def test_aggregate_failure_preserves_published_outputs_and_records_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)
            config["prices_output"].parent.mkdir(parents=True, exist_ok=True)
            config["prices_output"].write_text("stable-prices\n", encoding="utf-8")
            config["metadata_output"].write_text(
                '{"stable": true}\n', encoding="utf-8"
            )

            def executor(command: list[str]) -> int:
                write_bucket_artifacts(command, rows=1)
                metadata_path = Path(command[command.index("--metadata-output") + 1])
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["raw_rows"] = "not-an-integer"
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
                return 0

            manifest = execute_plan(plan, config, executor)
            saved = json.loads(
                config["manifest_output"].read_text(encoding="utf-8")
            )
            published_prices = config["prices_output"].read_text(encoding="utf-8")
            published_metadata = config["metadata_output"].read_text(
                encoding="utf-8"
            )

        self.assertEqual("partial", manifest["status"])
        self.assertEqual("aggregate_outputs", manifest["failed_stage"])
        self.assertIn("not-an-integer", manifest["error"])
        self.assertEqual("stable-prices\n", published_prices)
        self.assertEqual(
            '{"stable": true}\n',
            published_metadata,
        )
        self.assertEqual("partial", saved["status"])

    def test_empty_plan_is_explicit_noop_without_stale_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = {
                "source": "incremental_history_plan",
                "claim_boundary": (
                    "incremental_history_plan_only_not_history_fetch_success"
                ),
                "target_end_date": "2026-07-09",
                "fetch_symbols": [],
                "fetch_buckets": [],
            }
            config = incremental_execution_config(root)
            config["prices_output"].parent.mkdir(parents=True, exist_ok=True)
            config["prices_output"].write_text("stale-prices\n", encoding="utf-8")
            config["metadata_output"].write_text(
                '{"stale": true}\n', encoding="utf-8"
            )

            manifest = execute_plan(plan, config, self.fail)
            prices_exists = config["prices_output"].exists()
            metadata_exists = config["metadata_output"].exists()

        self.assertEqual("complete", manifest["status"])
        self.assertTrue(manifest["no_op"])
        self.assertEqual("plan_has_no_fetch_symbols", manifest["no_op_reason"])
        self.assertFalse(manifest["prices_output_written"])
        self.assertFalse(manifest["metadata_output_written"])
        self.assertFalse(prices_exists)
        self.assertFalse(metadata_exists)

    def test_combined_metadata_preserves_non_trading_audit_counts(self) -> None:
        items = [
            {
                "symbols": [{"symbol": "000001", "rows": 2}],
                "non_trading_policy": "drop",
                "raw_non_trading_rows": 3,
                "raw_invalid_non_trading_overlap_rows": 1,
                "raw_quality_counter_semantics": "raw_dimension_counts_not_additive",
                "non_trading_rows": 0,
                "dropped_non_trading_rows": 3,
                "retained_non_trading_rows": 0,
                "dropped_invalid_rows": 0,
                "tradestatus_missing_rows": 0,
            },
            {
                "symbols": [{"symbol": "600000", "rows": 2}],
                "non_trading_policy": "drop",
                "raw_non_trading_rows": 2,
                "raw_invalid_non_trading_overlap_rows": 2,
                "raw_quality_counter_semantics": "raw_dimension_counts_not_additive",
                "non_trading_rows": 0,
                "dropped_non_trading_rows": 2,
                "retained_non_trading_rows": 0,
                "dropped_invalid_rows": 0,
                "tradestatus_missing_rows": 0,
            },
        ]

        metadata = combine_metadata(
            {"fetch_symbols": ["000001", "600000"]},
            items,
            "zzshare",
            rows=4,
        )

        self.assertEqual("drop", metadata["non_trading_policy"])
        self.assertEqual(5, metadata["raw_non_trading_rows"])
        self.assertEqual(3, metadata["raw_invalid_non_trading_overlap_rows"])
        self.assertEqual(
            "raw_dimension_counts_not_additive",
            metadata["raw_quality_counter_semantics"],
        )
        self.assertEqual(5, metadata["dropped_non_trading_rows"])
        self.assertEqual(0, metadata["non_trading_rows"])
        self.assertEqual(0, metadata["retained_non_trading_rows"])
        self.assertFalse(metadata["partial_result"])
        self.assertEqual(
            "false_means_no_unaudited_gaps_"
            "audited_no_trading_updates_disclosed_separately",
            metadata["partial_result_semantics"],
        )
        self.assertFalse(metadata["rate_limit_budget_exhausted"])
        self.assertEqual([], metadata["unprocessed_symbols"])

    def test_combined_metadata_distinguishes_requested_and_output_symbols(self) -> None:
        metadata = combine_metadata(
            {"fetch_symbols": ["000001", "600000"]},
            [
                {
                    "symbols": [
                        {"symbol": "000001", "rows": 2},
                        {"symbol": "600000", "rows": 0},
                    ],
                    "raw_symbols": [
                        {"symbol": "000001", "rows": 2},
                        {"symbol": "600000", "rows": 1},
                    ],
                    "empty_symbols": ["600000"],
                    "non_trading_only_empty_symbols": ["600000"],
                }
            ],
            "baostock",
            rows=2,
        )

        self.assertEqual(1, metadata["symbol_count"])
        self.assertEqual(2, metadata["requested_symbol_count"])


if __name__ == "__main__":
    unittest.main()
