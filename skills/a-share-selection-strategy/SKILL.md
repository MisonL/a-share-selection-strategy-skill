---
name: a-share-selection-strategy
description: 提供可复现、可审查的股票选股流程。用于今日 A 股、全 A 扫描、扩大股票池、低价超短、prediction-derived、多因子评分、候选解释和策略审查；已落地港股/美股数据集可按同一契约审查。缺少本地行情或明确联网授权时，不得输出候选名单、模拟行情、预测或收益；所有输出均非投资建议、非交易指令。
---

# A-Share Selection Strategy

本 Skill 面向 AI Agent，把 A 股优先的股票选股任务拆成可解释、可验证、可复用的流程。默认工作流覆盖今日 A 股、全 A 严格扫描、低价超短和 prediction-derived 门禁；港股、美股等已落地数据集只能按同一契约审查。

核心原则：先定义数据契约，再校验、评分、过滤、排序和解释。任何结论都必须能追溯到输入数据、配置、脚本输出、JSON/CSV artifact 或真实门禁记录；不得伪造行情、候选股、LightGBM prediction、回测收益或联网结果。

## 启动顺序

先读本文件完成任务路径判断；再按命中场景读取一个 reference。不要把历史报告整篇塞进上下文。

| 场景 | 继续读取 |
| --- | --- |
| 汇报失败、0 候选、partial result、最终候选或机器字段解释 | [references/output-templates.md](references/output-templates.md) |
| 全 A、全市场、扩大股票池或真实广度扫描 | [references/full-a-strict-workflow.md](references/full-a-strict-workflow.md) |
| 脚本入口和 helper 边界 | [scripts/SCRIPTS.md](scripts/SCRIPTS.md) |
| 依赖、配置、字段映射和输入契约 | [references/script-index.md](references/script-index.md) |
| 可复制 demo、今日命令、联网取数、P1/P2/P3 门禁 | [references/runbook.md](references/runbook.md) |
| prediction-derived 公式、质量边界和回测口径 | [references/prediction-derived-profile.md](references/prediction-derived-profile.md) |
| 专题文档、历史复验证据或文档地图 | [references/index.md](references/index.md) |

## 任务拓扑

先选任务路径，再选评分 `mode`。任务路径回答“怎么取数和收口”，`mode=generic/prediction/auto` 只回答“最终评分按通用技术评分还是外部 prediction-derived 评分”。

| 路径 | 触发场景 | 首选动作 | 首轮必看 artifact | 不能误判 |
| --- | --- | --- | --- | --- |
| 无数据源 | 没有本地行情，也没有明确联网授权 | 用 [references/output-templates.md](references/output-templates.md) 的“无法直接选股”模板 | 无 | 不能输出候选名单、示例代码或模拟理由 |
| 本地评分 | 已有 `prices.csv` / `prices.parquet` | `run_today_a_share_selection.py --prices-input ...` 或先 `validate_ohlcv.py` | `summary.json`、`candidates.csv`、`diagnostics.csv` | 不能写成真实全市场扫描 |
| 定向真实任务 | 明确 symbol、板块或少量标的 | `run_today_a_share_selection.py --history-source ... --symbols ...` | `run_manifest.json`、`history_metadata.json`、`summary.json` | 不能外推全 A |
| 全 A 严格任务 | 全 A、全市场、扩大股票池、真实广度扫描 | 先读 [references/full-a-strict-workflow.md](references/full-a-strict-workflow.md) | `spot_metadata.json`、`selected_symbols.json`、`history_metadata.json`、`summary.json` | 不要把 `mode=auto` 当成全 A 工作流规划 |
| prediction-derived | 用户坚持原 prediction 口径，或输入已有预测列 | `validate_ohlcv.py --config scripts/prediction_profile_config.json` 后评分 | `prediction_summary.json`、prediction 字段、`prediction_candidates.csv` | 不要用 generic 结果替代 |

## Agent 执行协议

