# 脚本清单

本文件是 `scripts/` 目录入口分层面向人类和 Agent 的解释层。看到脚本文件时，先按“稳定 CLI / 取数入口 / 门禁回测入口 / 内部 helper”四类判断，不要按文件数量或 `__main__` 保护猜入口。

配置文件的权威路径在 `../configs/`；旧命令传入的 `scripts/*.json` 会由 CLI 自动回退到 `../configs/`。

脚本入口机器注册表见 `../configs/script_entrypoints.json`，它是入口机器分类事实源。本文件负责解释用途和选择规则；注册表只用于审计根层 `.py` 是否被归类，不是运行时 dispatcher，也不替代 CLI 合约。注册表 v2 额外标注 `visibility`、`kind`、`stability`、`domain` 和 `skill_route`；`skill_route=false` 的 internal helper 不进入 Agent 默认路由。

根层 `.py` 路径保持兼容；部分内部 helper 的真实实现已迁入 `lib/`，根层同名文件只做 re-export 和直接执行 fail-fast。用户命令仍使用本文件列出的根层 CLI，不直接调用 `lib/`。

新的内部 helper 不再新增到 `scripts/` 根层；默认放入 `lib/` 或后续更细分的内部子目录。根层 internal helper 只是兼容预算，后续迁移只能减少或保持，不应增加。HTML、runner、walk-forward、zzshare fetch、gates support 和 selection_core helper 已分别下沉到 `lib/report_html/`、`lib/runner/`、`lib/walk_forward/`、`lib/fetch/`、`lib/gates/` 和 `lib/selection_core/`，根层只保留相关 public CLI 和 4 个 compatibility wrapper。

依赖方向默认从公开 CLI 指向内部 helper；internal helper 默认不得 import public CLI。共享 OHLCV frame 校验逻辑位于 `lib/a_share_selection_validation.py`，公开 CLI 和内部 helper 都从内部模块复用。

`lib/` 内部实现分为纯 helper、parser 层和明确产物层。纯 helper 不得新增 argparse CLI、不得直接写出 CSV/JSON/HTML 等产物，也不得 import 公开 CLI；parser 层只构造 public CLI 的 `ArgumentParser`；明确产物层只在 public CLI 调用下写出 run artifact。`lib/fetch/zzshare_a_share_checkpoint.py` 是 zzshare 长跑 checkpoint artifact 边界，不是用户入口。需要直接执行时只允许 fail-fast。

`lib/selection_core/` 只接收评分、字段、符号、数据解析、披露、诊断和本地校验逻辑。runner 编排、HTML 展示、provider 取数、walk-forward artifact 检查和 gate/backtest support 不得放回 selection_core。

`compatibility_wrapper` 条目必须在 `../configs/script_entrypoints.json` 记录 `migration_target` 和 `deletion_blocker`；内部运行路径应优先导入 `lib.*`，没有外部兼容理由的 wrapper 应删除。

命令细节、依赖和字段映射仍以 [../references/script-reference.md](../references/script-reference.md) 为准；脚本边界和 helper 边界先读本文件。

逐个脚本的用途、必要性和迁移判断见 [../references/script-inventory.md](../references/script-inventory.md)。该文件只用于审查“为什么脚本多、每个是否必要”，不是常规任务启动路径。

## 稳定 CLI

| 脚本 | 用途 | 首先检查 |
| --- | --- | --- |
| `create_demo_data.py` | 生成本地 demo CSV | demo 不是真实行情 |
| `validate_ohlcv.py` | 校验 CSV/Parquet 行情输入 | 字段、日期、前导零、重复行、价格和历史窗口 |
| `score_candidates.py` | 本地行情评分并输出候选 CSV；可显式写性能 profile | `effective_empty_result`、`failed_symbols`、prediction 披露字段；`--profile-output` 默认关闭 |
| `run_today_a_share_selection.py` | 今日总控，串联取数、校验、评分、诊断和 HTML | `run_manifest.json`、`summary.json`、metadata；Baostock history 可显式输出 Parquet，默认仍为 CSV；`--score-profile` 仅增加观测产物；`--full-a-provenance` 仅显式消费已验证 lineage 并执行最终 breadth 对账 |
| `slice_prices_as_of.py` | 按信号日切片行情 | `actual_data_date`，不能只看退出码 |

## 取数入口

