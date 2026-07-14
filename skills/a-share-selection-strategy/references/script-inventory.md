# 脚本用途和必要性审计

本文件用于回答“为什么 `scripts/` 下还有很多 `.py`、每个脚本是否必要”。它是审计索引，不是运行时入口，不替代 `../configs/script_entrypoints.json`，也不进入 Skill 首轮读取路径。

当前根层 `.py` 共 33 个，其中公开 CLI 29 个、兼容 wrapper 4 个。`scripts/lib/` 是内部实现目录，不列入本表。判断脚本是否合理时先看 `公开 CLI 是否必须兼容` 和 `internal helper 是否还能继续下沉`，不要按文件数量直接合并。当前整个 `scripts/` 树有 117 个 Python 文件；其中 84 个是按领域分层的内部实现，不是 Agent 首轮入口。

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
| `fetch_akshare_a_share.py` | `fetch_cli` | `fetch` | 357 | Fetch A-share OHLCV data through akshare and save local gate files. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_akshare_hk_daily.py` | `fetch_cli` | `fetch` | 408 | Fetch Hong Kong OHLCV data through akshare stock_hk_daily. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_baostock_a_share.py` | `fetch_cli` | `fetch` | 597 | Fetch A-share OHLCV data through baostock and save CSV/Parquet gate files. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_baostock_a_share_universe.py` | `fetch_cli` | `fetch` | 163 | Fetch baostock A-share universe into a spot-compatible CSV snapshot. | 保留: public fetch CLI，全 A 股票池主入口，支持显式日期回看和失败重试，不能写成实时行情或实时全市场完成。 |
| `fetch_eastmoney_a_share_spot.py` | `fetch_cli` | `fetch` | 422 | Fetch Eastmoney A-share realtime spot snapshot into local CSV metadata. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_pytdx_a_share.py` | `fetch_cli` | `fetch` | 171 | Fetch A-share daily OHLCV data through pytdx and save gate files. | 保留: public fetch CLI，显式 no-token 补充源；缺换手率、可交易字段、官方授权和长期稳定证明。 |
| `fetch_yfinance_ohlcv.py` | `fetch_cli` | `fetch` | 345 | Fetch yfinance OHLCV data and save local gate files. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `fetch_zzshare_a_share.py` | `fetch_cli` | `fetch` | 411 | Fetch A-share OHLCV data through zzshare and save local gate files. | 保留: public fetch CLI，网络和数据源边界由 metadata 披露。 |
| `generate_lightgbm_predictions.py` | `gate_backtest_cli` | `gate_backtest` | 477 | Generate LightGBM prediction_score values from local OHLCV data. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `portfolio_equity_curve.py` | `gate_backtest_cli` | `gate_backtest` | 266 | Build a simple equal-weight equity curve from backtest CSV files. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `portfolio_overlap_report.py` | `gate_backtest_cli` | `gate_backtest` | 379 | Report overlap and capacity gates from backtest CSV files. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `prepare_history_retry_symbols.py` | `gate_backtest_cli` | `gate_backtest` | 231 | Prepare an auditable retry symbol list from history fetch artifacts. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `prepare_clean_history_pool.py` | `gate_backtest_cli` | `gate_backtest` | 327 | Prepare clean prices and metadata from existing history artifacts; optional verified delta merge or atomic clean-pool provenance output. | 保留: public recovery CLI，只处理既有 artifact；provenance 只校验 lineage，不联网、不提升最终全 A 声称。 |
| `prepare_incremental_history_plan.py` | `gate_backtest_cli` | `gate_backtest` | 599 | Prepare an incremental history fetch plan from universe and metadata. | 保留: public planning CLI，只生成增量计划，不证明抓取成功。 |
| `execute_incremental_history_plan.py` | `gate_backtest_cli` | `gate_backtest` | 212 | Execute one explicit provider across plan buckets and persist resumable artifacts. | 保留: public execution CLI，不自动切源，不证明全 A 完成。 |
| `probe_baostock_limit_fields.py` | `gate_backtest_cli` | `gate_backtest` | 421 | Probe baostock field availability without modeling limit rules. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `probe_external_source_stability.py` | `gate_backtest_cli` | `gate_backtest` | 571 | Run repeated external source probes through the stable fetch CLIs. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `run_baostock_walk_forward.py` | `gate_backtest_cli` | `gate_backtest` | 692 | Run the baostock prediction-derived walk-forward gate through existing CLIs. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `run_today_a_share_selection.py` | `stable_cli` | `selection_core` | 1309 | Run an auditable local A-share selection workflow through existing CLIs. | 保留: stable public CLI，用户命令兼容路径；full-A provenance 细节由 internal runner helper 实现。 |
| `score_candidates.py` | `stable_cli` | `selection_core` | 532 | Score stock candidates from local OHLCV data. | 保留: stable public CLI，用户命令兼容路径。 |
| `slice_prices_as_of.py` | `stable_cli` | `selection_core` | 118 | Slice local OHLCV rows to an as-of date to prevent future leakage. | 保留: stable public CLI，用户命令兼容路径。 |
| `summarize_walk_forward_run.py` | `gate_backtest_cli` | `gate_backtest` | 417 | Summarize and gate a real walk-forward run directory. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `validate_ohlcv.py` | `stable_cli` | `selection_core` | 84 | Validate local OHLCV data for A-share selection workflows. | 保留: stable public CLI，用户命令兼容路径。 |
| `validate_walk_forward_artifacts.py` | `gate_backtest_cli` | `gate_backtest` | 100 | Validate walk-forward artifact contents without rerunning the pipeline. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |
| `validate_walk_forward_manifest.py` | `gate_backtest_cli` | `gate_backtest` | 413 | Validate a walk-forward runner manifest without rerunning the pipeline. | 保留: public gate/backtest CLI，输出是诊断或门禁证据。 |

