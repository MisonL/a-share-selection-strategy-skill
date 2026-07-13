from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.gates.incremental_history_execution import (  # noqa: E402
    combine_metadata,
    execute_plan,
    publish_output_pair,
)
from execute_incremental_history_plan import build_config, build_parser  # noqa: E402
from tests.test_recovery_and_safety_helpers import (  # noqa: E402
    incremental_execution_config,
    incremental_execution_plan,
    write_bucket_artifacts,
)


class IncrementalHistoryExecutionSafetyTests(unittest.TestCase):
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
        self.assertEqual(5, metadata["dropped_non_trading_rows"])
        self.assertEqual(0, metadata["non_trading_rows"])
        self.assertEqual(0, metadata["retained_non_trading_rows"])
        self.assertFalse(metadata["partial_result"])
        self.assertFalse(metadata["rate_limit_budget_exhausted"])
        self.assertEqual([], metadata["unprocessed_symbols"])


if __name__ == "__main__":
    unittest.main()