| 脚本 | 数据源 | 边界 |
| --- | --- | --- |
| `fetch_eastmoney_a_share_spot.py` | 东方财富 A 股实时快照 | partial 分页不能写成全市场完成；长分页需稳定排序和 retry/page interval |
| `fetch_baostock_a_share_universe.py` | baostock `query_all_stock` A 股 universe | 只写 symbol/name 兼容快照；支持显式日期回看和失败重试；`fetch_errors/fetch_attempts/max_attempts` 用于复盘；不是实时行情、价格、成交额或全市场完成证明 |
| `fetch_baostock_a_share.py` | baostock A 股日线 | prices 输出按 `.csv/.parquet/.pq` 后缀显式选择，CSV 默认兼容；可复用 `symbol/name` CSV/Parquet，缺名和非交易行策略显式；检查失败、空 symbol、无效行和可交易字段 |
| `fetch_akshare_a_share.py` | akshare A 股日线 | fallback 成功不证明主接口稳定 |
| `fetch_pytdx_a_share.py` | pytdx A 股日线 | 自适应近期窗口请求；no-token OHLCV/amount 补充源；只允许同 `symbol+date` 合并，缺换手率、可交易字段、官方授权和长期稳定证明 |
| `fetch_akshare_hk_daily.py` | akshare 港股日线 | 不证明港交所日历或真实成交 |
| `fetch_zzshare_a_share.py` | zzshare A 股日线 | 检查 token、截断、频率和来源边界 |
| `fetch_yfinance_ohlcv.py` | yfinance 通用 OHLCV | market 只是标签，缺换手率时必须披露假设 |

## 门禁和回测入口

| 脚本 | 用途 | 不能外推 |
| --- | --- | --- |
| `generate_lightgbm_predictions.py` | 可选 LightGBM prediction 生成器 | 下游评分通过不能反推被跳过标的也通过 |
| `allocate_candidate_capital.py` | 单候选本地 sizing | 不是真实成交、券商订单或现金容量证明 |
| `allocate_portfolio_candidate_capital.py` | 组合级 sizing 和容量裁剪 | 裁剪后候选不能等同原始候选全通过 |
| `backtest_buy_hold.py` | close-to-close buy-hold 基线 | 默认零成本，不是真实净收益 |
| `portfolio_equity_curve.py` | 等权或 sizing 资金曲线 | 默认只按 complete trades 计算 |
| `portfolio_overlap_report.py` | 并发持仓、重叠和容量门禁 | 工作日日历不是交易所日历 |
| `run_baostock_walk_forward.py` | baostock walk-forward 总控 | `--offline-plan` 不执行真实门禁 |
| `prepare_history_retry_symbols.py` | 从 `selected_symbols.json` 和 `history_metadata.json` 汇总 failed/empty/truncated/unprocessed symbol，生成历史抓取重试清单 | 只生成 recovery plan，不证明全 A 完成 |
| `prepare_clean_history_pool.py` | 从 history metadata 和 short-history artifact 生成 clean prices/metadata；也可从已落地 effective history 显式推导短历史清单、合并已抓取 delta，或原子写 provenance | 短历史派生不与同轮内存增量合并共用；推导清单和 provenance 都只说明 artifact lineage，不联网、不补齐、不替代最终 runner、实时行情或选股证明 |
| `prepare_incremental_history_plan.py` | 对比当前 universe 和既有 history metadata 生成有界、可恢复的增量抓取计划 | 只生成 plan，不证明增量抓取成功；默认每 bucket 最多 200 个 symbol |
| `execute_incremental_history_plan.py` | 按计划 bucket 调用单一显式 provider，落盘 checkpoint、聚合增量 artifact，并可选执行 verified merge | 不自动切源；执行完成也不等于全 A 或选股门禁完成 |
| `summarize_walk_forward_run.py` | 汇总 walk-forward artifact | 未传 required model 参数时不能声称模型口径已验证 |
| `validate_walk_forward_manifest.py` | 校验 runner manifest | 不替代 artifact 内容复验 |
| `validate_walk_forward_artifacts.py` | 校验 walk-forward artifact 内容 | `capacity_gate_pass=false` 仍是容量门禁失败 |
| `probe_baostock_limit_fields.py` | baostock 涨跌停字段探测 | 字段可取不等于涨跌停规则已建模 |
| `probe_external_source_stability.py` | 外部源稳定性观察 | 覆盖 eastmoney、baostock_universe、akshare、pytdx、yfinance、baostock、zzshare；短窗口通过不证明长期稳定 |

## 内部 helper

这些模块可能带 `__main__`，但直接执行只用于 fail-fast 提示“不是 CLI 入口”。不要把它们当作用户入口、内部实现入口或 `--help` 合约：

