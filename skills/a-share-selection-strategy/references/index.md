# 文档地图

本目录按用途分层：先读入口文档，再按任务进入专题文档或历史复验报告。历史复验报告只记录当时证据，不代表当前代码一定仍处于同一状态；当前事实以代码、测试和最新提交为准。

## 文档分层

| 层级 | 文件 | 面向读者 | 作用 |
| --- | --- | --- | --- |
| 入口 | [../../../README.md](../../../README.md) | 人类和 Agent | 项目概览、5 分钟 demo、数据契约和文档导航 |
| 约束 | [../../../AGENTS.md](../../../AGENTS.md) | Agent | 仓库硬约束、禁止伪造、验证基线 |
| Skill | [../SKILL.md](../SKILL.md) | Agent | 触发场景、决策树、脚本路由 |
| 手册 | [runbook.md](runbook.md) | 实操者和 Agent | 完整 demo、联网取数、P1/P2/P3 门禁命令 |
| 工作流 | [full-a-strict-workflow.md](full-a-strict-workflow.md) | Agent | 全 A / 全市场真实任务的主路径、批次策略和失败恢复 |
| 专题 | [factor-framework.md](factor-framework.md)、[prediction-derived-profile.md](prediction-derived-profile.md) | 实现者和审查者 | 因子公式、预测列口径、评分边界 |
| 汇报 | [output-templates.md](output-templates.md) | Agent 和 reviewer | 按机器字段选择可复制汇报模板 |
| 证据 | `reviews/*.md` | reviewer | 历史真实复验、失败边界和不能外推项 |

## 快速入口

| 目标 | 先读 | 继续读 |
| --- | --- | --- |
| 跑本地 demo、今日入口、验证命令 | [项目 README](../../../README.md) | [runbook.md](runbook.md) |
| 让 AI Agent 正确调用本 Skill | [SKILL.md](../SKILL.md) | [prediction-derived-profile.md](prediction-derived-profile.md) |
| 跑全 A / 全市场真实任务 | [SKILL.md](../SKILL.md) | [full-a-strict-workflow.md](full-a-strict-workflow.md) |
| 了解评分因子和输出字段 | [factor-framework.md](factor-framework.md) | [prediction-derived-profile.md](prediction-derived-profile.md) |
| 解释 stdout、summary、manifest、失败门禁 | [output-templates.md](output-templates.md) | [runbook.md](runbook.md) |
| 查真实场景证据和边界 | [reviews/REAL-SCENARIO-GATES-2026-05-30.md](reviews/REAL-SCENARIO-GATES-2026-05-30.md) | 各 `reviews/P1-*` 和 `reviews/P2A-*` 报告 |

## Agent 读取顺序

1. [../../../AGENTS.md](../../../AGENTS.md)：仓库硬约束、禁止伪造、验证命令。
2. [../SKILL.md](../SKILL.md)：任务路由、输入契约、CLI 入口、汇报边界。
3. 若任务是全 A / 全市场 / 扩大股票池，先读 [full-a-strict-workflow.md](full-a-strict-workflow.md)。
4. [output-templates.md](output-templates.md)：按机器字段选择汇报模板和恢复动作。
5. 需要复制命令或跑真实门禁时，读 [runbook.md](runbook.md)。
6. 需要真实场景证据时，再读 `reviews/` 中的对应报告。

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
| [reviews/REAL-SCENARIO-GATES-2026-05-30.md](reviews/REAL-SCENARIO-GATES-2026-05-30.md) | 真实场景总门禁和边界总览 |
| [reviews/CURRENT-GATES-CLOSEOUT-2026-06-08.md](reviews/CURRENT-GATES-CLOSEOUT-2026-06-08.md) | 2026-06-08 当前 P1/P2/P3 门禁推进闭环 |
| [reviews/P1-PORTFOLIO-CAPACITY-2026-06-08.md](reviews/P1-PORTFOLIO-CAPACITY-2026-06-08.md) | 2026-06-08 独立 40-symbol 组合容量复验 |
| [reviews/P2A-BAOSTOCK-LIMIT-FIELDS-2026-05-30.md](reviews/P2A-BAOSTOCK-LIMIT-FIELDS-2026-05-30.md) | baostock 涨跌停字段探针证据 |
| [reviews/P1-PORTFOLIO-CAPACITY-SZ-MAINBOARD-2026-06-01.md](reviews/P1-PORTFOLIO-CAPACITY-SZ-MAINBOARD-2026-06-01.md) | 深市主板组合容量复验 |
| [reviews/P1-PORTFOLIO-CAPACITY-SSE603-LATEWINDOW-2026-06-01.md](reviews/P1-PORTFOLIO-CAPACITY-SSE603-LATEWINDOW-2026-06-01.md) | 沪市 603 late-window 复验 |
| [reviews/P1-PORTFOLIO-CAPACITY-SSE601-MONTHENDS-2026-06-01.md](reviews/P1-PORTFOLIO-CAPACITY-SSE601-MONTHENDS-2026-06-01.md) | 沪市 601 month-end 复验 |
| [reviews/P1-PORTFOLIO-CAPACITY-CYB-2026-06-01.md](reviews/P1-PORTFOLIO-CAPACITY-CYB-2026-06-01.md) | 创业板组合容量复验 |
| [reviews/P1-PORTFOLIO-CAPACITY-STAR-MARKET-2026-06-01.md](reviews/P1-PORTFOLIO-CAPACITY-STAR-MARKET-2026-06-01.md) | 科创板组合容量复验 |
