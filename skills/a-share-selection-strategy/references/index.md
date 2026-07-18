# 文档地图

本索引按用途分层：先读入口文档，再按任务进入 `instructions/`、`templates/`、`references/` 或 `evidence/`。历史复验报告只记录当时证据，不代表当前代码一定仍处于同一状态；当前事实以代码、测试和最新提交为准。

## 文档分层

| 层级 | 文件 | 面向读者 | 作用 |
| --- | --- | --- | --- |
| 入口 | [../../../README.md](../../../README.md) | 人类和 Agent | 项目概览、5 分钟 demo、数据契约和文档导航 |
| 约束 | 仓库根 AGENTS.md | Agent | 仓库硬约束、禁止伪造、验证基线 |
| Skill | [../SKILL.md](../SKILL.md) | Agent | 触发场景、任务拓扑、控制合同和硬边界 |
| 脚本分层 | [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md) | Agent 和实操者 | 稳定 CLI、取数入口、门禁回测入口和 helper 边界 |
| 脚本审计 | [script-inventory.md](script-inventory.md) | reviewer 和维护者 | 逐个脚本的用途、必要性判断、保留或迁移方向 |
| 脚本参考 | [script-reference.md](script-reference.md) | Agent 和实操者 | 配置文件、依赖、数据源能力边界、字段映射、输入契约和命令细节 |
| 机器配置 | `../configs/data_sources.json`、`../configs/source_routing.json`、`../configs/script_entrypoints.json` | Agent 和测试 | 数据源能力、业务场景源路由和脚本入口注册表；入口注册表 v2 拆分 `visibility/kind/stability/domain/skill_route`，只用于审计和一致性检查，不做运行时自动选源、自动 fallback 或脚本 dispatch |
| 手册 | [../instructions/runbook.md](../instructions/runbook.md) | 实操者和 Agent | 完整 demo、联网取数、P1/P2/P3 门禁命令 |
| 工作流 | [../instructions/full-a-strict-workflow.md](../instructions/full-a-strict-workflow.md) | Agent | 全 A / 全市场真实任务的主路径、批次策略和失败恢复 |
| 专题 | [factor-framework.md](factor-framework.md)、[prediction-derived-profile.md](prediction-derived-profile.md) | 实现者和审查者 | 因子公式、预测列口径、评分边界 |
| 汇报 | [../templates/output-templates.md](../templates/output-templates.md) 和 `../templates/output-templates-*.md` | Agent 和 reviewer | 先按机器字段路由，再按需读取长模板 |
| 证据 | `../evidence/reviews/*.md` | reviewer | 历史真实复验、失败边界和不能外推项 |

## 快速入口

| 目标 | 先读 | 继续读 |
| --- | --- | --- |
| 跑本地 demo、今日入口、验证命令 | [项目 README](../../../README.md) | [../instructions/runbook.md](../instructions/runbook.md) 的场景快速路由 |
| 让 AI Agent 正确调用本 Skill | [SKILL.md](../SKILL.md) | 只在需要脚本边界时读 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md) |
| 跑全 A / 全市场真实任务 | [SKILL.md](../SKILL.md) | [../instructions/full-a-strict-workflow.md](../instructions/full-a-strict-workflow.md) |
| 了解评分因子和输出字段 | [factor-framework.md](factor-framework.md) | [prediction-derived-profile.md](prediction-derived-profile.md) |
| 查 CLI 入口或 helper 边界 | [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md) | 需要配置、依赖或字段映射时读 [script-reference.md](script-reference.md) |
| 审查为什么脚本多、每个脚本是否必要 | [script-inventory.md](script-inventory.md) | 迁移前再对照 `../configs/script_entrypoints.json` |
| 判断数据源免费边界、字段范围和全 A 适用性 | [script-reference.md](script-reference.md) 的“数据源能力边界” | 全 A 主路径再读 [../instructions/full-a-strict-workflow.md](../instructions/full-a-strict-workflow.md) 的“数据源能力矩阵” |
| 机器校验数据源能力或业务场景路由是否漂移 | `../configs/data_sources.json`、`../configs/source_routing.json` | 再对照 [script-reference.md](script-reference.md) 和 [../instructions/full-a-strict-workflow.md](../instructions/full-a-strict-workflow.md) |
| 机器校验脚本入口分类是否漂移 | `../configs/script_entrypoints.json` | 再对照 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md) |
| 查配置、依赖或字段映射 | [script-reference.md](script-reference.md) | 只在需要复制完整命令时读 [../instructions/runbook.md](../instructions/runbook.md) |
| 解释 stdout、summary、manifest、失败门禁 | [../templates/output-templates.md](../templates/output-templates.md) | 命中低频场景时读对应 `../templates/output-templates-*.md` |
| 查当前真实门禁状态和边界 | [../evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md](../evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md) | 再按其中链接读取最新 dated evidence；历史报告不得直接覆盖当前状态 |