- `a_share_selection_calendar_contract.py`
- `a_share_selection_cli_guard.py`
- `a_share_selection_config.py`
- `a_share_selection_paths.py`

`lib/gates/incremental_history_execution.py` 只负责计划执行、resume、provider command 和 manifest 状态；`lib/gates/incremental_history_artifacts.py` 负责 bucket CSV/metadata 校验、聚合和原子发布。二者只能由公开 `execute_incremental_history_plan.py` 调用，都不是独立 CLI，也不允许隐式选择或切换数据源。

`lib/gates/full_a_clean_pool_provenance.py` 是由 `prepare_clean_history_pool.py` 调用的 artifact 校验 helper。它对 universe、原始 history、clean prices/metadata/report 和可选 short-history 清单重算 symbol 集合、计数、路径和 SHA-256；至少 4,000 个 symbol 的 sample guard 还必须与完整 baostock metadata 合同、逐标 freshness 和 history-clean 全行保真同时通过，数量本身不是完整性证明。`lib/gates/full_a_clean_pool_artifacts.py` 负责前后双指纹与路径身份，`lib/gates/full_a_clean_pool_lineage.py` 负责逐标日期与 retained row/content 对账，二者都不写 artifact。三个 helper 只返回证明数据，不写入、补齐或切换任何数据源，更不能单独提升 runner 的 `full_market_claim_allowed`。

`lib/runner/run_today_a_share_selection_full_a_provenance.py` 是 runner 的内部两阶段门禁：评分前读取 clean/final prices 的 `symbol` 列，绑定 exact clean/universe 输入、过滤计数和四类 symbol-set SHA-256；评分后用已验证 final 集合的数量和哈希对账 diagnostics/candidates。只有无任何剔除时才允许 breadth 声明，失败时清除未验证评分产物。它不是 CLI，也不改变默认 runner 输出。

`lib/runner/run_today_a_share_selection_prices_sidecar.py` 属于明确产物层，只能由公开 runner 写入和校验过滤后 Parquet 的 sidecar；复用时同时校验文件指纹、实际 row/symbol/date 统计、symbol-set SHA-256 和过滤契约。它不是独立 CLI，也不获取或补齐行情。

直接复用 Python 代码时，需要将本目录加入 `PYTHONPATH` 或 `sys.path`。不要把内部 helper 的导入路径当成稳定 package API。

HTML 报告模块已下沉到 `lib/report_html/`。`a_share_selection_html_sections.py`、`a_share_selection_html_scripts.py`、`a_share_selection_html_candidate_master.py` 仍是维护热点，只能继续作为展示层 helper 拆分，不能把候选事实、门禁判断或机器字段来源移动进 HTML 展示层。后续拆分时保留 `run_today_a_share_selection.py` 和 `report.html` 输出契约不变。

后续结构收口优先级：逐步解除 4 个 compatibility wrapper 的外部 root import blocker；HTML、runner、walk-forward、zzshare fetch helper、gates support helper 和 selection_core helper 已完成下沉；公开 CLI 路径默认冻结，不为整理目录而移动用户命令。

## 维护热点

以下文件是已知维护热点，不是新增入口，也不是当前必须拆分的阻塞项。后续拆分必须保持 public CLI、CSV/JSON artifact 和 `report.html` 输出契约不变。

| 文件 | 当前边界 | 后续拆分原则 |
| --- | --- | --- |
| `lib/report_html/a_share_selection_html_sections.py` | HTML section rendering | 只拆展示层 section 组合，不移动候选事实、门禁判断或机器字段来源 |
| `lib/report_html/a_share_selection_html_scripts.py` | HTML 内嵌交互脚本字符串 | 只拆前端展示脚本片段，不改变报告数据模型 |
| `lib/report_html/a_share_selection_html_candidate_master.py` | 候选详情展示组装 | 只拆 candidate display helpers，不改变候选 CSV/diagnostics 语义 |
| `lib/runner/run_today_a_share_selection_summary.py` | summary 字段投影和兼容字段组装 | 只按稳定领域子视图拆分，不改变 summary/stdout/CSV provenance 字段 |
| `run_today_a_share_selection.py` | public runner 编排和失败收口 | 继续下沉独立职责，但保留单一 public CLI、步骤顺序和失败清理语义 |

上述超过 800 行的文件已记录职责豁免。豁免原因不是忽略复杂度，而是当前内容分别属于声明式展示、字段投影或单入口编排；按固定行数机械拆分会扩大跨文件跳转和兼容回归面。只有形成可命名的独立职责，并有对应 artifact/HTML 契约测试时才继续拆分。

