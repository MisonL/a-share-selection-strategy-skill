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
| 汇报失败、0 候选、partial result、最终候选或机器字段解释 | [templates/output-templates.md](templates/output-templates.md) |
| 全 A、全市场、扩大股票池或真实广度扫描 | [instructions/full-a-strict-workflow.md](instructions/full-a-strict-workflow.md) |
| 脚本入口和 helper 边界 | [scripts/SCRIPTS.md](scripts/SCRIPTS.md) |
| 依赖、配置、数据源能力、字段映射和输入契约 | [references/script-reference.md](references/script-reference.md) |
| 可复制 demo、今日命令、联网取数、P1/P2/P3 门禁 | [instructions/runbook.md](instructions/runbook.md) |
| prediction-derived 公式、质量边界和回测口径 | [references/prediction-derived-profile.md](references/prediction-derived-profile.md) |
| 专题文档、历史复验证据或文档地图 | [references/index.md](references/index.md) |

## 任务拓扑

先选任务路径，再选评分 `mode`。任务路径回答“怎么取数和收口”，`mode=generic/prediction/auto` 只回答“最终评分按通用技术评分还是外部 prediction-derived 评分”。

用户只说“选 A 股”“今日 A 股选股”“真实选股”且没有给出明确 symbol、板块、本地股票池或本地行情文件时，默认按全 A 严格任务判断。这里的全 A 是沪深 A 股股票池（前缀过滤，不含北交所），固定 symbol、小样本或 demo 只能用于 smoke test、回归测试或用户明确限定的定向任务。

| 路径 | 触发场景 | 首选动作 | 首轮必看 artifact | 不能误判 |
| --- | --- | --- | --- | --- |
| 无数据源 | 没有本地行情，也没有明确联网授权 | 用 [templates/output-templates.md](templates/output-templates.md) 的“无法直接选股”模板 | 无 | 不能输出候选名单、示例股票代码或模拟理由 |
| 本地评分 | 已有 `prices.csv` / `prices.parquet` | 只评分时用 `validate_ohlcv.py` 后接 `score_candidates.py`；需要 manifest、summary 或 HTML 时用 `run_today_a_share_selection.py --prices-input ...` | `summary.json` 或 `score_candidates.py` stdout、`candidates.csv`、`diagnostics.csv` | 不能写成真实全市场扫描 |
| 定向真实任务 | 明确 symbol、板块或少量标的 | `run_today_a_share_selection.py --history-source ... --symbols ...`；列表较长时用 `--symbols-file ...` | `run_manifest.json`、`history_metadata.json`、`summary.json` | 不能外推全 A |
| 全 A 严格任务 | 全 A、全市场、扩大股票池、真实广度扫描；当前口径为沪深 A 股股票池（前缀过滤，不含北交所） | 先读 [instructions/full-a-strict-workflow.md](instructions/full-a-strict-workflow.md) | `spot_metadata.json`、`selected_symbols.json`、`history_metadata.json`、`summary.json` | 不要把 `mode=auto` 当成全 A 工作流规划 |
| prediction-derived | 用户坚持原 prediction 口径，或输入已有预测列 | `validate_ohlcv.py --config configs/prediction_profile_config.json` 后评分 | 外部输入先看 prediction 字段和 disclosure；本仓库生成预测时再看 `prediction_summary.json`；最终看 `prediction_candidates.csv` | 不要用 generic 结果替代 |

任务拓扑中的首选动作只能引用 `default_entry=true` 的公开 CLI。其他 `skill_route=true` public CLI 只在明确的路径、provider 或 artifact 门禁命中后选择。

## Agent 执行协议

1. 判断任务路径：无数据源、本地评分、定向真实任务、全 A 严格任务、prediction-derived。
2. 判断数据条件：本地价格文件、spot 快照、历史源、prediction 列、联网授权是否存在。
3. 只选择一个主入口和一条主路径，不要一开始混用多个入口。
4. 先读该路径的首轮 artifact，再决定是否继续下一轮或汇报。
5. 先读取 `summary.json` 或 stdout 中的通用字段：`execution_path`、`coverage_class`、`candidate_field_coverage`、`full_market_claim_allowed`、`full_market_claim_boundary`、`selection_failed_reason`、`selection_failed_next_action`。
6. 仅当本轮是全 A 严格任务或显式传入 `--full-a-provenance` 时，再读取 `full_a_provenance_validation_status`、`full_a_provenance_closure_eligible`、`full_a_provenance_as_of_date`、`full_a_provenance_final_filter_removed_symbol_count` 和 `full_a_provenance_output_cleanup_errors`。
7. 出现 strict gate failed、partial result、provider error、provenance 缺口、`output_written=false` 或 `full_market_claim_allowed=false` 时，先恢复或缩短结论，再汇报。

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