## Agent 读取顺序

1. 仓库根 AGENTS.md：仓库硬约束、禁止伪造、验证命令。
2. [../SKILL.md](../SKILL.md)：唯一的 Agent 任务路由入口。
3. 若任务是全 A / 全市场 / 扩大股票池，先读 [../instructions/full-a-strict-workflow.md](../instructions/full-a-strict-workflow.md)。
4. 需要确认 CLI 入口或 helper 边界时，读 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md)；需要依赖、数据源能力边界、输入契约或字段映射时，再读 [script-reference.md](script-reference.md)；只有审查脚本数量、逐个脚本必要性或迁移顺序时，才读 [script-inventory.md](script-inventory.md)。
5. [../templates/output-templates.md](../templates/output-templates.md)：按机器字段选择汇报模板和恢复动作；优先使用场景直跳表，只在路由命中时读取同级 `../templates/output-templates-*.md`。
6. 需要复制完整命令或跑真实门禁时，先看 [../instructions/runbook.md](../instructions/runbook.md) 的场景快速路由，再读对应章节。
7. 只有需要真实场景证据、历史复验口径或审计追溯时，才读 `../evidence/reviews/` 中的对应报告；历史报告不得覆盖当前代码、测试和本轮 artifact。

`../evals/evals.json` 是 Skill 触发和行为覆盖 manifest，不在真实选股任务的启动读取路径中。只有新增或重构 Skill 触发语义时才读取它，并按 `eval_files` 只打开相关场景分片：`generic.json`、`prediction.json`、`fetch.json` 或 `gates.json`。

## Agent 快速检查表

开始执行前，先回答这 5 个问题：

1. 这是本地评分、定向真实任务、全 A 严格任务，还是 prediction-derived？
2. 本轮主入口脚本是哪一个？
3. 本轮最先要看的 artifact 是什么？
4. 哪个字段一旦失败，就必须先恢复而不是继续汇报？
5. 本轮结果绝不能被写成什么？

如果这 5 个问题答不出来，不要急着跑命令。

## 汇报优先级

| 冲突来源 | 优先级 |
| --- | --- |
| 当前代码、当前测试、当前运行产物 | 最高 |
| `AGENTS.md` 的硬约束 | 高 |
| `SKILL.md` 和本目录专题文档 | 高 |
| 历史 review 报告 | 证据用途；不得覆盖当前代码事实 |
| 模板占位文本 | 仅供组织语言；不得当作事实 |

## 当前优先机器字段

