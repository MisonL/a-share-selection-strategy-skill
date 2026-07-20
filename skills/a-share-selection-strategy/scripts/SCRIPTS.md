# 脚本清单

本文件是 `scripts/` 目录入口分层面向人类和 Agent 的解释层。仅当任务拓扑没有给出默认动作，或需要判断公开 CLI、路径命中入口和 internal helper 边界时才读它；本地评分、定向真实任务和今日低价超短直接按 `SKILL.md` 的任务拓扑执行。

配置文件的权威路径在 `../configs/`；旧命令传入的 `scripts/*.json` 会由 CLI 自动回退到 `../configs/`。

脚本入口机器注册表见 `../configs/script_entrypoints.json`，它是入口机器分类事实源。本文件负责解释用途和选择规则；注册表只用于审计根层 `.py` 是否被归类，不是运行时 dispatcher，也不替代 CLI 合约。注册表 v3 将 `visibility`、`kind`、`stability`、`domain` 和 `default_entry` 作为分类轴，并以 `skill_route` 标记每个条目的路径命中资格：只有 `default_entry=true` 的三个常规主入口可由任务拓扑直接选择，其他 public CLI 仅在路径或 artifact 门禁命中后使用。

根层 `.py` 路径保持兼容；部分内部 helper 的真实实现已迁入 `lib/`，根层同名文件只做 re-export 和直接执行 fail-fast。用户命令仍使用本文件列出的根层 CLI，不直接调用 `lib/`。

新的 internal helper 不再新增到 `scripts/` 根层；默认放入 `lib/` 分层包。根层 internal helper 只是兼容预算，后续迁移只能减少或保持，不应增加。内部运行路径优先导入 `lib.*`，但 import 路径不是稳定用户 API；完整分层、复杂度豁免和迁移判断见 [../references/script-inventory.md](../references/script-inventory.md)。

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
| `probe_external_source_stability.py` | 外部源稳定性观察 | 覆盖 eastmoney、baostock_universe、akshare、pytdx、yfinance、baostock、zzshare；可选紧凑归档由 `lib/gates/external_source_evidence_archive.py` 负责；短窗口通过不证明长期稳定 |

## 内部 helper

以下 4 个根层 compatibility wrapper 可能带 `__main__`，但直接执行只用于 fail-fast 提示“不是 CLI 入口”。不要把它们当作用户入口、内部实现入口或 `--help` 合约：

- `a_share_selection_calendar_contract.py`
- `a_share_selection_cli_guard.py`
- `a_share_selection_config.py`
- `a_share_selection_paths.py`

`lib/a_share_selection_run_state.py` 是 runner 与 HTML 展示层共用的纯运行状态模块，不在 `scripts/` 根层、不属于根层 script entrypoint registry，也不是用户 CLI。`lib/report_html/` 只能作为展示层 helper，不能把候选事实、门禁判断或机器字段来源移入展示层；`report.html` 输出契约不变。全 A provenance、Parquet sidecar、复杂度豁免和维护热点只在审计或维护任务中按 [../references/script-inventory.md](../references/script-inventory.md) 读取。

## 判定规则

1. 常规本地或定向任务先按 `default_entry=true` 的 `validate_ohlcv.py`、`score_candidates.py`、`run_today_a_share_selection.py` 处理；`create_demo_data.py` 和 `slice_prices_as_of.py` 只在 demo 或时间切片路径命中时使用。
2. 看到 `fetch_*.py`，先按取数入口处理，检查数据源边界和落地 metadata。
3. 看到“门禁和回测入口”表中的任一 public CLI，先按门禁和回测入口处理；其中包括 prediction、sizing、backtest、portfolio、walk-forward、recovery、clean-pool、incremental plan/execute、validator 和 probe 路径。
4. 看到根层 `a_share_selection_calendar_contract.py`、`a_share_selection_cli_guard.py`、`a_share_selection_config.py`、`a_share_selection_paths.py`，先按兼容 wrapper 处理；`lib/report_html/` 是 HTML 展示层内部实现包，`lib/runner/` 是 `run_today_a_share_selection.py` 的内部实现包，`lib/walk_forward/` 是 public walk-forward gate CLI 的内部实现包，`lib/fetch/` 是 provider fetch helper 包，`lib/gates/` 是 gate/backtest support helper 包，`lib/selection_core/` 是评分、字段、符号和数据校验内部实现包。
5. `__main__` 只代表可 fail-fast，不代表对用户公开的 CLI 合约。

`default_entry=true` 表示 Agent 可直接按任务拓扑选择的三个常规主入口。`skill_route=true` 表示 public CLI 可在路径命中后引用，不表示 Agent 应在首轮从 29 个 public CLI 中随机选择；fetch、prediction、backtest、capacity、probe、recovery 和 validator CLI 仍只在路径命中或 artifact 门禁需要时使用。

## 入口选择规则

1. 用户给本地行情文件：只需要评分时优先 `validate_ohlcv.py` 后接 `score_candidates.py`；需要 `run_manifest.json`、`summary.json`、spot 合并或 HTML 时再用 `run_today_a_share_selection.py --prices-input`。
2. 用户要求小样本真实任务、明确 symbol 或明确本地股票池的低价超短：优先 `run_today_a_share_selection.py`；长列表用 `--symbols-file`，只审计命令用 `--plan-only`。
3. 用户要求今日 A 股、真实 A 股选股、全 A、全市场或扩大股票池，且没有限定 symbol 或本地股票池：先读 [../instructions/full-a-strict-workflow.md](../instructions/full-a-strict-workflow.md)，不要直接套默认小样本命令。
4. 需要恢复上一轮失败、空结果、截断或因预算耗尽未处理的 symbol：优先 `run_today_a_share_selection.py --resume-from <run_manifest.json>`，它生成 `resume_retry_symbols`，不证明全市场完成。
5. 用户坚持 prediction-derived：必须有真实 `prediction` 或 `prediction_score` 输入，再走 prediction-derived config。
6. 需要回测、容量或历史门禁：只在评分 artifact 已经闭环后进入预测、回测和门禁 CLI。
