from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

from validate_skill_changes import production_complexity_excesses


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/a-share-selection-strategy"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
DEFAULT_ENTRY_SCRIPTS = {
    "validate_ohlcv.py",
    "score_candidates.py",
    "run_today_a_share_selection.py",
}
PARSER_LAYERS = {"runner/run_today_a_share_selection_parser.py"}
ARTIFACT_LAYERS = {
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


def load_registry() -> dict:
    return json.loads(
        (SKILL_ROOT / "configs/script_entrypoints.json").read_text(encoding="utf-8")
    )


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


def markdown_link_targets(text: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)#][^)]+)\)", text)


def markdown_code_value(value: str) -> str:
    return value.strip().strip("`")


def markdown_code_bullets_after_heading(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index(heading)
    values = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        match = re.fullmatch(r"- `([^`]+)`", line.strip())
        if match:
            values.append(match.group(1))
    return values


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


class SkillEntrypointContractTests(unittest.TestCase):
    def test_task_topology_routes_exactly_to_default_public_entries(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        registry = load_registry()
        task_topology = markdown_table_rows_after_heading(skill, "## 任务拓扑")
        action_index = task_topology[0].index("首选动作")

        routed_scripts: set[str] = set()
        for row in task_topology[2:]:
            routed_scripts.update(python_script_mentions(row[action_index]))
        default_entries = {
            script
            for script, metadata in registry["entries"].items()
            if metadata["default_entry"]
        }

        self.assertEqual(DEFAULT_ENTRY_SCRIPTS, routed_scripts)
        self.assertEqual(DEFAULT_ENTRY_SCRIPTS, default_entries)
        for script in default_entries:
            with self.subTest(default_entry=script):
                metadata = registry["entries"][script]
                self.assertTrue(metadata["public_entry"])
                self.assertTrue(metadata["skill_route"])
                self.assertEqual("stable_cli", metadata["category"])
                self.assertFalse(metadata["network_required"])
        self.assertIn(
            "任务拓扑中的首选动作只能引用 `default_entry=true` 的公开 CLI",
            skill,
        )

    def test_local_and_targeted_route_uses_no_first_read_document(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        route_table = markdown_table_rows_after_heading(skill, "## 路径到入口的映射")

        for row in route_table[2:]:
            with self.subTest(route=row[0]):
                self.assertLessEqual(len(markdown_link_targets(row[1])), 1)
        local_route = next(
            row
            for row in route_table[2:]
            if row[0] == "本地评分 / 定向真实任务 / 今日低价超短"
        )
        self.assertEqual([], markdown_link_targets(local_route[1]))
        self.assertIn("不追加文档", local_route[1])
        self.assertIn("scripts/SCRIPTS.md", local_route[2])

    def test_registry_covers_root_scripts_and_documents_its_boundary(self) -> None:
        scripts_doc = (SCRIPTS_ROOT / "SCRIPTS.md").read_text(encoding="utf-8")
        registry = load_registry()

        self.assertEqual(
            sorted(path.name for path in SCRIPTS_ROOT.glob("*.py")),
            sorted(registry["entries"]),
        )
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
        self.assertIn("default_entry", scripts_doc)

    def test_inventory_covers_every_root_script_without_promoting_lib_files(self) -> None:
        inventory = (SKILL_ROOT / "references/script-inventory.md").read_text(
            encoding="utf-8"
        )
        scripts_index = (SCRIPTS_ROOT / "SCRIPTS.md").read_text(encoding="utf-8")
        references_index = (SKILL_ROOT / "references/index.md").read_text(
            encoding="utf-8"
        )
        registry = load_registry()
        rows = markdown_table_rows_after_heading(inventory, "## 脚本用途和必要性")
        self.assertEqual(
            ["脚本", "分类", "领域", "行数", "用途", "必要性判断"],
            rows[0],
        )
        body = rows[2:]
        inventory_by_script = {markdown_code_value(row[0]): row for row in body}

        self.assertEqual(set(registry["entries"]), set(inventory_by_script))
        self.assertEqual(len(registry["entries"]), len(body))
        for text in [
            "不是运行时入口",
            "不替代 `../configs/script_entrypoints.json`",
            "不进入 Skill 首轮读取路径",
            "新 helper 默认进入 `lib/`",
        ]:
            self.assertIn(text, inventory)
        self.assertIn("逐个脚本的用途、必要性和迁移判断", scripts_index)
        self.assertIn("不是常规任务启动路径", scripts_index)
        self.assertIn("lib/gates/external_source_evidence_archive.py", scripts_index)
        self.assertIn("审查为什么脚本多、每个脚本是否必要", references_index)

        root_scripts = sorted(SCRIPTS_ROOT.glob("*.py"))
        all_scripts = sorted(SCRIPTS_ROOT.rglob("*.py"))
        lib_scripts = sorted((SCRIPTS_ROOT / "lib").rglob("*.py"))
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
                    len((SCRIPTS_ROOT / script).read_text(encoding="utf-8").splitlines()),
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
        for path in (SCRIPTS_ROOT / "lib").glob("*.py"):
            self.assertNotIn(f"| `lib/{path.name}` |", inventory)

    def test_registry_schema_keeps_default_entry_separate_from_path_routing(self) -> None:
        registry = load_registry()
        scripts_index = (SCRIPTS_ROOT / "SCRIPTS.md").read_text(encoding="utf-8")
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                ROOT / "README.md",
                SKILL_ROOT / "SKILL.md",
                SKILL_ROOT / "references/index.md",
                SKILL_ROOT / "references/script-reference.md",
                SCRIPTS_ROOT / "SCRIPTS.md",
            ]
        )
        self.assertEqual(
            {"schema_version", "claim_boundary", "categories", "axes", "entries"},
            set(registry),
        )
        self.assertEqual(3, registry["schema_version"])
        self.assertEqual(
            {"visibility", "kind", "stability", "domain", "default_entry"},
            set(registry["axes"]),
        )
        self.assertEqual({"true", "false"}, set(registry["axes"]["default_entry"]))
        for text in ["script_entrypoints.json", "不做运行时 dispatch", "skill_route", "default_entry"]:
            self.assertIn(text, docs)

        allowed_categories = {
            "stable_cli",
            "fetch_cli",
            "gate_backtest_cli",
            "internal_helper",
        }
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
            "default_entry",
        }
        category_axes = {
            "stable_cli": ("public", "cli", "stable", "selection_core", True),
            "fetch_cli": ("public", "cli", "stable_external", "fetch", True),
            "gate_backtest_cli": ("public", "cli", "stable_gate", "gate_backtest", True),
            "internal_helper": ("internal", "helper", "internal", None, False),
        }
        wrapper_extra_keys = {"migration_target", "deletion_blocker"}
        optional_entry_keys = {"date_resolution", "retry_policy"}
        public_categories = {"stable_cli", "fetch_cli", "gate_backtest_cli"}
        for script, metadata in registry["entries"].items():
            with self.subTest(script=script):
                expected_keys = set(base_entry_keys)
                if metadata["domain"] == "compatibility_wrapper":
                    expected_keys.update(wrapper_extra_keys)
                self.assertEqual(set(), set(metadata) - expected_keys - optional_entry_keys)
                self.assertLessEqual(expected_keys, set(metadata))
                self.assertTrue((SCRIPTS_ROOT / script).is_file())
                self.assertEqual(script, Path(script).name)
                self.assertIn(metadata["category"], allowed_categories)
                for axis in ["visibility", "kind", "stability", "domain"]:
                    self.assertIn(metadata[axis], registry["axes"][axis])
                self.assertIsInstance(metadata["skill_route"], bool)
                self.assertIsInstance(metadata["default_entry"], bool)
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
                    self.assertFalse(metadata["default_entry"])
                if metadata["default_entry"]:
                    self.assertTrue(metadata["public_entry"])
                    self.assertTrue(metadata["skill_route"])
                    self.assertEqual("stable_cli", metadata["category"])
                if metadata["domain"] == "compatibility_wrapper":
                    self.assertTrue((SCRIPTS_ROOT / metadata["migration_target"]).is_file())
                    self.assertTrue(metadata["deletion_blocker"])

    def test_registry_keeps_expected_public_surface(self) -> None:
        registry = load_registry()
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
        self.assertNotIn("a_share_selection_html_sections.py", by_category["internal_helper"])
        self.assertNotIn(
            "run_today_a_share_selection_helpers.py", by_category["internal_helper"]
        )
        self.assertTrue(registry["entries"]["fetch_zzshare_a_share.py"]["network_required"])
        self.assertFalse(registry["entries"]["score_candidates.py"]["network_required"])
        self.assertIn(
            "prices.parquet",
            registry["entries"]["fetch_baostock_a_share.py"]["primary_artifacts"],
        )
        self.assertNotIn(
            "prices.parquet",
            registry["entries"]["fetch_akshare_a_share.py"]["primary_artifacts"],
        )

    def test_gate_backtest_table_and_classification_rule_match_registry(self) -> None:
        registry = load_registry()
        scripts_index = (SCRIPTS_ROOT / "SCRIPTS.md").read_text(encoding="utf-8")
        gate_backtest_scripts = {
            script
            for script, metadata in registry["entries"].items()
            if metadata["category"] == "gate_backtest_cli"
        }
        gate_backtest_rows = markdown_table_rows_after_heading(
            scripts_index, "## 门禁和回测入口"
        )
        documented_scripts = {
            markdown_code_value(row[0]) for row in gate_backtest_rows[2:]
        }

        self.assertEqual(gate_backtest_scripts, documented_scripts)
        self.assertIn(
            "看到“门禁和回测入口”表中的任一 public CLI，先按门禁和回测入口处理",
            scripts_index,
        )

    def test_root_internal_helper_surface_does_not_expand(self) -> None:
        scripts_index = (SCRIPTS_ROOT / "SCRIPTS.md").read_text(encoding="utf-8")
        inventory = (SKILL_ROOT / "references/script-inventory.md").read_text(
            encoding="utf-8"
        )
        script_reference = (SKILL_ROOT / "references/script-reference.md").read_text(
            encoding="utf-8"
        )
        registry = load_registry()
        root_helpers = {
            script
            for script, metadata in registry["entries"].items()
            if not metadata["public_entry"]
        }
        domain_counts: dict[str, int] = {}
        for script in root_helpers:
            domain = registry["entries"][script]["domain"]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        self.assertLessEqual(len(root_helpers), 4)
        for domain in [
            "fetch",
            "internal_support",
            "report_html",
            "runner",
            "selection_core",
            "walk_forward",
        ]:
            self.assertEqual(0, domain_counts.get(domain, 0))
        self.assertEqual(4, domain_counts["compatibility_wrapper"])
        self.assertEqual(
            sorted(root_helpers),
            sorted(markdown_code_bullets_after_heading(scripts_index, "## 内部 helper")),
        )
        self.assertIn("`lib/a_share_selection_run_state.py`", scripts_index)
        self.assertIn("不在 `scripts/` 根层", scripts_index)
        self.assertFalse((SCRIPTS_ROOT / "a_share_selection_run_state.py").exists())
        docs = "\n".join([scripts_index, script_reference, inventory])
        for text in [
            "新的 internal helper 不再新增到 `scripts/` 根层",
            "根层 internal helper 是兼容预算",
            "HTML 展示层、runner、walk-forward、zzshare fetch、gates support 和 selection_core helper 已分别下沉",
            "`scripts/lib/report_html/`、`scripts/lib/runner/`、`scripts/lib/walk_forward/`、`scripts/lib/fetch/`、`scripts/lib/gates/` 和 `scripts/lib/selection_core/`",
            "`lib/selection_core/` 只接收评分、字段、符号、数据解析、披露、诊断和本地校验逻辑",
            "runner 编排、HTML 展示、provider 取数、walk-forward artifact 检查和 gate/backtest support 不得放回 selection_core",
            "migration_target",
            "deletion_blocker",
        ]:
            self.assertIn(text, docs)
        self.assertIn("公开 CLI 保留", inventory)

    def test_large_internal_files_and_function_exemptions_stay_in_inventory(self) -> None:
        scripts_index = (SCRIPTS_ROOT / "SCRIPTS.md").read_text(encoding="utf-8")
        inventory = (SKILL_ROOT / "references/script-inventory.md").read_text(
            encoding="utf-8"
        )
        manifest = json.loads(
            (SKILL_ROOT / "configs/production_complexity_exemptions.json").read_text(
                encoding="utf-8"
            )
        )
        thresholds = manifest["thresholds"]
        self.assertEqual(
            {"file_lines": 800, "function_non_empty_lines": 80},
            thresholds,
        )
        hotspots, long_functions = production_complexity_excesses(
            file_line_threshold=thresholds["file_lines"],
            function_line_threshold=thresholds["function_non_empty_lines"],
        )
        self.assertNotIn("## 维护热点", scripts_index)
        for relative in sorted(hotspots):
            with self.subTest(path=relative):
                self.assertIn(f"| `{relative}` |", inventory)
        for text in [
            "维护热点",
            "不是当前必须拆分的阻塞项",
            "不移动候选事实、门禁判断或机器字段来源",
            "不改变报告数据模型",
            "不改变候选 CSV/diagnostics 语义",
            "summary/stdout/CSV provenance 字段",
            "步骤顺序",
            "职责豁免",
        ]:
            self.assertIn(text, inventory)
        self.assertEqual(
            "production_complexity_exemptions_not_permanent_waivers",
            manifest["claim_boundary"],
        )
        self.assertEqual(
            hotspots,
            set(manifest["file_exemptions"]),
        )
        self.assertTrue(long_functions)
        self.assertEqual(set(manifest["function_exemptions"]), long_functions)
        for identifier in sorted(long_functions):
            _, name = identifier.rsplit("::", 1)
            with self.subTest(function=identifier):
                self.assertIn(f"`{name}()`", inventory)

    def test_internal_helpers_do_not_depend_on_public_cli_entries(self) -> None:
        registry = load_registry()
        public_modules = {
            Path(script).stem
            for script, metadata in registry["entries"].items()
            if metadata["public_entry"]
        }
        violations = []
        for script, metadata in registry["entries"].items():
            if metadata["public_entry"]:
                continue
            source = (SCRIPTS_ROOT / script).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=script)
            for node in ast.walk(tree):
                for module in imported_top_level_modules(node):
                    if module in public_modules:
                        violations.append((script, module))
        self.assertEqual([], violations)
        docs = "\n".join(
            [
                (SKILL_ROOT / "references/script-inventory.md").read_text(
                    encoding="utf-8"
                ),
                (SKILL_ROOT / "references/script-reference.md").read_text(
                    encoding="utf-8"
                ),
            ]
        )
        self.assertIn("internal helper 默认不得 import public CLI", docs)
        self.assertIn("lib/a_share_selection_validation.py", docs)
        self.assertNotIn("当前唯一例外", docs)
        self.assertNotIn("validate_ohlcv.validate_frame", docs)

    def test_today_runner_reuses_internal_retry_plan_contract(self) -> None:
        runner = SCRIPTS_ROOT / "run_today_a_share_selection.py"
        retry_cli = SCRIPTS_ROOT / "prepare_history_retry_symbols.py"
        retry_helper = SCRIPTS_ROOT / "lib/runner/run_today_a_share_selection_retry_plan.py"
        runner_tree = ast.parse(runner.read_text(encoding="utf-8"), filename=str(runner))
        retry_cli_tree = ast.parse(
            retry_cli.read_text(encoding="utf-8"), filename=str(retry_cli)
        )
        runner_from_imports = {
            node.module
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        retry_cli_imports = {
            node.module
            for node in ast.walk(retry_cli_tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertTrue(retry_helper.is_file())
        self.assertIn("lib.runner.run_today_a_share_selection_retry_plan", runner_from_imports)
        self.assertNotIn(
            "prepare_history_retry_symbols",
            {
                module
                for node in ast.walk(runner_tree)
                for module in imported_top_level_modules(node)
            },
        )
        self.assertIn("lib.runner.run_today_a_share_selection_retry_plan", retry_cli_imports)

    def test_lib_helpers_keep_parser_and_artifact_side_effects_explicit(self) -> None:
        registry = load_registry()
        public_modules = {
            Path(script).stem
            for script, metadata in registry["entries"].items()
            if metadata["public_entry"]
        }
        lib_dir = SCRIPTS_ROOT / "lib"
        lib_files = sorted(
            path for path in lib_dir.rglob("*.py") if path.name != "__init__.py"
        )
        violations = []
        for path in lib_files:
            relative_path = path.relative_to(lib_dir).as_posix()
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            imported_modules = set()
            for node in ast.walk(tree):
                imported_modules.update(imported_top_level_modules(node))
                if isinstance(node, ast.Import) and any(
                    alias.name == "argparse" for alias in node.names
                ) and relative_path not in PARSER_LAYERS:
                    violations.append((path.name, "argparse"))
                if isinstance(node, ast.ImportFrom) and node.module == "argparse" and (
                    relative_path not in PARSER_LAYERS
                ):
                    violations.append((path.name, "argparse"))
                if calls_module_attribute(node, "argparse", "ArgumentParser") and (
                    relative_path not in PARSER_LAYERS
                ):
                    violations.append((path.name, "ArgumentParser"))
                for module, attribute in [
                    ("json", "dump"),
                    ("shutil", "copy"),
                    ("shutil", "copyfile"),
                    ("subprocess", "run"),
                ]:
                    if calls_module_attribute(node, module, attribute) and (
                        relative_path not in ARTIFACT_LAYERS
                    ):
                        violations.append((path.name, f"{module}.{attribute}"))
                if isinstance(node, ast.Attribute) and node.attr in {
                    "to_csv",
                    "to_json",
                    "write_text",
                    "write_bytes",
                    "mkdir",
                    "unlink",
                } and relative_path not in ARTIFACT_LAYERS:
                    violations.append((path.name, node.attr))
            for module in sorted(imported_modules & public_modules):
                violations.append((path.name, f"public_import:{module}"))
            if has_main_guard(tree):
                self.assertIn("fail_not_cli", source)
        self.assertEqual([], violations)

        inventory = (SKILL_ROOT / "references/script-inventory.md").read_text(
            encoding="utf-8"
        )
        scripts_index = (SCRIPTS_ROOT / "SCRIPTS.md").read_text(encoding="utf-8")
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for text in [
            "`lib/` 内部实现分为纯 helper、parser 层和明确产物层",
            "纯 helper 不得新增 argparse CLI",
            "不得直接写出 CSV/JSON/HTML 等产物",
            "parser 层只构造 public CLI 的 `ArgumentParser`",
            "明确产物层只在 public CLI 调用下写出 run artifact",
            "不得 import 公开 CLI",
        ]:
            self.assertIn(text, inventory)
        public_count = sum(
            bool(metadata["public_entry"])
            for metadata in registry["entries"].values()
        )
        self.assertIn(
            "`skill_route=true` 表示 public CLI 可在路径命中后引用", scripts_index
        )
        self.assertIn(f"从 {public_count} 个 public CLI 中随机选择", scripts_index)
        self.assertIn("`default_entry=true` 只标记", skill)
        self.assertNotIn(f"{public_count} 个 public CLI 都是默认入口", skill)

    def test_html_display_layer_details_are_not_in_the_first_read_script_page(self) -> None:
        scripts_index = (SCRIPTS_ROOT / "SCRIPTS.md").read_text(encoding="utf-8")
        inventory = (SKILL_ROOT / "references/script-inventory.md").read_text(
            encoding="utf-8"
        )
        registry = load_registry()
        for script in [
            "a_share_selection_html_sections.py",
            "a_share_selection_html_scripts.py",
            "a_share_selection_html_candidate_master.py",
        ]:
            with self.subTest(script=script):
                self.assertNotIn(script, registry["entries"])
                self.assertIn(script, inventory)
                self.assertNotIn(script, scripts_index)
        self.assertNotIn("a_share_selection_html_report.py", registry["entries"])
        self.assertIn("HTML 报告模块已下沉到 `lib/report_html/`", inventory)
        self.assertIn("只能继续作为展示层 helper 拆分", inventory)
        self.assertIn(
            "不能把候选事实、门禁判断或机器字段来源移动进 HTML 展示层",
            inventory,
        )
        self.assertIn("`report.html` 输出契约不变", inventory)
        self.assertIn("[../references/script-inventory.md]", scripts_index)