入口映射只在任务拓扑尚不能决定动作，或需要复制命令、确认依赖、字段映射或 helper 边界时展开。首轮只读只加载决定下一步的最小文档；不要因为一个路径列出多个资源就一次性全部打开。本地评分、定向真实任务和今日低价超短已由上方任务拓扑给出默认 CLI 与首轮 artifact，不必先读完整 [scripts/SCRIPTS.md](scripts/SCRIPTS.md)。只有需要区分公开 CLI、路径命中入口和内部 helper 时才读它；字段、配置或依赖再读 [references/script-reference.md](references/script-reference.md)，可复制完整命令或验证门禁才读 [instructions/runbook.md](instructions/runbook.md)。

| 路径 | 首轮读取 | 按需追加 |
| --- | --- | --- |
| 本地评分 / 定向真实任务 / 今日低价超短 | 不追加文档；直接按任务拓扑的默认 CLI 和首轮 artifact 执行 | 入口边界不清时读 [scripts/SCRIPTS.md](scripts/SCRIPTS.md)；字段、配置、依赖看 [references/script-reference.md](references/script-reference.md)；复制完整命令或验证门禁看 [instructions/runbook.md](instructions/runbook.md) |
| 全 A 严格任务 | [instructions/full-a-strict-workflow.md](instructions/full-a-strict-workflow.md) | 数据源字段和命令细节再按 workflow 指向读取 |
| prediction-derived 公式和质量口径 | [references/prediction-derived-profile.md](references/prediction-derived-profile.md) | CLI 边界不清时再读 [scripts/SCRIPTS.md](scripts/SCRIPTS.md) |
| helper 或内部模块边界 | [scripts/SCRIPTS.md](scripts/SCRIPTS.md) | 字段映射看 [references/script-reference.md](references/script-reference.md)；完整命令看 [instructions/runbook.md](instructions/runbook.md) |

## 每条路径的必看 artifact

向用户下结论前，至少确认：退出码、`summary.json`、关键 metadata、候选/诊断文件是否由本轮写出。只要 `summary_output_written`、`manifest_output_written`、`source_provenance`、`selection_failed_reason` 或 `selection_failed_next_action` 仍不清楚，就不要提前给“已完成”“已经跑通”“结果可信”这类结论。

## 稳定执行面

本 Skill 的稳定执行面是 CLI 和已落地文件，不是 Python package API。

必须保留的入口规则：

