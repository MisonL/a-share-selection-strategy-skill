# 脚本用途和必要性审计

本文件用于回答“为什么 `scripts/` 下还有很多 `.py`、每个脚本是否必要”。它是审计索引，不是运行时入口，不替代 `../configs/script_entrypoints.json`，也不进入 Skill 首轮读取路径。

当前根层 `.py` 共 33 个，其中公开 CLI 29 个、兼容 wrapper 4 个。`scripts/lib/` 是内部实现目录，不列入本表。判断脚本是否合理时先看 `公开 CLI 是否必须兼容` 和 `internal helper 是否还能继续下沉`，不要按文件数量直接合并。当前整个 `scripts/` 树有 122 个 Python 文件；其中 89 个是按领域分层的内部实现，不是 Agent 首轮入口。

结论：

- 公开 CLI 保留：用户命令、文档和测试依赖这些路径，不能为了目录整洁直接移动或合并。
- 内部 helper 已从根层移入 `scripts/lib/` 分层包；根层只保留 4 个兼容 wrapper，新 helper 默认进入 `lib/`。
- HTML 展示层、runner、walk-forward、zzshare fetch、gates support 和 selection_core helper 已分别下沉到 `scripts/lib/report_html/`、`scripts/lib/runner/`、`scripts/lib/walk_forward/`、`scripts/lib/fetch/`、`scripts/lib/gates/` 和 `scripts/lib/selection_core/`。后续优化方向是逐步解除 4 个兼容 wrapper 的 blocker，不改变 public CLI、`report.html` 和 CSV/JSON artifact 契约。
- `compatibility_wrapper` 只是短期外部兼容层，必须保留 `migration_target` 和 `deletion_blocker`；内部运行路径应优先导入 `lib.*`，blocker 解除后再删或迁。

## 脚本用途和必要性

