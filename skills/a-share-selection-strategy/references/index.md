# 文档地图

本索引按用途分层：先读入口文档，再按任务进入 `instructions/`、`templates/`、`references/` 或 `evidence/`。历史复验报告只记录当时证据，不代表当前代码一定仍处于同一状态；当前事实以代码、测试和最新提交为准。

## 文档分层

| 层级 | 文件 | 面向读者 | 作用 |
| --- | --- | --- | --- |
| 入口 | [../../../README.md](../../../README.md) | 人类和 Agent | 项目概览、5 分钟 demo、数据契约和文档导航 |
| 约束 | 仓库根 AGENTS.md | Agent | 仓库硬约束、禁止伪造、验证基线 |
| Skill | [../SKILL.md](../SKILL.md) | Agent | 触发场景、任务拓扑、控制合同和硬边界 |
| 脚本分层 | [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md) | Agent 和实操者 | 稳定 CLI、取数入口、门禁回测入口和 helper 边界 |
| 脚本参考 | [script-reference.md](script-reference.md) | Agent 和实操者 | 配置文件、依赖、字段映射、输入契约和命令细节 |
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
| 查配置、依赖或字段映射 | [script-reference.md](script-reference.md) | 只在需要复制完整命令时读 [../instructions/runbook.md](../instructions/runbook.md) |
| 解释 stdout、summary、manifest、失败门禁 | [../templates/output-templates.md](../templates/output-templates.md) | 命中低频场景时读对应 `../templates/output-templates-*.md` |
| 查真实场景证据和边界 | [../evidence/reviews/REAL-SCENARIO-GATES-2026-05-30.md](../evidence/reviews/REAL-SCENARIO-GATES-2026-05-30.md) | 各 `../evidence/reviews/P1-*` 和 `../evidence/reviews/P2A-*` 报告 |

## Agent 读取顺序

1. 仓库根 AGENTS.md：仓库硬约束、禁止伪造、验证命令。
2. [../SKILL.md](../SKILL.md)：唯一的 Agent 任务路由入口。
3. 若任务是全 A / 全市场 / 扩大股票池，先读 [../instructions/full-a-strict-workflow.md](../instructions/full-a-strict-workflow.md)。
4. 需要确认 CLI 入口或 helper 边界时，读 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md)；需要依赖、输入契约或字段映射时，再读 [script-reference.md](script-reference.md)。
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
| `prediction_input_source` | 今日 runner 是否消费外部 prediction 输入 | `not_used` 不能写成 prediction-derived 结果 |
| `prediction_model_executed_by_runner` | 今日 runner 是否执行预测模型 | `false` 不能写成 runner 训练或执行模型 |
| `prediction_model_executed_by_score_script` | `score_candidates.py` 是否执行预测模型 | `false` 只能说明评分消费已有预测列 |
| `prediction_source=external_unverified` | 预测列来源未由评分脚本验证 | 不能证明训练窗口、无泄漏或模型质量 |

`lightgbm_*` 字段仍会出现在旧产物、历史证据和兼容输出中。新报告优先引用上表的中性字段；引用旧字段时必须说明它是兼容字段或历史原始输出。

## 历史报告

| 文件 | 用途 |
| --- | --- |
| [../evidence/reviews/REAL-SCENARIO-GATES-2026-05-30.md](../evidence/reviews/REAL-SCENARIO-GATES-2026-05-30.md) | 真实场景总门禁和边界总览 |
| [../evidence/reviews/CURRENT-GATES-CLOSEOUT-2026-06-08.md](../evidence/reviews/CURRENT-GATES-CLOSEOUT-2026-06-08.md) | 2026-06-08 当前 P1/P2/P3 门禁推进闭环 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-2026-06-08.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-2026-06-08.md) | 2026-06-08 独立 40-symbol 组合容量复验 |
| [../evidence/reviews/P2A-BAOSTOCK-LIMIT-FIELDS-2026-05-30.md](../evidence/reviews/P2A-BAOSTOCK-LIMIT-FIELDS-2026-05-30.md) | baostock 涨跌停字段探针证据 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-SZ-MAINBOARD-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-SZ-MAINBOARD-2026-06-01.md) | 深市主板组合容量复验 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-SSE603-LATEWINDOW-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-SSE603-LATEWINDOW-2026-06-01.md) | 沪市 603 late-window 复验 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-SSE601-MONTHENDS-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-SSE601-MONTHENDS-2026-06-01.md) | 沪市 601 month-end 复验 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-CYB-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-CYB-2026-06-01.md) | 创业板组合容量复验 |
| [../evidence/reviews/P1-PORTFOLIO-CAPACITY-STAR-MARKET-2026-06-01.md](../evidence/reviews/P1-PORTFOLIO-CAPACITY-STAR-MARKET-2026-06-01.md) | 科创板组合容量复验 |
