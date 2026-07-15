# Full A Incremental Baostock Evidence 2026-07-15

本报告记录 2026-07-15 在本地真实环境完成的一次全 A 增量历史和最终评分复验。它用于工程性能、数据质量和 claim boundary 复核，不构成投资建议，不证明 prediction、回测收益、券商成交或未来稳定性。

## 运行范围

- Universe: Baostock A-share snapshot, resolved date `2026-07-14`, 5,200 symbols, `partial_result=false`。
- Base history: `/private/tmp/a-share-full-real-20260714-OaVibb/clean/prices.parquet`。
- Incremental run root: `/private/tmp/a-share-full-incremental-20260715-TpGWOP`。
- Provider: Baostock history with the same universe `symbol/name` input, `name_query_count=0`。
- Target date: `2026-07-14`。
- Scoring: generic `ultra_short_low_price_config.json`，没有 prediction 输入，runner 没有执行 LightGBM。

## 未分桶对照

先按旧的 7 bucket 计划执行，最大 bucket 包含 5,158 个 symbol。前 5 个小 bucket 完成后，大 bucket 运行 `1,928.714656` 秒，最终在 no-trading empty 严格校验处失败；manifest 总执行时间为 `1,928.732591` 秒，计划仍处于 `partial`，不能进入 merge 或评分。

这个结果证明两个边界：大 bucket 会把远端连接故障和恢复成本集中到一次运行中；strict no-trading empty 不应被当作普通成功空结果。该失败没有被静默转换为可用数据。

## 分桶优化结果

使用 `--max-bucket-symbols 200` 重新生成计划：

| 指标 | 结果 |
| --- | --- |
| bucket 数 | 32 |
| 计划 symbol | 5,200 |
| delta/full | 5,164 / 36 |
| 实际执行 bucket | 32 |
| reused bucket | 0 |
| fetch duration | 374.098691 秒 |
| executor duration | 374.511831 秒 |
| 进程总耗时 | 约 387.20 秒，约 6.45 分钟 |
| 最大单 bucket | 24.879578 秒 |
| 增量输出行 | 7,388 |
| rows per second | 19.727014 |
| symbols per fetch second | 13.900075 |

所有 bucket 完成，`failed_symbols=[]`、`unprocessed_symbols=[]`、`partial_result=false`。这里的 false 只表示没有未审计缺口；当前代码以 `partial_result_semantics=false_means_no_unaudited_gaps_audited_no_trading_updates_disclosed_separately` 固定机器语义，停牌空更新仍由 `no_trading_update_symbols` 单独披露。27 行无效或非交易数据全部显式丢弃，`invalid_rows=27` 与 `dropped_invalid_rows=27` 对账一致。

四个 symbol 只有非交易原始行且覆盖目标日：`002677`、`002759`、`300567`、`301234`。它们进入 `non_trading_only_empty_symbols` 和 `no_trading_update_symbols`，merge 保留 base 历史但最终 freshness 过滤仍排除它们；普通 empty、failed、未达目标日和未处理 symbol 没有被放行。

## Merge 和清洗

- Base rows: `1,886,135`。
- Incremental rows: `7,388`。
- Merged rows: `1,893,523`。
- Merged symbols: `5,202`，其中 2 个是 base 中保留的历史 extra symbols。
- Planned symbols: `5,200`。
- Replaced overlap rows: `0`。
- Merge duration: `2.770451` 秒。
- 清洗入口直接从 merged Parquet 推导短历史清单，未先让最终 runner 失败：耗时约 `5.12` 秒。
- `min_history_rows=120` 下发现并显式移除 36 只次新股，clean pool 为 `5,166` symbols、`1,891,295` rows。
- 短历史清单、clean metadata、clean report 通过同一次原子发布落盘；清单路径为 `/private/tmp/a-share-full-incremental-20260715-TpGWOP/clean-final/short_history_symbols.json`。

## 最终全 A 评分

最终命令使用 clean Parquet、当前 spot、`--filter-prices-to-spot-universe`、`--min-symbol-latest-date 2026-07-14` 和 `--prices-filter-output-format parquet`：

- runner status: `completed`。
- runner summary duration: `43.330821` 秒，进程总耗时约 `43.97` 秒。
- prices filter: 输入 5,166 symbols，保留 5,160，移除 6；其中 4 个是 no-trading stale symbols，2 个是 base extra symbols。
- final prices rows: `1,889,167`。
- diagnostics: `5,160`，与最终可评分 symbol 精确覆盖。
- candidates: `34`。
- score profile duration: `21.916072` 秒。
- scoring throughput: `86,200.074397` input rows/s，`235.443655` symbols/s。
- score profile 的主要阶段是 `groups_scored=11.852419` 秒；输入准备、过滤和输出均有独立 stage 记录。