| 字段 | 含义 | 报告边界 |
| --- | --- | --- |
| `execution_path` | 今日 runner 实际走过的任务路径 | 只说明本次执行事实，不等于任务目标已经满足 |
| `coverage_class` | 本轮覆盖等级，如本地输入、小样本、显式扩池 | `spot_derived_sample` 不能写成全 A 或扩大股票池 |
| `full_market_claim_allowed` | runner 是否允许自动宣称全市场闭环 | `false` 时必须按边界缩短结论 |
| `full_market_claim_boundary` | 不能外推为全市场闭环的具体原因 | 必须和候选数一起汇报 |
| `full_market_closure_eligible` | clean-pool provenance 对 universe/history/clean artifact 的预检查结果 | 要求至少 4,000 个 symbol、完整 baostock metadata 合同且清洗前后无排除；仍不能替代 runner 的 `full_market_claim_allowed` |
| `full_a_provenance_validation_status` | runner 对显式 clean-pool provenance 的两阶段验证状态 | 只有 `valid` 且最终过滤零剔除、diagnostics 全覆盖时才可能允许 breadth 声明 |
| `full_a_provenance_as_of_date` | universe snapshot、history metadata 与 history 实际最大交易日共同确认的新鲜度日期 | 必须与最终 runner 的 `--min-symbol-latest-date` 相同；不能把请求日当成未观测到的交易日 |
| `history.symbols_before_as_of_date_count` | history 中实际 `date_max` 未达到共同 as-of 的 symbol 数 | 正数时 `full_market_closure_eligible=false`，不得把全局最大日解释为逐标都已更新 |
| `full_a_provenance_output_cleanup_errors` | 评分后 provenance 对账失败时未能删除的候选或诊断路径 | 非空必须披露，残余文件不得作为本轮成功产物 |
| `prediction_input_source` | 今日 runner 是否消费外部 prediction 输入 | `not_used` 不能写成 prediction-derived 结果 |
| `prediction_model_executed_by_runner` | 今日 runner 是否执行预测模型 | `false` 不能写成 runner 训练或执行模型 |
| `prediction_model_executed_by_score_script` | `score_candidates.py` 是否执行预测模型 | `false` 只能说明评分消费已有预测列 |
| `prediction_source=external_unverified` | 预测列来源未由评分脚本验证 | 不能证明训练窗口、无泄漏或模型质量 |

`lightgbm_*` 字段仍会出现在旧产物、历史证据和兼容输出中。新报告优先引用上表的中性字段；引用旧字段时必须说明它是兼容字段或历史原始输出。

## 历史报告

