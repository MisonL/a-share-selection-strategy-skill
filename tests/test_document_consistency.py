from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentConsistencyTests(unittest.TestCase):
    def test_skill_resources_use_semantic_directories(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (
            ROOT / "skills/a-share-selection-strategy/SKILL.md"
        ).read_text(encoding="utf-8")
        index = (
            ROOT / "skills/a-share-selection-strategy/references/index.md"
        ).read_text(encoding="utf-8")

        for directory in ["instructions/", "templates/", "evidence/"]:
            self.assertIn(directory, readme)
        self.assertIn("instructions/runbook.md", skill)
        self.assertIn("templates/output-templates.md", skill)
        self.assertIn("references/script-reference.md", skill)
        self.assertIn("../evidence/reviews/", index)

        docs = readme + skill + index
        self.assertNotIn("references/runbook.md", docs)
        self.assertNotIn("references/output-templates.md", docs)
        self.assertNotIn("references/script-index.md", docs)
        self.assertNotIn("references/reviews/", docs)

    def test_agents_license_statement_matches_repository_license(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

        self.assertIn("MIT License", license_text)
        self.assertIn("MIT License", readme)
        self.assertNotIn("当前仓库未声明许可证", agents)

    def test_output_templates_reject_hidden_boundaries_and_trade_advice(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        templates = (
            ROOT
            / "skills/a-share-selection-strategy/templates/output-templates.md"
        ).read_text(encoding="utf-8")

        self.assertIn("market=A-share", templates)
        self.assertIn("用户要求直接给结论但要求隐藏边界", templates)
        self.assertIn("不能省略数据源、门禁和非投资建议边界", templates)
        for text in [
            "非投资建议",
            "非交易指令",
            "非真实成交",
            "非收益证明",
        ]:
            self.assertIn(text, templates)
            self.assertIn(text, readme)

    def test_docs_cover_spot_demo_and_provenance_outputs(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (
            ROOT / "skills/a-share-selection-strategy/SKILL.md"
        ).read_text(encoding="utf-8")
        runbook = (
            ROOT / "skills/a-share-selection-strategy/instructions/runbook.md"
        ).read_text(encoding="utf-8")

        for document in [readme, skill, runbook]:
            self.assertIn("--spot-input", document)
            self.assertIn("spot_industry", document)
            self.assertIn("source_provenance", document)
            self.assertIn("summary_output_written", document)
            self.assertIn("manifest_output_written", document)
        self.assertIn("candidate_field_coverage", skill)
        self.assertIn("selection_failed_reason", skill)
        self.assertIn("selection_failed_next_action", runbook)

    def test_skill_routes_full_market_tasks_to_dedicated_workflow(self) -> None:
        skill = (
            ROOT / "skills/a-share-selection-strategy/SKILL.md"
        ).read_text(encoding="utf-8")
        index = (
            ROOT / "skills/a-share-selection-strategy/references/index.md"
        ).read_text(encoding="utf-8")
        runbook = (
            ROOT / "skills/a-share-selection-strategy/instructions/runbook.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills/a-share-selection-strategy/instructions/full-a-strict-workflow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## 任务拓扑", skill)
        self.assertIn("全 A 严格任务", skill)
        self.assertIn("今日 A 股选股", skill)
        self.assertIn("默认按全 A 严格任务判断", skill)
        self.assertIn("full-a-strict-workflow.md", skill)
        self.assertIn("跑全 A / 全市场真实任务", index)
        self.assertIn("今日 A 股选股 / 真实 A 股选股 / 全 A", runbook)
        self.assertIn("用户没有限定 symbol、板块、本地股票池或本地行情文件", runbook)
        self.assertIn("## 当前推荐拓扑", workflow)
        self.assertIn("用户只说“选 A 股”", workflow)
        self.assertIn("eastmoney", workflow)
        self.assertIn("zzshare", workflow)
        self.assertIn("## 数据源能力矩阵", workflow)
        self.assertIn("`ZZSHARE_TOKEN`", workflow)
        self.assertIn("akshare", workflow)
        self.assertIn("fallback 成功不能写成主接口稳定", workflow)
        self.assertIn("query_stock_basic", workflow)
        self.assertIn("全市场 5000+ 标的会显著增加远端请求数", workflow)

    def test_docs_lock_data_source_capability_boundaries(self) -> None:
        index = (
            ROOT / "skills/a-share-selection-strategy/references/index.md"
        ).read_text(encoding="utf-8")
        runbook = (
            ROOT / "skills/a-share-selection-strategy/instructions/runbook.md"
        ).read_text(encoding="utf-8")
        script_reference = (
            ROOT / "skills/a-share-selection-strategy/references/script-reference.md"
        ).read_text(encoding="utf-8")
        data_sources = (
            ROOT / "skills/a-share-selection-strategy/configs/data_sources.json"
        ).read_text(encoding="utf-8")

        self.assertIn("数据源能力边界", index)
        self.assertIn("数据源免费边界", index)
        self.assertIn("数据源能力矩阵", index)
        self.assertIn("data_sources.json", index)
        self.assertIn("data_sources.json", script_reference)
        self.assertIn("## 数据源能力边界", script_reference)
        self.assertIn("fetch_eastmoney_a_share_spot.py", script_reference)
        self.assertIn("fetch_zzshare_a_share.py", script_reference)
        self.assertIn("ZZSHARE_TOKEN", script_reference)
        self.assertIn("不要把 token 放进 CLI 参数", script_reference)
        self.assertIn("ZZSHARE_TOKEN", data_sources)
        self.assertIn("capability_registry_only", data_sources)
        self.assertIn("最小单轮探针的解释规则", runbook)
        self.assertIn("fallback_errors", runbook)
        self.assertIn("market_label_only=true", runbook)
        self.assertIn("long_term_stability_claim", runbook)

    def test_data_source_registry_entries_are_documented(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        registry = json.loads((root / "configs/data_sources.json").read_text(encoding="utf-8"))
        script_reference = (root / "references/script-reference.md").read_text(encoding="utf-8")
        workflow = (root / "instructions/full-a-strict-workflow.md").read_text(encoding="utf-8")
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
        registry = json.loads((root / "configs/data_sources.json").read_text(encoding="utf-8"))
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
        self.assertEqual(1, registry["schema_version"])
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
            "full_a_stop_conditions",
            "cannot_prove",
        }
        source_key_pattern = re.compile(r"^[a-z][a-z0-9_]*$")

        for source, metadata in registry["sources"].items():
            with self.subTest(source=source):
                self.assertRegex(source, source_key_pattern)
                self.assertEqual(expected_metadata_keys, set(metadata))
                entry = metadata["entry"]
                self.assertTrue((root / "scripts" / entry).is_file())
                self.assertEqual(entry, Path(entry).name)
                self.assertIsInstance(metadata["requires_token"], bool)
                self.assertIsInstance(metadata["token_environment_variable"], str)
                self.assertIsInstance(metadata["primary_fields"], list)
                self.assertIsInstance(metadata["full_a_stop_conditions"], list)
                self.assertIsInstance(metadata["cannot_prove"], list)
                for key in ["service", "role", "full_a_role"]:
                    self.assertIsInstance(metadata[key], str)
                    self.assertTrue(metadata[key])
                if metadata["token_environment_variable"]:
                    self.assertIn(metadata["token_environment_variable"], docs)

    def test_script_entrypoint_registry_covers_root_scripts(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        scripts_root = root / "scripts"
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )

        root_scripts = sorted(path.name for path in scripts_root.glob("*.py"))
        registered_scripts = sorted(registry["entries"])

        self.assertEqual(root_scripts, registered_scripts)
        self.assertEqual(
            "script_entrypoint_registry_only_not_runtime_dispatch_or_cli_contract_replacement",
            registry["claim_boundary"],
        )

    def test_script_entrypoint_registry_schema_is_strict(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )
        scripts_index = (root / "scripts/SCRIPTS.md").read_text(encoding="utf-8")
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                ROOT / "README.md",
                root / "SKILL.md",
                root / "references/index.md",
                root / "references/script-reference.md",
                root / "scripts/SCRIPTS.md",
            ]
        )

        self.assertEqual({"schema_version", "claim_boundary", "categories", "entries"}, set(registry))
        self.assertEqual(1, registry["schema_version"])
        allowed_categories = {"stable_cli", "fetch_cli", "gate_backtest_cli", "internal_helper"}
        self.assertEqual(allowed_categories, set(registry["categories"]))
        self.assertIn("script_entrypoints.json", docs)
        self.assertIn("不做运行时 dispatch", docs)

        expected_entry_keys = {
            "category",
            "public_entry",
            "network_required",
            "real_gate_boundary",
            "primary_artifacts",
        }
        public_categories = {"stable_cli", "fetch_cli", "gate_backtest_cli"}
        for script, metadata in registry["entries"].items():
            with self.subTest(script=script):
                self.assertEqual(expected_entry_keys, set(metadata))
                self.assertTrue((root / "scripts" / script).is_file())
                self.assertEqual(script, Path(script).name)
                self.assertIn(metadata["category"], allowed_categories)
                self.assertIsInstance(metadata["public_entry"], bool)
                self.assertIsInstance(metadata["network_required"], bool)
                self.assertIsInstance(metadata["primary_artifacts"], list)
                self.assertIsInstance(metadata["real_gate_boundary"], str)
                self.assertTrue(metadata["real_gate_boundary"])
                if metadata["public_entry"]:
                    self.assertIn(metadata["category"], public_categories)
                    self.assertIn(script, scripts_index)
                else:
                    self.assertEqual("internal_helper", metadata["category"])

    def test_script_entrypoint_registry_keeps_expected_public_surface(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )
        by_category: dict[str, set[str]] = {}
        for script, metadata in registry["entries"].items():
            by_category.setdefault(metadata["category"], set()).add(script)

        self.assertEqual(
            {
                "create_demo_data.py",
                "validate_ohlcv.py",
                "score_candidates.py",
                "run_today_a_share_selection.py",
                "slice_prices_as_of.py",
            },
            by_category["stable_cli"],
        )
        self.assertEqual(
            {
                "fetch_eastmoney_a_share_spot.py",
                "fetch_baostock_a_share.py",
                "fetch_akshare_a_share.py",
                "fetch_akshare_hk_daily.py",
                "fetch_zzshare_a_share.py",
                "fetch_yfinance_ohlcv.py",
            },
            by_category["fetch_cli"],
        )
        self.assertIn("a_share_selection_html_sections.py", by_category["internal_helper"])
        self.assertIn("run_today_a_share_selection_helpers.py", by_category["internal_helper"])
        self.assertTrue(
            registry["entries"]["fetch_zzshare_a_share.py"]["network_required"]
        )
        self.assertFalse(
            registry["entries"]["score_candidates.py"]["network_required"]
        )

    def test_script_docs_keep_html_report_as_display_layer(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        scripts_index = (root / "scripts/SCRIPTS.md").read_text(encoding="utf-8")
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )

        for script in [
            "a_share_selection_html_sections.py",
            "a_share_selection_html_scripts.py",
            "a_share_selection_html_candidate_master.py",
        ]:
            with self.subTest(script=script):
                self.assertEqual(
                    "internal_helper",
                    registry["entries"][script]["category"],
                )
                self.assertFalse(registry["entries"][script]["public_entry"])
                self.assertIn(script, scripts_index)
        self.assertIn("HTML 报告模块是当前最大维护热点", scripts_index)
        self.assertIn("只能继续作为展示层 helper 拆分", scripts_index)
        self.assertIn("不能把候选事实、门禁判断或机器字段来源移动进 HTML 展示层", scripts_index)
        self.assertIn("`report.html` 输出契约不变", scripts_index)

    def test_runner_docs_cover_symbols_file_plan_and_resume_controls(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                root / "SKILL.md",
                root / "instructions/full-a-strict-workflow.md",
                root / "instructions/runbook.md",
                root / "references/script-reference.md",
                root / "scripts/SCRIPTS.md",
            ]
        )
        for text in ["--symbols-file", "--plan-only", "--resume-from"]:
            self.assertIn(text, docs)
        self.assertIn("plan_only", docs)
        self.assertIn("resume_retry_symbols", docs)
        self.assertIn("explicit_symbols_file", docs)
        self.assertIn("没有可重试 symbol", docs)
        self.assertIn("审计所需输入快照", docs)
        self.assertIn("resume_inherited_options", docs)
        self.assertIn("resume_sensitive_options_requiring_explicit_input", docs)
        self.assertIn("需要复用时必须本轮显式传 `--history-http-url`", docs)
        self.assertIn("历史源与上一轮一致", docs)
        self.assertIn("manifest 所在目录", docs)

    def test_unified_validation_entry_is_documented(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        closeout = root / "evidence/reviews/SKILL-SYSTEM-CLOSEOUT-2026-07-04.md"
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        validator = (ROOT / "validate_skill_changes.py").read_text(encoding="utf-8")
        closeout_text = closeout.read_text(encoding="utf-8")
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                ROOT / "README.md",
                ROOT / "AGENTS.md",
                root / "instructions/runbook.md",
                closeout,
            ]
        )
        result = subprocess.run(
            [sys.executable, str(ROOT / "validate_skill_changes.py"), "--list"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("python3 validate_skill_changes.py", docs)
        self.assertIn("本地仓库门禁", docs)
        self.assertIn("真实行情", docs)
        readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
        agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        runbook_text = (
            root / "instructions/runbook.md"
        ).read_text(encoding="utf-8")
        self.assertIn("runbook 验证命令", readme_text)
        self.assertNotIn("python3 -m json.tool", readme_text)
        self.assertNotIn("PYTHONPYCACHEPREFIX", readme_text)
        self.assertIn("validate_skill_changes.py` 的人工展开视图", agents_text)
        self.assertIn("validate_skill_changes.py` 的人工展开视图", runbook_text)
        self.assertNotIn("/Users/", validator)
        self.assertIn("Path.home()", validator)
        self.assertIn("historical leaked-key probe split", validator)
        self.assertIn('ROOT / ".github"', validator)
        self.assertIn("Local validation gates:", result.stdout)
        self.assertIn("full unittest suite", result.stdout)
        self.assertIn("text whitespace and conflict marker scan", result.stdout)
        self.assertIn("External gates not run", result.stdout)
        self.assertIn(
            "SKILL-SYSTEM-CLOSEOUT-2026-07-04.md",
            (root / "references/index.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "python3 validate_skill_changes.py --skip-skill-validate --skip-tests",
            workflow,
        )
        self.assertIn("Run repo health checks", workflow)
        for path in [
            "configs/data_sources.json",
            "evidence/reviews/SKILL-SYSTEM-CLOSEOUT-2026-07-04.md",
            "a_share_selection_command_safety.py",
            "prepare_history_retry_symbols.py",
            "tests/test_recovery_and_safety_helpers.py",
            "validate_skill_changes.py",
        ]:
            with self.subTest(path=path):
                self.assertIn(path, closeout_text)

    def test_skill_docs_define_agent_execution_and_recovery_protocol(self) -> None:
        skill = (
            ROOT / "skills/a-share-selection-strategy/SKILL.md"
        ).read_text(encoding="utf-8")
        index = (
            ROOT / "skills/a-share-selection-strategy/references/index.md"
        ).read_text(encoding="utf-8")
        templates = (
            ROOT
            / "skills/a-share-selection-strategy/templates/output-templates.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills/a-share-selection-strategy/instructions/full-a-strict-workflow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## Agent 执行协议", skill)
        self.assertIn("## Agent 控制合同", skill)
        self.assertIn("## 路径到入口的映射", skill)
        self.assertIn("## 每条路径的必看 artifact", skill)
        self.assertIn("## Agent 快速检查表", index)
        self.assertIn("## 恢复动作快速路由", templates)
        self.assertIn("全 A 严格任务汇报骨架", templates)
        self.assertIn("candidate_field_coverage", skill)
        self.assertIn("selection_failed_reason", templates)
        self.assertIn("## 失败恢复路由", workflow)
        self.assertIn("prepare_history_retry_symbols.py", workflow)
        self.assertIn("retry_plan_only_not_full_market_completion", workflow)
        self.assertIn("不要只给页面链接或只报最终候选数", workflow)
        self.assertIn("metadata.json`，若缺失则回退读取 `history_metadata.json`", workflow)
        self.assertNotIn("cp \"$RUN/clean/history_metadata.json\" \"$RUN/clean/metadata.json\"", workflow)

    def test_runner_code_exposes_machine_execution_path_for_skill_routes(self) -> None:
        skill = (
            ROOT / "skills/a-share-selection-strategy/SKILL.md"
        ).read_text(encoding="utf-8")
        runner = (
            ROOT / "skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py"
        ).read_text(encoding="utf-8")
        summary = (
            ROOT
            / "skills/a-share-selection-strategy/scripts/run_today_a_share_selection_summary.py"
        ).read_text(encoding="utf-8")
        provenance = (
            ROOT
            / "skills/a-share-selection-strategy/scripts/run_today_a_share_selection_provenance.py"
        ).read_text(encoding="utf-8")

        self.assertIn("本地评分", skill)
        self.assertIn("定向真实任务", skill)
        self.assertIn("全 A 严格任务", skill)
        self.assertIn("prediction-derived", skill)
        self.assertIn("execution_path", runner)
        self.assertIn("history_fetch_spot_derived_sample", runner)
        self.assertIn("history_fetch_spot_derived_explicit_limit", runner)
        self.assertIn("explicit_symbols", runner)
        self.assertIn("explicit_symbols_file", runner)
        self.assertIn("resume_retry_symbols", runner)
        self.assertIn("local_prices_", runner)
        self.assertIn("coverage_class", runner)
        self.assertIn("full_market_claim_allowed", runner)
        self.assertIn("full_market_claim_boundary", runner)
        self.assertIn("\"execution_path\"", summary)
        self.assertIn("\"coverage_class\"", summary)
        self.assertIn("\"full_market_claim_boundary\"", summary)
        self.assertIn("\"execution_path\"", provenance)
        self.assertIn("\"coverage_class\"", provenance)
        self.assertIn("\"full_market_claim_boundary\"", provenance)


if __name__ == "__main__":
    unittest.main()