本轮 `coverage_class=local_input`，`full_market_claim_allowed=false`，边界为 `local_prices_input_not_full_market_scan`。这是基于已经落地并审计的本地 merged/clean artifact 的真实数据评分，不把一次本地复跑写成新一轮独立全市场证明。

## 当前代码离线重放

修复 merged metadata 顶层日期后，使用同一份已落地增量 artifact 离线重放，不重新联网：

- merged prices SHA-256 与修复前完全一致：`eb8c3015887033e14cac34bb3bf87fcfae9fc86fa5cbb93e8cd0684e1b64b4cf`。
- merged metadata 现在记录 `date_min=2025-01-02`、`date_max=2026-07-14`、`end_date=2026-07-14`，不再继承旧 base 的 `end_date=2026-07-13`。
- 当前代码 merge 进程耗时约 `10.21` 秒，其中 merge helper `4.757690` 秒；clean 进程耗时约 `8.07` 秒。
- 当前代码最终 runner 仍完成 5,160 diagnostics 和 34 candidates，summary duration 为 `76.030658` 秒，进程总耗时约 `83.84` 秒，score profile 为 `34.117824` 秒。
- 与前一次成功输出相比，去除三个随输出目录变化的 provenance 路径字段后，candidates 34/34、diagnostics 5,160/5,160 逐字段完全一致；clean Parquet SHA-256 也完全一致。

两次最终 runner 的进程总耗时分别约 `43.97` 秒和 `83.84` 秒，显示本机负载、文件缓存和 I/O 状态会造成明显波动。两次结果只能作为观测区间，不能作为稳定 SLA；瓶颈判断应优先看 profile 分阶段和远端增量总耗时。

## 字段覆盖边界

本轮 Baostock universe 文件主要提供 `symbol/name`，没有行业、市值、PE、PB 等展示字段。34 个候选中：

- `one_year_pct_chg`: 34/34。
- `industry`: 0/34。
- `market_cap`: 0/34。
- `pe_ttm`: 0/34。
- `pb_lf`: 0/34。

这些是字段缺失通知，不是核心评分成功的替代证明，也不能用 symbol、价格或旧值伪造。Eastmoney spot 仍只能作为显式可选展示 enrichment；其失败或 partial 不得阻塞 Baostock universe 加历史主路径。

## 结论和不可外推项

1. 目前全 A 增量的主要瓶颈仍是远端逐 symbol history I/O，200-symbol 分桶把单次故障和恢复范围从 5,158 限制到最多 200，实测把成功增量执行控制在约 6.45 分钟。
2. 本地清洗、Parquet 过滤和评分合计约几十秒，不是当前主瓶颈；继续增加免费数据源不能直接消除 Baostock 逐 symbol 请求成本，只能作为补充、对照或故障恢复渠道，并且必须保持字段和 claim boundary 门禁。
3. 当前证据不证明 Baostock、Eastmoney、zzshare、Pytdx、Akshare 或 yfinance 的长期稳定、免费额度、授权状态或未来可用性。
4. 当前证据不证明真实 LightGBM prediction、样本外回测、券商订单、成交、滑点、容量或候选适合交易。

## 仓库回归验证

本轮实现完成后使用仓库统一入口执行完整本地门禁：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pyarrow python validate_skill_changes.py
```

- Skill `quick_validate` 通过。
- JSON、YAML、compileall、diff whitespace、冲突标记、密钥和 `__pycache__` 检查通过。
- 在 Python 3.11 和 `constraints-ci.txt` 的精确直接依赖版本下，串行 unittest 共 837 项，全部通过；测试阶段 181.010 秒，统一入口总耗时 185.85 秒。
- CI 分片集合与完整 discovery 的 837 个 test ID 全集完全相等且无重复；九个分片均在同一精确依赖环境通过。
- 分片测试数分别为：`core` 228、`providers` 155、`gates` 235、`report` 70、`runner-core` 40、`runner-providers` 28、`runner-artifacts` 28、`runner-plan-resume` 28、`runner-universe` 25。
- 分片墙钟时间会受并行负载、文件缓存和本机状态影响，本轮只将它用于验证分片边界和 CI 可执行性，不外推为 GitHub Actions SLA 或业务流程 SLA。
- 本轮仓库回归没有重新联网执行全 A 行情抓取，也没有执行真实 LightGBM prediction、样本外回测或券商门禁；前文真实场景数据来自已记录的 2026-07-15 运行和离线 artifact 重放。