| 文件 | 用途 |
| --- | --- |
| [../evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md](../evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md) | 当前真实门禁唯一人工入口，汇总最新证据、有限范围状态和仍未证明项 |
| [../evidence/reviews/ARCHIVE-TIMEOUT-REVIEW-2026-07-18.md](../evidence/reviews/ARCHIVE-TIMEOUT-REVIEW-2026-07-18.md) | 2026-07-18 外部源探针紧凑归档与验证器超时清理的 Claude、OMP 和 Codex 审查、独立复现及修复边界 |
| [../evidence/reviews/PYTDX-DEFAULT-ENDPOINT-2026-07-17.md](../evidence/reviews/PYTDX-DEFAULT-ENDPOINT-2026-07-17.md) | 2026-07-17 Pytdx 默认 endpoint 调整、三次新默认真实复验、两 symbol 复验、第三方依赖警告和不外推边界 |
| [../evidence/reviews/EXTERNAL-SOURCE-STABILITY-2026-07-17.md](../evidence/reviews/EXTERNAL-SOURCE-STABILITY-2026-07-17.md) | 2026-07-17 七个外部 source 的三次短窗口探测、Eastmoney/Pytdx 失败关闭、Akshare provider observation 和 Pytdx 显式 host 诊断 |
| [../evidence/reviews/CLAUDE-OMP-REMAINING-OPTIMIZATION-REVIEW-2026-07-15.md](../evidence/reviews/CLAUDE-OMP-REMAINING-OPTIMIZATION-REVIEW-2026-07-15.md) | 2026-07-15 Claude、OMP 和 Codex 对剩余 Skill 优化项的只读复核、分歧裁定及远端 frontmatter 门禁建议 |
| [../evidence/reviews/CLAUDE-OMP-SYSTEM-REVIEW-2026-07-15.md](../evidence/reviews/CLAUDE-OMP-SYSTEM-REVIEW-2026-07-15.md) | 2026-07-15 Claude、OMP 和 Codex 对当前 Skill 体系及 `09efee4..2a7c321` 的复核、分歧裁定和待修文档合同 |
| [../evidence/reviews/SKILL-OPTIMIZATION-CLOSEOUT-2026-07-15.md](../evidence/reviews/SKILL-OPTIMIZATION-CLOSEOUT-2026-07-15.md) | 2026-07-15 Skill 优化提交边界、双依赖 profile 完整回归、CI 分片合同和远端 pending 边界 |
| [../evidence/reviews/CLAUDE-OMP-UNCOMMITTED-REVIEW-2026-07-15.md](../evidence/reviews/CLAUDE-OMP-UNCOMMITTED-REVIEW-2026-07-15.md) | 2026-07-15 Claude、OMP 和 Codex 对未提交变更的只读终审、交叉验证和剩余边界 |
| [../evidence/reviews/FULL-A-INCREMENTAL-BAOSTOCK-2026-07-15.md](../evidence/reviews/FULL-A-INCREMENTAL-BAOSTOCK-2026-07-15.md) | 2026-07-15 Baostock 全 A 增量分桶实测、短历史清洗、最终评分和 claim boundary |
| [../evidence/reviews/FULL-A-PROVENANCE-RUN-2026-07-14.md](../evidence/reviews/FULL-A-PROVENANCE-RUN-2026-07-14.md) | 2026-07-14 schema v2 provenance、真实 5,202 标的最终 runner、性能与 claim=false 边界 |
| [../evidence/reviews/FULL-A-WORKFLOW-BOTTLENECK-2026-07-09.md](../evidence/reviews/FULL-A-WORKFLOW-BOTTLENECK-2026-07-09.md) | 2026-07-09 全 A 实跑耗时、瓶颈、clean pool 和不可外推边界 |
| [../evidence/reviews/FULL-A-WORKFLOW-BOTTLENECK-2026-07-12.md](../evidence/reviews/FULL-A-WORKFLOW-BOTTLENECK-2026-07-12.md) | 2026-07-12 全 A 实跑最新耗时、短历史恢复、评分瓶颈和字段边界 |
| [../evidence/reviews/SKILL-SYSTEM-CLOSEOUT-2026-07-04.md](../evidence/reviews/SKILL-SYSTEM-CLOSEOUT-2026-07-04.md) | 2026-07-04 Skill 体系优化收尾、本地门禁和外部门禁边界 |
| [../evidence/reviews/REAL-SCENARIO-GATES-2026-05-30.md](../evidence/reviews/REAL-SCENARIO-GATES-2026-05-30.md) | 真实场景总门禁和边界总览 |
| [../evidence/reviews/CURRENT-GATES-CLOSEOUT-2026-06-08.md](../evidence/reviews/CURRENT-GATES-CLOSEOUT-2026-06-08.md) | 2026-06-08 当前 P1/P2/P3 门禁推进闭环 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-2026-06-08.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-2026-06-08.md) | 2026-06-08 独立 40-symbol 组合容量复验 |
| [../evidence/reviews/P2A-BAOSTOCK-LIMIT-FIELDS-2026-05-30.md](../evidence/reviews/P2A-BAOSTOCK-LIMIT-FIELDS-2026-05-30.md) | baostock 涨跌停字段探针证据 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-SZ-MAINBOARD-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-SZ-MAINBOARD-2026-06-01.md) | 深市主板组合容量复验 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-SSE603-LATEWINDOW-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-SSE603-LATEWINDOW-2026-06-01.md) | 沪市 603 late-window 复验 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-SSE601-MONTHENDS-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-SSE601-MONTHENDS-2026-06-01.md) | 沪市 601 month-end 复验 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-CYB-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-CYB-2026-06-01.md) | 创业板组合容量复验 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-STAR-MARKET-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-STAR-MARKET-2026-06-01.md) | 科创板组合容量复验 |