| 脚本 | 分类 | 领域 | 行数 | 用途 | 必要性判断 |
| --- | --- | --- | ---: | --- | --- |
| `a_share_selection_calendar_contract.py` | `internal_helper` | `compatibility_wrapper` | 11 | Compatibility wrapper for shared calendar contract constants. | 暂留: 外部 root import 兼容层；真实实现已在 `lib/`，blocker 解除后删除。 |
| `a_share_selection_cli_guard.py` | `internal_helper` | `compatibility_wrapper` | 9 | Compatibility wrapper for the internal CLI guard helper. | 暂留: 外部 root import 兼容层；真实实现已在 `lib/`，blocker 解除后删除。 |
| `a_share_selection_config.py` | `internal_helper` | `compatibility_wrapper` | 11 | Compatibility wrapper for configuration loading helpers. | 暂留: 外部 root import 兼容层；真实实现已在 `lib/`，blocker 解除后删除。 |
| `a_share_selection_paths.py` | `internal_helper` | `compatibility_wrapper` | 11 | Compatibility wrapper for shared filesystem path helpers. | 暂留: 外部 root import 兼容层；真实实现已在 `lib/`，blocker 解除后删除。 |
| `allocate_candidate_capital.py` | `gate_backtest_cli` | `gate_backtest` | 234 | Allocate traceable capital fields for candidate trades. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `allocate_portfolio_candidate_capital.py` | `gate_backtest_cli` | `gate_backtest` | 113 | Allocate candidate capital with portfolio-aware capacity gates. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `backtest_buy_hold.py` | `gate_backtest_cli` | `gate_backtest` | 348 | Run a minimal close-to-close buy-hold backtest from local files. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `create_demo_data.py` | `stable_cli` | `selection_core` | 315 | Create deterministic demo OHLCV CSV files for quick-start smoke tests. | 保留: stable public CLI，用户命令兼容路径。 |
| `fetch_akshare_a_share.py` | `fetch_cli` | `fetch` | 378 | Fetch A-share OHLCV data through akshare and save local gate files. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_akshare_hk_daily.py` | `fetch_cli` | `fetch` | 408 | Fetch Hong Kong OHLCV data through akshare stock_hk_daily. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_baostock_a_share.py` | `fetch_cli` | `fetch` | 651 | Fetch A-share OHLCV data through baostock and save CSV/Parquet gate files. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_baostock_a_share_universe.py` | `fetch_cli` | `fetch` | 167 | Fetch baostock A-share universe into a spot-compatible CSV snapshot. | 保留: public fetch CLI，全 A 股票池主入口，支持显式日期回看和失败重试，不能写成实时行情或实时全市场完成。 |
| `fetch_eastmoney_a_share_spot.py` | `fetch_cli` | `fetch` | 422 | Fetch Eastmoney A-share realtime spot snapshot into local CSV metadata. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_pytdx_a_share.py` | `fetch_cli` | `fetch` | 171 | Fetch A-share daily OHLCV data through pytdx and save gate files. | 保留: public fetch CLI，显式 no-token 补充源；缺换手率、可交易字段、官方授权和长期稳定证明。 |
| `fetch_yfinance_ohlcv.py` | `fetch_cli` | `fetch` | 345 | Fetch yfinance OHLCV data and save local gate files. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_zzshare_a_share.py` | `fetch_cli` | `fetch` | 411 | Fetch A-share OHLCV data through zzshare and save local gate files. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `generate_lightgbm_predictions.py` | `gate_backtest_cli` | `gate_backtest` | 477 | Generate LightGBM prediction_score values from local OHLCV data. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `portfolio_equity_curve.py` | `gate_backtest_cli` | `gate_backtest` | 266 | Build a simple equal-weight equity curve from backtest CSV files. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `portfolio_overlap_report.py` | `gate_backtest_cli` | `gate_backtest` | 379 | Report overlap and capacity gates from backtest CSV files. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `prepare_history_retry_symbols.py` | `gate_backtest_cli` | `gate_backtest` | 101 | Prepare an auditable retry symbol list from history fetch artifacts. | 保留: public gate/backtest CLI；恢复计划纯逻辑位于 `lib/runner/`，输出仍是诊断或门禁证据。 |
| `prepare_clean_history_pool.py` | `gate_backtest_cli` | `gate_backtest` | 415 | Prepare clean prices, derived short-history audit, metadata, optional verified delta merge, or atomic clean-pool provenance from existing artifacts. | 保留: public recovery CLI，只处理既有 artifact；推导清单和 provenance 只校验 lineage，不联网、不提升最终全 A 声称。 |
| `prepare_incremental_history_plan.py` | `gate_backtest_cli` | `gate_backtest` | 638 | Prepare a bounded, resumable incremental history fetch plan from universe and metadata. | 保留: public planning CLI，只生成增量计划，不证明抓取成功。 |
| `execute_incremental_history_plan.py` | `gate_backtest_cli` | `gate_backtest` | 306 | Execute one explicit provider across bounded plan buckets and persist resumable artifacts. | 保留: public execution CLI，不自动切源，不证明全 A 完成。 |
| `probe_baostock_limit_fields.py` | `gate_backtest_cli` | `gate_backtest` | 421 | Probe baostock field availability without modeling limit rules. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `probe_external_source_stability.py` | `gate_backtest_cli` | `gate_backtest` | 783 | Run repeated external source probes through the stable fetch CLIs. | 保留: public gate/backtest CLI，输出是诊断或门禁证据；紧凑摘要和归档实现位于 `lib/gates/`，不扩大 CLI 职责。 |
| `run_baostock_walk_forward.py` | `gate_backtest_cli` | `gate_backtest` | 692 | Run the baostock prediction-derived walk-forward gate through existing CLIs. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `run_today_a_share_selection.py` | `stable_cli` | `selection_core` | 1340 | Run an auditable local A-share selection workflow through existing CLIs. | 保留: stable public CLI，用户命令兼容路径；full-A provenance 细节由 internal runner helper 实现。 |
| `score_candidates.py` | `stable_cli` | `selection_core` | 532 | Score stock candidates from local OHLCV data. | 保留: stable public CLI，用户命令兼容路径。 |
| `slice_prices_as_of.py` | `stable_cli` | `selection_core` | 118 | Slice local OHLCV rows to an as-of date to prevent future leakage. | 保留: stable public CLI，用户命令兼容路径。 |
| `summarize_walk_forward_run.py` | `gate_backtest_cli` | `gate_backtest` | 417 | Summarize and gate a real walk-forward run directory. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `validate_ohlcv.py` | `stable_cli` | `selection_core` | 84 | Validate local OHLCV data for A-share selection workflows. | 保留: stable public CLI，用户命令兼容路径。 |
| `validate_walk_forward_artifacts.py` | `gate_backtest_cli` | `gate_backtest` | 100 | Validate walk-forward artifact contents without rerunning the pipeline. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `validate_walk_forward_manifest.py` | `gate_backtest_cli` | `gate_backtest` | 413 | Validate a walk-forward runner manifest without rerunning the pipeline. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |

## 内部实现边界

依赖方向默认从公开 CLI 指向内部 helper；internal helper 默认不得 import public CLI。共享 OHLCV frame 校验逻辑位于 `lib/a_share_selection_validation.py`，公开 CLI 和内部 helper 都从内部模块复用。跨 runner 与 HTML 展示层的纯运行状态契约集中在 `lib/a_share_selection_run_state.py`，包括 partial result、synthetic demo 和 step execution 判定；`lib/report_html/` 可以依赖这一共享模块，但不得 import `lib.runner`，共享模块也不得 import `lib.runner` 或 `lib.report_html`。

`lib/` 内部实现分为纯 helper、parser 层和明确产物层。纯 helper 不得新增 argparse CLI、不得直接写出 CSV/JSON/HTML 等产物，也不得 import 公开 CLI；parser 层只构造 public CLI 的 `ArgumentParser`；明确产物层只在 public CLI 调用下写出 run artifact。`lib/runner/run_today_a_share_selection_retry_plan.py` 是 `prepare_history_retry_symbols.py` 与今日 runner 共同复用的恢复计划纯逻辑，根层 CLI 只保留 parser 和 artifact I/O。`lib/fetch/zzshare_a_share_checkpoint.py` 是 zzshare 长跑 checkpoint artifact 边界，不是用户入口。需要直接执行时只允许 fail-fast。

`lib/selection_core/` 只接收评分、字段、符号、数据解析、披露、诊断和本地校验逻辑。runner 编排、HTML 展示、provider 取数、walk-forward artifact 检查和 gate/backtest support 不得放回 selection_core。

`compatibility_wrapper` 条目必须在 `../configs/script_entrypoints.json` 记录 `migration_target` 和 `deletion_blocker`；内部运行路径应优先导入 `lib.*`，没有外部兼容理由的 wrapper 应删除。直接复用 Python 代码时，需要将 `scripts/` 加入 `PYTHONPATH` 或 `sys.path`，但不要把内部 helper 的导入路径当成稳定 package API。

### 全 A provenance 和明确产物层

`lib/gates/incremental_history_execution.py` 只负责计划执行、resume、provider command 和 manifest 状态；`lib/gates/incremental_history_artifacts.py` 负责 bucket CSV/metadata 校验、聚合和原子发布。二者只能由公开 `execute_incremental_history_plan.py` 调用，都不是独立 CLI，也不允许隐式选择或切换数据源。

`lib/gates/external_source_stability_summary.py` 是外部源探针的纯摘要投影和紧凑严格失败诊断 helper。它只从既有 result 选择字段、计算检查投影和格式化已脱敏定位信息，不运行 provider 命令、不写 artifact，也不新增 CLI。

`lib/gates/full_a_clean_pool_provenance.py` 是由 `prepare_clean_history_pool.py` 调用的 artifact 校验 helper。它对 universe、原始 history、clean prices/metadata/report 和可选 short-history 清单重算 symbol 集合、计数、路径和 SHA-256；至少 4,000 个 symbol 的 sample guard 还必须与完整 baostock metadata 合同、逐标 freshness 和 history-clean 全行保真同时通过，数量本身不是完整性证明。`lib/gates/full_a_clean_pool_artifacts.py` 负责前后双指纹与路径身份，`lib/gates/full_a_clean_pool_lineage.py` 负责逐标日期与 retained row/content 对账，二者都不写 artifact。三个 helper 只返回证明数据，不写入、补齐或切换任何数据源，更不能单独提升 runner 的 `full_market_claim_allowed`。

`lib/runner/run_today_a_share_selection_full_a_provenance.py` 是 runner 的内部两阶段门禁：评分前读取 clean/final prices 的 `symbol` 列，绑定 exact clean/universe 输入、过滤计数和四类 symbol-set SHA-256；评分后用已验证 final 集合的数量和哈希对账 diagnostics/candidates。只有无任何剔除时才允许 breadth 声明，失败时清除未验证评分产物。它不是 CLI，也不改变默认 runner 输出。

`lib/runner/run_today_a_share_selection_prices_sidecar.py` 属于明确产物层，只能由公开 runner 写入和校验过滤后 Parquet 的 sidecar；复用时同时校验文件指纹、实际 row/symbol/date 统计、symbol-set SHA-256 和过滤契约。它不是独立 CLI，也不获取或补齐行情。

HTML 报告模块已下沉到 `lib/report_html/`。`a_share_selection_html_sections.py`、`a_share_selection_html_scripts.py`、`a_share_selection_html_candidate_master.py` 只能继续作为展示层 helper 拆分，不能把候选事实、门禁判断或机器字段来源移动进 HTML 展示层。后续拆分时保留 `run_today_a_share_selection.py` 和 `report.html` 输出契约不变。

## 后续迁移顺序

1. 继续冻结 29 个 public CLI 根层路径，先维护命令兼容。
2. 不再新增根层 internal helper；新 helper 进入 `scripts/lib/` 或后续内部子包。
3. HTML、runner、walk-forward、zzshare fetch helper、gates support helper 与 selection_core helper 已完成下沉；继续拆 HTML 大文件时只拆展示逻辑，不移动事实判断。
4. 兼容 wrapper 保留到 blocker 解除；不要为了减少 4 个 wrapper 破坏旧 import 或测试。
5. 每次迁移都同步 `script_entrypoints.json`、本文件、`tests/test_skill_entrypoint_contracts.py` 和相关文档一致性测试。

## 维护热点

这些文件当前仍偏大，但已经迁入内部实现层。它们不是新增入口，也不是当前必须拆分的阻塞项，不扩大根层入口面；后续拆分应作为独立任务处理。它们属于声明式展示、字段投影或报告组装边界，按固定行数拆分会增加跨文件跳转并扩大 `report.html` 回归面；在 public CLI、CSV/JSON 和 HTML 契约均有测试保护前，允许保持内聚实现。

| 文件 | 原因 | 约束 |
| --- | --- | --- |
| `lib/report_html/a_share_selection_html_sections.py` | HTML section rendering 集中，行数最高 | 只拆展示层 section 组合，不移动候选事实、门禁判断或机器字段来源 |
| `lib/report_html/a_share_selection_html_scripts.py` | 静态报告交互脚本集中 | 只拆 HTML 交互脚本片段，不改变报告数据模型 |
| `lib/report_html/a_share_selection_html_candidate_master.py` | 候选详情展示组装集中 | 只拆 candidate display helpers，不改变候选 CSV/diagnostics 语义 |
| `lib/runner/run_today_a_share_selection_summary.py` | summary 字段投影和兼容字段集中 | 只按稳定子视图拆分，不改变 summary/stdout/CSV provenance 字段 |
| `run_today_a_share_selection.py` | 单一 public runner 的编排和失败收口集中 | 继续下沉独立职责，但不拆成多个用户入口或改变步骤顺序 |

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
