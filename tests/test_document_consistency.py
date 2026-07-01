from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentConsistencyTests(unittest.TestCase):
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
            / "skills/a-share-selection-strategy/references/output-templates.md"
        ).read_text(encoding="utf-8")

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
            ROOT / "skills/a-share-selection-strategy/references/runbook.md"
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
            ROOT / "skills/a-share-selection-strategy/references/runbook.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills/a-share-selection-strategy/references/full-a-strict-workflow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## 任务拓扑", skill)
        self.assertIn("全 A 严格任务", skill)
        self.assertIn("full-a-strict-workflow.md", skill)
        self.assertIn("跑全 A / 全市场真实任务", index)
        self.assertIn("如果任务目标是“全 A / 全市场 / 扩大股票池 / 真实广度扫描”", runbook)
        self.assertIn("## 当前推荐拓扑", workflow)
        self.assertIn("eastmoney", workflow)
        self.assertIn("zzshare", workflow)
        self.assertIn("query_stock_basic", workflow)
        self.assertIn("全市场 5000+ 标的会显著增加远端请求数", workflow)

    def test_skill_docs_define_agent_execution_and_recovery_protocol(self) -> None:
        skill = (
            ROOT / "skills/a-share-selection-strategy/SKILL.md"
        ).read_text(encoding="utf-8")
        index = (
            ROOT / "skills/a-share-selection-strategy/references/index.md"
        ).read_text(encoding="utf-8")
        templates = (
            ROOT
            / "skills/a-share-selection-strategy/references/output-templates.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "skills/a-share-selection-strategy/references/full-a-strict-workflow.md"
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
        self.assertIn("history_fetch_explicit_symbols", runner)
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