1. 判断任务路径：无数据源、本地评分、定向真实任务、全 A 严格任务、prediction-derived。
2. 判断数据条件：本地价格文件、spot 快照、历史源、prediction 列、联网授权是否存在。
3. 只选择一个主入口和一条主路径，不要一开始混用多个入口。
4. 先读该路径的首轮 artifact，再决定是否继续下一轮或汇报。
5. 先读取 `summary.json` 或 stdout 中的 `execution_path`、`coverage_class`、`candidate_field_coverage`、`full_market_claim_allowed`、`full_market_claim_boundary`、`selection_failed_reason`、`selection_failed_next_action`。
6. 出现 strict gate failed、partial result、provider error、provenance 缺口、`output_written=false` 或 `full_market_claim_allowed=false` 时，先恢复或缩短结论，再汇报。

默认不要先做这些事：

- 不要先生成 HTML 再判断本轮是否成功。
- 不要先看候选股数量再判断数据链是否闭环。
- 不要把 demo、小样本、固定池命令当成全市场路径。
- 不要把 `mode=auto` 当成“工作流自动规划”。
- 不要把历史 review 报告当成当前推荐命令。

## Agent 控制合同

每次执行前先把任务收敛成 5 个控制项；执行后用机器字段回填，不靠印象判断。

| 控制项 | Agent 必须确定 | 可观测字段或产物 | 停止条件 |
| --- | --- | --- | --- |
| 任务目标 | 本地评分、定向真实任务、全 A 严格任务、prediction-derived 之一 | `execution_path`、`coverage_class`、`candidate_field_coverage` | 无法归类时先澄清，不盲跑 |
| 数据输入 | 本地文件、spot 快照、历史源、prediction 列是否存在 | `input_metadata`、`source_scope`、`source_provenance` | 来源不明时不能声称真实行情或全市场 |
| 执行动作 | 只选一个主入口和一条主路径 | `run_manifest.json.steps[]` | 多入口混跑且无统一 manifest 时不下结论 |
| 质量门禁 | validate、history、score、partial、empty、failed symbols | `summary.json`、`history_metadata.json`、`diagnostics.csv` | strict gate failed、partial 或 `output_written=false` 时先恢复 |
| 汇报边界 | 本轮能否按用户目标汇报 | `full_market_claim_allowed`、`full_market_claim_boundary`、`selection_failed_reason`、`selection_failed_next_action` | `false` 或非空失败原因时必须缩短结论并说明边界 |

高效执行的标准不是“尽快出 HTML”，而是每轮都能回答：这次跑了哪条路径、覆盖到哪里、哪些字段阻止外推、下一步该恢复还是汇报。

## 路径到入口的映射

入口映射只在需要复制命令、确认依赖、字段映射或 helper 边界时展开。先用 [scripts/SCRIPTS.md](scripts/SCRIPTS.md) 区分稳定 CLI、取数入口、门禁回测入口和内部 helper；需要配置、依赖、字段映射或完整命令时再读 [references/script-index.md](references/script-index.md) 和 [references/runbook.md](references/runbook.md)。

| 路径 | 命令来源 |
| --- | --- |
| 本地评分 / 定向真实任务 / 今日低价超短 | [scripts/SCRIPTS.md](scripts/SCRIPTS.md)、[references/script-index.md](references/script-index.md)、[references/runbook.md](references/runbook.md) |
| 全 A 严格任务 | [references/full-a-strict-workflow.md](references/full-a-strict-workflow.md) |
| prediction-derived 公式和质量口径 | [references/prediction-derived-profile.md](references/prediction-derived-profile.md) |
| helper 或内部模块边界 | [scripts/SCRIPTS.md](scripts/SCRIPTS.md) |

## 每条路径的必看 artifact