## 后续迁移顺序

1. 继续冻结 29 个 public CLI 根层路径，先维护命令兼容。
2. 不再新增根层 internal helper；新 helper 进入 `scripts/lib/` 或后续内部子包。
3. HTML、runner、walk-forward、zzshare fetch helper、gates support helper 与 selection_core helper 已完成下沉；继续拆 HTML 大文件时只拆展示逻辑，不移动事实判断。
4. 兼容 wrapper 保留到 blocker 解除；不要为了减少 4 个 wrapper 破坏旧 import 或测试。
5. 每次迁移都同步 `script_entrypoints.json`、本文件和文档一致性测试。

## 维护热点

这些文件当前仍偏大，但已经迁入内部实现层。它们不扩大根层入口面，不阻塞当前 Skill 使用；后续拆分应作为独立任务处理。它们属于声明式展示、字段投影或报告组装边界，按固定行数拆分会增加跨文件跳转并扩大 `report.html` 回归面；在 public CLI、CSV/JSON 和 HTML 契约均有测试保护前，允许保持内聚实现。

| 文件 | 原因 | 约束 |
| --- | --- | --- |
| `lib/report_html/a_share_selection_html_sections.py` | HTML section rendering 集中，行数最高 | 只拆展示层 section 组合，不移动候选事实、门禁判断或机器字段来源 |
| `lib/report_html/a_share_selection_html_scripts.py` | 静态报告交互脚本集中 | 只拆 HTML 交互脚本片段，不改变报告数据模型 |
| `lib/report_html/a_share_selection_html_candidate_master.py` | 候选详情展示组装集中 | 只拆 candidate display helpers，不改变候选 CSV/diagnostics 语义 |
| `lib/runner/run_today_a_share_selection_summary.py` | summary 字段投影和兼容字段集中 | 只按稳定子视图拆分，不改变 summary/stdout/CSV provenance 字段 |
| `run_today_a_share_selection.py` | 单一 public runner 的编排和失败收口集中 | 继续下沉独立职责，但不拆成多个用户入口或改变步骤顺序 |
