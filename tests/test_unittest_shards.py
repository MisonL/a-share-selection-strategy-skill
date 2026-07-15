from __future__ import annotations

from pathlib import Path
import sys
import unittest

TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_ROOT))

from run_unittest_shard import (
    RUNNER_METHOD_SHARDS,
    RUNNER_TEST_FILE,
    SHARDS,
    all_test_ids,
    discover_test_files,
    files_for_shard,
    runner_method_names,
    runner_method_shard,
    test_ids_for_shard,
)


class UnittestShardContractTests(unittest.TestCase):
    def test_all_test_files_are_assigned_to_exactly_one_nonempty_shard(self) -> None:
        discovered = {
            path.name
            for path in discover_test_files()
            if path.name != RUNNER_TEST_FILE
        }
        assignments = {
            shard: {
                path.name
                for path in files_for_shard(shard)
                if path.name != RUNNER_TEST_FILE
            }
            for shard in SHARDS
        }

        flattened = [name for names in assignments.values() for name in names]
        self.assertEqual(discovered, set(flattened))
        self.assertEqual(len(discovered), len(flattened))

    def test_runner_methods_are_assigned_to_exactly_one_nonempty_shard(self) -> None:
        methods = runner_method_names()
        assignments = {
            shard: {
                method for method in methods if runner_method_shard(method) == shard
            }
            for shard in RUNNER_METHOD_SHARDS
        }

        self.assertTrue(all(assignments.values()))
        flattened = [name for names in assignments.values() for name in names]
        self.assertEqual(set(methods), set(flattened))
        self.assertEqual(len(methods), len(flattened))

    def test_shard_suites_execute_every_test_exactly_once(self) -> None:
        assignments = {shard: test_ids_for_shard(shard) for shard in SHARDS}
        self.assertTrue(all(assignments.values()))
        flattened = [test_id for tests in assignments.values() for test_id in tests]
        self.assertEqual(len(flattened), len(set(flattened)))
        self.assertEqual(set(all_test_ids()), set(flattened))

    def test_heavy_suites_keep_dedicated_shards(self) -> None:
        for shard in RUNNER_METHOD_SHARDS:
            self.assertIn(
                RUNNER_TEST_FILE,
                {path.name for path in files_for_shard(shard)},
            )
        self.assertIn(
            "test_today_a_share_html_report.py",
            {path.name for path in files_for_shard("report")},
        )
        self.assertIn(
            "test_recovery_and_safety_helpers.py",
            {path.name for path in files_for_shard("gates")},
        )
        self.assertIn(
            "test_fetch_zzshare_a_share.py",
            {path.name for path in files_for_shard("providers")},
        )


if __name__ == "__main__":
    unittest.main()