向用户下结论前，至少确认：退出码、`summary.json`、关键 metadata、候选/诊断文件是否由本轮写出。只要 `summary_output_written`、`manifest_output_written`、`source_provenance`、`selection_failed_reason` 或 `selection_failed_next_action` 仍不清楚，就不要提前给“已完成”“已经跑通”“结果可信”这类结论。

## 稳定执行面

本 Skill 的稳定执行面是 CLI 和已落地文件，不是 Python package API。

必须保留的入口规则：

- 优先处理用户提供的本地 CSV/Parquet；只有明确联网授权时才取数。
- 联网结果必须先落地为本地行情文件和 metadata，再校验、评分、解释。
- `validate_ohlcv.py`、`score_candidates.py`、`run_today_a_share_selection.py` 是常规主入口；全 A 严格任务还必须先读 [references/full-a-strict-workflow.md](references/full-a-strict-workflow.md)。
- `scripts/` 下的 `__main__` 保护不等于用户 CLI 合约；`a_share_selection_*.py`、`run_today_a_share_selection_*.py`、`walk_forward_*.py` 和 `lightgbm_prediction_summary.py` 多数是 helper 或内部模块，不是用户 CLI 入口；详见 [scripts/SCRIPTS.md](scripts/SCRIPTS.md)。
- `--spot-input` 可合并已落地实时快照展示字段；`spot_industry` 等 spot 展示字段只用于候选、诊断和 HTML 展示，不参与核心评分；匹配数量以 `summary.json.spot_matched_symbols` 为准。
- 当前 CLI 链路支持 CSV/Parquet 输入，但中间产物默认写 CSV；严格全链路无 CSV 不能通过事后转换伪装满足。
- 依赖缺失、联网失败、provider partial、strict gate failed 都必须显式报告；不得用 mock、跳过依赖或旧文件冒充成功。

## 关键边界

- 最小行情字段、日期格式、前导零、成交量单位、prediction-derived 必需列和数据源字段映射见 [references/script-index.md](references/script-index.md)。
- `mode=auto` 只选择评分口径，不规划全 A 工作流；generic 技术评分不消费 `prediction` 或 `prediction_score`。
- `score_candidates.py` 只消费预测列，不训练 LightGBM，也不会用技术因子伪造机器学习预测。
- `prediction_source=external_unverified`、`prediction_model_executed_by_runner=false` 或 `prediction_model_executed_by_score_script=false` 不能证明上游模型真实、无泄漏或已执行。
- `effective_empty_result=true` 是成功空结果，不证明策略有效；`output_written=false` 是输入失败或严格门禁失败，不能写成成功 0 候选。
- `report.html` 只是展示层；事实仍以 JSON/CSV、退出码和门禁字段为准。
- 候选、sizing、回测或资金曲线必须写明非投资建议、非交易指令、非真实成交、非收益证明。

## 审查与验证边界

- 目标、市场、周期、股票池和评分 `mode` 必须能回到输入字段、配置和 artifact。
- 因子公式、权重、硬过滤、排序和候选解释要与配置一致；通用公式细节见 [references/factor-framework.md](references/factor-framework.md)。
- 未来数据、缺失值、前导零损坏、重复日期、不同市场量纲混用、停牌和涨跌停约束缺口，都必须显式披露或失败。
- mock、demo、小样本、固定池、partial result、fallback 或外部未验证 prediction，都不能写成真实全市场闭环。
- 能运行时至少验证输入校验、评分排序、过滤原因、输出字段和失败路径；有历史数据时再验证时间切分、样本外、成本滑点、组合资金曲线和不可交易状态。
- 不能运行真实验证时，明确说明“未验证真实行情结果”，不要用理论推导冒充已通过。

## 维护本 Skill

修改本仓库代码或 Skill 时，按仓库根 AGENTS.md 跑 JSON/YAML、py_compile、unittest、quick_validate，并校验 `agents/openai.yaml`。`evals/evals.json` 是触发和行为覆盖资产，不在真实选股任务启动路径中；新增或重构 Skill 触发语义时才读取。