机器可校验的精确豁免集合位于 `../configs/production_complexity_exemptions.json`。`validate_skill_changes.py` 会按生产文件总行数和函数非空行数重算当前集合；新增超限、漏登记或已经不再超限的陈旧豁免都会失败。

超过 80 行但仍保持内聚的函数也必须显式登记。当前豁免只适用于声明式构造，不适用于网络循环、状态机、失败处理或评分执行流：

| 函数 | 声明式职责 | 后续治理条件 |
| --- | --- | --- |
| `candidate_stock_dialog()` | 生成单一候选详情 dialog 的 HTML 结构 | 形成稳定展示子组件并通过 HTML 快照/浏览器回归后拆分 |
| `history_selection_fields()` | 定义历史抓取展示字段顺序和标签 | 字段分组成为独立用户视图时拆分 |
| `runner_disclosure_stdout()` | 定义 runner stdout 机器字段投影 | stdout 契约分组并有兼容测试时拆分 |
| `history_metadata_for_output()` | 将 provider metadata 投影为 runner 字段 | provider-neutral 与 provider-specific 字段形成稳定边界时拆分 |
| `add_history_options()` | 集中声明 history argparse 参数 | 参数组拥有独立 parser 合约时拆分 |
| `provenance_fields()` | 定义 provenance 字段映射 | 字段组形成稳定 schema 子对象时拆分 |

## 判定规则

1. 看到 `create_demo_data.py`、`validate_ohlcv.py`、`score_candidates.py`、`run_today_a_share_selection.py`、`slice_prices_as_of.py`，先按稳定 CLI 处理。
2. 看到 `fetch_*.py`，先按取数入口处理，检查数据源边界和落地 metadata。
3. 看到 `generate_lightgbm_predictions.py`、`allocate_*_capital.py`、`backtest_*`、`portfolio_*`、`run_baostock_walk_forward.py`、`validate_walk_forward_*`、`probe_*`，先按门禁和回测入口处理。
4. 看到根层 `a_share_selection_calendar_contract.py`、`a_share_selection_cli_guard.py`、`a_share_selection_config.py`、`a_share_selection_paths.py`，先按兼容 wrapper 处理；`lib/report_html/` 是 HTML 展示层内部实现包，`lib/runner/` 是 `run_today_a_share_selection.py` 的内部实现包，`lib/walk_forward/` 是 public walk-forward gate CLI 的内部实现包，`lib/fetch/` 是 provider fetch helper 包，`lib/gates/` 是 gate/backtest support helper 包，`lib/selection_core/` 是评分、字段、符号和数据校验内部实现包。
5. `__main__` 只代表可 fail-fast，不代表对用户公开的 CLI 合约。

`skill_route=true` 表示脚本允许被任务拓扑引用，不表示 Agent 应在首轮从 29 个 public CLI 中随机选择。默认主入口仍是 `validate_ohlcv.py`、`score_candidates.py` 和 `run_today_a_share_selection.py`；fetch、prediction、backtest、capacity、probe、recovery 和 validator CLI 只在路径命中或 artifact 门禁需要时使用。

## 入口选择规则

1. 用户给本地行情文件：只需要评分时优先 `validate_ohlcv.py` 后接 `score_candidates.py`；需要 `run_manifest.json`、`summary.json`、spot 合并或 HTML 时再用 `run_today_a_share_selection.py --prices-input`。
2. 用户要求小样本真实任务、明确 symbol 或明确本地股票池的低价超短：优先 `run_today_a_share_selection.py`；长列表用 `--symbols-file`，只审计命令用 `--plan-only`。
3. 用户要求今日 A 股、真实 A 股选股、全 A、全市场或扩大股票池，且没有限定 symbol 或本地股票池：先读 [../instructions/full-a-strict-workflow.md](../instructions/full-a-strict-workflow.md)，不要直接套默认小样本命令。
4. 需要恢复上一轮失败、空结果、截断或因预算耗尽未处理的 symbol：优先 `run_today_a_share_selection.py --resume-from <run_manifest.json>`，它生成 `resume_retry_symbols`，不证明全市场完成。
5. 用户坚持 prediction-derived：必须有真实 `prediction` 或 `prediction_score` 输入，再走 prediction-derived config。
6. 需要回测、容量或历史门禁：只在评分 artifact 已经闭环后进入预测、回测和门禁 CLI。