- 优先处理用户提供的本地 CSV/Parquet；只有明确联网授权时才取数。
- 联网结果必须先落地为本地行情文件和 metadata，再校验、评分、解释。
- `validate_ohlcv.py`、`score_candidates.py`、`run_today_a_share_selection.py` 是常规主入口；全 A 严格任务还必须先读 [instructions/full-a-strict-workflow.md](instructions/full-a-strict-workflow.md)。
- `scripts/` 下的 `__main__` 保护不等于用户 CLI 合约；根层 `a_share_selection_*.py` 只保留兼容 wrapper，不是用户 CLI 入口；HTML、runner、walk-forward、zzshare fetch、gates support 和 selection_core helper 已分别下沉到 `scripts/lib/report_html/`、`scripts/lib/runner/`、`scripts/lib/walk_forward/`、`scripts/lib/fetch/`、`scripts/lib/gates/` 和 `scripts/lib/selection_core/`，详见 [scripts/SCRIPTS.md](scripts/SCRIPTS.md)。
- 脚本入口机器注册表见 `configs/script_entrypoints.json`；v3 将 `visibility/kind/stability/domain/default_entry` 作为分类轴，并以 `skill_route` 标记路径命中资格，只用于审计根层 `.py` 分类，不做运行时 dispatch 或 CLI 合约替代。
- `default_entry=true` 只标记 `validate_ohlcv.py`、`score_candidates.py` 和 `run_today_a_share_selection.py` 三个任务拓扑默认主入口。`skill_route=true` 仍表示公开 CLI 可在路径命中后引用，不表示默认选择。新增默认路由前先更新注册表和 `tests/test_skill_entrypoint_contracts.py`；文档语义变化时同时更新关联的文档一致性测试。
- `--spot-input` 可合并已落地实时快照展示字段；`spot_industry` 等 spot 展示字段只用于候选、诊断和 HTML 展示，不参与核心评分；匹配数量以 `summary.json.spot_matched_symbols` 为准。只有显式传 `--filter-prices-to-spot-universe` 时，runner 才会把本地 `--prices-input` 复跑收敛到当前 spot/universe；只有显式传 `--min-symbol-latest-date` 时，runner 才会剔除最新日期过期的 symbol。大 clean prices 复跑可显式加 `--prices-filter-output-format parquet`，让过滤后的运行内 prices 直接以 Parquet 交给 validate/score；默认仍保留输入格式。
- `run_today_a_share_selection.py` 的联网历史抓取默认写 `prices.csv`。只有 `--history-source baostock` 可显式加 `--history-output-format parquet` 或 `pq`，让大批量已抓取行情直接以 Parquet 进入 validate/score，并保留 HTML 候选 K 线；运行环境必须提供 `pyarrow` 或 `fastparquet`，缺失时在联网前失败。该参数只减少本地写入和后续读取成本，不提高远端请求吞吐，也不改变 provider 路由、字段、门禁或全 A 声明边界。
- `score_candidates.py --profile-output` 和 runner `--score-profile` 只增加显式性能观测 JSON，不改变候选、诊断、排序、失败路径或默认 artifact 集合；profile 不能替代行情、候选或性能收益门禁。
- `--symbols-file` 是长 symbol 池的稳定入口；`execution_path_reason=explicit_symbols_file` 仍表示显式股票池，不代表全 A 自动闭环。
- `--plan-only` 只写计划和审计所需输入快照，不执行 fetch、validate 或 score；`steps[].executed=false` 且 `commands_executed=false`，不能当成取数、校验或评分已完成。
- `--resume-from` 只从上一轮 `selected_symbols.json` 和 `history_metadata.json` 生成 `resume_retry_symbols`，用于失败、空结果、截断或因预算耗尽未处理的 symbol 重跑；manifest 会记录 `resume_inherited_options`，但它仍不能当成全市场完成证明。
- 当前 CLI 链路支持 CSV/Parquet 输入，但中间产物默认写 CSV；严格全链路无 CSV 不能通过事后转换伪装满足。
- 依赖缺失、联网失败、provider partial、strict gate failed 都必须显式报告；不得用 mock、跳过依赖或旧文件冒充成功。

## 关键边界

- 最小行情字段、日期格式、前导零、成交量单位、prediction-derived 必需列和数据源字段映射见 [references/script-reference.md](references/script-reference.md)。
- 数据源能力机器注册表见 `configs/data_sources.json`；业务场景到主源/备用源/补充源的路由见 `configs/source_routing.json`。二者只用于审计和一致性检查，不做运行时自动选源或自动 fallback；CLI fallback 必须显式传参，`runtime_cli_explicit_fallback_requires_parameter=true`。
- `mode=auto` 只选择评分口径，不规划全 A 工作流；generic 技术评分不消费 `prediction` 或 `prediction_score`。
- `score_candidates.py` 只消费预测列，不训练 LightGBM，也不会用技术因子伪造机器学习预测。
- `prediction_source=external_unverified`、`prediction_model_executed_by_runner=false` 或 `prediction_model_executed_by_score_script=false` 不能证明上游模型真实、无泄漏或已执行。
- `effective_empty_result` 和 `empty_result_reason` 是成功空结果的审计字段；优先从 stdout、summary、diagnostics 或 candidates 中读取。`output_written=false` 是输入失败或严格门禁失败，不能写成成功 0 候选。
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

修改本仓库代码或 Skill 时，按仓库根 AGENTS.md 跑 JSON/YAML、py_compile、unittest、quick_validate，并校验 `agents/openai.yaml`。`evals/evals.json` 是触发和行为覆盖 manifest，不在真实选股任务启动路径中；新增或重构 Skill 触发语义时，按 manifest 只读取相关场景分片。
