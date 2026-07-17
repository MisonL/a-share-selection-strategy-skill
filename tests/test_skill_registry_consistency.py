from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SkillRegistryConsistencyTests(unittest.TestCase):
    def test_data_source_registry_entries_are_documented(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        registry = json.loads(
            (root / "configs/data_sources.json").read_text(encoding="utf-8")
        )
        script_reference = (root / "references/script-reference.md").read_text(
            encoding="utf-8"
        )
        workflow = (root / "instructions/full-a-strict-workflow.md").read_text(
            encoding="utf-8"
        )
        scripts_index = (root / "scripts/SCRIPTS.md").read_text(encoding="utf-8")

        self.assertEqual(
            "capability_registry_only_not_runtime_source_selection_or_stability_proof",
            registry["claim_boundary"],
        )
        for source, metadata in registry["sources"].items():
            with self.subTest(source=source):
                entry = metadata["entry"]
                self.assertIn(entry, script_reference)
                self.assertIn(entry, scripts_index)
                self.assertTrue(metadata["full_a_role"])
                self.assertIn(entry.split("_", 1)[0], script_reference + workflow)
                for field in metadata["primary_fields"]:
                    self.assertIsInstance(field, str)
                    self.assertTrue(field)
                for limitation in metadata["cannot_prove"]:
                    self.assertIsInstance(limitation, str)
                    self.assertTrue(limitation)

    def test_data_source_registry_schema_is_strict(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        registry = json.loads(
            (root / "configs/data_sources.json").read_text(encoding="utf-8")
        )
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                root / "instructions/full-a-strict-workflow.md",
                root / "instructions/runbook.md",
                root / "references/index.md",
                root / "references/script-reference.md",
            ]
        )

        self.assertEqual({"schema_version", "claim_boundary", "sources"}, set(registry))
        self.assertEqual(2, registry["schema_version"])
        self.assertIsInstance(registry["sources"], dict)
        self.assertTrue(registry["sources"])
        expected_metadata_keys = {
            "entry",
            "service",
            "role",
            "requires_token",
            "token_environment_variable",
            "primary_fields",
            "full_a_role",
            "full_a_hard_stop_conditions",
            "full_a_recovery_or_reporting_conditions",
            "cannot_prove",
        }
        optional_metadata_keys = {
            "date_resolution",
            "retry_policy",
            "license_claim_boundary",
            "merge_contract",
        }
        source_key_pattern = re.compile(r"^[a-z][a-z0-9_]*$")

        for source, metadata in registry["sources"].items():
            with self.subTest(source=source):
                self.assertRegex(source, source_key_pattern)
                self.assertEqual(
                    set(),
                    set(metadata) - expected_metadata_keys - optional_metadata_keys,
                )
                self.assertLessEqual(expected_metadata_keys, set(metadata))
                entry = metadata["entry"]
                self.assertTrue((root / "scripts" / entry).is_file())
                self.assertEqual(entry, Path(entry).name)
                self.assertIsInstance(metadata["requires_token"], bool)
                self.assertIsInstance(metadata["token_environment_variable"], str)
                self.assertIsInstance(metadata["primary_fields"], list)
                self.assertIsInstance(metadata["full_a_hard_stop_conditions"], list)
                self.assertIsInstance(
                    metadata["full_a_recovery_or_reporting_conditions"],
                    list,
                )
                self.assertIsInstance(metadata["cannot_prove"], list)
                for key in ["service", "role", "full_a_role"]:
                    self.assertIsInstance(metadata[key], str)
                    self.assertTrue(metadata[key])
                if metadata["token_environment_variable"]:
                    self.assertIn(metadata["token_environment_variable"], docs)

        self.assertEqual(
            "primary_universe_symbol_pool_for_history_breadth",
            registry["sources"]["baostock_universe"]["full_a_role"],
        )
        self.assertEqual(
            "supplemental_realtime_display_enrichment",
            registry["sources"]["eastmoney_spot"]["full_a_role"],
        )
        self.assertIn(
            "primary_full_a_universe_availability",
            registry["sources"]["eastmoney_spot"]["cannot_prove"],
        )
        self.assertEqual(
            "explicit_full_a_history_provider_cold_start_or_incremental",
            registry["sources"]["zzshare_history"]["full_a_role"],
        )
        self.assertEqual(
            "explicit_full_a_history_provider_bucketed_incremental",
            registry["sources"]["baostock_history"]["full_a_role"],
        )
        self.assertIn(
            "empty_symbols_nonempty",
            registry["sources"]["zzshare_history"][
                "full_a_recovery_or_reporting_conditions"
            ],
        )
        self.assertNotIn(
            "empty_symbols_nonempty",
            registry["sources"]["zzshare_history"][
                "full_a_hard_stop_conditions"
            ],
        )
        self.assertIn(
            "audited_no_trading_empty_symbols_nonempty",
            registry["sources"]["baostock_history"][
                "full_a_recovery_or_reporting_conditions"
            ],
        )
        self.assertIn(
            "unaudited_empty_symbols_nonempty",
            registry["sources"]["baostock_history"][
                "full_a_hard_stop_conditions"
            ],
        )
        self.assertEqual(
            [],
            registry["sources"]["eastmoney_spot"][
                "full_a_hard_stop_conditions"
            ],
        )

    def test_source_routing_registry_is_strict_and_documented(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        routing = json.loads(
            (root / "configs/source_routing.json").read_text(encoding="utf-8")
        )
        data_sources = json.loads(
            (root / "configs/data_sources.json").read_text(encoding="utf-8")
        )
        entrypoints = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                root / "SKILL.md",
                root / "references/index.md",
                root / "references/script-reference.md",
                root / "instructions/full-a-strict-workflow.md",
                root / "instructions/runbook.md",
            ]
        )

        self.assertEqual(
            {
                "schema_version",
                "claim_boundary",
                "routing_policy",
                "scenarios",
            },
            set(routing),
        )
        self.assertEqual(3, routing["schema_version"])
        self.assertEqual(
            "scenario_source_routing_only_not_runtime_auto_selection_or_fallback",
            routing["claim_boundary"],
        )
        self.assertEqual(
            {
                "automatic_source_selection": False,
                "automatic_fallback": False,
                "runtime_cli_explicit_fallback_requires_parameter": True,
                "explicit_fallback_sources_do_not_disable_cli_fallback_parameter": True,
                "network_sources_must_persist_tabular_artifact_and_metadata": True,
                "local_validation_does_not_prove_real_external_gates": True,
            },
            routing["routing_policy"],
        )
        self.assertIn("source_routing.json", docs)
        self.assertIn("automatic_source_selection=false", docs)
        self.assertIn("automatic_fallback=false", docs)
        self.assertIn("runtime_cli_explicit_fallback_requires_parameter=true", docs)
        self.assertIn(
            "`explicit_fallback_sources=[]` 表示该场景不推荐自动或预设备用源",
            docs,
        )

        expected_scenarios = {
            "local_scoring",
            "targeted_a_share_real_task",
            "full_a_strict_scan",
            "prediction_derived_a_share",
            "hong_kong_dataset_review",
            "overseas_ticker_review",
            "external_source_probe",
        }
        self.assertEqual(expected_scenarios, set(routing["scenarios"]))

        allowed_sources = set(data_sources["sources"])
        allowed_entrypoints = set(entrypoints["entries"])
        scenario_keys = {
            "description",
            "primary_sources",
            "explicit_fallback_sources",
            "supplemental_sources",
            "stable_entrypoints",
            "required_fields",
            "hard_stop_conditions",
            "recovery_or_reporting_conditions",
            "reporting_boundary",
        }
        optional_keys = {
            "default_controls",
            "history_provider_options",
            "supplemental_merge_contracts",
        }
        for scenario, metadata in routing["scenarios"].items():
            with self.subTest(scenario=scenario):
                self.assertEqual(set(), set(metadata) - scenario_keys - optional_keys)
                self.assertLessEqual(scenario_keys, set(metadata))
                for key in [
                    "primary_sources",
                    "explicit_fallback_sources",
                    "supplemental_sources",
                ]:
                    for source in metadata[key]:
                        self.assertIn(source, allowed_sources)
                for source in metadata.get("history_provider_options", []):
                    self.assertIn(source, allowed_sources)
                for entrypoint in metadata["stable_entrypoints"]:
                    self.assertIn(entrypoint, allowed_entrypoints)
                    self.assertTrue(entrypoints["entries"][entrypoint]["public_entry"])
                    self.assertTrue(entrypoints["entries"][entrypoint]["skill_route"])
                for key in [
                    "description",
                    "reporting_boundary",
                ]:
                    self.assertIsInstance(metadata[key], str)
                    self.assertTrue(metadata[key])
                self.assertTrue(metadata["required_fields"])
                self.assertTrue(metadata["hard_stop_conditions"])
                self.assertIsInstance(
                    metadata["recovery_or_reporting_conditions"],
                    list,
                )

        full_a = routing["scenarios"]["full_a_strict_scan"]
        self.assertEqual(
            ["baostock_universe"],
            full_a["primary_sources"],
        )
        self.assertEqual(
            ["zzshare_history", "baostock_history"],
            full_a["history_provider_options"],
        )
        self.assertEqual([], full_a["explicit_fallback_sources"])
        self.assertIn(
            "execute_incremental_history_plan.py",
            full_a["stable_entrypoints"],
        )
        self.assertEqual(
            1,
            full_a["default_controls"]["zzshare_history"][
                "history_max_concurrent_symbol_requests"
            ],
        )
        self.assertEqual(
            120,
            full_a["default_controls"]["zzshare_history"][
                "history_max_rate_limit_sleep_seconds"
            ],
        )
        self.assertEqual(
            3,
            full_a["default_controls"]["zzshare_history"][
                "history_max_429_events"
            ],
        )
        self.assertEqual(
            900,
            full_a["default_controls"]["zzshare_history"][
                "history_max_runtime_seconds"
            ],
        )
        self.assertIn("eastmoney_spot", full_a["supplemental_sources"])
        self.assertIn("pytdx_history", full_a["supplemental_sources"])
        self.assertNotIn("baostock_history", full_a["supplemental_sources"])
        self.assertNotIn("pytdx_history", full_a["primary_sources"])
        self.assertEqual(
            {
                "universe_partial_result_true",
                "history_failed_symbols_nonempty",
                "history_unprocessed_symbols_nonempty",
                "possibly_truncated_symbols_nonempty",
                "rate_limit_budget_exhausted_true",
                "history_empty_symbols_without_clean_pool_or_no_trading_audit",
            },
            set(full_a["hard_stop_conditions"]),
        )
        self.assertEqual(
            {
                "history_empty_symbols_with_clean_pool_or_no_trading_audit",
                "short_history_symbols_nonempty",
                "audited_no_trading_update_symbols_nonempty",
                "full_market_claim_allowed_false",
            },
            set(full_a["recovery_or_reporting_conditions"]),
        )
        for text in [
            "显式选择一个历史 provider",
            "ZZShare 冷启动或增量 breadth",
            "Baostock 分桶增量 breadth",
            "hard_stop_conditions",
            "recovery_or_reporting_conditions",
            "不表示自动选源",
        ]:
            self.assertIn(text, docs)
        runbook = (root / "instructions/runbook.md").read_text(encoding="utf-8")
        for text in [
            "全 A 历史必须显式选择一个历史 provider",
            "ZZShare 冷启动或增量 breadth",
            "Baostock 分桶增量 breadth",
        ]:
            with self.subTest(runbook_provider_contract=text):
                self.assertIn(text, runbook)
        for text in [
            "`zzshare` 是当前全 A 历史主路径",
            "全 A clean pool 复核才优先考虑它",
        ]:
            with self.subTest(runbook_stale_provider_contract=text):
                self.assertNotIn(text, runbook)
        pytdx_contract = full_a["supplemental_merge_contracts"]["pytdx_history"]
        self.assertEqual(["symbol", "date"], pytdx_contract["join_keys"])
        self.assertTrue(pytdx_contract["strict_fields_same_date_required"])
        self.assertFalse(pytdx_contract["selection_ready"])
        self.assertTrue(pytdx_contract["forbid_previous_date_strict_field_fill"])


if __name__ == "__main__":
    unittest.main()
