from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def markdown_table_rows_after_heading(text: str, heading: str) -> list[list[str]]:
    lines = text.splitlines()
    start = lines.index(heading)
    table_lines = []
    for line in lines[start + 1 :]:
        if not table_lines and not line.startswith("|"):
            continue
        if table_lines and not line.startswith("|"):
            break
        if line.startswith("|"):
            table_lines.append(line)
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in table_lines
    ]


def markdown_code_value(value: str) -> str:
    return value.strip().strip("`")


def markdown_link_targets(text: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)#][^)]+)\)", text)


def python_script_mentions(text: str) -> set[str]:
    return set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\.py\b", text))


def imported_top_level_modules(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name.split(".", 1)[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module.split(".", 1)[0]]
    return []


def has_main_guard(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        comparison = node.test
        if not isinstance(comparison, ast.Compare):
            continue
        if (
            not isinstance(comparison.left, ast.Name)
            or comparison.left.id != "__name__"
        ):
            continue
        for comparator in comparison.comparators:
            if isinstance(comparator, ast.Constant) and comparator.value == "__main__":
                return True
    return False


def calls_module_attribute(node: ast.AST, module: str, attribute: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == module
    )


class DocumentConsistencyTests(unittest.TestCase):
    def test_large_test_files_have_explicit_complexity_exemptions(self) -> None:
        tests_root = ROOT / "tests"
        manifest = json.loads(
            (tests_root / "complexity_exemptions.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            {
                "schema_version",
                "claim_boundary",
                "hard_line_threshold",
                "reassessment_line_thresholds",
                "exemptions",
                "reassessments",
            },
            set(manifest),
        )
        self.assertEqual(3, manifest["schema_version"])
        self.assertEqual(
            "temporary_test_file_complexity_exemptions_not_permanent_waivers",
            manifest["claim_boundary"],
        )
        self.assertEqual(1000, manifest["hard_line_threshold"])

        thresholds = manifest["reassessment_line_thresholds"]
        self.assertEqual({"test_today_a_share_selection_runner.py"}, set(thresholds))
        for path, threshold in thresholds.items():
            with self.subTest(threshold_path=path):
                self.assertIsInstance(threshold, int)
                self.assertGreater(threshold, 0)
                self.assertLess(
                    len((tests_root / path).read_text(encoding="utf-8").splitlines()),
                    threshold,
                    f"{path} reached its explicit reassessment threshold of {threshold} lines",
                )
        runner_reassessment = (
            "a runner option, provider, or output artifact is added, or this file reaches 7000 lines"
        )
        self.assertEqual(
            runner_reassessment,
            manifest["exemptions"]["test_today_a_share_selection_runner.py"][
                "reassess_when"
            ],
        )
        self.assertEqual(
            runner_reassessment,
            manifest["reassessments"]["test_today_a_share_selection_runner.py"][
                "next_trigger"
            ],
        )

        oversized = {
            path.name
            for path in tests_root.glob("test_*.py")
            if len(path.read_text(encoding="utf-8").splitlines())
            >= manifest["hard_line_threshold"]
        }
        exemptions = manifest["exemptions"]
        self.assertEqual(oversized, set(exemptions))
        for path, metadata in exemptions.items():
            with self.subTest(path=path):
                self.assertEqual(
                    {"reason", "split_boundary", "reassess_when"},
                    set(metadata),
                )
                for value in metadata.values():
                    self.assertIsInstance(value, str)
                    self.assertGreaterEqual(len(value.strip()), 24)
        reassessments = manifest["reassessments"]
        self.assertTrue(set(reassessments).issubset(exemptions))
        for path, metadata in reassessments.items():
            with self.subTest(reassessment=path):
                self.assertEqual(
                    {"assessed_on", "trigger", "decision", "next_trigger"},
                    set(metadata),
                )
                self.assertRegex(metadata["assessed_on"], r"^\d{4}-\d{2}-\d{2}$")
                for key in ("trigger", "decision", "next_trigger"):
                    self.assertGreaterEqual(len(metadata[key].strip()), 24)
                self.assertEqual(
                    metadata["next_trigger"],
                    exemptions[path]["reassess_when"],
                )

    def test_skill_resources_use_semantic_directories(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (ROOT / "skills/a-share-selection-strategy/SKILL.md").read_text(
            encoding="utf-8"
        )
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

    def test_current_real_gate_index_is_the_single_current_entry(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        index = (root / "references/index.md").read_text(encoding="utf-8")
        full_a_workflow = (
            root / "instructions/full-a-strict-workflow.md"
        ).read_text(encoding="utf-8")
        current_path = root / "evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md"
        current = current_path.read_text(encoding="utf-8")

        self.assertIn(str(current_path.relative_to(ROOT)), agents)
        self.assertNotIn("当前真实门禁优先级以", agents)
        self.assertIn(
            "../evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md",
            index,
        )
        self.assertIn(
            "../evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md",
            full_a_workflow,
        )
        for value in [
            "verified_limited_scope",
            "verified_small_scope_only",
            "verified_fixed_scope_only",
            "not_proven",
            "not_run",
            "full_market_claim_allowed=false",
            "真实 LightGBM prediction-derived",
            "券商订单、真实成交、滑点和真实资金容量",
            "Eastmoney spot 与旧默认 Pytdx 均为 0/3",
            "后续独立复验的新 Pytdx 默认 endpoint",
            "不属于上述 21 次统计",
            "本地验证边界",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, current)
        for target in markdown_link_targets(current):
            self.assertTrue((current_path.parent / target).is_file(), target)

    def test_skill_markdown_links_resolve_to_existing_files(self) -> None:
        skill_root = ROOT / "skills/a-share-selection-strategy"
        for document in sorted(skill_root.rglob("*.md")):
            text = document.read_text(encoding="utf-8")
            for target in markdown_link_targets(text):
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                path = (document.parent / target.split("#", 1)[0]).resolve()
                with self.subTest(document=document.name, target=target):
                    self.assertTrue(path.is_file(), target)

    def test_skill_route_table_keeps_single_first_read_entry(self) -> None:
        skill = (ROOT / "skills/a-share-selection-strategy/SKILL.md").read_text(
            encoding="utf-8"
        )
        route_table = markdown_table_rows_after_heading(skill, "## 路径到入口的映射")

        for row in route_table[2:]:
            with self.subTest(route=row[0]):
                self.assertEqual(1, len(markdown_link_targets(row[1])))

    def test_skill_task_topology_routes_only_to_public_cli(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )
        task_topology = markdown_table_rows_after_heading(skill, "## 任务拓扑")
        header = task_topology[0]
        action_index = header.index("首选动作")

        routed_scripts: set[str] = set()
        for row in task_topology[2:]:
            routed_scripts.update(python_script_mentions(row[action_index]))

        self.assertEqual(
            {
                "validate_ohlcv.py",
                "score_candidates.py",
                "run_today_a_share_selection.py",
            },
            routed_scripts,
        )
        for script in routed_scripts:
            with self.subTest(script=script):
                metadata = registry["entries"][script]
                self.assertTrue(metadata["public_entry"])
                self.assertTrue(metadata["skill_route"])
        self.assertIn("首选动作只能引用 `skill_route=true` 的公开 CLI", skill)

    def test_output_templates_reject_hidden_boundaries_and_trade_advice(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        templates = (
            ROOT / "skills/a-share-selection-strategy/templates/output-templates.md"
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
        skill = (ROOT / "skills/a-share-selection-strategy/SKILL.md").read_text(
            encoding="utf-8"
        )
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
        skill = (ROOT / "skills/a-share-selection-strategy/SKILL.md").read_text(
            encoding="utf-8"
        )
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
        self.assertIn("沪深 A 股股票池（前缀过滤，不含北交所）", skill)
        self.assertIn("今日 A 股选股", skill)
        self.assertIn("默认按全 A 严格任务判断", skill)
        self.assertIn("full-a-strict-workflow.md", skill)
        self.assertIn("跑全 A / 全市场真实任务", index)
        self.assertIn("今日 A 股选股 / 真实 A 股选股 / 全 A", runbook)
        self.assertIn("沪深 A 股股票池（前缀过滤，不含北交所）", runbook)
        self.assertIn("用户没有限定 symbol、板块、本地股票池或本地行情文件", runbook)
        self.assertIn("## 当前推荐拓扑", workflow)
        self.assertIn("用户只说“选 A 股”", workflow)
        self.assertIn("沪深 A 股股票池（前缀过滤，不含北交所）", workflow)
        self.assertIn("baostock_universe", workflow)
        self.assertIn("eastmoney", workflow)
        self.assertIn("zzshare", workflow)
        self.assertIn("## 数据源能力矩阵", workflow)
        self.assertIn("`ZZSHARE_TOKEN`", workflow)
        self.assertIn("akshare", workflow)
        self.assertIn("fallback 成功不能写成主接口稳定", workflow)
        self.assertIn("fetch_spot_fallback_used", workflow)
        self.assertIn("fetch_spot_primary_failure", workflow)
        self.assertIn("query_stock_basic", workflow)
        self.assertIn("全市场 5000+ 标的会显著增加远端请求数", workflow)
        self.assertIn("--derive-all-spot-symbols", workflow)
        self.assertIn("--retry-interval-seconds", workflow)
        self.assertIn("--request-interval-seconds", workflow)
        self.assertIn("实时展示增强", workflow)

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
        self.assertIn("fetch_baostock_a_share_universe.py", script_reference)
        self.assertIn("fetch_zzshare_a_share.py", script_reference)
        self.assertIn("ZZSHARE_TOKEN", script_reference)
        self.assertIn("不要把 token 放进 CLI 参数", script_reference)
        self.assertIn("ZZSHARE_TOKEN", data_sources)
        self.assertIn("capability_registry_only", data_sources)
        self.assertIn("最小单轮探针的解释规则", runbook)
        self.assertIn("fallback_errors", runbook)
        self.assertIn("market_label_only=true", runbook)
        self.assertIn("long_term_stability_claim", runbook)
        self.assertIn("--archive-dir", runbook)
        self.assertIn("code=archive_failed", runbook)
        self.assertIn("A_SHARE_SELECTION_EVIDENCE_ROOT", runbook)
        self.assertIn("不要把 `~/.cache` 当成持久证据根目录", runbook)
        self.assertIn("owner-only `0700`", runbook)
        self.assertIn("archive_manifest.json", runbook)
        self.assertIn("SHA-256", runbook)
        self.assertIn("也不能是符号链接", runbook)
        self.assertIn("metadata 键名和值中的敏感字符串", runbook)
        self.assertIn("脱敏后重名键会保留为稳定的 distinct 字段", runbook)
        self.assertIn("原始 `/tmp` 路径作为本轮 provenance", runbook)
        self.assertIn("绝不复制价格 CSV、Parquet", runbook)
        self.assertIn("不改变数据源路由、自动 fallback、host rotation", runbook)
        self.assertIn("选择依据是 [2026-07-17 的外部源稳定性诊断]", runbook)
        self.assertIn("仅记录改后复验", runbook)

    def test_readme_documents_local_shard_as_iterative_only(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("python tests/run_unittest_shard.py gates", readme)
        self.assertIn("它只用于开发反馈", readme)
        self.assertIn(
            "python3 validate_skill_changes.py --dependency-profile ci",
            readme,
        )

    def test_script_entrypoint_registry_covers_root_scripts(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        scripts_root = root / "scripts"
        scripts_doc = (scripts_root / "SCRIPTS.md").read_text(encoding="utf-8")
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
        self.assertNotIn(
            "本文件是 `scripts/` 目录入口分层的唯一事实源",
            scripts_doc,
        )
        self.assertIn("机器分类事实源", scripts_doc)
        self.assertIn("人类和 Agent 的解释层", scripts_doc)

    def test_script_inventory_covers_root_script_registry(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        scripts_root = root / "scripts"
        inventory_path = root / "references/script-inventory.md"
        inventory = inventory_path.read_text(encoding="utf-8")
        scripts_index = (root / "scripts/SCRIPTS.md").read_text(encoding="utf-8")
        references_index = (root / "references/index.md").read_text(encoding="utf-8")
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )

        rows = markdown_table_rows_after_heading(inventory, "## 脚本用途和必要性")
        header = rows[0]
        self.assertEqual(
            ["脚本", "分类", "领域", "行数", "用途", "必要性判断"],
            header,
        )
        body = rows[2:]
        inventory_by_script = {markdown_code_value(row[0]): row for row in body}
        root_scripts = sorted(scripts_root.glob("*.py"))

        self.assertEqual(set(registry["entries"]), set(inventory_by_script))
        self.assertEqual(len(registry["entries"]), len(body))
        self.assertIn("不是运行时入口", inventory)
        self.assertIn("不替代 `../configs/script_entrypoints.json`", inventory)
        self.assertIn("不进入 Skill 首轮读取路径", inventory)
        self.assertIn("新 helper 默认进入 `lib/`", inventory)
        self.assertIn("逐个脚本的用途、必要性和迁移判断", scripts_index)
        self.assertIn("不是常规任务启动路径", scripts_index)
        self.assertIn("审查为什么脚本多、每个脚本是否必要", references_index)

        all_scripts = sorted(scripts_root.rglob("*.py"))
        lib_scripts = sorted((scripts_root / "lib").rglob("*.py"))
        public_count = sum(
            bool(metadata["public_entry"])
            for metadata in registry["entries"].values()
        )
        wrapper_count = sum(
            metadata["domain"] == "compatibility_wrapper"
            for metadata in registry["entries"].values()
        )
        self.assertIn(
            f"当前根层 `.py` 共 {len(root_scripts)} 个，其中公开 CLI "
            f"{public_count} 个、兼容 wrapper {wrapper_count} 个",
            inventory,
        )
        self.assertIn(
            f"当前整个 `scripts/` 树有 {len(all_scripts)} 个 Python 文件；"
            f"其中 {len(lib_scripts)} 个是按领域分层的内部实现",
            inventory,
        )

        for script, metadata in registry["entries"].items():
            with self.subTest(script=script):
                row = inventory_by_script[script]
                self.assertEqual(metadata["category"], markdown_code_value(row[1]))
                self.assertEqual(metadata["domain"], markdown_code_value(row[2]))
                self.assertEqual(
                    len((root / "scripts" / script).read_text(encoding="utf-8").splitlines()),
                    int(row[3]),
                )
                self.assertTrue(row[4])
                self.assertTrue(row[5])
                if metadata["public_entry"]:
                    self.assertIn("保留", row[5])
                    self.assertNotIn("下沉", row[5])
                else:
                    self.assertNotIn("public CLI", row[5])
                if metadata["domain"] == "compatibility_wrapper":
                    self.assertIn("blocker", row[5])
                if metadata["domain"] == "report_html":
                    self.assertIn("展示层", row[5])

        self.assertIn("lib/gates/external_source_evidence_archive.py", scripts_index)

        for path in (root / "scripts/lib").glob("*.py"):
            self.assertNotIn(f"`lib/{path.name}`", inventory)
            self.assertNotIn(f"`scripts/lib/{path.name}`", inventory)

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

        self.assertEqual(
            {"schema_version", "claim_boundary", "categories", "axes", "entries"},
            set(registry),
        )
        self.assertEqual(2, registry["schema_version"])
        allowed_categories = {
            "stable_cli",
            "fetch_cli",
            "gate_backtest_cli",
            "internal_helper",
        }
        self.assertEqual(allowed_categories, set(registry["categories"]))
        expected_axes = {"visibility", "kind", "stability", "domain"}
        self.assertEqual(expected_axes, set(registry["axes"]))
        self.assertIn("script_entrypoints.json", docs)
        self.assertIn("不做运行时 dispatch", docs)
        self.assertIn("visibility", docs)
        self.assertIn("skill_route", docs)

        base_entry_keys = {
            "category",
            "visibility",
            "kind",
            "stability",
            "domain",
            "skill_route",
            "public_entry",
            "network_required",
            "real_gate_boundary",
            "primary_artifacts",
        }
        wrapper_extra_keys = {"migration_target", "deletion_blocker"}
        optional_entry_keys = {"date_resolution", "retry_policy"}
        public_categories = {"stable_cli", "fetch_cli", "gate_backtest_cli"}
        category_axes = {
            "stable_cli": ("public", "cli", "stable", "selection_core", True),
            "fetch_cli": ("public", "cli", "stable_external", "fetch", True),
            "gate_backtest_cli": (
                "public",
                "cli",
                "stable_gate",
                "gate_backtest",
                True,
            ),
            "internal_helper": ("internal", "helper", "internal", None, False),
        }
        for script, metadata in registry["entries"].items():
            with self.subTest(script=script):
                expected_entry_keys = set(base_entry_keys)
                if metadata.get("domain") == "compatibility_wrapper":
                    expected_entry_keys.update(wrapper_extra_keys)
                self.assertEqual(
                    set(),
                    set(metadata) - expected_entry_keys - optional_entry_keys,
                )
                self.assertLessEqual(expected_entry_keys, set(metadata))
                self.assertTrue((root / "scripts" / script).is_file())
                self.assertEqual(script, Path(script).name)
                self.assertIn(metadata["category"], allowed_categories)
                self.assertIn(metadata["visibility"], registry["axes"]["visibility"])
                self.assertIn(metadata["kind"], registry["axes"]["kind"])
                self.assertIn(metadata["stability"], registry["axes"]["stability"])
                self.assertIn(metadata["domain"], registry["axes"]["domain"])
                self.assertIsInstance(metadata["skill_route"], bool)
                self.assertIsInstance(metadata["public_entry"], bool)
                self.assertIsInstance(metadata["network_required"], bool)
                self.assertIsInstance(metadata["primary_artifacts"], list)
                self.assertIsInstance(metadata["real_gate_boundary"], str)
                self.assertTrue(metadata["real_gate_boundary"])
                visibility, kind, stability, domain, skill_route = category_axes[
                    metadata["category"]
                ]
                self.assertEqual(visibility, metadata["visibility"])
                self.assertEqual(kind, metadata["kind"])
                self.assertEqual(stability, metadata["stability"])
                self.assertEqual(skill_route, metadata["skill_route"])
                if metadata["public_entry"]:
                    self.assertIn(metadata["category"], public_categories)
                    self.assertIn(script, scripts_index)
                    self.assertEqual(domain, metadata["domain"])
                else:
                    self.assertEqual("internal_helper", metadata["category"])
                    self.assertFalse(metadata["skill_route"])
                if metadata["domain"] == "compatibility_wrapper":
                    migration_target = root / "scripts" / metadata["migration_target"]
                    self.assertTrue(migration_target.is_file())
                    self.assertTrue(metadata["deletion_blocker"])

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
                "fetch_baostock_a_share_universe.py",
                "fetch_baostock_a_share.py",
                "fetch_akshare_a_share.py",
                "fetch_akshare_hk_daily.py",
                "fetch_pytdx_a_share.py",
                "fetch_zzshare_a_share.py",
                "fetch_yfinance_ohlcv.py",
            },
            by_category["fetch_cli"],
        )
        self.assertNotIn(
            "a_share_selection_html_sections.py", by_category["internal_helper"]
        )
        self.assertNotIn(
            "run_today_a_share_selection_helpers.py", by_category["internal_helper"]
        )
        self.assertTrue(
            registry["entries"]["fetch_zzshare_a_share.py"]["network_required"]
        )
        self.assertFalse(registry["entries"]["score_candidates.py"]["network_required"])
        self.assertIn(
            "prices.parquet",
            registry["entries"]["fetch_baostock_a_share.py"]["primary_artifacts"],
        )
        self.assertNotIn(
            "prices.parquet",
            registry["entries"]["fetch_akshare_a_share.py"]["primary_artifacts"],
        )

    def test_root_internal_helper_surface_does_not_expand(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )
        current_root_internal_helpers = {
            script
            for script, metadata in registry["entries"].items()
            if not metadata["public_entry"]
        }
        domain_counts = {}
        for script in current_root_internal_helpers:
            domain = registry["entries"][script]["domain"]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                root / "scripts/SCRIPTS.md",
                root / "references/script-reference.md",
            ]
        )

        self.assertLessEqual(len(current_root_internal_helpers), 4)
        self.assertEqual(0, domain_counts.get("fetch", 0))
        self.assertEqual(0, domain_counts.get("internal_support", 0))
        self.assertEqual(0, domain_counts.get("report_html", 0))
        self.assertEqual(0, domain_counts.get("runner", 0))
        self.assertEqual(0, domain_counts.get("selection_core", 0))
        self.assertEqual(0, domain_counts.get("walk_forward", 0))
        self.assertEqual(4, domain_counts["compatibility_wrapper"])
        self.assertIn("新的内部 helper 不再新增到 `scripts/` 根层", docs)
        self.assertIn("根层 internal helper 是兼容预算", docs)
        self.assertIn(
            "HTML、runner、walk-forward、zzshare fetch、gates support 和 selection_core helper 已分别下沉",
            docs,
        )
        self.assertIn(
            "`lib/report_html/`、`lib/runner/`、`lib/walk_forward/`、`lib/fetch/`、`lib/gates/` 和 `lib/selection_core/`",
            docs,
        )
        self.assertIn(
            "`lib/selection_core/` 只接收评分、字段、符号、数据解析、披露、诊断和本地校验逻辑",
            docs,
        )
        self.assertIn(
            "runner 编排、HTML 展示、provider 取数、walk-forward artifact 检查和 gate/backtest support 不得放回 selection_core",
            docs,
        )
        self.assertIn("公开 CLI 路径默认冻结", docs)
        self.assertIn("migration_target", docs)
        self.assertIn("deletion_blocker", docs)

    def test_known_large_internal_files_are_documented_as_maintenance_hotspots(
        self,
    ) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        scripts_index = (root / "scripts/SCRIPTS.md").read_text(encoding="utf-8")
        inventory = (root / "references/script-inventory.md").read_text(
            encoding="utf-8"
        )
        docs = scripts_index + "\n" + inventory
        scripts_root = root / "scripts"
        hotspots = sorted(
            path
            for path in scripts_root.rglob("*.py")
            if len(path.read_text(encoding="utf-8").splitlines()) > 800
        )

        for path in hotspots:
            with self.subTest(path=path.name):
                self.assertGreater(
                    len(path.read_text(encoding="utf-8").splitlines()),
                    300,
                )
                relative = path.relative_to(scripts_root).as_posix()
                table_row = f"| `{relative}` |"
                self.assertIn(table_row, scripts_index)
                self.assertIn(table_row, inventory)

        self.assertIn("维护热点", scripts_index)
        self.assertIn("不是当前必须拆分的阻塞项", scripts_index)
        self.assertIn("不移动候选事实、门禁判断或机器字段来源", docs)
        self.assertIn("不改变报告数据模型", docs)
        self.assertIn("不改变候选 CSV/diagnostics 语义", docs)
        self.assertIn("summary/stdout/CSV provenance 字段", docs)
        self.assertIn("步骤顺序", docs)
        self.assertIn("职责豁免", docs)

        complexity_manifest = json.loads(
            (root / "configs/production_complexity_exemptions.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "production_complexity_exemptions_not_permanent_waivers",
            complexity_manifest["claim_boundary"],
        )
        self.assertEqual(
            {path.relative_to(scripts_root).as_posix() for path in hotspots},
            set(complexity_manifest["file_exemptions"]),
        )

        long_functions = []
        for path in scripts_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.end_lineno - node.lineno + 1 > 80:
                    long_functions.append((path, node.name))
        self.assertTrue(long_functions)
        for path, name in long_functions:
            with self.subTest(path=path.name, function=name):
                self.assertIn(f"`{name}()`", docs)

    def test_internal_helpers_do_not_depend_on_public_cli_entries(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )
        public_modules = {
            Path(script).stem
            for script, metadata in registry["entries"].items()
            if metadata["public_entry"]
        }
        allowed_public_cli_imports: set[tuple[str, str]] = set()

        violations = []
        for script, metadata in registry["entries"].items():
            if metadata["public_entry"]:
                continue
            source = (root / "scripts" / script).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=script)
            for node in ast.walk(tree):
                for module in imported_top_level_modules(node):
                    if (
                        module in public_modules
                        and (script, module) not in allowed_public_cli_imports
                    ):
                        violations.append((script, module))

        self.assertEqual([], violations)
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                root / "scripts/SCRIPTS.md",
                root / "references/script-reference.md",
            ]
        )
        self.assertIn("internal helper 默认不得 import public CLI", docs)
        self.assertIn("lib/a_share_selection_validation.py", docs)
        self.assertNotIn("当前唯一例外", docs)
        self.assertNotIn("validate_ohlcv.validate_frame", docs)

    def test_lib_helpers_stay_internal_and_side_effect_free(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )
        public_modules = {
            Path(script).stem
            for script, metadata in registry["entries"].items()
            if metadata["public_entry"]
        }
        lib_dir = root / "scripts/lib"
        lib_files = sorted(
            path for path in lib_dir.rglob("*.py") if path.name != "__init__.py"
        )
        violations = []
        scripts_index = (root / "scripts/SCRIPTS.md").read_text(encoding="utf-8")
        parser_layer = {
            "runner/run_today_a_share_selection_parser.py",
        }
        artifact_layers = {
            "fetch/zzshare_a_share_checkpoint.py",
            "fetch/zzshare_a_share_quality.py",
            "gates/external_source_evidence_archive.py",
            "gates/incremental_history_artifacts.py",
            "gates/incremental_history_execution.py",
            "gates/lightgbm_prediction_summary.py",
            "report_html/a_share_selection_html_report.py",
            "runner/run_today_a_share_selection_helpers.py",
            "runner/run_today_a_share_selection_full_a_provenance.py",
            "runner/run_today_a_share_selection_history.py",
            "runner/run_today_a_share_selection_outputs.py",
            "runner/run_today_a_share_selection_prices_sidecar.py",
            "selection_core/a_share_selection_diagnostics.py",
        }

        self.assertTrue(lib_files)
        for path in lib_files:
            relative_path = path.relative_to(lib_dir).as_posix()
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            imported_modules = set()
            for node in ast.walk(tree):
                imported_modules.update(imported_top_level_modules(node))
                if (
                    isinstance(node, ast.Import)
                    and any(alias.name == "argparse" for alias in node.names)
                    and relative_path not in parser_layer
                ):
                    violations.append((path.name, "argparse"))
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "argparse"
                    and relative_path not in parser_layer
                ):
                    violations.append((path.name, "argparse"))
                if (
                    calls_module_attribute(node, "argparse", "ArgumentParser")
                    and relative_path not in parser_layer
                ):
                    violations.append((path.name, "ArgumentParser"))
                for module, attribute in [
                    ("json", "dump"),
                    ("shutil", "copy"),
                    ("shutil", "copyfile"),
                    ("subprocess", "run"),
                ]:
                    if (
                        calls_module_attribute(node, module, attribute)
                        and relative_path not in artifact_layers
                    ):
                        violations.append((path.name, f"{module}.{attribute}"))
                if (
                    isinstance(node, ast.Attribute)
                    and node.attr
                    in {
                        "to_csv",
                        "to_json",
                        "write_text",
                        "write_bytes",
                        "mkdir",
                        "unlink",
                    }
                    and relative_path not in artifact_layers
                ):
                    violations.append((path.name, node.attr))
            public_imports = imported_modules & public_modules
            for module in sorted(public_imports):
                violations.append((path.name, f"public_import:{module}"))
            if has_main_guard(tree):
                self.assertIn("fail_not_cli", source)

        self.assertEqual([], violations)
        self.assertIn(
            "`lib/` 内部实现分为纯 helper、parser 层和明确产物层", scripts_index
        )
        self.assertIn("纯 helper 不得新增 argparse CLI", scripts_index)
        self.assertIn("不得直接写出 CSV/JSON/HTML 等产物", scripts_index)
        self.assertIn("parser 层只构造 public CLI 的 `ArgumentParser`", scripts_index)
        self.assertIn(
            "明确产物层只在 public CLI 调用下写出 run artifact", scripts_index
        )
        self.assertIn("不得 import 公开 CLI", scripts_index)
        self.assertIn("`skill_route=true` 表示脚本允许被任务拓扑引用", scripts_index)
        public_count = sum(
            bool(metadata["public_entry"])
            for metadata in registry["entries"].values()
        )
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        expected_count_text = f"{public_count} 个 public CLI"
        self.assertIn(f"从 {expected_count_text} 中随机选择", scripts_index)
        self.assertIn(f"{expected_count_text} 都是默认入口", skill)

    def test_script_reference_does_not_advertise_unregistered_fetch_sources(
        self,
    ) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        script_reference = (root / "references/script-reference.md").read_text(
            encoding="utf-8"
        )
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )
        data_sources = json.loads(
            (root / "configs/data_sources.json").read_text(encoding="utf-8")
        )

        self.assertNotIn("tushare", script_reference.lower())
        self.assertNotIn("fetch_tushare", "\n".join(registry["entries"]))
        self.assertNotIn("tushare", "\n".join(data_sources["sources"]))
        self.assertIn("未出现在 `../configs/script_entrypoints.json`", script_reference)

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
                self.assertNotIn(script, registry["entries"])
                self.assertIn(script, scripts_index)
        self.assertNotIn("a_share_selection_html_report.py", registry["entries"])
        self.assertIn("HTML 报告模块已下沉到 `lib/report_html/`", scripts_index)
        self.assertIn("只能继续作为展示层 helper 拆分", scripts_index)
        self.assertIn(
            "不能把候选事实、门禁判断或机器字段来源移动进 HTML 展示层", scripts_index
        )
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

    def test_incremental_docs_define_aggregation_and_baostock_empty_contract(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        workflow = (root / "instructions/full-a-strict-workflow.md").read_text(
            encoding="utf-8"
        )
        script_reference = (root / "references/script-reference.md").read_text(
            encoding="utf-8"
        )
        docs = "\n".join(
            [
                workflow,
                (root / "instructions/runbook.md").read_text(encoding="utf-8"),
                script_reference,
            ]
        )
        self.assertIn("`requested_symbol_count` 表示本轮计划 symbol 数", docs)
        self.assertIn("`symbol_count` 表示实际产生至少一行可合并历史的 symbol 数", docs)
        self.assertIn(
            "false_means_no_unaudited_gaps_audited_no_trading_updates_disclosed_separately",
            docs,
        )
        self.assertIn(
            "--baostock-non-trading-policy drop`、`--baostock-drop-invalid-rows`、`--baostock-allow-non-trading-empty`",
            docs,
        )
        self.assertIn("名称输入与 name policy 是独立契约", docs)
        for name, document in [
            ("full-a-strict-workflow", workflow),
            ("script-reference", script_reference),
        ]:
            with self.subTest(document=name):
                for contract in [
                    "`empty_symbols == no_trading_update_symbols == non_trading_only_empty_symbols`",
                    "false_means_no_unaudited_gaps_audited_no_trading_updates_disclosed_separately",
                    "`provider=baostock`",
                    "`date_max=target_end_date`",
                    "不出现在 delta prices",
                    "merge 保留 base",
                    "普通 empty",
                    "最终 freshness 仍不通过",
                ]:
                    self.assertIn(contract, document)

    def test_clean_pool_parquet_output_is_documented(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        documents = {
            "runbook": root / "instructions/runbook.md",
            "script-reference": root / "references/script-reference.md",
        }

        for name, path in documents.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(document=name):
                for contract in [
                    "`prepare_clean_history_pool.py --output <path>.parquet`",
                    "`.parquet` 或 `.pq`",
                    "`pyarrow` 或 `fastparquet`",
                    "不使用 runner 的 `--prices-filter-output-format`",
                    "默认示例仍写 CSV",
                    "不能解释为严格全链路无 CSV",
                ]:
                    self.assertIn(contract, text)

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
        runbook_text = (root / "instructions/runbook.md").read_text(encoding="utf-8")
        self.assertIn("runbook 验证命令", readme_text)
        self.assertNotIn("python3 -m json.tool", readme_text)
        self.assertNotIn("PYTHONPYCACHEPREFIX", readme_text)
        self.assertIn("validate_skill_changes.py` 的人工展开视图", agents_text)
        self.assertIn("validate_skill_changes.py` 的人工展开视图", runbook_text)
        self.assertIn("无 `uv` 时创建临时虚拟环境", runbook_text)
        self.assertIn(
            "等价替换为 `/tmp/a-share-selection-skill-venv/bin/python`",
            runbook_text,
        )
        self.assertIn(
            "/tmp/a-share-selection-skill-venv/bin/python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py --help",
            runbook_text,
        )
        self.assertNotIn("/Users/", validator)
        self.assertIn("Path.home()", validator)
        self.assertIn("historical leaked-key probe split", validator)
        self.assertIn('ROOT / ".github"', validator)
        self.assertIn("Local validation gates:", result.stdout)
        self.assertIn("full unittest suite", result.stdout)
        self.assertIn("Skill frontmatter contract", result.stdout)
        self.assertIn("YAML agent manifest parse", result.stdout)
        self.assertIn("text whitespace and conflict marker scan", result.stdout)
        self.assertIn("task tracking contract", result.stdout)
        self.assertIn("production complexity contract", result.stdout)
        self.assertIn("External gates not run", result.stdout)
        self.assertIn('glob("*.yaml")', validator)
        self.assertIn("no YAML agent manifest files found", validator)
        self.assertIn('--with", "pyyaml', validator)
        for text in [
            "'display_name', 'short_description', 'default_prompt'",
            "raise RuntimeError(f'{manifest}: expected mapping root')",
            "raise RuntimeError(f'{manifest}: missing interface mapping')",
            "raise RuntimeError(f'{manifest}: missing interface.{key}')",
        ]:
            self.assertIn(text, validator)
        self.assertNotIn("assert isinstance(data, dict)", validator)
        self.assertNotIn("assert isinstance(interface, dict)", validator)
        for text in [
            'glob("*.yaml")',
            '"display_name", "short_description", "default_prompt"',
            "missing interface mapping",
            "missing interface.",
        ]:
            with self.subTest(validation_doc=text):
                self.assertIn(text, agents_text)
                self.assertIn(text, runbook_text)
        self.assertIn(
            "SKILL-SYSTEM-CLOSEOUT-2026-07-04.md",
            (root / "references/index.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "python3 validate_skill_changes.py --skip-skill-validate --skip-tests",
            workflow,
        )
        self.assertIn(
            "Repository-owned Skill frontmatter contract still runs",
            workflow,
        )
        for document in [readme_text, agents_text, runbook_text]:
            with self.subTest(frontmatter_document=document[:32]):
                self.assertIn(
                    "仓库自有的 `SKILL.md` frontmatter 合同",
                    document,
                )
                self.assertIn(
                    "`--skip-skill-validate` 只跳过本机 `quick_validate.py`",
                    document,
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

    def test_task_tracking_file_is_the_single_machine_checked_source(self) -> None:
        tasks_path = ROOT / "tasks.csv"
        with tasks_path.open(encoding="utf-8", newline="") as handle:
            tasks = list(csv.DictReader(handle))
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        validator = (ROOT / "validate_skill_changes.py").read_text(encoding="utf-8")

        self.assertTrue(tasks)
        self.assertEqual(
            ["ID", "标题", "内容", "验收标准", "审查要求", "状态", "标签"],
            list(tasks[0]),
        )
        self.assertLessEqual(sum(row["状态"] == "进行中" for row in tasks), 1)
        self.assertIn("`tasks.csv` 是本仓库唯一任务驱动源", agents)
        self.assertIn('TASKS_FILE = ROOT / "tasks.csv"', validator)
        self.assertIn("check_task_tracking", validator)

    def test_ci_direct_dependency_constraints_are_exact_and_documented(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        requirements = "\n".join(
            [
                (root / "requirements.txt").read_text(encoding="utf-8"),
                (root / "requirements-parquet.txt").read_text(encoding="utf-8"),
            ]
        )
        constraints = (root / "constraints-ci.txt").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [ROOT / "README.md", ROOT / "AGENTS.md"]
        )

        expected = {"pandas", "numpy", "pyarrow", "pyyaml"}
        pinned = {}
        for line in constraints.splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            name, separator, version = text.partition("==")
            self.assertEqual("==", separator)
            self.assertTrue(name)
            self.assertTrue(version)
            pinned[name.lower()] = version

        self.assertEqual(expected, set(pinned))
        self.assertIn("pandas>=", requirements)
        self.assertIn("numpy>=", requirements)
        self.assertIn("pyarrow>=", requirements)
        self.assertIn("pyyaml>=", requirements)
        self.assertIn("-c skills/a-share-selection-strategy/constraints-ci.txt", workflow)
        self.assertIn("constraints-ci.txt", workflow)
        self.assertIn("CI 直接依赖约束", docs)
        self.assertIn("--dependency-profile ci", docs)
        self.assertIn("--dependency-profile", (ROOT / "validate_skill_changes.py").read_text(encoding="utf-8"))
        self.assertIn("--with-requirements", (ROOT / "validate_skill_changes.py").read_text(encoding="utf-8"))
        self.assertNotIn("uv run", workflow.split("Run test shard", 1)[1])

    def test_validation_timeouts_are_bounded_and_documented(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        validator = (ROOT / "validate_skill_changes.py").read_text(encoding="utf-8")
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                ROOT / "README.md",
                ROOT / "AGENTS.md",
                root / "instructions/runbook.md",
            ]
        )

        self.assertIn("timeout-minutes: 15", workflow)
        self.assertIn("DEFAULT_COMMAND_TIMEOUT_SECONDS = 900.0", validator)
        self.assertIn("--command-timeout-seconds", validator)
        self.assertIn("validation command timed out", validator)
        self.assertIn("默认超时 900 秒", docs)
        self.assertIn("模块可用性探针使用 `min(N, 10)` 秒", docs)
        self.assertIn("`SIGTERM` 后 `SIGKILL`", docs)
        self.assertIn("即使主进程先退出", docs)
        self.assertIn("总超时为 15 分钟", docs)
        self.assertIn("不是性能 SLA", docs)

    def test_skill_docs_define_agent_execution_and_recovery_protocol(self) -> None:
        skill = (ROOT / "skills/a-share-selection-strategy/SKILL.md").read_text(
            encoding="utf-8"
        )
        index = (
            ROOT / "skills/a-share-selection-strategy/references/index.md"
        ).read_text(encoding="utf-8")
        templates = (
            ROOT / "skills/a-share-selection-strategy/templates/output-templates.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills/a-share-selection-strategy/instructions/full-a-strict-workflow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## Agent 执行协议", skill)
        self.assertIn("## Agent 控制合同", skill)
        self.assertIn("## 路径到入口的映射", skill)
        self.assertIn("## 每条路径的必看 artifact", skill)
        self.assertIn("首轮只读能决定下一步的最小文档", skill)
        self.assertIn("字段、配置、依赖看", skill)
        self.assertIn("复制完整命令或验证门禁看", skill)
        self.assertIn(
            "完整命令看 [instructions/runbook.md](instructions/runbook.md)", skill
        )
        self.assertNotIn("reference/runbook", skill)
        self.assertNotIn(
            "| 本地评分 / 定向真实任务 / 今日低价超短 | [scripts/SCRIPTS.md](scripts/SCRIPTS.md)、[references/script-reference.md](references/script-reference.md)、[instructions/runbook.md](instructions/runbook.md) |",
            skill,
        )
        route_table = markdown_table_rows_after_heading(skill, "## 路径到入口的映射")
        self.assertGreaterEqual(len(route_table), 3)
        self.assertEqual(["路径", "首轮读取", "按需追加"], route_table[0])
        for row in route_table:
            with self.subTest(row=row):
                self.assertEqual(3, len(row))
        self.assertIn("## Agent 快速检查表", index)
        self.assertIn("## 恢复动作快速路由", templates)
        self.assertIn("全 A 严格任务汇报骨架", templates)
        self.assertIn("candidate_field_coverage", skill)
        self.assertIn("selection_failed_reason", templates)
        self.assertIn("## 失败恢复路由", workflow)
        self.assertIn("prepare_history_retry_symbols.py", workflow)
        self.assertIn("retry_plan_only_not_full_market_completion", workflow)
        self.assertIn("不要只给页面链接或只报最终候选数", workflow)
        self.assertIn(
            "metadata.json`，若缺失则回退读取 `history_metadata.json`", workflow
        )
        self.assertNotIn(
            'cp "$RUN/clean/history_metadata.json" "$RUN/clean/metadata.json"', workflow
        )

    def test_runner_code_exposes_machine_execution_path_for_skill_routes(self) -> None:
        skill = (ROOT / "skills/a-share-selection-strategy/SKILL.md").read_text(
            encoding="utf-8"
        )
        runner = (
            ROOT
            / "skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py"
        ).read_text(encoding="utf-8")
        summary = (
            ROOT
            / "skills/a-share-selection-strategy/scripts/lib/runner/run_today_a_share_selection_summary.py"
        ).read_text(encoding="utf-8")
        provenance = (
            ROOT
            / "skills/a-share-selection-strategy/scripts/lib/runner/run_today_a_share_selection_provenance.py"
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
        self.assertIn('"execution_path"', summary)
        self.assertIn('"coverage_class"', summary)
        self.assertIn('"full_market_claim_boundary"', summary)
        self.assertIn('"execution_path"', provenance)
        self.assertIn('"coverage_class"', provenance)
        self.assertIn('"full_market_claim_boundary"', provenance)

    def test_full_a_clean_pool_provenance_contract_is_documented(self) -> None:
        root = ROOT / "skills/a-share-selection-strategy"
        workflow = (root / "instructions/full-a-strict-workflow.md").read_text(
            encoding="utf-8"
        )
        runbook = (root / "instructions/runbook.md").read_text(encoding="utf-8")
        script_reference = (root / "references/script-reference.md").read_text(
            encoding="utf-8"
        )
        index = (root / "references/index.md").read_text(encoding="utf-8")
        scripts = (root / "scripts/SCRIPTS.md").read_text(encoding="utf-8")
        registry = json.loads(
            (root / "configs/script_entrypoints.json").read_text(encoding="utf-8")
        )

        for document in [workflow, runbook, script_reference]:
            self.assertIn("--universe-input", document)
            self.assertIn("--universe-metadata", document)
            self.assertIn("--provenance-output", document)
            self.assertIn("--full-a-provenance", document)
            self.assertIn("full_market_closure_eligible", document)
            self.assertIn("diagnostics", document)
        self.assertIn("不能替代 runner 的 `full_market_claim_allowed`", index)
        self.assertIn("不能单独提升 runner 的 `full_market_claim_allowed`", scripts)
        self.assertIn(
            "lib/runner/run_today_a_share_selection_full_a_provenance.py",
            scripts,
        )
        self.assertIn("clean_pool_removed_symbols_not_full_market", workflow)
        self.assertIn("4,000", workflow)
        self.assertIn("universe_breadth_below_full_a_minimum", workflow)
        self.assertIn("history_symbols_before_as_of_date_not_full_market", workflow)
        self.assertIn("全行", workflow)
        self.assertIn("history.as_of_date", workflow)
        self.assertIn("full_a_provenance_output_cleanup_errors", workflow)
        self.assertIn("full_a_provenance_as_of_date", index)
        self.assertIn("不能传 Eastmoney", workflow)
        self.assertIn("不能使用 Eastmoney spot metadata", script_reference)
        self.assertIn("逐原因对账", script_reference)
        self.assertIn(
            "full_a_clean_pool_provenance.json",
            registry["entries"]["prepare_clean_history_pool.py"]["primary_artifacts"],
        )


if __name__ == "__main__":
    unittest.main()
